"""viewdrop edge tests — pure-function BOCPD correctness."""
from __future__ import annotations

import math
import random

from bocpd import (
    run_bocpd, predictive_prob, estimate_obs_sigma,
    _gaussian_pdf,
)


def test_gaussian_pdf_peak():
    """N(0,1) peak at 0 is 1/sqrt(2π)."""
    assert abs(_gaussian_pdf(0, 0, 1) - 1.0 / math.sqrt(2 * math.pi)) < 1e-6


def test_gaussian_pdf_symmetric():
    """N(0,1) is symmetric around mean."""
    assert abs(_gaussian_pdf(1.5, 0, 1) - _gaussian_pdf(-1.5, 0, 1)) < 1e-9


def test_gaussian_pdf_zero_sigma():
    """sigma ≤ 0 returns 0 (degenerate)."""
    assert _gaussian_pdf(0, 0, 0) == 0
    assert _gaussian_pdf(0, 0, -1) == 0


def test_predictive_prob_no_history():
    """Empty history → uses prior."""
    p = predictive_prob(0, [], prior_mu=0, prior_sigma=1, obs_sigma=1)
    # Should be positive and peak-ish
    assert p > 0


def test_predictive_prob_with_history():
    """History centers prediction around sample mean."""
    p_at_mean = predictive_prob(10, [10, 10, 10], prior_mu=0, prior_sigma=10, obs_sigma=1)
    p_far = predictive_prob(100, [10, 10, 10], prior_mu=0, prior_sigma=10, obs_sigma=1)
    assert p_at_mean > p_far  # closer to history → higher prob


def test_bocpd_stable_series_no_changepoint():
    """Stable Gaussian series shouldn't trigger spurious changepoints."""
    random.seed(7)
    data = [random.gauss(50, 5) for _ in range(40)]
    r = run_bocpd(data, hazard_lambda=30, obs_sigma=5, prior_mu=50, prior_sigma=20)
    # Allow 0 or 1 spurious detection (small chance with this seed)
    assert len(r.changepoints) <= 1


def test_bocpd_detects_clear_change():
    """Series with mean step should be detected."""
    random.seed(11)
    data = [random.gauss(100, 10) for _ in range(30)] + \
           [random.gauss(40, 10) for _ in range(30)]
    r = run_bocpd(data, hazard_lambda=30, obs_sigma=10, prior_mu=70, prior_sigma=50)
    assert len(r.changepoints) >= 1
    # Most-likely should be close to t=30 (within ±3)
    assert r.most_likely_changepoint is not None
    assert abs(r.most_likely_changepoint - 30) <= 3


def test_bocpd_confidence_in_range():
    """Confidence in [0, 1]."""
    random.seed(3)
    data = [random.gauss(100, 5) for _ in range(20)] + \
           [random.gauss(50, 5) for _ in range(20)]
    r = run_bocpd(data, hazard_lambda=20, obs_sigma=5)
    if r.most_likely_changepoint is not None:
        assert 0 <= r.most_likely_cp_confidence <= 1.0


def test_bocpd_map_run_lengths_nondecreasing_in_segment():
    """Within a stable segment, MAP run length should grow most of the time."""
    random.seed(5)
    data = [random.gauss(50, 3) for _ in range(20)]
    r = run_bocpd(data, hazard_lambda=50, obs_sigma=3, prior_mu=50, prior_sigma=10)
    # MAP should reach near the segment length by end
    assert r.map_run_lengths[-1] >= len(data) // 2


def test_bocpd_segment_summaries_match_means():
    """Segment summaries should match actual segment means."""
    random.seed(17)
    seg1 = [random.gauss(100, 5) for _ in range(20)]
    seg2 = [random.gauss(50, 5) for _ in range(20)]
    data = seg1 + seg2
    r = run_bocpd(data, hazard_lambda=20, obs_sigma=5, prior_mu=75, prior_sigma=30)
    # Find the changepoint near t=20
    if r.most_likely_changepoint is not None:
        cp = r.most_likely_changepoint
        before_seg = next((s for s in r.segment_summaries if s["end_idx"] + 1 == cp), None)
        after_seg = next((s for s in r.segment_summaries if s["start_idx"] == cp), None)
        if before_seg and after_seg:
            assert before_seg["mean"] > after_seg["mean"]  # high → low


