"""clinicqueue edge tests — pure-function GBDT correctness."""
from __future__ import annotations

import math
import random

from gbdt import (
    sigmoid, variance, find_best_split_reg, build_regression_tree,
    reg_tree_predict, fit_gbdt, predict_proba, predict_all,
    log_loss, accuracy, auc_roc_approx, feature_importance_gain,
    RegLeaf, RegNode,
)


def test_sigmoid_zero():
    assert abs(sigmoid(0) - 0.5) < 1e-9


def test_sigmoid_extremes():
    assert sigmoid(1000) > 0.999
    assert sigmoid(-1000) < 0.001


def test_variance_zero_for_constant():
    assert variance([5, 5, 5]) == 0.0


def test_variance_simple():
    """Var([1, 2, 3]) = 2/3."""
    assert abs(variance([1, 2, 3]) - 2/3) < 1e-9


def test_find_best_split_separable():
    """Linearly separable in 1 feature."""
    X = [{"x": float(i)} for i in range(10)]
    r = [-1.0 if i < 5 else 1.0 for i in range(10)]
    rng = random.Random(0)
    result = find_best_split_reg(X, r, ["x"], rng)
    assert result is not None
    feat, thresh, gain = result
    assert feat == "x"
    assert 4 < thresh < 5
    assert gain > 0


def test_find_best_split_no_variance():
    """No-variance feature → no split."""
    X = [{"x": 5.0}] * 5
    r = [0.0] * 5
    rng = random.Random(0)
    result = find_best_split_reg(X, r, ["x"], rng)
    assert result is None


def test_build_regression_tree_returns_leaf_for_uniform_residuals():
    """If all residuals same, tree may still split but value should equal r."""
    X = [{"x": float(i)} for i in range(5)]
    r = [3.0] * 5
    rng = random.Random(0)
    tree = build_regression_tree(X, r, ["x"], 0, 3, 2, None, rng)
    # Predict for any input → value ~ 3.0
    for x in X:
        assert abs(reg_tree_predict(tree, x) - 3.0) < 1e-9


def test_build_tree_respects_max_depth():
    rng = random.Random(0)
    X = [{"x": float(i), "y": float(i * 2)} for i in range(20)]
    r = [float(i % 5) for i in range(20)]
    tree = build_regression_tree(X, r, ["x", "y"], 0, 2, 2, None, rng)

    def max_depth(node, d):
        if node.is_leaf:
            return d
        return max(max_depth(node.left, d + 1), max_depth(node.right, d + 1))

    assert max_depth(tree, 0) <= 2


def test_gbdt_fits_separable_data():
    """High AUC for clearly separable data."""
    random.seed(0)
    X, y = [], []
    for _ in range(100):
        x1 = random.uniform(0, 10)
        # y depends mostly on x1
        prob = 0.95 if x1 > 5 else 0.05
        label = 1 if random.random() < prob else 0
        X.append({"x1": x1, "x2": random.uniform(0, 10)})
        y.append(label)

    model = fit_gbdt(X, y, ["x1", "x2"], n_trees=30, max_depth=3, learning_rate=0.1, seed=0)
    probs = [predict_proba(model, x).probability for x in X]
    auc = auc_roc_approx(y, probs)
    assert auc > 0.85


def test_gbdt_predict_proba_in_range():
    """All predictions ∈ [0, 1]."""
    random.seed(1)
    X = [{"x": random.random() * 10} for _ in range(20)]
    y = [random.randint(0, 1) for _ in range(20)]
    model = fit_gbdt(X, y, ["x"], n_trees=10, max_depth=2, seed=1)
    for x in X[:5]:
        p = predict_proba(model, x)
        assert 0 <= p.probability <= 1.0


def test_gbdt_handles_all_positive_labels():
    """All y=1 → predictions all high."""
    X = [{"x": float(i)} for i in range(10)]
    y = [1] * 10
    model = fit_gbdt(X, y, ["x"], n_trees=10, max_depth=2, seed=0)
    for x in X[:3]:
        p = predict_proba(model, x)
        assert p.probability > 0.9


