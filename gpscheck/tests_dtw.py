"""gpscheck edge tests — pure-function DTW correctness."""
from __future__ import annotations

from dtw import (
    GPSPoint, Route, haversine, point_dist, route_total_distance,
    route_duration_s, route_avg_speed_kmh,
    dtw_cost_matrix, dtw_backtrace, compute_dtw,
    identify_deviations, classify_route, extra_distance_estimate,
    Verdict,
)


def test_haversine_zero_distance():
    """Same point → 0 distance."""
    assert haversine(25.0, 121.5, 25.0, 121.5) == 0.0


def test_haversine_symmetric():
    """haversine(a,b) == haversine(b,a)."""
    d1 = haversine(25.0, 121.5, 25.1, 121.6)
    d2 = haversine(25.1, 121.6, 25.0, 121.5)
    assert abs(d1 - d2) < 0.01


def test_haversine_realistic_taipei_distance():
    """Taipei 101 to TSA airport ~4 km (haversine)."""
    d = haversine(25.0339, 121.5645, 25.0697, 121.5520)
    assert 3500 < d < 5000  # haversine ≈ 4.1 km


def test_route_total_distance():
    """Sum of consecutive haversines."""
    r = Route("r", [
        GPSPoint(25.0, 121.5, 0),
        GPSPoint(25.01, 121.5, 60),
        GPSPoint(25.02, 121.5, 120),
    ])
    total = route_total_distance(r)
    # Two haversines of ~1.11 km each
    assert 2000 < total < 2500


def test_route_total_distance_single_point():
    """Single-point route → 0."""
    r = Route("r", [GPSPoint(25.0, 121.5, 0)])
    assert route_total_distance(r) == 0


def test_route_avg_speed_basic():
    """Average speed = total_dist / duration in km/h."""
    # 2 km in 60 seconds = 120 km/h
    r = Route("r", [
        GPSPoint(25.0, 121.5, 0),
        GPSPoint(25.018, 121.5, 60),  # ~2 km north
    ])
    speed = route_avg_speed_kmh(r)
    assert 100 < speed < 150


def test_dtw_identical_routes_zero_cost():
    """Identical routes → 0 cost, similarity 100."""
    r1 = Route("a", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.51), GPSPoint(25.02, 121.52)])
    r2 = Route("b", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.51), GPSPoint(25.02, 121.52)])
    r = compute_dtw(r1, r2)
    assert r.distance_total_m == 0
    assert r.similarity_score == 100.0


def test_dtw_symmetric_within_tolerance():
    """DTW(a,b) ≈ DTW(b,a) (modulo path tie-breaking)."""
    r1 = Route("a", [GPSPoint(25.0, 121.5), GPSPoint(25.02, 121.51)])
    r2 = Route("b", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.51), GPSPoint(25.02, 121.51)])
    d1 = compute_dtw(r1, r2)
    d2 = compute_dtw(r2, r1)
    # Both should reach the same total cost (commutative under min(up, left, diag))
    assert abs(d1.distance_total_m - d2.distance_total_m) < 0.1


def test_dtw_cost_monotonic_in_deviation():
    """More deviated route → higher DTW cost (lower similarity)."""
    planned = Route("p", [GPSPoint(25.0, 121.5, 0), GPSPoint(25.05, 121.5, 300),
                            GPSPoint(25.1, 121.5, 600)])
    # close to planned
    close = Route("a", [GPSPoint(25.0, 121.5, 0), GPSPoint(25.05, 121.501, 300),
                          GPSPoint(25.1, 121.5, 600)])
    # far from planned
    far = Route("b", [GPSPoint(25.0, 121.5, 0), GPSPoint(25.05, 121.55, 300),
                       GPSPoint(25.1, 121.5, 600)])
    d_close = compute_dtw(close, planned)
    d_far = compute_dtw(far, planned)
    assert d_close.similarity_score > d_far.similarity_score


def test_dtw_cost_matrix_dimensions():
    """Cost matrix is n × m for sequences of length n and m."""
    a = [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.5)]
    b = [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.5), GPSPoint(25.02, 121.5)]
    C = dtw_cost_matrix(a, b)
    assert len(C) == 2
    assert all(len(row) == 3 for row in C)


