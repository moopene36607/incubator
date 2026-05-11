"""Edge-case tests for qreg.py -- pure-function quantile regression.

Run: python3 tests_qreg.py
"""
from __future__ import annotations

import math
import sys

from qreg import (
    FeatureEncoder, fit_quantile, predict_quantiles,
    pinball_loss_one, pinball_loss_mean, check_coverage, coverage_report,
    negotiation_anchors, classify_offer,
)


def assert_close(a, b, tol=1e-3, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


def test_pinball_at_zero_diff():
    assert pinball_loss_one(5.0, 5.0, 0.5) == 0.0


def test_pinball_under_prediction():
    # y > yhat -> loss = tau * (y - yhat)
    assert_close(pinball_loss_one(10.0, 8.0, 0.9), 0.9 * 2.0, msg="under-prediction at tau=0.9")
    assert_close(pinball_loss_one(10.0, 8.0, 0.1), 0.1 * 2.0, msg="under-prediction at tau=0.1")


def test_pinball_over_prediction():
    # y < yhat -> loss = (yhat - y) * (1 - tau)
    assert_close(pinball_loss_one(8.0, 10.0, 0.9), 2.0 * 0.1, msg="over-prediction at tau=0.9")
    assert_close(pinball_loss_one(8.0, 10.0, 0.1), 2.0 * 0.9, msg="over-prediction at tau=0.1")


def test_pinball_asymmetric():
    # At tau=0.9, under-predicting (y > yhat) is much worse than over-predicting.
    high_loss = pinball_loss_one(10.0, 8.0, 0.9)   # 0.9 * 2 = 1.8
    low_loss = pinball_loss_one(8.0, 10.0, 0.9)    # 0.1 * 2 = 0.2
    assert high_loss > low_loss, "high tau punishes under-prediction more"


def test_encoder_numeric_zscore():
    rows = [{"a": 10}, {"a": 20}, {"a": 30}]
    enc = FeatureEncoder(numeric_features=["a"], categorical_features=[])
    enc.fit(rows)
    # mean 20, stdev sqrt(((10-20)^2+(20-20)^2+(30-20)^2)/3) = sqrt(200/3)
    sd = math.sqrt(200.0 / 3.0)
    assert_close(enc.numeric_mean["a"], 20.0, msg="mean")
    assert_close(enc.numeric_std["a"], sd, msg="stdev")
    x = enc.transform({"a": 30})
    assert_close(x[0], 10.0 / sd, msg="transform z-score")


def test_encoder_categorical_one_hot_drops_first():
    rows = [{"c": "x"}, {"c": "y"}, {"c": "z"}]
    enc = FeatureEncoder(numeric_features=[], categorical_features=["c"])
    enc.fit(rows)
    # Drops first level "x"; keeps "y" and "z" as expanded columns.
    assert enc.expanded_names == ["c=y", "c=z"]
    # Reference level "x" -> all zeros
    assert enc.transform({"c": "x"}) == [0.0, 0.0]
    # "y" -> [1, 0]
    assert enc.transform({"c": "y"}) == [1.0, 0.0]
    # "z" -> [0, 1]
    assert enc.transform({"c": "z"}) == [0.0, 1.0]


def test_encoder_zero_variance_numeric_does_not_crash():
    # All values equal -> stdev=0 -> code uses 1.0 as numerical safeguard.
    rows = [{"a": 5}, {"a": 5}]
    enc = FeatureEncoder(numeric_features=["a"], categorical_features=[])
    enc.fit(rows)
    assert enc.numeric_std["a"] == 1.0
    assert enc.transform({"a": 5}) == [0.0]


def test_quantile_recovers_unconditional_quantile():
    # Constant X -> conditional quantile = unconditional quantile of y.
    # Use X = [[0]] for all samples and check P50, P25, P75 of training y.
    y = [10.0, 20.0, 30.0, 40.0, 50.0]
    X = [[0.0]] * len(y)
    model = fit_quantile(X, y, feature_names=["x"],
                         tau_levels=(0.25, 0.5, 0.75), lr=0.5, max_iter=3000)
    p = predict_quantiles(model, [0.0])
    # P50 should be close to median 30
    assert_close(p.quantiles[0.5], 30.0, tol=2.0, msg="P50 ≈ median")
    # P25 ≈ 20, P75 ≈ 40 (with linear interpolation 25th percentile of [10..50])
    assert p.quantiles[0.25] <= p.quantiles[0.5] <= p.quantiles[0.75]


def test_quantile_monotonicity():
    # After post-processing, predictions must be non-decreasing in tau.
    y = [10, 12, 15, 18, 20, 22, 25, 28, 30, 35, 40, 50]
    X = [[float(i)] for i in range(len(y))]
    model = fit_quantile(X, y, ["x"], tau_levels=(0.1, 0.25, 0.5, 0.75, 0.9), lr=0.05, max_iter=2000)
    p = predict_quantiles(model, [5.0])
    prev = -float("inf")
    for tau in sorted(p.quantiles.keys()):
        cur = p.quantiles[tau]
        assert cur >= prev - 1e-9, f"monotonicity broken: {prev} -> {cur}"
        prev = cur


def test_quantile_linear_relationship():
    # If y = 2 * x + 10, then Q_0.5(y | x) = 2x + 10 exactly. Train and verify.
    # Raw (unscaled) x is used here, which makes subgradient descent slow; allow generous tol.
    X = [[float(i)] for i in range(1, 21)]
    y = [2.0 * i + 10.0 for i in range(1, 21)]
    model = fit_quantile(X, y, ["x"], tau_levels=(0.5,), lr=0.05, max_iter=5000)
    p = predict_quantiles(model, [5.0])
    # Tolerance covers slow convergence on unscaled features; what matters is direction.
    assert_close(p.quantiles[0.5], 20.0, tol=5.0, msg="linear y=2x+10 at x=5")
    # And the model should learn positive slope.
    assert model.coefs[0.5][0] > 0, "slope sign should be positive"


def test_coverage_approaches_tau():
    # With well-fit model, fraction of y_i <= Q_tau(x_i) should be close to tau.
    y = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
    X = [[float(i)] for i in range(len(y))]
    model = fit_quantile(X, y, ["x"], tau_levels=(0.1, 0.5, 0.9), lr=0.05, max_iter=3000)
    cov = coverage_report(model, X, y)
    # Tolerance is loose because subgradient GD on pinball is non-smooth.
    assert abs(cov[0.5] - 0.5) <= 0.25, f"P50 coverage off: {cov[0.5]}"
    assert cov[0.9] >= cov[0.5] - 1e-6, "higher tau -> higher coverage"
    assert cov[0.1] <= cov[0.5] + 1e-6, "lower tau -> lower coverage"


def test_negotiation_anchors_ordered():
    # Synthetic quantile prediction.
    from qreg import QuantilePrediction
    pred = QuantilePrediction(
        quantiles={0.1: 10, 0.25: 15, 0.5: 20, 0.75: 25, 0.9: 30},
        feature_contributions={},
    )
    a = negotiation_anchors(pred)
    assert a.walk_away < a.fair_low < a.median < a.fair_high < a.ceiling


def test_classify_offer_below_walkaway():
    from qreg import NegotiationAnchors
    a = NegotiationAnchors(walk_away=10, fair_low=15, median=20, fair_high=25, ceiling=30)
    label, _ = classify_offer(8, a)
    assert "撿到便宜" in label


def test_classify_offer_in_range():
    from qreg import NegotiationAnchors
    a = NegotiationAnchors(walk_away=10, fair_low=15, median=20, fair_high=25, ceiling=30)
    label, _ = classify_offer(20, a)
    assert "行情價" in label


def test_classify_offer_above_ceiling():
    from qreg import NegotiationAnchors
    a = NegotiationAnchors(walk_away=10, fair_low=15, median=20, fair_high=25, ceiling=30)
    label, _ = classify_offer(35, a)
    assert "超出行情" in label


def test_fit_quantile_empty_raises():
    try:
        fit_quantile([], [], [])
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty input")


def test_quantile_feature_contributions_returned():
    X = [[1.0, 2.0], [2.0, 1.0], [3.0, 3.0], [4.0, 2.0]]
    y = [10.0, 15.0, 25.0, 30.0]
    model = fit_quantile(X, y, ["a", "b"], tau_levels=(0.5,), lr=0.05, max_iter=500)
    p = predict_quantiles(model, [2.5, 2.5])
    assert 0.5 in p.feature_contributions
    contribs = p.feature_contributions[0.5]
    assert len(contribs) == 2
    # Should be sorted by |contrib| desc.
    assert abs(contribs[0][2]) >= abs(contribs[1][2])


def test_quantile_deterministic_with_seed():
    X = [[float(i)] for i in range(20)]
    y = [float(i) * 2.0 + 5.0 for i in range(20)]
    m1 = fit_quantile(X, y, ["x"], tau_levels=(0.5,), lr=0.05, max_iter=1000, seed=42)
    m2 = fit_quantile(X, y, ["x"], tau_levels=(0.5,), lr=0.05, max_iter=1000, seed=42)
    assert_close(m1.intercepts[0.5], m2.intercepts[0.5], tol=1e-9, msg="seed determinism")


def test_pinball_loss_mean_zero_for_perfect_predictions():
    y = [10.0, 20.0, 30.0]
    yhat = [10.0, 20.0, 30.0]
    assert pinball_loss_mean(y, yhat, 0.5) == 0.0
    assert pinball_loss_mean(y, yhat, 0.1) == 0.0
    assert pinball_loss_mean(y, yhat, 0.9) == 0.0


def test_higher_quantile_predicts_higher_or_equal():
    # Across many random feature vectors, P90 >= P50 >= P10 must hold.
    y = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
    X = [[float(i)] for i in range(len(y))]
    model = fit_quantile(X, y, ["x"], tau_levels=(0.1, 0.5, 0.9), lr=0.05, max_iter=2000)
    for v in [-2.0, 0.0, 2.0, 5.0, 10.0]:
        p = predict_quantiles(model, [v])
        assert p.quantiles[0.1] <= p.quantiles[0.5] <= p.quantiles[0.9], \
            f"monotonicity broken at x={v}: {p.quantiles}"


def test_classify_offer_boundary_walk_away():
    # actual_rent exactly at walk_away -> should still be "撿到便宜" (inclusive boundary)
    from qreg import NegotiationAnchors
    a = NegotiationAnchors(walk_away=10, fair_low=15, median=20, fair_high=25, ceiling=30)
    label, _ = classify_offer(10, a)
    assert "撿到便宜" in label


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
