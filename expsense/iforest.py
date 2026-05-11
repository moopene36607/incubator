"""expsense — Isolation Forest for SME reimbursement anomaly detection.

Liu, Ting, Zhou (2008): outliers are easier to isolate in random partition
trees. Each tree:
  1. Pick random feature
  2. Pick random split value between feature min/max
  3. Recurse into left/right subsets
  4. Stop at height limit ⌈log₂(sample_size)⌉ or single-point leaves

Anomaly score for a point x:
  E[path_length(x)] = average over n_trees
  c(n) = 2·H(n-1) - 2(n-1)/n ≈ 2·(ln(n-1)+0.5772) - 2(n-1)/n
       = expected path length of unsuccessful BST search of size n
  s(x) = 2 ^ (-E[path_length] / c(sample_size))
  s → 1 = anomaly (short path, easy to isolate)
  s → 0.5 = normal
  s → 0 = inlier (deep in cluster)

Pure stdlib (random + math + dataclass).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


# ============== Helpers ==============
def harmonic(n: int) -> float:
    """H(n) = 1 + 1/2 + ... + 1/n ≈ ln(n) + γ + 1/(2n)"""
    if n <= 0:
        return 0.0
    # Use exact for small n, approximation otherwise
    if n <= 100:
        return sum(1.0 / i for i in range(1, n + 1))
    # Asymptotic
    return math.log(n) + 0.5772156649 + 0.5 / n


def c_factor(n: int) -> float:
    """Expected path length of unsuccessful BST search of size n."""
    if n <= 1:
        return 0.0
    return 2 * harmonic(n - 1) - 2 * (n - 1) / n


# ============== Tree nodes ==============
@dataclass
class IsolationLeaf:
    size: int
    is_leaf: bool = True


@dataclass
class IsolationNode:
    split_feature: str
    split_value: float
    left: "IsolationNode | IsolationLeaf"
    right: "IsolationNode | IsolationLeaf"
    is_leaf: bool = False


def build_tree(X: list[dict[str, float]], features: list[str],
                current_height: int, height_limit: int,
                rng: random.Random) -> IsolationNode | IsolationLeaf:
    """Recursively build one isolation tree."""
    n = len(X)
    if n <= 1 or current_height >= height_limit:
        return IsolationLeaf(size=n)

    # Pick a random feature that has variance
    valid_features = []
    for f in features:
        values = [x[f] for x in X]
        if max(values) > min(values):
            valid_features.append(f)
    if not valid_features:
        return IsolationLeaf(size=n)

    feat = rng.choice(valid_features)
    values = [x[feat] for x in X]
    f_min, f_max = min(values), max(values)
    split = rng.uniform(f_min, f_max)

    left = [x for x in X if x[feat] < split]
    right = [x for x in X if x[feat] >= split]

    return IsolationNode(
        split_feature=feat,
        split_value=split,
        left=build_tree(left, features, current_height + 1, height_limit, rng),
        right=build_tree(right, features, current_height + 1, height_limit, rng),
    )


def path_length(point: dict[str, float], node: IsolationNode | IsolationLeaf,
                 current_height: int) -> float:
    """Path length to reach the leaf containing this point."""
    if node.is_leaf:
        return current_height + c_factor(node.size)
    if point[node.split_feature] < node.split_value:
        return path_length(point, node.left, current_height + 1)
    else:
        return path_length(point, node.right, current_height + 1)


# ============== Forest ==============
@dataclass
class IsolationForest:
    trees: list[IsolationNode | IsolationLeaf] = field(default_factory=list)
    sample_size: int = 256
    n_trees: int = 100
    features: list[str] = field(default_factory=list)


def fit_iforest(X: list[dict[str, float]], features: list[str],
                 n_trees: int = 100, sample_size: int = 256,
                 seed: int = 42) -> IsolationForest:
    """Fit ensemble of isolation trees on subsamples."""
    rng = random.Random(seed)
    sample_size = min(sample_size, len(X))
    height_limit = max(1, math.ceil(math.log2(sample_size)))

    trees = []
    for _ in range(n_trees):
        if len(X) <= sample_size:
            sample = list(X)
        else:
            sample = rng.sample(X, sample_size)
        tree = build_tree(sample, features, 0, height_limit, rng)
        trees.append(tree)

    return IsolationForest(
        trees=trees, sample_size=sample_size, n_trees=n_trees, features=features,
    )


def anomaly_score(point: dict[str, float], forest: IsolationForest) -> float:
    """0-1 score, higher = more anomalous.

    s(x) = 2 ^ (-E[h(x)] / c(sample_size))
    """
    if not forest.trees:
        return 0.5
    avg_path = sum(path_length(point, t, 0) for t in forest.trees) / len(forest.trees)
    c = c_factor(forest.sample_size)
    if c == 0:
        return 0.5
    return 2 ** (-avg_path / c)


def score_all(X: list[dict[str, float]], forest: IsolationForest) -> list[float]:
    """Return anomaly score for every point."""
    return [anomaly_score(x, forest) for x in X]


def top_k_anomalies(X: list[dict[str, float]], scores: list[float],
                     k: int = 10, threshold: float | None = None) -> list[tuple[int, float, dict]]:
    """Top-k highest-scoring anomalies. Optionally filter by threshold."""
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: -x[1])
    out = []
    for idx, score in indexed[:k]:
        if threshold is not None and score < threshold:
            break
        out.append((idx, score, X[idx]))
    return out


# ============== Feature explanation (which feature pushed it to be anomaly) ==============
def feature_contribution(point: dict[str, float], forest: IsolationForest) -> dict[str, float]:
    """Approximate per-feature anomaly contribution.

    For each feature, compute average split depth where this feature was used
    in the path traversal — features appearing high in the tree (low depth)
    contributed more to isolating this point.
    """
    contribs: dict[str, list[float]] = {f: [] for f in forest.features}

    def walk(point, node, depth, found_features):
        if node.is_leaf:
            return
        if point[node.split_feature] < node.split_value:
            found_features.append((node.split_feature, depth))
            walk(point, node.left, depth + 1, found_features)
        else:
            found_features.append((node.split_feature, depth))
            walk(point, node.right, depth + 1, found_features)

    for tree in forest.trees:
        path_features: list[tuple[str, int]] = []
        walk(point, tree, 0, path_features)
        for f, depth in path_features:
            contribs[f].append(depth)

    out = {}
    for f, depths in contribs.items():
        if depths:
            avg_depth = sum(depths) / len(depths)
            # Lower depth = more isolating power
            out[f] = round(1.0 / (avg_depth + 1), 3)
        else:
            out[f] = 0.0
    return out
