"""crybabel edge tests — pure-function Random Forest correctness."""
from __future__ import annotations

import random
import math

from rf import (
    gini_impurity, class_distribution, find_best_split, build_tree,
    tree_predict, fit_forest, predict_one, predict, accuracy,
    feature_importance_simple, TreeLeaf, TreeNode, bootstrap_sample,
)


def test_gini_pure():
    """All same class → 0."""
    assert gini_impurity({"A": 10}) == 0.0


def test_gini_max_two_class():
    """50/50 split → 0.5."""
    assert abs(gini_impurity({"A": 5, "B": 5}) - 0.5) < 1e-9


def test_gini_three_class_uniform():
    """3-class uniform → 1 - 3·(1/3)² = 2/3."""
    assert abs(gini_impurity({"A": 1, "B": 1, "C": 1}) - 2/3) < 1e-9


def test_class_distribution():
    """Counts labels."""
    d = class_distribution(["A", "A", "B", "A", "C"])
    assert d == {"A": 3, "B": 1, "C": 1}


def test_find_best_split_separable():
    """Linearly separable: best split at threshold ~10."""
    X = [{"x": 1}, {"x": 2}, {"x": 3}, {"x": 15}, {"x": 18}, {"x": 20}]
    y = ["A", "A", "A", "B", "B", "B"]
    rng = random.Random(0)
    result = find_best_split(X, y, ["x"], rng)
    assert result is not None
    feat, thresh, gini = result
    assert feat == "x"
    assert 3 < thresh < 15
    assert gini == 0.0    # perfect split


def test_find_best_split_no_variance():
    """If feature has no variance, no split possible."""
    X = [{"x": 5}, {"x": 5}, {"x": 5}]
    y = ["A", "B", "A"]
    rng = random.Random(0)
    result = find_best_split(X, y, ["x"], rng)
    assert result is None


def test_build_tree_returns_leaf_for_pure_class():
    """All same class → leaf."""
    X = [{"x": 1}, {"x": 2}, {"x": 3}]
    y = ["A", "A", "A"]
    rng = random.Random(0)
    tree = build_tree(X, y, ["x"], 0, 5, 2, None, rng)
    assert tree.is_leaf
    assert tree.predict_class() == "A"


def test_build_tree_respects_max_depth():
    """Tree depth bounded."""
    rng = random.Random(0)
    X = [{"x": i, "y": (i * 7) % 11} for i in range(40)]
    y = [f"c{i % 5}" for i in range(40)]
    tree = build_tree(X, y, ["x", "y"], 0, 3, 2, None, rng)

    def max_depth(node, d):
        if node.is_leaf:
            return d
        return max(max_depth(node.left, d + 1), max_depth(node.right, d + 1))

    assert max_depth(tree, 0) <= 3


def test_tree_predict_returns_leaf():
    """Prediction traverses to a leaf."""
    rng = random.Random(0)
    X = [{"x": 1}, {"x": 5}]
    y = ["A", "B"]
    tree = build_tree(X, y, ["x"], 0, 3, 2, None, rng)
    leaf = tree_predict(tree, {"x": 0})
    assert isinstance(leaf, TreeLeaf)


def test_bootstrap_sample_size():
    """Bootstrap sample has same size as input."""
    X = list(range(10))
    y = ["A"] * 10
    rng = random.Random(0)
    Xb, yb = bootstrap_sample(X, y, rng)
    assert len(Xb) == 10
    assert len(yb) == 10


def test_forest_separable_classes():
    """RF should achieve high accuracy on clearly separable data."""
    random.seed(42)
    X, y = [], []
    for _ in range(40):
        X.append({"x": random.gauss(10, 2), "y": random.gauss(10, 2)})
        y.append("A")
    for _ in range(40):
        X.append({"x": random.gauss(90, 2), "y": random.gauss(90, 2)})
        y.append("B")
    forest = fit_forest(X, y, ["x", "y"], n_trees=30, max_depth=5, seed=42)
    preds = predict(forest, X)
    acc = accuracy(preds, y)
    assert acc >= 0.95


