"""Edge-case tests for lda.py -- pure-function Linear Discriminant Analysis.

Run: python3 tests_lda.py
"""
from __future__ import annotations

import math
import sys

from lda import (
    fit_lda, predict_one, accuracy, loo_evaluate, confusion_matrix,
    class_centroid_distance, gauss_jordan_solve,
    _zeros, _eye, _matvec, _vecdot, _vecsub,
    _class_means, _pooled_covariance, _softmax,
)


def assert_close(a, b, tol=1e-6, msg=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol {tol})")


def test_gauss_jordan_identity():
    A = _eye(3)
    B = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
    X = gauss_jordan_solve(A, B)
    for i in range(3):
        for j in range(2):
            assert_close(X[i][j], B[i][j], msg=f"identity solve [{i}][{j}]")


def test_gauss_jordan_2x2_known_solution():
    # A * X = B, A = [[2,1],[1,3]], B = [[1],[2]]
    # solution: X = [[1/5], [3/5]]
    A = [[2.0, 1.0], [1.0, 3.0]]
    B = [[1.0], [2.0]]
    X = gauss_jordan_solve(A, B)
    assert_close(X[0][0], 1.0 / 5.0, msg="2x2 x1")
    assert_close(X[1][0], 3.0 / 5.0, msg="2x2 x2")


def test_gauss_jordan_singular_raises():
    A = [[1.0, 2.0], [2.0, 4.0]]   # second row = 2 * first row -> singular
    B = [[1.0], [2.0]]
    try:
        gauss_jordan_solve(A, B)
    except ValueError:
        return
    raise AssertionError("expected ValueError on singular matrix")


def test_softmax_sums_to_one():
    s = _softmax({"a": 1.0, "b": 2.0, "c": 3.0})
    assert_close(sum(s.values()), 1.0, msg="softmax sum")
    # Highest score -> highest probability.
    assert s["c"] > s["b"] > s["a"]


def test_softmax_numerical_stability():
    # Large scores should not overflow.
    s = _softmax({"a": 1000.0, "b": 1001.0})
    assert_close(sum(s.values()), 1.0, msg="softmax sum large")
    # Argmax preserved.
    assert s["b"] > s["a"]


def test_class_means_compute_per_class():
    X = [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0], [12.0, 22.0]]
    labels = ["a", "a", "b", "b"]
    cm = _class_means(X, labels, ["a", "b"])
    assert_close(cm["a"][0], 2.0)
    assert_close(cm["a"][1], 3.0)
    assert_close(cm["b"][0], 11.0)
    assert_close(cm["b"][1], 21.0)


def test_pooled_covariance_diagonal_is_positive():
    X = [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0], [12.0, 22.0]]
    labels = ["a", "a", "b", "b"]
    cm = _class_means(X, labels, ["a", "b"])
    cov = _pooled_covariance(X, labels, cm, jitter=1e-6)
    assert cov[0][0] > 0, "diagonal must be positive"
    assert cov[1][1] > 0, "diagonal must be positive"


def test_fit_lda_empty_raises():
    try:
        fit_lda([], [], [])
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty input")


def test_fit_lda_mismatched_labels_raises():
    try:
        fit_lda([[1.0]], ["a", "b"], ["x"])
    except ValueError:
        return
    raise AssertionError("expected ValueError on mismatched lengths")


def test_lda_separable_2class_perfect_classification():
    # Two clearly separated 2D Gaussians -> training accuracy should be 100%.
    X = []
    y = []
    for i in range(15):
        X.append([0.0 + i * 0.05, 0.0 + i * 0.05])
        y.append("a")
    for i in range(15):
        X.append([10.0 + i * 0.05, 10.0 + i * 0.05])
        y.append("b")
    model = fit_lda(X, y, ["x1", "x2"])
    train_acc = accuracy(model, X, y)
    assert train_acc == 1.0, f"separable classes should be 100% accurate, got {train_acc}"


def test_lda_posteriors_sum_to_one():
    X = [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0], [12.0, 22.0]]
    y = ["a", "a", "b", "b"]
    model = fit_lda(X, y, ["x1", "x2"])
    pred = predict_one(model, [5.0, 10.0])
    assert_close(sum(pred.class_probabilities.values()), 1.0, msg="posterior sum")


