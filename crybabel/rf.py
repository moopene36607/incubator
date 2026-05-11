"""crybabel — Random Forest classification for tabular features (pure stdlib).

Breiman (2001) Random Forest: ensemble of decision trees, each:
  - Built on a bootstrap sample of the training data
  - At each split, considers a random subset of features (typically √F)
  - Splits chosen by minimizing Gini impurity (variance-like alternative to entropy)
Prediction = majority vote across all trees + class probability from vote shares.

Pure stdlib (random + math + collections + dataclass). No numpy / no scikit-learn.
Suitable for small-to-medium tabular tasks (< 1000 samples, < 50 features).
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field


# ============== Domain types ==============
@dataclass
class TreeLeaf:
    class_counts: dict[str, int]
    is_leaf: bool = True

    def predict_class(self) -> str:
        if not self.class_counts:
            return "unknown"
        return max(self.class_counts.items(), key=lambda kv: kv[1])[0]

    def predict_proba(self) -> dict[str, float]:
        total = sum(self.class_counts.values()) or 1
        return {c: cnt / total for c, cnt in self.class_counts.items()}


@dataclass
class TreeNode:
    split_feature: str
    threshold: float
    left: "TreeNode | TreeLeaf"
    right: "TreeNode | TreeLeaf"
    is_leaf: bool = False


# ============== Impurity ==============
def gini_impurity(class_counts: dict[str, int]) -> float:
    """1 - Σ p_i², lower = purer."""
    total = sum(class_counts.values())
    if total == 0:
        return 0.0
    return 1.0 - sum((c / total) ** 2 for c in class_counts.values())


def class_distribution(labels: list[str]) -> dict[str, int]:
    return dict(Counter(labels))


# ============== Build single tree ==============
def find_best_split(X: list[dict[str, float]], y: list[str],
                     features: list[str], rng: random.Random,
                     max_features: int | None = None) -> tuple[str, float, float] | None:
    """Find (feature, threshold, weighted_gini) that minimizes Gini impurity.
    Considers a random subset of features (Breiman's variance reduction trick)."""
    n = len(X)
    if n < 2:
        return None
    if max_features and max_features < len(features):
        feat_subset = rng.sample(features, max_features)
    else:
        feat_subset = features

    best_gini = float("inf")
    best_feat = None
    best_thresh = None

    for feat in feat_subset:
        # Candidate thresholds: midpoints between sorted unique values
        values = sorted(set(x[feat] for x in X))
        if len(values) < 2:
            continue
        thresholds = [(values[i] + values[i + 1]) / 2 for i in range(len(values) - 1)]
        # Sub-sample thresholds if too many (linear → many tries)
        if len(thresholds) > 20:
            thresholds = rng.sample(thresholds, 20)

        for thresh in thresholds:
            left_labels = [y[i] for i in range(n) if X[i][feat] < thresh]
            right_labels = [y[i] for i in range(n) if X[i][feat] >= thresh]
            if not left_labels or not right_labels:
                continue
            g_left = gini_impurity(class_distribution(left_labels))
            g_right = gini_impurity(class_distribution(right_labels))
            weighted = (len(left_labels) * g_left + len(right_labels) * g_right) / n
            if weighted < best_gini:
                best_gini = weighted
                best_feat = feat
                best_thresh = thresh

    if best_feat is None:
        return None
    return best_feat, best_thresh, best_gini


def build_tree(X: list[dict[str, float]], y: list[str], features: list[str],
                depth: int, max_depth: int, min_samples_split: int,
                max_features: int | None, rng: random.Random) -> TreeNode | TreeLeaf:
    """Recursive tree builder."""
    counts = class_distribution(y)
    if depth >= max_depth or len(X) < min_samples_split or len(counts) == 1:
        return TreeLeaf(class_counts=counts)

    split = find_best_split(X, y, features, rng, max_features)
    if split is None:
        return TreeLeaf(class_counts=counts)

    feat, thresh, _ = split
    left_X = [X[i] for i in range(len(X)) if X[i][feat] < thresh]
    left_y = [y[i] for i in range(len(X)) if X[i][feat] < thresh]
    right_X = [X[i] for i in range(len(X)) if X[i][feat] >= thresh]
    right_y = [y[i] for i in range(len(X)) if X[i][feat] >= thresh]

    if not left_X or not right_X:
        return TreeLeaf(class_counts=counts)

    return TreeNode(
        split_feature=feat,
        threshold=thresh,
        left=build_tree(left_X, left_y, features, depth + 1, max_depth,
                         min_samples_split, max_features, rng),
        right=build_tree(right_X, right_y, features, depth + 1, max_depth,
                          min_samples_split, max_features, rng),
    )


def tree_predict(tree: TreeNode | TreeLeaf, x: dict[str, float]) -> TreeLeaf:
    """Traverse tree to leaf."""
    cur = tree
    while not cur.is_leaf:
        if x[cur.split_feature] < cur.threshold:
            cur = cur.left
        else:
            cur = cur.right
    return cur


# ============== Random Forest ==============
@dataclass
class RandomForest:
    trees: list[TreeNode | TreeLeaf]
    features: list[str]
    classes: list[str]
    n_trees: int
    max_depth: int
    max_features: int


def bootstrap_sample(X: list, y: list, rng: random.Random) -> tuple[list, list]:
    """Sample with replacement."""
    n = len(X)
    indices = [rng.randrange(n) for _ in range(n)]
    return [X[i] for i in indices], [y[i] for i in indices]


def fit_forest(X: list[dict[str, float]], y: list[str], features: list[str],
                n_trees: int = 100, max_depth: int = 10,
                min_samples_split: int = 2, max_features: int | None = None,
                seed: int = 42) -> RandomForest:
    """Train Random Forest via bagging + random feature subsets."""
    rng = random.Random(seed)
    if max_features is None:
        max_features = max(1, int(math.sqrt(len(features))))
    classes = sorted(set(y))

    trees = []
    for _ in range(n_trees):
        X_boot, y_boot = bootstrap_sample(X, y, rng)
        tree = build_tree(X_boot, y_boot, features, 0, max_depth,
                           min_samples_split, max_features, rng)
        trees.append(tree)

    return RandomForest(
        trees=trees, features=features, classes=classes,
        n_trees=n_trees, max_depth=max_depth, max_features=max_features,
    )


@dataclass
class Prediction:
    predicted_class: str
    confidence: float                        # vote share of winning class
    class_probabilities: dict[str, float]    # vote share per class
    tree_predictions: list[str] = field(default_factory=list)


def predict_one(forest: RandomForest, x: dict[str, float]) -> Prediction:
    """Predict for a single sample."""
    votes: Counter = Counter()
    tree_preds = []
    for tree in forest.trees:
        leaf = tree_predict(tree, x)
        pred = leaf.predict_class()
        votes[pred] += 1
        tree_preds.append(pred)

    total = sum(votes.values()) or 1
    class_probs = {c: votes.get(c, 0) / total for c in forest.classes}
    pred_class = votes.most_common(1)[0][0]
    confidence = votes[pred_class] / total

    return Prediction(
        predicted_class=pred_class,
        confidence=round(confidence, 3),
        class_probabilities={c: round(p, 3) for c, p in class_probs.items()},
        tree_predictions=tree_preds,
    )


def predict(forest: RandomForest, X: list[dict[str, float]]) -> list[Prediction]:
    return [predict_one(forest, x) for x in X]


# ============== Evaluation ==============
def accuracy(predictions: list[Prediction], y_true: list[str]) -> float:
    if not predictions:
        return 0.0
    correct = sum(1 for p, t in zip(predictions, y_true) if p.predicted_class == t)
    return correct / len(predictions)


def feature_importance_simple(forest: RandomForest, X: list[dict[str, float]],
                                 y: list[str]) -> dict[str, float]:
    """Approximate importance: count how often each feature appears in splits across trees,
    weighted by depth (higher = more important)."""
    importance: dict[str, float] = {f: 0.0 for f in forest.features}

    def walk(node, depth):
        if node.is_leaf:
            return
        weight = 1.0 / (depth + 1)
        importance[node.split_feature] = importance.get(node.split_feature, 0.0) + weight
        walk(node.left, depth + 1)
        walk(node.right, depth + 1)

    for tree in forest.trees:
        walk(tree, 0)

    total = sum(importance.values()) or 1
    return {f: round(v / total, 3) for f, v in sorted(importance.items(), key=lambda kv: -kv[1])}
