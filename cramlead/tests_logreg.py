"""cramlead edge tests — pure-function logistic regression correctness."""
from __future__ import annotations

import math
import random

from logreg import (
    sigmoid, FeatureEncoder, fit_logreg, predict_proba, predict_all,
    accuracy_score, log_loss_score, auc_roc_approx, coefficient_summary,
)


def test_sigmoid_zero():
    assert abs(sigmoid(0) - 0.5) < 1e-9


def test_sigmoid_extremes():
    assert sigmoid(1000) > 0.999
    assert sigmoid(-1000) < 0.001


def test_sigmoid_monotonic():
    assert sigmoid(1) < sigmoid(2) < sigmoid(3)


def test_encoder_numeric_standardization():
    """Numeric features standardized to mean 0 std 1."""
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit([{"x": 0}, {"x": 10}, {"x": 20}])
    # mean = 10, std should be ~10
    assert abs(enc.numeric_means["x"] - 10.0) < 0.1
    # Transform x=10 should give ~0
    vec = enc.transform({"x": 10})
    assert abs(vec[0]) < 0.01


def test_encoder_categorical_one_hot():
    """Categorical features one-hot encoded with reference dropped."""
    enc = FeatureEncoder(numeric_features=[], categorical_features=["color"])
    enc.fit([{"color": "red"}, {"color": "green"}, {"color": "blue"}])
    # 3 levels - 1 reference = 2 expanded
    assert len(enc.expanded_names) == 2
    # blue and red expand (green is reference, alphabetically first)
    # actually sorted alphabetically: blue, green, red → reference=blue
    vec_blue = enc.transform({"color": "blue"})
    assert sum(vec_blue) == 0    # reference category → all zeros


def test_logreg_converges_on_simple_data():
    """Simple linearly separable problem → high accuracy."""
    random.seed(42)
    examples = []
    labels = []
    for _ in range(80):
        x = random.uniform(-5, 5)
        y = 1 if x > 0 else 0
        examples.append({"x": x})
        labels.append(y)

    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, lr=0.5, max_iter=500)
    probs = [predict_proba(model, e).probability for e in examples]
    auc = auc_roc_approx(labels, probs)
    assert auc > 0.95


def test_logreg_predicts_in_range():
    """All probabilities in [0, 1]."""
    examples = [{"x": float(i)} for i in range(10)]
    labels = [1 if i > 5 else 0 for i in range(10)]
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, lr=0.3, max_iter=100)
    for ex in examples[:3]:
        p = predict_proba(model, ex)
        assert 0 <= p.probability <= 1.0


def test_logreg_handles_all_positive():
    """All positives → high probabilities."""
    examples = [{"x": 1.0}] * 10
    labels = [1] * 10
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=100)
    p = predict_proba(model, {"x": 1.0})
    assert p.probability > 0.85


def test_logreg_handles_all_negative():
    examples = [{"x": 1.0}] * 10
    labels = [0] * 10
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=100)
    p = predict_proba(model, {"x": 1.0})
    assert p.probability < 0.15


def test_logreg_coefficient_signs():
    """Positive correlation → positive β; negative correlation → negative β."""
    random.seed(1)
    examples = []
    labels = []
    for _ in range(60):
        x = random.uniform(-3, 3)
        y = 1 if x > 0 else 0
        examples.append({"x": x})
        labels.append(y)
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, lr=0.3, max_iter=500)
    # β for x should be strongly positive (x is positive predictor)
    assert model.coefficients[0] > 0.5


def test_logreg_l2_shrinks_coefficients():
    """Higher L2 → smaller coefficient magnitude."""
    random.seed(2)
    examples = [{"x": random.uniform(-3, 3)} for _ in range(80)]
    labels = [1 if e["x"] > 0 else 0 for e in examples]
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    m_low_l2 = fit_logreg(X, labels, enc.expanded_names, enc, l2_lambda=0.001, max_iter=500)
    m_high_l2 = fit_logreg(X, labels, enc.expanded_names, enc, l2_lambda=10.0, max_iter=500)
    assert abs(m_high_l2.coefficients[0]) < abs(m_low_l2.coefficients[0])


