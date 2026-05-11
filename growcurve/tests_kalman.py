"""growcurve edge tests — pure-function Kalman filter correctness."""
from __future__ import annotations

import math

from kalman import (
    mat2x2_mul, mat2x2_transpose, mat2x2_inv, mat2x2_add, mat2x2_sub,
    mat2x2_vec, I2,
    Measurement, KalmanConfig, kalman_pipeline,
    interpolate_who, who_percentile, detect_anomalies,
    WHO_BOY_P50_KG, WHO_GIRL_P50_KG,
)


def test_mat2x2_mul_identity():
    """A × I = A."""
    A = [[2.0, 3.0], [4.0, 5.0]]
    assert mat2x2_mul(A, I2) == A
    assert mat2x2_mul(I2, A) == A


def test_mat2x2_transpose():
    A = [[1.0, 2.0], [3.0, 4.0]]
    AT = mat2x2_transpose(A)
    assert AT == [[1.0, 3.0], [2.0, 4.0]]


def test_mat2x2_inv():
    """A × A^-1 = I."""
    A = [[4.0, 2.0], [3.0, 5.0]]
    Ainv = mat2x2_inv(A)
    prod = mat2x2_mul(A, Ainv)
    for i in range(2):
        for j in range(2):
            expected = 1.0 if i == j else 0.0
            assert abs(prod[i][j] - expected) < 1e-9


def test_mat2x2_inv_singular():
    """Singular matrix raises."""
    try:
        mat2x2_inv([[1.0, 2.0], [2.0, 4.0]])
        assert False, "should have raised"
    except ValueError:
        pass


def test_mat2x2_add_sub_inverse():
    """(A + B) - B = A."""
    A = [[1.0, 2.0], [3.0, 4.0]]
    B = [[5.0, 6.0], [7.0, 8.0]]
    assert mat2x2_sub(mat2x2_add(A, B), B) == A


def test_kalman_constant_signal():
    """Constant true value + noisy observations → smoothed converges to constant."""
    import random
    random.seed(0)
    true_w = 7.0
    measurements = [Measurement(d, true_w + random.gauss(0, 0.1)) for d in range(20)]
    config = KalmanConfig()
    result = kalman_pipeline(measurements, config)
    # End smoothed weight should be near 7.0
    assert abs(result.smoothed_weight[-1] - true_w) < 0.15


def test_kalman_noise_reduction():
    """Smoothed range much smaller than raw range."""
    import random
    random.seed(1)
    measurements = [Measurement(d, 6.5 + random.gauss(0, 0.2)) for d in range(20)]
    config = KalmanConfig()
    result = kalman_pipeline(measurements, config)
    raw_range = max(result.raw_measurements) - min(result.raw_measurements)
    smoothed_range = max(result.smoothed_weight) - min(result.smoothed_weight)
    assert smoothed_range < raw_range * 0.5


def test_kalman_tracks_linear_trend():
    """Linear trend should be recovered."""
    import random
    random.seed(2)
    true_w = 6.0
    measurements = []
    for d in range(15):
        true_w += 0.020   # 20 g/day
        measurements.append(Measurement(d, true_w + random.gauss(0, 0.05)))
    result = kalman_pipeline(measurements)
    # Recent velocity should be close to 20 g/day
    recent_vel_g = sum(result.smoothed_velocity[-5:]) / 5 * 1000
    assert 10 < recent_vel_g < 30


def test_who_p50_interpolation():
    """Interpolation between known points returns reasonable value."""
    # 1.5 month should be between P50(1)=4.5 and P50(2)=5.6, around 5.05
    v = interpolate_who(1.5, WHO_BOY_P50_KG)
    assert 4.5 < v < 5.6
    assert abs(v - 5.05) < 0.1


def test_who_p50_clamped():
    """Out-of-range months clamped."""
    assert interpolate_who(-5, WHO_BOY_P50_KG) == WHO_BOY_P50_KG[0]
    assert interpolate_who(100, WHO_BOY_P50_KG) == WHO_BOY_P50_KG[24]