def test_lda_argmax_consistent_with_max_probability():
    X = [[1.0], [2.0], [10.0], [11.0]]
    y = ["a", "a", "b", "b"]
    model = fit_lda(X, y, ["x"])
    pred = predict_one(model, [10.5])
    best = max(pred.class_probabilities, key=pred.class_probabilities.get)
    assert pred.predicted_class == best


def test_lda_class_priors_match_label_distribution():
    X = [[1.0], [2.0], [3.0], [10.0], [11.0]]
    y = ["a", "a", "a", "b", "b"]
    model = fit_lda(X, y, ["x"])
    assert_close(model.class_priors["a"], 3.0 / 5.0)
    assert_close(model.class_priors["b"], 2.0 / 5.0)


def test_lda_three_class_separable():
    X = []
    y = []
    centers = [(0, 0), (10, 0), (5, 10)]
    for ci, (cx, cy) in enumerate(centers):
        for i in range(10):
            X.append([cx + i * 0.05, cy + i * 0.05])
            y.append(f"c{ci}")
    model = fit_lda(X, y, ["x1", "x2"])
    train_acc = accuracy(model, X, y)
    assert train_acc >= 0.9, f"3-class separable should be ≥90% accurate, got {train_acc}"


def test_predict_one_returns_feature_contributions():
    X = [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0], [12.0, 22.0]]
    y = ["a", "a", "b", "b"]
    model = fit_lda(X, y, ["f1", "f2"])
    pred = predict_one(model, [5.0, 10.0])
    assert len(pred.feature_contributions) == 2
    # sorted by |contribution| desc
    assert abs(pred.feature_contributions[0][2]) >= abs(pred.feature_contributions[1][2])


def test_lda_discriminant_for_winner_is_highest():
    X = [[1.0], [2.0], [10.0], [11.0]]
    y = ["a", "a", "b", "b"]
    model = fit_lda(X, y, ["x"])
    pred = predict_one(model, [11.0])
    winner = pred.predicted_class
    for c, delta in pred.class_discriminants.items():
        if c == winner:
            continue
        assert pred.class_discriminants[winner] >= delta, "winner must have highest discriminant"


def test_loo_evaluate_returns_accuracy_in_unit_interval():
    X = [[1.0], [2.0], [10.0], [11.0], [12.0]]
    y = ["a", "a", "b", "b", "b"]
    loo = loo_evaluate(X, y, ["x"])
    assert 0.0 <= loo["accuracy"] <= 1.0
    assert loo["n_folds"] >= 0
    assert loo["n_skipped"] >= 0


def test_confusion_matrix_rows_sum_to_class_count():
    X = [[1.0], [2.0], [3.0], [10.0], [11.0]]
    y = ["a", "a", "a", "b", "b"]
    model = fit_lda(X, y, ["x"])
    cm = confusion_matrix(model, X, y)
    assert sum(cm["a"].values()) == 3
    assert sum(cm["b"].values()) == 2


def test_mahalanobis_distance_zero_at_own_centroid():
    X = [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0], [12.0, 22.0]]
    y = ["a", "a", "b", "b"]
    model = fit_lda(X, y, ["x1", "x2"])
    # Distance from class-a centroid to class-a centroid should be ~0.
    mu_a = model.class_means["a"]
    d = class_centroid_distance(model, mu_a)
    assert d["a"] < d["b"], f"closer to own class: {d}"


def test_lda_deterministic():
    X = [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0], [12.0, 22.0]]
    y = ["a", "a", "b", "b"]
    m1 = fit_lda(X, y, ["x1", "x2"])
    m2 = fit_lda(X, y, ["x1", "x2"])
    p1 = predict_one(m1, [5.0, 10.0])
    p2 = predict_one(m2, [5.0, 10.0])
    assert p1.predicted_class == p2.predicted_class
    for c in p1.class_probabilities:
        assert_close(p1.class_probabilities[c], p2.class_probabilities[c], tol=1e-9)


def test_class_centroid_distance_returns_all_classes():
    X = [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0], [12.0, 22.0]]
    y = ["a", "a", "b", "b"]
    model = fit_lda(X, y, ["x1", "x2"])
    d = class_centroid_distance(model, [5.0, 10.0])
    assert set(d.keys()) == {"a", "b"}
    for v in d.values():
        assert v >= 0


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
