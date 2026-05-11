"""Edge-case tests for hb_shrink.py -- pure-function HB shrinkage.

Run: python tests_hb.py
"""
from __future__ import annotations

import math
import sys

from hb_shrink import (
    Review, Query, fit_hb, recommend_for_query,
    naive_vs_shrunk_table, most_corrected_cells, model_summary,
    _pooled_within_variance, _method_of_moments_tau_squared, _group_by_cell,
)


def _r(breed, brand, rating):
    return Review(breed=breed, brand=brand, rating=rating)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


def test_empty_raises():
    try:
        fit_hb([])
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty input")


def test_single_cell_single_review():
    # One review, one cell -> mu_global = its mean, sigma falls back, tau=0 (one cell).
    m = fit_hb([_r("a", "x", 4.0)])
    assert m.mu_global == 4.0
    assert m.n_cells == 1
    # With only one cell, tau^2 method-of-moments = max(0, 0 - sigma^2/1) <= 0 -> 0 -> complete pooling.
    cell = m.cells[("a", "x")]
    assert_close(cell.shrunk_mean, 4.0, msg="single review collapses to its own mean")


def test_two_cells_equal_n_no_drift():
    reviews = [
        _r("a", "x", 5.0), _r("a", "x", 5.0), _r("a", "x", 5.0),
        _r("a", "y", 3.0), _r("a", "y", 3.0), _r("a", "y", 3.0),
    ]
    m = fit_hb(reviews)
    assert_close(m.mu_global, 4.0, msg="mu_global = avg of cell means")
    cx = m.cells[("a", "x")]
    cy = m.cells[("a", "y")]
    # Within each cell variance is zero -> sigma fallback to overall variance.
    # Shrinkage should still pull cells toward 4.0, but with finite tau the cells stay close to 5/3.
    assert cx.shrunk_mean <= 5.0
    assert cy.shrunk_mean >= 3.0
    assert cx.shrunk_mean > cy.shrunk_mean, "high cell still ranks above low cell"


def test_high_n_low_n_shrinkage_asymmetric():
    # A 30-sample cell with mean ~4.6, and a 2-sample cell with mean 5.0.
    # Shrinkage should pull the 2-sample cell harder.
    # Use jittered ratings so pooled within-variance > 0 (otherwise w collapses to 1).
    big_jitter = [4.4, 4.5, 4.6, 4.7, 4.8, 4.5, 4.6, 4.7, 4.5, 4.6,
                  4.4, 4.8, 4.5, 4.6, 4.7, 4.5, 4.6, 4.5, 4.7, 4.6,
                  4.4, 4.6, 4.8, 4.5, 4.7, 4.6, 4.5, 4.6, 4.7, 4.5]
    big = [_r("a", "big", v) for v in big_jitter]
    small = [_r("a", "small", 5.0), _r("a", "small", 5.0)]
    other = [_r("a", "ref", v) for v in (3.3, 3.5, 3.7, 3.4, 3.6, 3.5, 3.3, 3.6, 3.5, 3.7)]
    m = fit_hb(big + small + other)
    big_c = m.cells[("a", "big")]
    small_c = m.cells[("a", "small")]
    # big cell: shrinkage weight close to 1 -> shrunk_mean ~ raw_mean
    # small cell: shrinkage weight smaller -> shrunk_mean pulled toward mu_global
    assert big_c.shrinkage_weight > small_c.shrinkage_weight, "big-n more trusted"
    assert abs(big_c.shrunk_mean - big_c.raw_mean) < abs(small_c.shrunk_mean - small_c.raw_mean), \
        "small-n cell corrected more than big-n cell"


def test_shrinkage_weight_in_unit_interval():
    reviews = []
    for breed in ("a", "b"):
        for brand in ("x", "y", "z"):
            for r in (3.5, 4.0, 4.5, 4.2):
                reviews.append(_r(breed, brand, r))
    m = fit_hb(reviews)
    for c in m.cells.values():
        assert 0.0 <= c.shrinkage_weight <= 1.0, f"w out of [0,1]: {c.shrinkage_weight}"


def test_posterior_variance_smaller_than_within():
    # Posterior variance should be smaller than naive sigma^2/n for individual cells
    # when tau is finite (because the prior tightens the estimate).
    reviews = []
    for brand in ("a", "b", "c", "d"):
        for r in (4.0, 4.2, 4.4, 4.1, 4.3):
            reviews.append(_r("dog", brand, r))
    m = fit_hb(reviews)
    sigma_sq = m.sigma_within ** 2
    for (b, br), c in m.cells.items():
        if m.tau_between > 0:
            naive_var = sigma_sq / c.n_samples
            assert c.posterior_std ** 2 <= naive_var + 1e-9, \
                f"posterior var ({c.posterior_std**2}) should be <= naive var ({naive_var})"


