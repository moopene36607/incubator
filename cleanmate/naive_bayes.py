"""cleanmate — Multinomial Naive Bayes for customer-specialty matching (pure stdlib).

Naive Bayes assumes feature independence given the class:
  P(c | x_1, ..., x_n) ∝ P(c) × Π P(x_i | c)

Trained from historical (features, label) pairs with Laplace (additive) smoothing
to handle unseen feature combinations:
  P(x_i = v | c) = (count(x_i=v, c) + α) / (count(c) + α × |unique_values_i|)

Pure stdlib (math + collections + dataclass). No numpy / no scikit-learn.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field


# ============== Domain types ==============
@dataclass
class TrainingExample:
    """One historical (features, label) pair."""
    features: dict[str, str]    # feature_name → categorical value
    label: str                  # the class to predict


@dataclass
class NaiveBayesModel:
    """Trained Naive Bayes."""
    classes: list[str]
    class_log_priors: dict[str, float]                                   # log P(c)
    feature_log_likelihoods: dict[str, dict[str, dict[str, float]]]      # feature → value → class → log P
    feature_value_universe: dict[str, set[str]]                          # feature → all observed values
    feature_names: list[str]
    n_training: int
    smoothing_alpha: float


@dataclass
class PredictionResult:
    predicted_class: str
    class_probabilities: dict[str, float]    # normalized P(c | x)
    class_log_probabilities: dict[str, float]
    top_contributing_features: list[tuple[str, str, float]]     # (feature, value, log-likelihood-boost)


# ============== Training ==============
def fit_naive_bayes(examples: list[TrainingExample],
                     feature_names: list[str],
                     smoothing_alpha: float = 1.0) -> NaiveBayesModel:
    """Train Multinomial Naive Bayes with Laplace smoothing."""
    n = len(examples)
    if n == 0:
        return NaiveBayesModel(
            classes=[], class_log_priors={}, feature_log_likelihoods={},
            feature_value_universe={}, feature_names=feature_names,
            n_training=0, smoothing_alpha=smoothing_alpha,
        )

    # Class priors
    class_counts = Counter(ex.label for ex in examples)
    classes = sorted(class_counts.keys())
    class_log_priors = {c: math.log(class_counts[c] / n) for c in classes}

    # Feature value universe (observed values)
    feature_value_universe: dict[str, set[str]] = {f: set() for f in feature_names}
    for ex in examples:
        for f in feature_names:
            if f in ex.features:
                feature_value_universe[f].add(str(ex.features[f]))

    # Conditional log likelihoods
    # feature_log_likelihoods[feature][value][class] = log P(feature=value | class)
    feature_log_likelihoods: dict[str, dict[str, dict[str, float]]] = {}

    for f in feature_names:
        feature_log_likelihoods[f] = {}
        n_values = max(1, len(feature_value_universe[f]))    # at least 1 to avoid /0
        # Count(feature=value, class)
        joint_counts: dict[tuple[str, str], int] = Counter()
        for ex in examples:
            v = ex.features.get(f)
            if v is not None:
                joint_counts[(str(v), ex.label)] += 1

        for v in feature_value_universe[f]:
            feature_log_likelihoods[f][v] = {}
            for c in classes:
                count_fv_c = joint_counts.get((v, c), 0)
                count_c = class_counts[c]
                # Laplace smoothing
                prob = (count_fv_c + smoothing_alpha) / (count_c + smoothing_alpha * n_values)
                feature_log_likelihoods[f][v][c] = math.log(prob)

    return NaiveBayesModel(
        classes=classes,
        class_log_priors=class_log_priors,
        feature_log_likelihoods=feature_log_likelihoods,
        feature_value_universe={f: set(s) for f, s in feature_value_universe.items()},
        feature_names=feature_names,
        n_training=n,
        smoothing_alpha=smoothing_alpha,
    )


# ============== Prediction ==============
def predict_one(model: NaiveBayesModel, features: dict[str, str]) -> PredictionResult:
    """Predict class probabilities for a single feature vector."""
    if not model.classes:
        return PredictionResult(
            predicted_class="unknown", class_probabilities={},
            class_log_probabilities={}, top_contributing_features=[],
        )

    log_posteriors = {}
    feature_contribs_by_class: dict[str, list[tuple[str, str, float]]] = {c: [] for c in model.classes}

    for c in model.classes:
        log_p = model.class_log_priors[c]
        for f in model.feature_names:
            v = str(features.get(f, ""))
            if not v:
                continue
            if f in model.feature_log_likelihoods:
                # Use observed value's log-likelihood; for unseen value, fall back to
                # smoothed estimate using universe size + alpha
                if v in model.feature_log_likelihoods[f]:
                    ll = model.feature_log_likelihoods[f][v][c]
                else:
                    # Unseen value: P = α / (count_c + α × |values|)
                    # Compute approximately using model's smoothing alpha
                    n_values = max(1, len(model.feature_value_universe.get(f, set())))
                    n_c = math.exp(model.class_log_priors[c]) * model.n_training
                    ll = math.log(model.smoothing_alpha / (n_c + model.smoothing_alpha * n_values))
                log_p += ll
                feature_contribs_by_class[c].append((f, v, ll))
        log_posteriors[c] = log_p

    # Numerical stability: subtract max log_posterior before exponentiating
    max_log = max(log_posteriors.values())
    exps = {c: math.exp(lp - max_log) for c, lp in log_posteriors.items()}
    total = sum(exps.values())
    class_probabilities = {c: round(v / total, 4) for c, v in exps.items()}

    predicted_class = max(class_probabilities.items(), key=lambda kv: kv[1])[0]
    # Top features pushing the predicted class
    top_feats = sorted(feature_contribs_by_class[predicted_class], key=lambda t: t[2], reverse=True)[:5]

    return PredictionResult(
        predicted_class=predicted_class,
        class_probabilities=class_probabilities,
        class_log_probabilities={c: round(lp, 4) for c, lp in log_posteriors.items()},
        top_contributing_features=[(f, v, round(ll, 3)) for f, v, ll in top_feats],
    )


def predict_all(model: NaiveBayesModel, X: list[dict[str, str]]) -> list[PredictionResult]:
    return [predict_one(model, x) for x in X]


# ============== Evaluation ==============
def accuracy(model: NaiveBayesModel, examples: list[TrainingExample]) -> float:
    if not examples:
        return 0.0
    correct = 0
    for ex in examples:
        pred = predict_one(model, ex.features)
        if pred.predicted_class == ex.label:
            correct += 1
    return correct / len(examples)


def loo_evaluate(examples: list[TrainingExample],
                  feature_names: list[str], smoothing_alpha: float = 1.0) -> dict:
    """Leave-one-out cross-validation."""
    if len(examples) < 2:
        return {"accuracy": 0.0, "n_folds": 0}
    correct = 0
    for i in range(len(examples)):
        train = examples[:i] + examples[i + 1:]
        test = examples[i]
        model = fit_naive_bayes(train, feature_names, smoothing_alpha)
        pred = predict_one(model, test.features)
        if pred.predicted_class == test.label:
            correct += 1
    return {
        "accuracy": round(correct / len(examples), 4),
        "n_folds": len(examples),
    }


def confusion_matrix(model: NaiveBayesModel,
                       examples: list[TrainingExample]) -> dict[tuple[str, str], int]:
    """Confusion matrix: (true_label, predicted_label) → count."""
    cm: Counter = Counter()
    for ex in examples:
        pred = predict_one(model, ex.features)
        cm[(ex.label, pred.predicted_class)] += 1
    return dict(cm)


# ============== Feature importance ==============
def feature_value_class_strength(model: NaiveBayesModel) -> dict[str, dict[str, dict[str, float]]]:
    """For each (feature, value, class) → log-likelihood. Useful for explanation."""
    return model.feature_log_likelihoods


def class_distinctive_features(model: NaiveBayesModel, target_class: str,
                                  top_n: int = 5) -> list[tuple[str, str, float]]:
    """Find feature-value pairs most distinctive for the target class
    (max log P(v | target) - mean log P(v | other classes))."""
    if target_class not in model.classes:
        return []
    distinctive = []
    for f in model.feature_names:
        if f not in model.feature_log_likelihoods:
            continue
        for v in model.feature_value_universe.get(f, set()):
            target_ll = model.feature_log_likelihoods[f][v].get(target_class, 0)
            other_lls = [
                model.feature_log_likelihoods[f][v][c]
                for c in model.classes if c != target_class
            ]
            if other_lls:
                avg_other = sum(other_lls) / len(other_lls)
                distinctiveness = target_ll - avg_other
                distinctive.append((f, v, distinctiveness))

    distinctive.sort(key=lambda t: -t[2])
    return [(f, v, round(d, 3)) for f, v, d in distinctive[:top_n]]