def test_forest_returns_class_probabilities_sum_to_one():
    """Probabilities sum to 1."""
    random.seed(0)
    X = [{"x": float(i)} for i in range(20)]
    y = ["A" if i < 10 else "B" for i in range(20)]
    forest = fit_forest(X, y, ["x"], n_trees=20, max_depth=3, seed=0)
    pred = predict_one(forest, {"x": 5})
    assert abs(sum(pred.class_probabilities.values()) - 1.0) < 1e-9


def test_forest_confidence_in_range():
    """Confidence ∈ [0, 1]."""
    random.seed(1)
    X = [{"x": float(i)} for i in range(30)]
    y = [f"c{i % 3}" for i in range(30)]
    forest = fit_forest(X, y, ["x"], n_trees=20, max_depth=4, seed=1)
    for x in X[:5]:
        pred = predict_one(forest, x)
        assert 0 <= pred.confidence <= 1.0


def test_forest_n_trees_correct():
    """Forest contains exactly n_trees."""
    random.seed(0)
    X = [{"x": float(i)} for i in range(10)]
    y = ["A" if i < 5 else "B" for i in range(10)]
    forest = fit_forest(X, y, ["x"], n_trees=15, max_depth=3, seed=0)
    assert len(forest.trees) == 15


def test_forest_deterministic_with_seed():
    """Same seed → same forest."""
    X = [{"x": float(i), "y": float(i * 2)} for i in range(20)]
    y = ["A" if i % 2 == 0 else "B" for i in range(20)]
    f1 = fit_forest(X, y, ["x", "y"], n_trees=10, max_depth=3, seed=42)
    f2 = fit_forest(X, y, ["x", "y"], n_trees=10, max_depth=3, seed=42)
    # Same predictions
    for x in X[:5]:
        p1 = predict_one(f1, x)
        p2 = predict_one(f2, x)
        assert p1.predicted_class == p2.predicted_class
        assert p1.confidence == p2.confidence


def test_feature_importance_higher_for_useful_feature():
    """Feature that's actually predictive should have higher importance than noise."""
    random.seed(13)
    X, y = [], []
    for i in range(60):
        useful = random.gauss(0, 1) + (5 if i % 2 == 0 else 0)
        noise1 = random.gauss(0, 1)
        noise2 = random.gauss(0, 1)
        X.append({"useful": useful, "noise1": noise1, "noise2": noise2})
        y.append("A" if i % 2 == 0 else "B")
    forest = fit_forest(X, y, ["useful", "noise1", "noise2"], n_trees=50,
                          max_depth=4, max_features=3, seed=13)
    imp = feature_importance_simple(forest, X, y)
    assert imp["useful"] > imp["noise1"]
    assert imp["useful"] > imp["noise2"]


def test_accuracy_helper():
    """Accuracy computation correct."""
    from rf import Prediction
    preds = [
        Prediction("A", 0.9, {"A": 0.9, "B": 0.1}),
        Prediction("B", 0.7, {"A": 0.3, "B": 0.7}),
        Prediction("A", 0.6, {"A": 0.6, "B": 0.4}),
    ]
    y = ["A", "B", "B"]
    # 2 of 3 correct
    assert abs(accuracy(preds, y) - 2/3) < 1e-9


def test_tree_leaf_predict_proba():
    """TreeLeaf.predict_proba returns normalized."""
    leaf = TreeLeaf(class_counts={"A": 3, "B": 1, "C": 1})
    probs = leaf.predict_proba()
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert probs["A"] == 0.6


if __name__ == "__main__":
    tests = [
        test_gini_pure,
        test_gini_max_two_class,
        test_gini_three_class_uniform,
        test_class_distribution,
        test_find_best_split_separable,
        test_find_best_split_no_variance,
        test_build_tree_returns_leaf_for_pure_class,
        test_build_tree_respects_max_depth,
        test_tree_predict_returns_leaf,
        test_bootstrap_sample_size,
        test_forest_separable_classes,
        test_forest_returns_class_probabilities_sum_to_one,
        test_forest_confidence_in_range,
        test_forest_n_trees_correct,
        test_forest_deterministic_with_seed,
        test_feature_importance_higher_for_useful_feature,
        test_accuracy_helper,
        test_tree_leaf_predict_proba,
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