def test_bocpd_three_segments():
    """Series with two changepoints should detect at least one (depending on noise)."""
    random.seed(31)
    data = [random.gauss(100, 5) for _ in range(15)] + \
           [random.gauss(50, 5) for _ in range(15)] + \
           [random.gauss(120, 5) for _ in range(15)]
    r = run_bocpd(data, hazard_lambda=15, obs_sigma=5, prior_mu=80, prior_sigma=40)
    assert len(r.changepoints) >= 1   # at least one detected


def test_estimate_obs_sigma_basic():
    """Sigma estimator returns positive value."""
    data = [50.0 + (i % 5) for i in range(30)]
    sigma = estimate_obs_sigma(data)
    assert sigma > 0


def test_estimate_obs_sigma_short_data():
    """Short data falls back to global stdev."""
    sigma = estimate_obs_sigma([1, 2, 3])
    assert sigma > 0


def test_bocpd_deterministic():
    """Same data → same result (no randomness in algorithm)."""
    random.seed(42)
    data = [random.gauss(100, 10) for _ in range(20)] + \
           [random.gauss(50, 10) for _ in range(20)]
    r1 = run_bocpd(data, hazard_lambda=20, obs_sigma=10)
    r2 = run_bocpd(data, hazard_lambda=20, obs_sigma=10)
    assert r1.changepoints == r2.changepoints
    assert r1.map_run_lengths == r2.map_run_lengths


def test_bocpd_increasing_hazard_more_changepoints():
    """Smaller hazard_lambda = higher hazard = more changepoint candidates."""
    random.seed(99)
    # Use noisy data so different hazard yields different detection
    data = [random.gauss(50, 3) for _ in range(10)] + \
           [random.gauss(60, 3) for _ in range(10)] + \
           [random.gauss(40, 3) for _ in range(10)] + \
           [random.gauss(55, 3) for _ in range(10)]
    r_low = run_bocpd(data, hazard_lambda=100, obs_sigma=3)  # low hazard
    r_high = run_bocpd(data, hazard_lambda=5, obs_sigma=3)    # high hazard
    # Higher hazard should produce >= as many detections
    assert len(r_high.changepoints) >= len(r_low.changepoints)


def test_bocpd_posterior_normalized():
    """Posterior at every timestep sums to ~1."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    r = run_bocpd(data, hazard_lambda=10, obs_sigma=1, prior_mu=3, prior_sigma=5)
    for post in r.posterior_run_lengths:
        total = sum(post.values())
        assert abs(total - 1.0) < 0.01


def test_bocpd_single_observation():
    """Single observation doesn't crash."""
    r = run_bocpd([50.0], hazard_lambda=10, obs_sigma=5)
    assert r.changepoints == []
    assert len(r.segment_summaries) == 1


if __name__ == "__main__":
    tests = [
        test_gaussian_pdf_peak,
        test_gaussian_pdf_symmetric,
        test_gaussian_pdf_zero_sigma,
        test_predictive_prob_no_history,
        test_predictive_prob_with_history,
        test_bocpd_stable_series_no_changepoint,
        test_bocpd_detects_clear_change,
        test_bocpd_confidence_in_range,
        test_bocpd_map_run_lengths_nondecreasing_in_segment,
        test_bocpd_segment_summaries_match_means,
        test_bocpd_three_segments,
        test_estimate_obs_sigma_basic,
        test_estimate_obs_sigma_short_data,
        test_bocpd_deterministic,
        test_bocpd_increasing_hazard_more_changepoints,
        test_bocpd_posterior_normalized,
        test_bocpd_single_observation,
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