def test_who_percentile_at_median():
    """Weight at WHO P50 → percentile ~50."""
    pct, tier = who_percentile(7.9, 6, "boy")
    assert 40 < pct < 60


def test_who_percentile_below_p3():
    """Very light weight → below P3."""
    pct, tier = who_percentile(5.0, 6, "boy")
    assert pct < 5
    assert "P3" in tier or "顯著偏輕" in tier


def test_who_percentile_above_p97():
    """Very heavy weight → above P97."""
    pct, tier = who_percentile(11.0, 6, "boy")
    assert pct > 95


def test_detect_anomalies_normal_growth():
    """Normal growth → no urgent flag."""
    import random
    random.seed(3)
    measurements = []
    w = 7.0
    for d in range(15):
        w += 0.020    # 20 g/day, healthy
        measurements.append(Measurement(d, w + random.gauss(0, 0.05)))
    result = kalman_pipeline(measurements)
    flags = detect_anomalies(result, age_months_at_start=4.0, sex="boy")
    urgent = [f for f in flags if f.severity == "urgent"]
    assert len(urgent) == 0


def test_detect_anomalies_slow_growth():
    """Very slow growth → urgent flag."""
    import random
    random.seed(4)
    measurements = []
    w = 6.5
    for d in range(15):
        w += 0.003    # only 3 g/day
        measurements.append(Measurement(d, w + random.gauss(0, 0.06)))
    result = kalman_pipeline(measurements)
    flags = detect_anomalies(result, age_months_at_start=4.0, sex="boy")
    urgent = [f for f in flags if f.severity == "urgent" and f.flag_type == "velocity_below_normal"]
    assert len(urgent) >= 1


def test_detect_anomalies_below_p3():
    """Severely underweight infant → below_p3 flag."""
    measurements = []
    w = 4.0    # Way below P50 for 4-mo (7.0)
    for d in range(10):
        w += 0.010
        measurements.append(Measurement(d, w))
    result = kalman_pipeline(measurements)
    flags = detect_anomalies(result, age_months_at_start=4.0, sex="boy")
    p3_flags = [f for f in flags if f.flag_type == "below_p3"]
    assert len(p3_flags) >= 1


def test_kalman_deterministic():
    """Same measurements → same output."""
    measurements = [Measurement(d, 6.0 + d * 0.02) for d in range(10)]
    r1 = kalman_pipeline(measurements)
    r2 = kalman_pipeline(measurements)
    assert r1.smoothed_weight == r2.smoothed_weight


def test_kalman_smoothed_increases_for_increasing_data():
    """For monotonically increasing observations, smoothed should also be ~monotonic."""
    import random
    random.seed(5)
    measurements = []
    w = 5.0
    for d in range(15):
        w += 0.030    # strong gain
        measurements.append(Measurement(d, w + random.gauss(0, 0.03)))
    result = kalman_pipeline(measurements)
    # Smoothed at end > start
    assert result.smoothed_weight[-1] > result.smoothed_weight[0]


def test_velocity_sign_correct():
    """Positive trend → positive velocity in smoothed."""
    measurements = [Measurement(d, 6.0 + d * 0.025) for d in range(10)]
    result = kalman_pipeline(measurements)
    # Most velocities should be positive
    positive = sum(1 for v in result.smoothed_velocity if v > 0)
    assert positive >= len(result.smoothed_velocity) // 2


if __name__ == "__main__":
    tests = [
        test_mat2x2_mul_identity,
        test_mat2x2_transpose,
        test_mat2x2_inv,
        test_mat2x2_inv_singular,
        test_mat2x2_add_sub_inverse,
        test_kalman_constant_signal,
        test_kalman_noise_reduction,
        test_kalman_tracks_linear_trend,
        test_who_p50_interpolation,
        test_who_p50_clamped,
        test_who_percentile_at_median,
        test_who_percentile_below_p3,
        test_who_percentile_above_p97,
        test_detect_anomalies_normal_growth,
        test_detect_anomalies_slow_growth,
        test_detect_anomalies_below_p3,
        test_kalman_deterministic,
        test_kalman_smoothed_increases_for_increasing_data,
        test_velocity_sign_correct,
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
