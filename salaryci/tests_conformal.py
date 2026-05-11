"""salaryci edge tests — pure-function conformal prediction correctness."""
from __future__ import annotations

from conformal import (
    JobseekerProfile, select_calibration_set, predict_median,
    nonconformity_scores, conformal_quantile, predict_interval,
    negotiation_anchors,
)
from corpus import CORPUS, filter_corpus, SalaryRecord


def test_corpus_nonempty():
    assert len(CORPUS) >= 50


def test_filter_corpus_industry():
    sw = filter_corpus(industry="SOFTWARE")
    assert len(sw) > 0
    for r in sw:
        assert r.industry == "SOFTWARE"


def test_filter_corpus_role_level():
    backend_mid = filter_corpus(industry="SOFTWARE", role_family="BACKEND", level="MID")
    assert len(backend_mid) > 0
    for r in backend_mid:
        assert r.role_family == "BACKEND" and r.level == "MID"


def test_filter_corpus_exp_band():
    band = filter_corpus(exp_band=(3, 5))
    assert len(band) > 0
    for r in band:
        assert 3 <= r.exp_years <= 5


def test_calibration_set_tier1_exact():
    """For common Backend MID 4y profile, Tier 1 should hit (≥6 records)."""
    p = JobseekerProfile(industry="SOFTWARE", role_family="BACKEND", level="MID",
                         exp_years=4, location="TAIPEI")
    cal, desc = select_calibration_set(p)
    assert len(cal) >= 6
    assert "level=MID" in desc


def test_calibration_set_relaxation():
    """Rare profile (e.g., BIO DATA STAFF 10y) falls back to broader filter."""
    p = JobseekerProfile(industry="BIO", role_family="DATA", level="STAFF",
                         exp_years=10, location="TAIPEI")
    cal, desc = select_calibration_set(p)
    # Should still return something via relaxation
    assert len(cal) > 0
    # Description indicates some form of relaxation (not exact Tier 1)
    relaxation_markers = ("放寬", "嚴重不足", "跨產業", "only")
    assert any(m in desc for m in relaxation_markers), f"description={desc!r}"


def test_nonconformity_scores_nonneg():
    cal = filter_corpus(industry="SOFTWARE", role_family="BACKEND", level="MID")
    point = predict_median(cal, JobseekerProfile("SOFTWARE", "BACKEND", "MID", 4, "TAIPEI"))
    scores = nonconformity_scores(cal, point)
    assert all(s >= 0 for s in scores)
    assert len(scores) == len(cal)


def test_conformal_quantile_ordering():
    """Larger alpha => smaller quantile (looser interval)."""
    scores = [1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0]
    q_90 = conformal_quantile(scores, alpha=0.10)
    q_50 = conformal_quantile(scores, alpha=0.50)
    assert q_90 >= q_50  # 90% CI wider than 50%


def test_conformal_quantile_empty():
    assert conformal_quantile([], alpha=0.1) == 0.0


def test_predict_interval_basic():
    p = JobseekerProfile(industry="SOFTWARE", role_family="BACKEND", level="MID",
                         exp_years=4, location="TAIPEI", current_offer_ntd_k=68)
    r = predict_interval(p)
    # Interval ordered correctly
    assert r.lower_ci_ntd_k <= r.median_estimate_ntd_k <= r.upper_ci_ntd_k
    # Coverage level set to 90%
    assert r.confidence_level == 0.9
    # Offer position computed
    assert r.offer_position_pct is not None
    assert r.offer_vs_median_pct is not None


def test_offer_below_median_negative_pct():
    p = JobseekerProfile(industry="SOFTWARE", role_family="BACKEND", level="MID",
                         exp_years=4, location="TAIPEI", current_offer_ntd_k=50)
    r = predict_interval(p)
    assert r.offer_vs_median_pct < 0    # 50 well below NT$72K median


def test_offer_above_median_positive_pct():
    p = JobseekerProfile(industry="SOFTWARE", role_family="BACKEND", level="MID",
                         exp_years=4, location="TAIPEI", current_offer_ntd_k=85)
    r = predict_interval(p)
    assert r.offer_vs_median_pct > 0


def test_negotiation_anchors_ordering():
    """walk-away < median < aim_for < stretch."""
    p = JobseekerProfile(industry="SOFTWARE", role_family="BACKEND", level="MID",
                         exp_years=4, location="TAIPEI")
    r = predict_interval(p)
    a = negotiation_anchors(r)
    assert a["walk_away_ntd_k"] <= a["median_anchor_ntd_k"]
    assert a["median_anchor_ntd_k"] <= a["aim_for_ntd_k"]
    assert a["aim_for_ntd_k"] <= a["stretch_target_ntd_k"]


def test_smaller_alpha_wider_interval():
    """99% CI should be wider than 90%."""
    p = JobseekerProfile(industry="SOFTWARE", role_family="BACKEND", level="MID",
                         exp_years=4, location="TAIPEI")
    r90 = predict_interval(p, alpha=0.10)
    r99 = predict_interval(p, alpha=0.01)
    width90 = r90.upper_ci_ntd_k - r90.lower_ci_ntd_k
    width99 = r99.upper_ci_ntd_k - r99.lower_ci_ntd_k
    assert width99 >= width90


def test_deterministic():
    """Same profile → same result (no randomness)."""
    p = JobseekerProfile(industry="SOFTWARE", role_family="BACKEND", level="MID",
                         exp_years=4, location="TAIPEI", current_offer_ntd_k=68)
    r1 = predict_interval(p)
    r2 = predict_interval(p)
    assert r1.median_estimate_ntd_k == r2.median_estimate_ntd_k
    assert r1.lower_ci_ntd_k == r2.lower_ci_ntd_k
    assert r1.upper_ci_ntd_k == r2.upper_ci_ntd_k


def test_lower_ci_nonneg():
    """Even for low-salary cluster, lower CI clamped to 0."""
    p = JobseekerProfile(industry="RETAIL", role_family="OPS", level="JUNIOR",
                         exp_years=1, location="TAIPEI")
    r = predict_interval(p, alpha=0.01)  # very wide interval
    assert r.lower_ci_ntd_k >= 0


if __name__ == "__main__":
    tests = [
        test_corpus_nonempty,
        test_filter_corpus_industry,
        test_filter_corpus_role_level,
        test_filter_corpus_exp_band,
        test_calibration_set_tier1_exact,
        test_calibration_set_relaxation,
        test_nonconformity_scores_nonneg,
        test_conformal_quantile_ordering,
        test_conformal_quantile_empty,
        test_predict_interval_basic,
        test_offer_below_median_negative_pct,
        test_offer_above_median_positive_pct,
        test_negotiation_anchors_ordering,
        test_smaller_alpha_wider_interval,
        test_deterministic,
        test_lower_ci_nonneg,
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