def test_dtw_alignment_path_starts_at_origin_ends_at_corner():
    """Path starts (0,0) and ends (n-1, m-1)."""
    a = [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.51), GPSPoint(25.02, 121.52)]
    b = [GPSPoint(25.0, 121.5), GPSPoint(25.02, 121.52)]
    C = dtw_cost_matrix(a, b)
    path = dtw_backtrace(C)
    assert path[0] == (0, 0)
    assert path[-1] == (len(a) - 1, len(b) - 1)


def test_dtw_path_monotonic_non_decreasing():
    """Alignment path is monotonically non-decreasing in both indices."""
    a = [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.51), GPSPoint(25.02, 121.52)]
    b = [GPSPoint(25.0, 121.5), GPSPoint(25.015, 121.52)]
    C = dtw_cost_matrix(a, b)
    path = dtw_backtrace(C)
    for i in range(1, len(path)):
        assert path[i][0] >= path[i - 1][0]
        assert path[i][1] >= path[i - 1][1]


def test_classify_route_thresholds():
    """Verdict matches expected thresholds."""
    from dtw import DTWResult
    r_normal = DTWResult(0, 0, 1, 90, [])
    r_minor = DTWResult(0, 0, 1, 78, [])
    r_sig = DTWResult(0, 0, 1, 60, [])
    r_major = DTWResult(0, 0, 1, 30, [])
    assert classify_route(r_normal) == Verdict.NORMAL
    assert classify_route(r_minor) == Verdict.MINOR_DEVIATION
    assert classify_route(r_sig) == Verdict.SIGNIFICANT_DEVIATION
    assert classify_route(r_major) == Verdict.MAJOR_DEVIATION


def test_identify_deviations_threshold():
    """Deviations below threshold not flagged."""
    actual = Route("a", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.5)])
    planned = Route("p", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.5)])
    result = compute_dtw(actual, planned)
    devs = identify_deviations(actual, planned, result.alignment_path, threshold_m=100)
    assert len(devs) == 0


def test_identify_deviations_flag_real_dev():
    """Big deviation does get flagged."""
    actual = Route("a", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.6)])  # 10 km east
    planned = Route("p", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.5)])
    result = compute_dtw(actual, planned)
    devs = identify_deviations(actual, planned, result.alignment_path, threshold_m=500)
    assert len(devs) >= 1


def test_extra_distance_estimate():
    """Longer actual route returns positive extra."""
    short = Route("s", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.5)])
    long = Route("l", [GPSPoint(25.0, 121.5), GPSPoint(25.005, 121.6),
                         GPSPoint(25.01, 121.5)])
    assert extra_distance_estimate(long, short) > 0


def test_deterministic():
    """Same inputs → same DTW result."""
    a = Route("a", [GPSPoint(25.0, 121.5), GPSPoint(25.01, 121.51)])
    b = Route("b", [GPSPoint(25.0, 121.5), GPSPoint(25.02, 121.52)])
    r1 = compute_dtw(a, b)
    r2 = compute_dtw(a, b)
    assert r1.distance_total_m == r2.distance_total_m
    assert r1.similarity_score == r2.similarity_score
    assert r1.alignment_path == r2.alignment_path


def test_empty_sequence():
    """Empty sequence handled gracefully."""
    r = compute_dtw(Route("a", []), Route("b", [GPSPoint(25.0, 121.5)]))
    assert r.distance_total_m == 0


if __name__ == "__main__":
    tests = [
        test_haversine_zero_distance,
        test_haversine_symmetric,
        test_haversine_realistic_taipei_distance,
        test_route_total_distance,
        test_route_total_distance_single_point,
        test_route_avg_speed_basic,
        test_dtw_identical_routes_zero_cost,
        test_dtw_symmetric_within_tolerance,
        test_dtw_cost_monotonic_in_deviation,
        test_dtw_cost_matrix_dimensions,
        test_dtw_alignment_path_starts_at_origin_ends_at_corner,
        test_dtw_path_monotonic_non_decreasing,
        test_classify_route_thresholds,
        test_identify_deviations_threshold,
        test_identify_deviations_flag_real_dev,
        test_extra_distance_estimate,
        test_deterministic,
        test_empty_sequence,
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