def test_credible_interval_brackets_shrunk_mean():
    reviews = [_r("a", "x", 4.0 + 0.1 * i) for i in range(-3, 4)]
    reviews += [_r("a", "y", 3.0 + 0.2 * i) for i in range(-2, 3)]
    m = fit_hb(reviews)
    for c in m.cells.values():
        assert c.ci_low <= c.shrunk_mean <= c.ci_high, \
            f"CI [{c.ci_low}, {c.ci_high}] doesn't bracket shrunk_mean {c.shrunk_mean}"


def test_recommend_shrinks_low_n_more_than_high_n():
    # Brand "novel" has 1 review of 5.0; brand "veteran" has 20 reviews around 4.5.
    # HB property: the LOW-N cell is shrunk much more (lower shrinkage_weight, larger raw-to-shrunk gap)
    # than the HIGH-N cell. Strict re-ranking is data-dependent, but this asymmetry is the
    # core James-Stein guarantee.
    reviews = [_r("a", "novel", 5.0)]
    veteran_jitter = [4.3, 4.4, 4.5, 4.6, 4.7, 4.5, 4.6, 4.4, 4.5, 4.6,
                       4.3, 4.7, 4.5, 4.4, 4.6, 4.5, 4.4, 4.6, 4.5, 4.7]
    reviews += [_r("a", "veteran", v) for v in veteran_jitter]
    reviews += [_r("a", "ref", v) for v in (2.8, 3.0, 3.2, 2.9, 3.1, 3.0, 2.8, 3.2, 3.0, 3.1)]
    reviews += [_r("a", "ref2", v) for v in (3.8, 4.0, 4.2, 3.9, 4.1, 4.0, 3.8, 4.2, 4.0, 4.1)]
    m = fit_hb(reviews)
    novel = m.cells[("a", "novel")]
    veteran = m.cells[("a", "veteran")]
    assert novel.shrinkage_weight < veteran.shrinkage_weight, \
        f"low-n cell should be trusted less: novel w={novel.shrinkage_weight}, vet w={veteran.shrinkage_weight}"
    novel_gap = abs(novel.raw_mean - novel.shrunk_mean)
    vet_gap = abs(veteran.raw_mean - veteran.shrunk_mean)
    assert novel_gap > vet_gap, \
        f"low-n cell should be corrected more: novel gap={novel_gap}, vet gap={vet_gap}"
    # And recommendations must still respect rank order (sorted by shrunk_mean desc).
    recs = recommend_for_query(m, Query(breed="a"), top_k=4)
    shrunk_means = [r.shrunk_mean for r in recs]
    assert shrunk_means == sorted(shrunk_means, reverse=True), \
        f"recs not sorted by shrunk_mean desc: {shrunk_means}"


def test_recommend_returns_empty_for_unknown_breed():
    reviews = [_r("a", "x", 4.0), _r("a", "y", 4.5)]
    m = fit_hb(reviews)
    recs = recommend_for_query(m, Query(breed="z"))
    assert recs == [], "unknown breed should return no recommendations"


def test_mu_global_uses_cell_average_not_review_average():
    # Cell A has 30 reviews mean 4.0, Cell B has 2 reviews mean 5.0.
    # Review-weighted mean -> ~4.06; cell-weighted mean -> 4.5.
    reviews = [_r("a", "x", 4.0) for _ in range(30)]
    reviews += [_r("a", "y", 5.0), _r("a", "y", 5.0)]
    m = fit_hb(reviews)
    assert_close(m.mu_global, 4.5, msg="mu_global is unweighted cell-mean average")


def test_pooled_within_variance_skips_singletons():
    cell_samples = {
        ("a", "x"): [4.0],            # singleton -- skipped
        ("a", "y"): [3.0, 5.0],        # variance = 1.0 over Bessel-corrected (n-1=1)
        ("a", "z"): [4.0, 4.0, 4.0],   # variance = 0
    }
    s = _pooled_within_variance(cell_samples)
    # pooled = ((3-4)^2 + (5-4)^2 + 0+0+0) / (1 + 2) = 2/3
    assert_close(s, 2.0 / 3.0, msg="pooled within-variance")


def test_method_of_moments_clipped_at_zero():
    # All cell means identical -> no between-cell variance -> tau^2 should clip to 0.
    cells = [(4.0, 5), (4.0, 5), (4.0, 5)]
    tau_sq = _method_of_moments_tau_squared(cells, sigma_within_sq=1.0, mu_global=4.0)
    assert tau_sq == 0.0


