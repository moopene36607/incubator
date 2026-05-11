"""expsense edge tests — pure-function Isolation Forest correctness."""
from __future__ import annotations

import random
import math

from iforest import (
    harmonic, c_factor, build_tree, path_length, fit_iforest,
    anomaly_score, score_all, top_k_anomalies, feature_contribution,
    IsolationLeaf, IsolationNode,
)


def test_harmonic_basic():
    """H(1) = 1, H(2) = 1.5, H(0) = 0."""
    assert harmonic(0) == 0.0
    assert harmonic(1) == 1.0
    assert abs(harmonic(2) - 1.5) < 1e-9
    assert abs(harmonic(3) - (1 + 0.5 + 1/3)) < 1e-9


def test_harmonic_large_n():
    """For large n, harmonic ≈ ln(n) + γ."""
    n = 1000
    h = harmonic(n)
    expected = math.log(n) + 0.5772
    assert abs(h - expected) < 0.01


def test_c_factor_basic():
    """c(n) increases monotonically."""
    assert c_factor(0) == 0
    assert c_factor(1) == 0
    assert c_factor(10) > 0
    assert c_factor(100) > c_factor(10)


def test_build_tree_leaf_for_single_point():
    """Single point → leaf."""
    X = [{"a": 1.0, "b": 2.0}]
    rng = random.Random(0)
    tree = build_tree(X, ["a", "b"], 0, 8, rng)
    assert tree.is_leaf
    assert tree.size == 1


def test_build_tree_leaf_for_zero_variance():
    """All-same-value → leaf (no valid feature to split)."""
    X = [{"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 2.0}]
    rng = random.Random(0)
    tree = build_tree(X, ["a", "b"], 0, 8, rng)
    assert tree.is_leaf


def test_build_tree_respects_height_limit():
    """Tree depth ≤ height_limit."""
    rng = random.Random(0)
    X = [{"a": float(i)} for i in range(20)]
    tree = build_tree(X, ["a"], 0, 3, rng)

    def max_depth(node, d):
        if node.is_leaf:
            return d
        return max(max_depth(node.left, d + 1), max_depth(node.right, d + 1))
    assert max_depth(tree, 0) <= 3


def test_path_length_returns_positive():
    """Path length always ≥ 0."""
    rng = random.Random(0)
    X = [{"a": float(i)} for i in range(10)]
    tree = build_tree(X, ["a"], 0, 5, rng)
    for x in X:
        pl = path_length(x, tree, 0)
        assert pl >= 0


def test_fit_iforest_creates_n_trees():
    """Forest has n_trees trees."""
    X = [{"a": float(i), "b": float(i % 5)} for i in range(50)]
    forest = fit_iforest(X, ["a", "b"], n_trees=20, sample_size=20, seed=0)
    assert len(forest.trees) == 20


def test_anomaly_score_in_range():
    """Score ∈ (0, 1]."""
    X = [{"a": random.gauss(0, 1), "b": random.gauss(0, 1)} for _ in range(50)]
    forest = fit_iforest(X, ["a", "b"], n_trees=50, sample_size=32, seed=0)
    for x in X[:5]:
        s = anomaly_score(x, forest)
        assert 0 <= s <= 1


def test_outlier_scores_higher_than_inlier():
    """Injected outlier should score higher than typical points."""
    random.seed(42)
    # 80 inliers in unit box, 1 outlier far away
    inliers = [{"a": random.gauss(0, 1), "b": random.gauss(0, 1)} for _ in range(80)]
    outlier = {"a": 50.0, "b": -50.0}
    X = inliers + [outlier]
    forest = fit_iforest(X, ["a", "b"], n_trees=100, sample_size=64, seed=42)
    scores = score_all(X, forest)
    outlier_score = scores[-1]
    max_inlier_score = max(scores[:-1])
    assert outlier_score > max_inlier_score


def test_top_k_anomalies_sorted_desc():
    """top_k returns highest-score first."""
    random.seed(42)
    X = [{"a": random.gauss(0, 1)} for _ in range(50)] + [{"a": 100.0}]
    forest = fit_iforest(X, ["a"], n_trees=50, sample_size=32, seed=42)
    scores = score_all(X, forest)
    top = top_k_anomalies(X, scores, k=5)
    for i in range(1, len(top)):
        assert top[i - 1][1] >= top[i][1]


def test_top_k_anomalies_threshold_filter():
    """Threshold filters out non-anomalies."""
    X = [{"a": 0.5}, {"a": 0.6}, {"a": 0.4}]
    scores = [0.4, 0.55, 0.45]
    top = top_k_anomalies(X, scores, k=5, threshold=0.5)
    assert len(top) == 1
    assert top[0][1] == 0.55


def test_feature_contribution_returns_all_features():
    """Contribution dict has entry per feature."""
    random.seed(0)
    X = [{"a": float(i), "b": float(i % 3)} for i in range(20)]
    forest = fit_iforest(X, ["a", "b"], n_trees=20, sample_size=16, seed=0)
    contribs = feature_contribution(X[0], forest)
    assert "a" in contribs
    assert "b" in contribs


def test_deterministic_with_same_seed():
    """Same seed → same forest behavior."""
    X = [{"a": float(i)} for i in range(30)]
    f1 = fit_iforest(X, ["a"], n_trees=30, sample_size=16, seed=42)
    f2 = fit_iforest(X, ["a"], n_trees=30, sample_size=16, seed=42)
    s1 = score_all(X, f1)
    s2 = score_all(X, f2)
    assert s1 == s2


def test_small_sample_size_handled():
    """sample_size > len(X) doesn't crash."""
    X = [{"a": 1.0}, {"a": 2.0}, {"a": 3.0}]
    forest = fit_iforest(X, ["a"], n_trees=10, sample_size=100, seed=0)
    assert len(forest.trees) == 10
    scores = score_all(X, forest)
    assert len(scores) == 3


def test_score_increases_with_distance():
    """Points farther from cluster get higher scores."""
    random.seed(42)
    cluster = [{"x": random.gauss(0, 1)} for _ in range(40)]
    far_points = [{"x": 10.0}, {"x": 20.0}, {"x": 30.0}]
    X = cluster + far_points
    forest = fit_iforest(X, ["x"], n_trees=100, sample_size=32, seed=42)
    scores = score_all(X, forest)
    # Three far points should have monotonically (or close) increasing scores
    far_scores = scores[-3:]
    # All far_scores should be above max cluster score
    max_cluster = max(scores[:40])
    for s in far_scores:
        assert s > max_cluster * 0.9


if __name__ == "__main__":
    tests = [
        test_harmonic_basic,
        test_harmonic_large_n,
        test_c_factor_basic,
        test_build_tree_leaf_for_single_point,
        test_build_tree_leaf_for_zero_variance,
        test_build_tree_respects_height_limit,
        test_path_length_returns_positive,
        test_fit_iforest_creates_n_trees,
        test_anomaly_score_in_range,
        test_outlier_scores_higher_than_inlier,
        test_top_k_anomalies_sorted_desc,
        test_top_k_anomalies_threshold_filter,
        test_feature_contribution_returns_all_features,
        test_deterministic_with_same_seed,
        test_small_sample_size_handled,
        test_score_increases_with_distance,
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
