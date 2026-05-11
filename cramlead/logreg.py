"""cramlead — Logistic Regression with L2 regularization (pure stdlib).

Binary classification via maximum-likelihood logistic regression:
  P(y=1 | x) = sigmoid(x·β + b)
  Loss = -Σ [y log p + (1-y) log(1-p)] + (λ/2) ||β||²
  Gradient: ∂L/∂β_j = Σ (p_i - y_i) × x_ij + λ β_j

Pure stdlib (math + dataclass + collections). Manual matrix ops.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field


# ============== Basic numeric ==============
def sigmoid(z: float) -> float:
    """Numerically stable sigmoid."""
    if z < -500:
        return 0.0
    if z > 500:
        return 1.0
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


# ============== Feature engineering ==============
@dataclass
class FeatureEncoder:
    """One-hot encode categorical features + standardize numeric features."""
    numeric_features: list[str]
    categorical_features: list[str]
    numeric_means: dict[str, float] = field(default_factory=dict)
    numeric_stds: dict[str, float] = field(default_factory=dict)
    categorical_levels: dict[str, list[str]] = field(default_factory=dict)
    expanded_names: list[str] = field(default_factory=list)

    def fit(self, examples: list[dict]) -> "FeatureEncoder":
        for f in self.numeric_features:
            values = [float(ex[f]) for ex in examples if f in ex]
            if values:
                self.numeric_means[f] = statistics.mean(values)
                self.numeric_stds[f] = (
                    statistics.stdev(values) if len(values) > 1 else 1.0
                ) or 1.0

        for f in self.categorical_features:
            levels = sorted(set(str(ex[f]) for ex in examples if f in ex))
            # Drop first level (reference category) for identifiability
            self.categorical_levels[f] = levels

        # Build expanded feature names
        names = list(self.numeric_features)
        for f in self.categorical_features:
            for lvl in self.categorical_levels[f][1:]:    # skip reference (first)
                names.append(f"{f}={lvl}")
        self.expanded_names = names
        return self

    def transform(self, example: dict) -> list[float]:
        """Convert one example to feature vector (already standardized)."""
        vec = []
        for f in self.numeric_features:
            val = float(example.get(f, self.numeric_means.get(f, 0.0)))
            std = self.numeric_stds.get(f, 1.0)
            vec.append((val - self.numeric_means.get(f, 0.0)) / std)
        for f in self.categorical_features:
            levels = self.categorical_levels.get(f, [])
            val = str(example.get(f, ""))
            for lvl in levels[1:]:    # skip reference
                vec.append(1.0 if val == lvl else 0.0)
        return vec


# ============== Logistic regression ==============
@dataclass
class LogRegModel:
    coefficients: list[float]      # β
    intercept: float                # b
    feature_names: list[str]
    encoder: FeatureEncoder
    n_iterations_used: int
    final_loss: float
    learning_rate: float
    l2_lambda: float
    converged: bool


def _matvec(X: list[list[float]], beta: list[float]) -> list[float]:
    """X · β: each row of X dot product with β."""
    return [sum(xi * bj for xi, bj in zip(row, beta)) for row in X]


def fit_logreg(X: list[list[float]], y: list[int],
                feature_names: list[str], encoder: FeatureEncoder,
                lr: float = 0.1, l2_lambda: float = 0.01,
                max_iter: int = 1000, tol: float = 1e-6) -> LogRegModel:
    """Train logistic regression via gradient descent."""
    n = len(X)
    if n == 0:
        return LogRegModel(
            coefficients=[], intercept=0.0, feature_names=feature_names,
            encoder=encoder, n_iterations_used=0, final_loss=0.0,
            learning_rate=lr, l2_lambda=l2_lambda, converged=True,
        )
    p = len(X[0])
    beta = [0.0] * p
    b = math.log((sum(y) + 1) / (n - sum(y) + 1))    # logit of empirical prior
    prev_loss = float("inf")
    iter_used = 0
    converged = False

    for it in range(max_iter):
        iter_used = it + 1
        # Compute logits + predictions
        logits = [b + sum(xi * bj for xi, bj in zip(row, beta)) for row in X]
        preds = [sigmoid(z) for z in logits]

        # Compute gradient
        grad_beta = [0.0] * p
        grad_b = 0.0
        for i in range(n):
            err = preds[i] - y[i]
            grad_b += err
            for j in range(p):
                grad_beta[j] += err * X[i][j]
        # Apply L2 regularization (but not on intercept)
        for j in range(p):
            grad_beta[j] = grad_beta[j] / n + l2_lambda * beta[j]
        grad_b /= n

        # Update
        for j in range(p):
            beta[j] -= lr * grad_beta[j]
        b -= lr * grad_b

        # Compute loss
        eps = 1e-15
        loss = 0.0
        for i in range(n):
            pp = max(eps, min(1 - eps, preds[i]))
            loss += -(y[i] * math.log(pp) + (1 - y[i]) * math.log(1 - pp))
        loss /= n
        loss += 0.5 * l2_lambda * sum(bj ** 2 for bj in beta)

        if abs(prev_loss - loss) < tol:
            converged = True
            break
        prev_loss = loss

    return LogRegModel(
        coefficients=[round(bj, 6) for bj in beta],
        intercept=round(b, 6),
        feature_names=feature_names,
        encoder=encoder,
        n_iterations_used=iter_used,
        final_loss=round(prev_loss, 6),
        learning_rate=lr,
        l2_lambda=l2_lambda,
        converged=converged,
    )


# ============== Prediction ==============
@dataclass
class LogRegPrediction:
    probability: float
    logit: float
    feature_contributions: list[tuple[str, float, float]]    # (name, value, β × value)


def predict_proba(model: LogRegModel, raw_example: dict) -> LogRegPrediction:
    """Predict P(y=1 | x) for one raw example dict."""
    x_vec = model.encoder.transform(raw_example)
    logit = model.intercept + sum(xi * bj for xi, bj in zip(x_vec, model.coefficients))
    p = sigmoid(logit)
    contribs = [
        (name, round(val, 3), round(val * bj, 4))
        for name, val, bj in zip(model.feature_names, x_vec, model.coefficients)
    ]
    contribs.sort(key=lambda t: -abs(t[2]))
    return LogRegPrediction(
        probability=round(p, 4),
        logit=round(logit, 4),
        feature_contributions=contribs,
    )


def predict_all(model: LogRegModel, raw_examples: list[dict]) -> list[LogRegPrediction]:
    return [predict_proba(model, ex) for ex in raw_examples]


# ============== Coefficient interpretation ==============
def coefficient_summary(model: LogRegModel) -> list[tuple[str, float, float, str]]:
    """Returns sorted (name, β, odds_ratio, direction) tuples."""
    out = []
    for name, bj in zip(model.feature_names, model.coefficients):
        odds_ratio = math.exp(bj)
        direction = "正向 (預測報名)" if bj > 0.01 else ("負向 (預測流失)" if bj < -0.01 else "中性")
        out.append((name, round(bj, 4), round(odds_ratio, 3), direction))
    out.sort(key=lambda t: -abs(t[1]))
    return out


# ============== Evaluation ==============
def accuracy_score(y_true: list[int], probs: list[float], threshold: float = 0.5) -> float:
    if not y_true:
        return 0.0
    correct = sum(1 for y, p in zip(y_true, probs)
                   if (p >= threshold and y == 1) or (p < threshold and y == 0))
    return correct / len(y_true)


def log_loss_score(y_true: list[int], probs: list[float], eps: float = 1e-15) -> float:
    if not y_true:
        return 0.0
    total = 0.0
    for y, p in zip(y_true, probs):
        p = max(eps, min(1 - eps, p))
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(y_true)


def auc_roc_approx(y_true: list[int], probs: list[float]) -> float:
    pos = [p for y, p in zip(y_true, probs) if y == 1]
    neg = [p for y, p in zip(y_true, probs) if y == 0]
    if not pos or not neg:
        return 0.5
    count = 0
    for p in pos:
        for n in neg:
            if p > n:
                count += 1
            elif p == n:
                count += 0.5
    return count / (len(pos) * len(neg))