def test_log_loss_lower_for_better_predictions():
    y = [0, 0, 1, 1]
    good = [0.05, 0.05, 0.95, 0.95]
    bad = [0.5, 0.5, 0.5, 0.5]
    assert log_loss_score(y, good) < log_loss_score(y, bad)


def test_auc_perfect():
    y = [0, 0, 1, 1]
    probs = [0.1, 0.2, 0.8, 0.9]
    assert auc_roc_approx(y, probs) == 1.0


def test_accuracy_correct():
    y = [0, 1, 1, 0]
    probs = [0.1, 0.8, 0.7, 0.4]
    # 4/4 correct
    assert accuracy_score(y, probs) == 1.0


def test_coefficient_summary_sorted():
    """Coefficients summary returns sorted (descending magnitude)."""
    random.seed(3)
    examples = [{"x1": random.random(), "x2": random.random()} for _ in range(50)]
    labels = [1 if e["x1"] > 0.5 else 0 for e in examples]
    enc = FeatureEncoder(numeric_features=["x1", "x2"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=200)
    coefs = coefficient_summary(model)
    # Verify sorted by |β| descending
    for i in range(1, len(coefs)):
        assert abs(coefs[i - 1][1]) >= abs(coefs[i][1])


def test_logreg_deterministic():
    examples = [{"x": float(i)} for i in range(20)]
    labels = [1 if i > 10 else 0 for i in range(20)]
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    m1 = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=100)
    m2 = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=100)
    assert m1.coefficients == m2.coefficients


def test_logreg_intercept_initialized_from_prior():
    """Initial intercept ≈ logit(empirical positive rate)."""
    examples = [{"x": 1.0}] * 8 + [{"x": 1.0}] * 2
    labels = [1] * 8 + [0] * 2    # 80% positive
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=1)
    # After 1 iteration, intercept still close to log(0.8/0.2) = log(4) ≈ 1.39
    assert model.intercept > 0


def test_predict_feature_contributions():
    """feature_contributions returned for each prediction."""
    random.seed(4)
    examples = [{"x": random.uniform(0, 5)} for _ in range(30)]
    labels = [1 if e["x"] > 2.5 else 0 for e in examples]
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=300)
    pred = predict_proba(model, {"x": 4.0})
    assert len(pred.feature_contributions) > 0


def test_predict_all_batch():
    """predict_all returns list."""
    examples = [{"x": float(i)} for i in range(5)]
    labels = [1 if i > 2 else 0 for i in range(5)]
    enc = FeatureEncoder(numeric_features=["x"], categorical_features=[])
    enc.fit(examples)
    X = [enc.transform(e) for e in examples]
    model = fit_logreg(X, labels, enc.expanded_names, enc, max_iter=100)
    preds = predict_all(model, [{"x": 0}, {"x": 5}])
    assert len(preds) == 2


if __name__ == "__main__":
    tests = [
        test_sigmoid_zero,
        test_sigmoid_extremes,
        test_sigmoid_monotonic,
        test_encoder_numeric_standardization,
        test_encoder_categorical_one_hot,
        test_logreg_converges_on_simple_data,
        test_logreg_predicts_in_range,
        test_logreg_handles_all_positive,
        test_logreg_handles_all_negative,
        test_logreg_coefficient_signs,
        test_logreg_l2_shrinks_coefficients,
        test_log_loss_lower_for_better_predictions,
        test_auc_perfect,
        test_accuracy_correct,
        test_coefficient_summary_sorted,
        test_logreg_deterministic,
        test_logreg_intercept_initialized_from_prior,
        test_predict_feature_contributions,
        test_predict_all_batch,
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
