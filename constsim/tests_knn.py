"""constsim edge tests — pure-function k-NN correctness."""
from __future__ import annotations

import math

from knn import (
    FeatureSpec, TrainingCase, weighted_distance, auto_scale,
    knn_predict, loo_evaluate, numeric_feature_correlations,
    categorical_feature_mean_diff,
)


def test_weighted_distance_identical():
    """Same case → distance 0."""
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    q = {"x": 5.0}
    d, _ = weighted_distance(q, q, specs)
    assert d == 0.0


def test_weighted_distance_categorical_match():
    """Same categorical → 0; different → weight."""
    specs = [FeatureSpec("c", "categorical", 2.0)]
    d_same, _ = weighted_distance({"c": "A"}, {"c": "A"}, specs)
    d_diff, _ = weighted_distance({"c": "A"}, {"c": "B"}, specs)
    assert d_same == 0.0
    assert d_diff == math.sqrt(2.0)


def test_weighted_distance_numeric_scale():
    """Larger scale = smaller relative distance."""
    spec_small = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    spec_large = [FeatureSpec("x", "numeric", 1.0, 100.0)]
    d_small, _ = weighted_distance({"x": 10.0}, {"x": 5.0}, spec_small)
    d_large, _ = weighted_distance({"x": 10.0}, {"x": 5.0}, spec_large)
    assert d_small > d_large


