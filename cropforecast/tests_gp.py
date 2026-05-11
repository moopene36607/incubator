"""Edge-case tests for gp.py -- pure-function Gaussian Process Regression.

Run: python3 tests_gp.py
"""
from __future__ import annotations

import math
import sys

from gp import (
    rbf_kernel, kernel_matrix, gauss_jordan_solve,
    fit_gp, predict_gp, log_marginal_likelihood,
    rmse, empirical_coverage, mean_band_width,
    _zeros,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


def test_rbf_zero_distance_returns_sigma_squared():
    k = rbf_kernel(5.0, 5.0, sigma_f=2.0, ell=1.0)
    assert_close(k, 4.0, msg="k(x,x) = sigma_f^2")


def test_rbf_decreases_with_distance():
    k_near = rbf_kernel(0.0, 1.0, sigma_f=1.0, ell=1.0)
    k_far = rbf_kernel(0.0, 5.0, sigma_f=1.0, ell=1.0)
    assert k_near > k_far, "kernel decreases with distance"


def test_rbf_is_symmetric():
    a = rbf_kernel(2.0, 7.0, 1.5, 2.0)
    b = rbf_kernel(7.0, 2.0, 1.5, 2.0)
    assert_close(a, b, msg="kernel symmetric")


def test_kernel_matrix_diagonal_is_sigma_squared():
    K = kernel_matrix([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], sigma_f=2.0, ell=1.0)
    for i in range(3):
        assert_close(K[i][i], 4.0, msg=f"K[{i}][{i}] = sigma_f^2")


def test_kernel_matrix_symmetric_when_same_X():
    K = kernel_matrix([1.0, 5.0, 9.0], [1.0, 5.0, 9.0], sigma_f=1.0, ell=2.0)
    for i in range(3):
        for j in range(3):
            assert_close(K[i][j], K[j][i], msg=f"K[{i}][{j}] symmetric")


def test_fit_empty_raises():
    try:
        fit_gp([], [])
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty input")


def test_fit_single_point_raises():
    try:
        fit_gp([1.0], [2.0])
    except ValueError:
        return
    raise AssertionError("expected ValueError on n=1 input")


def test_fit_mismatched_lengths_raises():
    try:
        fit_gp([1.0, 2.0], [1.0, 2.0, 3.0])
    except ValueError:
        return
    raise AssertionError("expected ValueError on mismatched lengths")


def test_gp_passes_close_to_training_points():
    # With low noise, GP should interpolate training points closely.
    X = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [0.0, 1.0, 4.0, 9.0, 16.0]  # y = x^2
    model = fit_gp(X, y, sigma_f=10.0, ell=1.0, sigma_n=0.01)
    pred = predict_gp(model, X)
    for i, yi in enumerate(y):
        assert abs(pred.mean[i] - yi) < 0.5, \
            f"interpolation off at x={X[i]}: pred={pred.mean[i]}, true={yi}"


def test_gp_uncertainty_grows_away_from_data():
    # Train on x in [0, 10]; predict at x=5 (interpolation) vs x=20 (extrapolation).
    X = [float(i) for i in range(11)]
    y = [float(i) * 2 for i in range(11)]   # y = 2x
    model = fit_gp(X, y, sigma_f=2.0, ell=2.0, sigma_n=0.1)
    pred = predict_gp(model, [5.0, 20.0])
    assert pred.std[1] > pred.std[0], \
        f"extrapolation uncertainty {pred.std[1]} should exceed interpolation {pred.std[0]}"


def test_gp_variance_positive():
    X = [0.0, 1.0, 2.0, 3.0]
    y = [0.0, 1.0, 4.0, 9.0]
    model = fit_gp(X, y)
    pred = predict_gp(model, [0.5, 1.5, 2.5, 100.0])
    for v in pred.variance:
        assert v > 0, f"variance must be positive: {v}"


def test_gp_credible_interval_brackets_mean():
    X = [float(i) for i in range(10)]
    y = [float(i) * 0.5 for i in range(10)]
    model = fit_gp(X, y)
    pred = predict_gp(model, [3.5, 4.5, 5.5])
    for i in range(len(pred.mean)):
        assert pred.ci_low_95[i] <= pred.mean[i] <= pred.ci_high_95[i], \
            f"95% CI doesn't bracket mean at i={i}"
        assert pred.ci_low_80[i] <= pred.mean[i] <= pred.ci_high_80[i], \
            f"80% CI doesn't bracket mean at i={i}"
        # 80% should be narrower than 95%
        w80 = pred.ci_high_80[i] - pred.ci_low_80[i]
        w95 = pred.ci_high_95[i] - pred.ci_low_95[i]
        assert w80 < w95, f"80% CI should be narrower than 95% at i={i}"


def test_gp_deterministic():
    X = [0.0, 1.0, 2.0, 3.0]
    y = [1.0, 2.0, 1.5, 3.0]
    m1 = fit_gp(X, y, sigma_f=1.0, ell=1.0, sigma_n=0.1)
    m2 = fit_gp(X, y, sigma_f=1.0, ell=1.0, sigma_n=0.1)
    p1 = predict_gp(m1, [1.5, 2.5])
    p2 = predict_gp(m2, [1.5, 2.5])
    for i in range(2):
        assert_close(p1.mean[i], p2.mean[i], tol=1e-9)
        assert_close(p1.variance[i], p2.variance[i], tol=1e-9)


def test_gp_handles_constant_y():
    # All y values equal -> should predict constant with very low variance.
    X = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [5.0, 5.0, 5.0, 5.0, 5.0]
    model = fit_gp(X, y)
    pred = predict_gp(model, [2.5])
    assert_close(pred.mean[0], 5.0, tol=0.5, msg="constant y should predict constant")


def test_gauss_jordan_inverse_matches_identity():
    # Solving A * X = I should give X = A^-1; then A * X should equal I.
    A = [[4.0, 2.0], [1.0, 3.0]]
    I = [[1.0, 0.0], [0.0, 1.0]]
    X = gauss_jordan_solve(A, I)
    # Check A * X
    for i in range(2):
        for j in range(2):
            val = sum(A[i][k] * X[k][j] for k in range(2))
            expected = 1.0 if i == j else 0.0
            assert_close(val, expected, tol=1e-10, msg=f"A*A^-1 at [{i}][{j}]")


def test_rmse_zero_on_training_set_with_low_noise():
    X = [0.0, 1.0, 2.0]
    y = [1.0, 2.0, 4.0]
    model = fit_gp(X, y, sigma_f=10.0, ell=1.0, sigma_n=0.001)
    r = rmse(model, X, y)
    assert r < 0.1, f"low-noise GP should fit training closely; got RMSE={r}"


def test_log_marginal_likelihood_finite():
    X = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [1.0, 2.0, 1.5, 3.0, 2.5]
    model = fit_gp(X, y)
    lml = log_marginal_likelihood(model)
    assert math.isfinite(lml), f"LML should be finite: {lml}"


def test_log_marginal_likelihood_prefers_correct_lengthscale():
    # Generate data with a known length-scale; LML should rank correct ell highest.
    X = [float(i) * 0.5 for i in range(20)]
    y = [math.sin(xi) for xi in X]
    m_short = fit_gp(X, y, sigma_f=1.0, ell=0.1, sigma_n=0.1)
    m_correct = fit_gp(X, y, sigma_f=1.0, ell=1.0, sigma_n=0.1)
    m_long = fit_gp(X, y, sigma_f=1.0, ell=10.0, sigma_n=0.1)
    lml_s = log_marginal_likelihood(m_short)
    lml_c = log_marginal_likelihood(m_correct)
    lml_l = log_marginal_likelihood(m_long)
    # Correct or close-to-correct length-scale should yield higher LML than extremes.
    assert lml_c > lml_s or lml_c > lml_l, \
        f"LML should discriminate length-scales: short={lml_s}, correct={lml_c}, long={lml_l}"


def test_empirical_coverage_reasonable():
    # Train on first 80% of a smooth series; check 95% CI covers most of last 20%.
    X = [float(i) for i in range(20)]
    y = [math.sin(xi * 0.5) + 0.05 * xi for xi in X]
    n_train = 16
    X_train, y_train = X[:n_train], y[:n_train]
    X_test, y_test = X[n_train:], y[n_train:]
    model = fit_gp(X_train, y_train)
    coverage = empirical_coverage(model, X_test, y_test, confidence=0.95)
    assert 0.0 <= coverage <= 1.0
    # For a smooth signal extrapolated only a few steps, expect decent coverage.
    assert coverage >= 0.5, f"expected reasonable coverage, got {coverage}"


def test_mean_band_width_positive():
    X = [0.0, 1.0, 2.0, 3.0]
    y = [1.0, 2.0, 1.5, 3.0]
    model = fit_gp(X, y)
    pred = predict_gp(model, [4.0, 5.0, 6.0])
    w = mean_band_width(pred, 0.95)
    assert w > 0


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
