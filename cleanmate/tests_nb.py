"""cleanmate edge tests — pure-function Naive Bayes correctness."""
from __future__ import annotations

import math

from naive_bayes import (
    TrainingExample, fit_naive_bayes, predict_one, predict_all,
    accuracy, loo_evaluate, confusion_matrix,
    class_distinctive_features,
)


def test_nb_empty_examples():
    """Empty training set → no classes."""
    model = fit_naive_bayes([], ["f"])
    assert model.classes == []


def test_nb_single_class():
    """All same label → predicts that label."""
    examples = [
        TrainingExample({"a": "x"}, "A"),
        TrainingExample({"a": "y"}, "A"),
    ]
    model = fit_naive_bayes(examples, ["a"])
    pred = predict_one(model, {"a": "x"})
    assert pred.predicted_class == "A"
    assert pred.class_probabilities["A"] == 1.0


def test_nb_two_class_separable():
    """Cleanly separable classes."""
    examples = [
        TrainingExample({"f": "x"}, "A"),
        TrainingExample({"f": "x"}, "A"),
        TrainingExample({"f": "x"}, "A"),
        TrainingExample({"f": "y"}, "B"),
        TrainingExample({"f": "y"}, "B"),
        TrainingExample({"f": "y"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["f"])
    assert predict_one(model, {"f": "x"}).predicted_class == "A"
    assert predict_one(model, {"f": "y"}).predicted_class == "B"


def test_nb_probabilities_sum_to_one():
    """Class probabilities normalize to 1."""
    examples = [
        TrainingExample({"a": "x", "b": "p"}, "A"),
        TrainingExample({"a": "y", "b": "q"}, "B"),
        TrainingExample({"a": "x", "b": "q"}, "A"),
    ]
    model = fit_naive_bayes(examples, ["a", "b"])
    pred = predict_one(model, {"a": "x", "b": "p"})
    assert abs(sum(pred.class_probabilities.values()) - 1.0) < 1e-6


def test_nb_laplace_smoothing_handles_unseen():
    """Unseen feature value gets nonzero probability via smoothing."""
    examples = [
        TrainingExample({"f": "x"}, "A"),
        TrainingExample({"f": "y"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["f"])
    # Query with unseen value "z"
    pred = predict_one(model, {"f": "z"})
    # Should still produce valid probabilities (not crash)
    assert sum(pred.class_probabilities.values()) > 0


def test_nb_class_priors():
    """Imbalanced data → priors reflect class frequencies."""
    examples = (
        [TrainingExample({"a": "x"}, "A") for _ in range(8)]
        + [TrainingExample({"a": "y"}, "B") for _ in range(2)]
    )
    model = fit_naive_bayes(examples, ["a"])
    # log P(A) > log P(B)
    assert model.class_log_priors["A"] > model.class_log_priors["B"]
    # Ratio ≈ 8/10 vs 2/10
    assert abs(math.exp(model.class_log_priors["A"]) - 0.8) < 0.01
    assert abs(math.exp(model.class_log_priors["B"]) - 0.2) < 0.01


def test_nb_accuracy_perfect_on_training():
    """Cleanly separated classes → 100% accuracy on training."""
    examples = [
        TrainingExample({"f": "A_only"}, "A"),
        TrainingExample({"f": "A_only"}, "A"),
        TrainingExample({"f": "B_only"}, "B"),
        TrainingExample({"f": "B_only"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["f"])
    acc = accuracy(model, examples)
    assert acc == 1.0


def test_nb_loo_evaluation_runs():
    """LOO returns accuracy in [0, 1]."""
    examples = [
        TrainingExample({"a": "x"}, "A"),
        TrainingExample({"a": "x"}, "A"),
        TrainingExample({"a": "y"}, "B"),
        TrainingExample({"a": "y"}, "B"),
    ]
    metrics = loo_evaluate(examples, ["a"])
    assert 0 <= metrics["accuracy"] <= 1.0
    assert metrics["n_folds"] == 4


def test_nb_confusion_matrix():
    """Confusion matrix tracks (true, pred) counts."""
    examples = [
        TrainingExample({"f": "x"}, "A"),
        TrainingExample({"f": "y"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["f"])
    cm = confusion_matrix(model, examples)
    # Both correct
    assert cm.get(("A", "A"), 0) == 1
    assert cm.get(("B", "B"), 0) == 1


def test_nb_distinctive_features():
    """Distinctive features for class = features with high P(f|c) relative to others."""
    examples = [
        TrainingExample({"f": "rare_A"}, "A"),
        TrainingExample({"f": "rare_A"}, "A"),
        TrainingExample({"f": "common"}, "A"),
        TrainingExample({"f": "common"}, "B"),
        TrainingExample({"f": "common"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["f"])
    feats = class_distinctive_features(model, "A", top_n=2)
    # "rare_A" should be the top distinctive feature for A
    top_feat = feats[0]
    assert top_feat[1] == "rare_A"


def test_nb_deterministic():
    """Same examples → same model."""
    examples = [TrainingExample({"a": "x"}, "A"), TrainingExample({"a": "y"}, "B")]
    m1 = fit_naive_bayes(examples, ["a"])
    m2 = fit_naive_bayes(examples, ["a"])
    p1 = predict_one(m1, {"a": "x"})
    p2 = predict_one(m2, {"a": "x"})
    assert p1.class_probabilities == p2.class_probabilities


def test_nb_log_probabilities_consistent():
    """log_probabilities arg-max consistent with probabilities arg-max."""
    examples = [
        TrainingExample({"a": "x", "b": "p"}, "A"),
        TrainingExample({"a": "y", "b": "q"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["a", "b"])
    pred = predict_one(model, {"a": "x", "b": "p"})
    log_argmax = max(pred.class_log_probabilities.items(), key=lambda kv: kv[1])[0]
    prob_argmax = max(pred.class_probabilities.items(), key=lambda kv: kv[1])[0]
    assert log_argmax == prob_argmax


def test_nb_contributing_features_returned():
    """Top contributing features list non-empty."""
    examples = [
        TrainingExample({"a": "x", "b": "p"}, "A"),
        TrainingExample({"a": "y", "b": "q"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["a", "b"])
    pred = predict_one(model, {"a": "x", "b": "p"})
    assert len(pred.top_contributing_features) > 0


def test_nb_missing_feature_in_query():
    """Missing features in query still produces prediction."""
    examples = [
        TrainingExample({"a": "x", "b": "p"}, "A"),
        TrainingExample({"a": "y", "b": "q"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["a", "b"])
    pred = predict_one(model, {"a": "x"})    # b is missing
    assert pred.predicted_class in ["A", "B"]


def test_nb_three_class():
    """3-class problem with clear partition."""
    examples = [
        TrainingExample({"f": "p"}, "A"),
        TrainingExample({"f": "p"}, "A"),
        TrainingExample({"f": "q"}, "B"),
        TrainingExample({"f": "q"}, "B"),
        TrainingExample({"f": "r"}, "C"),
        TrainingExample({"f": "r"}, "C"),
    ]
    model = fit_naive_bayes(examples, ["f"])
    assert predict_one(model, {"f": "p"}).predicted_class == "A"
    assert predict_one(model, {"f": "q"}).predicted_class == "B"
    assert predict_one(model, {"f": "r"}).predicted_class == "C"


def test_nb_predict_all_batch():
    """predict_all returns list of predictions."""
    examples = [
        TrainingExample({"f": "x"}, "A"),
        TrainingExample({"f": "y"}, "B"),
    ]
    model = fit_naive_bayes(examples, ["f"])
    preds = predict_all(model, [{"f": "x"}, {"f": "y"}, {"f": "x"}])
    assert len(preds) == 3
    assert preds[0].predicted_class == "A"


if __name__ == "__main__":
    tests = [
        test_nb_empty_examples,
        test_nb_single_class,
        test_nb_two_class_separable,
        test_nb_probabilities_sum_to_one,
        test_nb_laplace_smoothing_handles_unseen,
        test_nb_class_priors,
        test_nb_accuracy_perfect_on_training,
        test_nb_loo_evaluation_runs,
        test_nb_confusion_matrix,
        test_nb_distinctive_features,
        test_nb_deterministic,
        test_nb_log_probabilities_consistent,
        test_nb_contributing_features_returned,
        test_nb_missing_feature_in_query,
        test_nb_three_class,
        test_nb_predict_all_batch,
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