def test_auto_scale_uses_stdev():
    """auto_scale sets numeric scale to population stdev."""
    cases = [
        TrainingCase("a", {"x": 0.0}, 1.0),
        TrainingCase("b", {"x": 10.0}, 2.0),
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    scaled = auto_scale(cases, specs)
    # stdev of [0, 10] = 7.07
    assert abs(scaled[0].scale - 7.07) < 0.1


def test_knn_predict_uses_k():
    """k=3 uses 3 nearest cases."""
    cases = [
        TrainingCase("a", {"x": 1.0}, 10.0),
        TrainingCase("b", {"x": 2.0}, 20.0),
        TrainingCase("c", {"x": 10.0}, 100.0),
        TrainingCase("d", {"x": 20.0}, 200.0),
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred = knn_predict({"x": 1.5}, cases, specs, k=3)
    assert pred.n_neighbors_used == 3


def test_knn_predict_value_in_range():
    """Predicted value should be in range of neighbor targets."""
    cases = [
        TrainingCase("a", {"x": 1.0}, 10.0),
        TrainingCase("b", {"x": 2.0}, 20.0),
        TrainingCase("c", {"x": 3.0}, 30.0),
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred = knn_predict({"x": 2.0}, cases, specs, k=3)
    assert 10.0 <= pred.predicted_value <= 30.0


def test_knn_predict_closer_higher_weight():
    """Distance weighting: closest neighbor pulls prediction."""
    cases = [
        TrainingCase("a", {"x": 1.0}, 100.0),    # very close to query
        TrainingCase("b", {"x": 10.0}, 0.0),     # far away
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred = knn_predict({"x": 1.0}, cases, specs, k=2, distance_weighted=True)
    # Should be much closer to 100 (closest neighbor) than 0
    assert pred.predicted_value > 50.0


def test_knn_predict_std_zero_for_identical_targets():
    """If all neighbors have same target → std = 0."""
    cases = [
        TrainingCase("a", {"x": 1.0}, 50.0),
        TrainingCase("b", {"x": 2.0}, 50.0),
        TrainingCase("c", {"x": 3.0}, 50.0),
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred = knn_predict({"x": 2.0}, cases, specs, k=3)
    assert pred.predicted_std == 0.0


def test_knn_predict_confidence_band():
    """Confidence band = (pred - std, pred + std)."""
    cases = [
        TrainingCase("a", {"x": 1.0}, 0.0),
        TrainingCase("b", {"x": 2.0}, 100.0),
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred = knn_predict({"x": 1.5}, cases, specs, k=2)
    assert pred.confidence_band[0] <= pred.predicted_value
    assert pred.predicted_value <= pred.confidence_band[1]


def test_knn_predict_with_categorical():
    """Categorical features influence distance."""
    cases = [
        TrainingCase("a", {"x": 5.0, "type": "A"}, 100.0),
        TrainingCase("b", {"x": 5.0, "type": "B"}, 200.0),
    ]
    specs = [
        FeatureSpec("x", "numeric", 1.0, 1.0),
        FeatureSpec("type", "categorical", 10.0),    # high weight
    ]
    pred_A = knn_predict({"x": 5.0, "type": "A"}, cases, specs, k=1)
    pred_B = knn_predict({"x": 5.0, "type": "B"}, cases, specs, k=1)
    assert pred_A.predicted_value == 100.0
    assert pred_B.predicted_value == 200.0


def test_loo_evaluate_returns_metrics():
    """LOO returns MAE, MAPE, RMSE."""
    cases = [
        TrainingCase(f"c{i}", {"x": float(i)}, float(i * 10))
        for i in range(5)
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    metrics = loo_evaluate(cases, specs, k=2)
    assert "mae" in metrics
    assert "mape" in metrics
    assert "rmse" in metrics
    assert metrics["mae"] >= 0


def test_loo_evaluate_perfect_data():
    """Identical features → low LOO error."""
    cases = [
        TrainingCase(f"c{i}", {"x": 5.0}, 100.0) for i in range(5)
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    metrics = loo_evaluate(cases, specs, k=2)
    assert metrics["mae"] == 0.0


def test_numeric_feature_correlations():
    """Linear y=2x correlation should be 1.0."""
    cases = [
        TrainingCase(f"c{i}", {"x": float(i)}, float(i * 2))
        for i in range(10)
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    corr = numeric_feature_correlations(cases, specs)
    assert abs(corr["x"] - 1.0) < 0.001


def test_categorical_feature_mean_diff():
    """Per-category target means."""
    cases = [
        TrainingCase("a", {"type": "X"}, 100.0),
        TrainingCase("b", {"type": "X"}, 200.0),
        TrainingCase("c", {"type": "Y"}, 50.0),
    ]
    specs = [FeatureSpec("type", "categorical", 1.0)]
    means = categorical_feature_mean_diff(cases, specs)
    assert means["type"]["X"] == 150.0
    assert means["type"]["Y"] == 50.0


def test_knn_deterministic():
    """Same query + cases → same prediction."""
    cases = [
        TrainingCase("a", {"x": 1.0}, 10.0),
        TrainingCase("b", {"x": 2.0}, 20.0),
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred1 = knn_predict({"x": 1.5}, cases, specs, k=2)
    pred2 = knn_predict({"x": 1.5}, cases, specs, k=2)
    assert pred1.predicted_value == pred2.predicted_value


def test_knn_predict_neighbor_order_sorted():
    """Neighbors returned sorted by distance ascending."""
    cases = [
        TrainingCase(f"c{i}", {"x": float(i)}, float(i))
        for i in range(10)
    ]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred = knn_predict({"x": 5.0}, cases, specs, k=5)
    distances = [n.distance for n in pred.neighbors]
    assert distances == sorted(distances)


def test_knn_handles_single_case():
    """k > n cases → returns all cases."""
    cases = [TrainingCase("a", {"x": 5.0}, 100.0)]
    specs = [FeatureSpec("x", "numeric", 1.0, 1.0)]
    pred = knn_predict({"x": 10.0}, cases, specs, k=5)
    assert pred.n_neighbors_used == 1
    assert pred.predicted_value == 100.0


if __name__ == "__main__":
    tests = [
        test_weighted_distance_identical,
        test_weighted_distance_categorical_match,
        test_weighted_distance_numeric_scale,
        test_auto_scale_uses_stdev,
        test_knn_predict_uses_k,
        test_knn_predict_value_in_range,
        test_knn_predict_closer_higher_weight,
        test_knn_predict_std_zero_for_identical_targets,
        test_knn_predict_confidence_band,
        test_knn_predict_with_categorical,
        test_loo_evaluate_returns_metrics,
        test_loo_evaluate_perfect_data,
        test_numeric_feature_correlations,
        test_categorical_feature_mean_diff,
        test_knn_deterministic,
        test_knn_predict_neighbor_order_sorted,
        test_knn_handles_single_case,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
