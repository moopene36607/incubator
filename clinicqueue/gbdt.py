"""clinicqueue — Gradient Boosting Decision Trees for tabular binary classification.

Friedman (2001) gradient boosting: sequentially fit weak learners (regression
trees) to the negative gradient of the loss with respect to F(x):

  For binary classification with logistic loss:
    F_0(x) = log(p / (1-p)) where p = mean(y)
    For m in 1..M:
      r_i = y_i - sigmoid(F_{m-1}(x_i))   # negative gradient
      h_m = fit_regression_tree(X, r)
      F_m(x) = F_{m-1}(x) + learning_rate × h_m(x)
    Predict: sigmoid(F_M(x))

Regression tree (CART): at each node, find (feature, threshold) minimizing
weighted MSE; recurse until max_depth or min_samples.

Pure stdlib (math + random + dataclass). No numpy / no scikit-learn.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field


def sigmoid(x: float) -> float:
    # Clipped to avoid overflow
    if x < -500:
        return 0.0
    if x > 500:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


# ============== Regression tree (CART) ==============
@dataclass
class RegLeaf:
    value: float                # mean of residuals in this leaf
    n_samples: int
    is_leaf: bool = True


@dataclass
class RegNode:
    split_feature: str
    threshold: float
    left: "RegNode | RegLeaf"
    right: "RegNode | RegLeaf"
    is_leaf: bool = False
    gain: float = 0.0


def variance(values: list[float]) -> float:
    """Population variance."""
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n


def find_best_split_reg(X: list[dict[str, float]], r: list[float],
                          features: list[str],
                          rng: random.Random,
                          max_features: int | None = None) -> tuple[str, float, float] | None:
    """Find (feature, threshold, gain) minimizing weighted variance of residuals."""
    n = len(X)
    if n < 2:
        return None
    base_var = variance(r) * n

    feat_subset = features
    if max_features and max_features < len(features):
        feat_subset = rng.sample(features, max_features)

    best_gain = 0.0
    best_feat = None
    best_thresh = None

    for feat in feat_subset:
        values = sorted(set(x[feat] for x in X))
        if len(values) < 2:
            continue
        thresholds = [(values[i] + values[i + 1]) / 2 for i in range(len(values) - 1)]
        if len(thresholds) > 20:
            thresholds = rng.sample(thresholds, 20)

        for thresh in thresholds:
            left_r = [r[i] for i in range(n) if X[i][feat] < thresh]
            right_r = [r[i] for i in range(n) if X[i][feat] >= thresh]
            if not left_r or not right_r:
                continue
            weighted_var = variance(left_r) * len(left_r) + variance(right_r) * len(right_r)
            gain = base_var - weighted_var
            if gain > best_gain:
                best_gain = gain
                best_feat = feat
                best_thresh = thresh

    if best_feat is None:
        return None
    return best_feat, best_thresh, best_gain


def build_regression_tree(X: list[dict[str, float]], r: list[float],
                            features: list[str], depth: int, max_depth: int,
                            min_samples_split: int, max_features: int | None,
                            rng: random.Random) -> RegNode | RegLeaf:
    """Recursive regression tree builder."""
    n = len(X)
    leaf_value = sum(r) / n if n else 0.0
    if depth >= max_depth or n < min_samples_split:
        return RegLeaf(value=leaf_value, n_samples=n)

    split = find_best_split_reg(X, r, features, rng, max_features)
    if split is None:
        return RegLeaf(value=leaf_value, n_samples=n)

    feat, thresh, gain = split
    left_X = [X[i] for i in range(n) if X[i][feat] < thresh]
    left_r = [r[i] for i in range(n) if X[i][feat] < thresh]
    right_X = [X[i] for i in range(n) if X[i][feat] >= thresh]
    right_r = [r[i] for i in range(n) if X[i][feat] >= thresh]

    if not left_X or not right_X:
        return RegLeaf(value=leaf_value, n_samples=n)

    return RegNode(
        split_feature=feat, threshold=thresh,
        left=build_regression_tree(left_X, left_r, features, depth + 1, max_depth,
                                      min_samples_split, max_features, rng),
        right=build_regression_tree(right_X, right_r, features, depth + 1, max_depth,
                                       min_samples_split, max_features, rng),
        gain=gain,
    )


def reg_tree_predict(tree: RegNode | RegLeaf, x: dict[str, float]) -> float:
    """Walk tree to leaf, return value."""
    cur = tree
    while not cur.is_leaf:
        if x[cur.split_feature] < cur.threshold:
            cur = cur.left
        else:
            cur = cur.right
    return cur.value


# ============== Gradient Boosting ==============
@dataclass
class GBDTModel:
    trees: list[RegNode | RegLeaf]
    initial_F: float
    learning_rate: float
    n_trees: int
    max_depth: int
    features: list[str]


def fit_gbdt(X: list[dict[str, float]], y: list[int],
              features: list[str], n_trees: int = 50,
              max_depth: int = 3, learning_rate: float = 0.1,
              min_samples_split: int = 2, max_features: int | None = None,
              seed: int = 42) -> GBDTModel:
    """Train GBDT binary classifier with logistic loss."""
    rng = random.Random(seed)
    n = len(y)
    p_initial = sum(y) / n if n else 0.5
    p_initial = max(0.01, min(0.99, p_initial))
    F_0 = math.log(p_initial / (1.0 - p_initial))
    F_current = [F_0] * n

    if max_features is None:
        max_features = max(1, int(math.sqrt(len(features))))

    trees = []
    for m in range(n_trees):
        # Compute residuals (negative gradient of logistic loss)
        residuals = [y[i] - sigmoid(F_current[i]) for i in range(n)]
        # Fit regression tree to residuals
        tree = build_regression_tree(X, residuals, features, 0, max_depth,
                                       min_samples_split, max_features, rng)
        trees.append(tree)
        # Update F_current
        for i in range(n):
            F_current[i] += learning_rate * reg_tree_predict(tree, X[i])

    return GBDTModel(
        trees=trees, initial_F=F_0, learning_rate=learning_rate,
        n_trees=n_trees, max_depth=max_depth, features=features,
    )


@dataclass
class GBDTPrediction:
    probability: float       # P(positive)
    log_odds: float
    contributing_trees: int


def predict_proba(model: GBDTModel, x: dict[str, float]) -> GBDTPrediction:
    """Return P(y=1 | x)."""
    F = model.initial_F
    for tree in model.trees:
        F += model.learning_rate * reg_tree_predict(tree, x)
    return GBDTPrediction(
        probability=round(sigmoid(F), 4),
        log_odds=round(F, 4),
        contributing_trees=len(model.trees),
    )


def predict_all(model: GBDTModel, X: list[dict[str, float]]) -> list[GBDTPrediction]:
    return [predict_proba(model, x) for x in X]


# ============== Feature importance ==============
def feature_importance_gain(model: GBDTModel) -> dict[str, float]:
    """Sum of gain attributable to each feature across all trees."""
    importance: dict[str, float] = defaultdict(float)

    def walk(node, depth):
        if node.is_leaf:
            return
        importance[node.split_feature] += node.gain
        walk(node.left, depth + 1)
        walk(node.right, depth + 1)

    for tree in model.trees:
        walk(tree, 0)

    total = sum(importance.values()) or 1.0
    return {f: round(v / total, 3) for f, v in sorted(importance.items(), key=lambda kv: -kv[1])}


# ============== Evaluation ==============
def log_loss(y_true: list[int], probs: list[float], eps: float = 1e-15) -> float:
    """Binary cross-entropy."""
    n = len(y_true)
    if n == 0:
        return 0.0
    total = 0.0
    for y, p in zip(y_true, probs):
        p = max(eps, min(1 - eps, p))
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / n


def accuracy(y_true: list[int], probs: list[float], threshold: float = 0.5) -> float:
    """Classification accuracy at given threshold."""
    n = len(y_true)
    if n == 0:
        return 0.0
    correct = sum(1 for y, p in zip(y_true, probs)
                   if (p >= threshold and y == 1) or (p < threshold and y == 0))
    return correct / n


def auc_roc_approx(y_true: list[int], probs: list[float]) -> float:
    """Approximate AUC via Mann-Whitney U statistic."""
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