def test_complete_pooling_when_tau_zero():
    # Identical cell means -> tau=0 -> shrunk_mean for every cell equals mu_global.
    reviews = [
        _r("a", "x", 4.0), _r("a", "x", 4.0),
        _r("a", "y", 4.0), _r("a", "y", 4.0),
        _r("a", "z", 4.0), _r("a", "z", 4.0),
    ]
    m = fit_hb(reviews)
    for c in m.cells.values():
        assert_close(c.shrunk_mean, m.mu_global, tol=1e-9, msg="tau=0 -> complete pooling")
        assert c.shrinkage_weight == 0.0


def test_delta_sign_matches_correction_direction():
    # Cell A high raw mean, mu_global lower -> delta = raw - shrunk > 0.
    # Cell B low raw mean, mu_global higher -> delta < 0.
    # Needs within-cell noise on the 'mid' anchor so pooled sigma_within > 0.
    reviews = [_r("a", "high", 4.9), _r("a", "high", 4.9)]
    reviews += [_r("a", "low", 2.0), _r("a", "low", 2.0)]
    mid_jitter = (3.3, 3.5, 3.7, 3.4, 3.6, 3.5, 3.3, 3.7)
    reviews += [_r("a", "mid", v) for v in mid_jitter]
    m = fit_hb(reviews)
    high = m.cells[("a", "high")]
    low = m.cells[("a", "low")]
    assert high.raw_mean - high.shrunk_mean > 0, "high cell should be pulled down"
    assert low.raw_mean - low.shrunk_mean < 0, "low cell should be pulled up"


def test_most_corrected_cells_sorted_by_abs_delta():
    reviews = []
    reviews += [_r("a", "extreme_high", 5.0)]
    reviews += [_r("a", "extreme_low", 1.5)]
    reviews += [_r("a", "stable", 3.8) for _ in range(20)]
    reviews += [_r("a", "calm", 3.5) for _ in range(10)]
    m = fit_hb(reviews)
    rows = most_corrected_cells(m, top_n=3)
    brands = [r["brand"] for r in rows]
    assert "stable" not in brands or brands.index("stable") == 2, \
        "stable should be last; extreme cells corrected most"


def test_model_summary_keys():
    reviews = [_r("a", "x", 4.0), _r("a", "x", 4.2), _r("a", "y", 3.8)]
    m = fit_hb(reviews)
    s = model_summary(m)
    for k in ("n_total_reviews", "n_cells", "mu_global", "sigma_within", "tau_between", "icc"):
        assert k in s, f"summary missing key {k}"
    assert 0 <= s["icc"] <= 1


def test_no_negative_n_samples():
    reviews = [_r("a", "x", 4.0)]
    m = fit_hb(reviews)
    for c in m.cells.values():
        assert c.n_samples >= 1


def test_grouping_correctness():
    reviews = [_r("a", "x", 4.0), _r("a", "y", 3.0), _r("a", "x", 4.5)]
    grouped = _group_by_cell(reviews)
    assert grouped[("a", "x")] == [4.0, 4.5]
    assert grouped[("a", "y")] == [3.0]


def test_recommendation_ranks_are_sequential():
    reviews = []
    for brand in ("a", "b", "c", "d"):
        for r in (4.0, 4.5, 4.2):
            reviews.append(_r("dog", brand, r))
    m = fit_hb(reviews)
    recs = recommend_for_query(m, Query(breed="dog"), top_k=4)
    for i, r in enumerate(recs, 1):
        assert r.rank == i, f"rank should be sequential; got {r.rank} at index {i}"


def test_naive_vs_shrunk_table_has_all_cells():
    reviews = [_r("a", "x", 4.0), _r("a", "y", 3.5), _r("b", "x", 4.2)]
    m = fit_hb(reviews)
    table = naive_vs_shrunk_table(m)
    assert len(table) == 3


def test_shrunk_mean_between_raw_and_global():
    # Standard HB property: shrunk_mean is a convex combination of raw_mean and mu_global.
    reviews = []
    for brand in ("a", "b", "c"):
        for r in (4.0, 4.3, 4.6):
            reviews.append(_r("dog", brand, r))
    reviews.append(_r("dog", "outlier", 2.0))
    m = fit_hb(reviews)
    g = m.mu_global
    for c in m.cells.values():
        lo, hi = sorted((c.raw_mean, g))
        assert lo - 1e-9 <= c.shrunk_mean <= hi + 1e-9, \
            f"shrunk_mean {c.shrunk_mean} not between raw {c.raw_mean} and global {g}"


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