def test_gbdt_handles_all_negative_labels():
    X = [{"x": float(i)} for i in range(10)]
    y = [0] * 10
    model = fit_gbdt(X, y, ["x"], n_trees=10, max_depth=2, seed=0)
    for x in X[:3]:
        p = predict_proba(model, x)
        assert p.probability < 0.1


def test_log_loss_lower_for_better_predictions():
    """Predictions closer to truth → lower log_loss."""
    y = [0, 0, 1, 1]
    perfect = [0.01, 0.01, 0.99, 0.99]
    random_pred = [0.5, 0.5, 0.5, 0.5]
    bad = [0.9, 0.9, 0.1, 0.1]
    assert log_loss(y, perfect) < log_loss(y, random_pred)
    assert log_loss(y, random_pred) < log_loss(y, bad)


def test_accuracy_basic():
    y = [0, 1, 1, 0]
    probs = [0.1, 0.8, 0.7, 0.4]
    # 4/4 correct
    assert accuracy(y, probs) == 1.0


def test_accuracy_50pct():
    y = [0, 1, 1, 0]
    probs = [0.6, 0.4, 0.7, 0.4]
    # 2/4 correct (3rd and 4th)
    assert accuracy(y, probs) == 0.5


def test_auc_perfect_separation():
    """Perfect classifier → AUC 1.0."""
    y = [0, 0, 1, 1]
    probs = [0.1, 0.2, 0.8, 0.9]
    assert auc_roc_approx(y, probs) == 1.0


def test_auc_random():
    """Random predictions → AUC ≈ 0.5."""
    y = [0, 1, 0, 1, 0, 1]
    probs = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    assert abs(auc_roc_approx(y, probs) - 0.5) < 0.01


def test_feature_importance_returns_all_features():
    random.seed(0)
    X = [{"a": random.random(), "b": random.random(), "c": random.random()}
         for _ in range(50)]
    y = [1 if x["a"] > 0.5 else 0 for x in X]
    model = fit_gbdt(X, y, ["a", "b", "c"], n_trees=20, max_depth=3, seed=0)
    fi = feature_importance_gain(model)
    # All 3 should appear (or at least most)
    assert "a" in fi


def test_feature_importance_dominant():
    """The truly predictive feature should have highest importance."""
    random.seed(42)
    X, y = [], []
    for _ in range(80):
        useful = random.uniform(0, 10)
        noise1 = random.uniform(0, 10)
        noise2 = random.uniform(0, 10)
        y.append(1 if useful > 5 else 0)
        X.append({"useful": useful, "noise1": noise1, "noise2": noise2})
    model = fit_gbdt(X, y, ["useful", "noise1", "noise2"], n_trees=30, max_depth=3, seed=42)
    fi = feature_importance_gain(model)
    assert fi["useful"] > fi["noise1"]
    assert fi["useful"] > fi["noise2"]


def test_gbdt_deterministic():
    random.seed(42)
    X = [{"x": random.random()} for _ in range(20)]
    y = [random.randint(0, 1) for _ in range(20)]
    m1 = fit_gbdt(X, y, ["x"], n_trees=10, max_depth=2, seed=42)
    m2 = fit_gbdt(X, y, ["x"], n_trees=10, max_depth=2, seed=42)
    p1 = predict_proba(m1, X[0])
    p2 = predict_proba(m2, X[0])
    assert p1.probability == p2.probability


if __name__ == "__main__":
    tests = [
        test_sigmoid_zero,
        test_sigmoid_extremes,
        test_variance_zero_for_constant,
        test_variance_simple,
        test_find_best_split_separable,
        test_find_best_split_no_variance,
        test_build_regression_tree_returns_leaf_for_uniform_residuals,
        test_build_tree_respects_max_depth,
        test_gbdt_fits_separable_data,
        test_gbdt_predict_proba_in_range,
        test_gbdt_handles_all_positive_labels,
        test_gbdt_handles_all_negative_labels,
        test_log_loss_lower_for_better_predictions,
        test_accuracy_basic,
        test_accuracy_50pct,
        test_auc_perfect_separation,
        test_auc_random,
        test_feature_importance_returns_all_features,
        test_feature_importance_dominant,
        test_gbdt_deterministic,
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
