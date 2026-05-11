"""constsim — Weighted k-Nearest Neighbors regression for construction quotes.

k-NN is an instance-based lazy learner: for a new query x, find the k closest
training points by distance, and return aggregated label (mean for regression,
majority vote for classification).

For mixed numeric + categorical features, we use a custom distance:
  d(x, y) = sqrt(Σ_numeric w_i × ((x_i - y_i) / scale_i)² + Σ_categorical w_j × (x_j ≠ y_j))

Pure stdlib (math + statistics + dataclass + collections). No numpy.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field


# ============== Domain types ==============
@dataclass
class FeatureSpec:
    name: str
    kind: str           # "numeric" or "categorical"
    weight: float = 1.0
    scale: float = 1.0  # for numeric: scale factor (typically std)


@dataclass
class TrainingCase:
    case_id: str
    features: dict[str, float | str]
    target: float       # the quote / price


@dataclass
class Neighbor:
    case_id: str
    distance: float
    target: float
    features: dict[str, float | str]


@dataclass
class KNNPrediction:
    predicted_value: float
    predicted_std: float
    n_neighbors_used: int
    neighbors: list[Neighbor]
    confidence_band: tuple[float, float]   # (lower, upper) at 1 std
    feature_distance_breakdown: dict[str, float]   # per-feature contribution to dist


# ============== Distance metric ==============
def weighted_distance(query: dict[str, float | str],
                        case: dict[str, float | str],
                        specs: list[FeatureSpec]) -> tuple[float, dict[str, float]]:
    """Weighted Euclidean (numeric) + Hamming (categorical) distance.

    Returns (total_distance, per-feature contribution dict).
    """
    total_sq = 0.0
    contributions = {}
    for spec in specs:
        q_val = query.get(spec.name)
        c_val = case.get(spec.name)
        if q_val is None or c_val is None:
            contributions[spec.name] = 0.0
            continue

        if spec.kind == "numeric":
            scale = max(spec.scale, 1e-9)
            diff = (float(q_val) - float(c_val)) / scale
            contrib = spec.weight * diff ** 2
        else:    # categorical
            contrib = spec.weight if q_val != c_val else 0.0

        total_sq += contrib
        contributions[spec.name] = round(contrib, 4)

    return math.sqrt(max(0.0, total_sq)), contributions


# ============== Auto-scale numeric features ==============
def auto_scale(cases: list[TrainingCase], specs: list[FeatureSpec]) -> list[FeatureSpec]:
    """Set FeatureSpec.scale to population std for numeric features."""
    updated = []
    for spec in specs:
        if spec.kind == "numeric":
            values = [float(c.features[spec.name]) for c in cases
                       if c.features.get(spec.name) is not None]
            if values:
                if len(values) > 1:
                    std = statistics.stdev(values)
                else:
                    std = 1.0
                updated.append(FeatureSpec(
                    name=spec.name, kind=spec.kind, weight=spec.weight,
                    scale=max(std, 0.01),
                ))
            else:
                updated.append(spec)
        else:
            updated.append(spec)
    return updated


# ============== k-NN prediction ==============
def knn_predict(query: dict[str, float | str], cases: list[TrainingCase],
                 specs: list[FeatureSpec], k: int = 5,
                 distance_weighted: bool = True) -> KNNPrediction:
    """Run k-NN regression on training cases."""
    # Compute distance to every case
    neighbors_all: list[tuple[float, TrainingCase, dict[str, float]]] = []
    for case in cases:
        d, contrib = weighted_distance(query, case.features, specs)
        neighbors_all.append((d, case, contrib))

    neighbors_all.sort(key=lambda t: t[0])
    top_k = neighbors_all[:k]

    # Aggregate target
    if distance_weighted:
        # Inverse distance weighting (avoid 0 division)
        weights = [1.0 / (d + 0.01) for d, _, _ in top_k]
        total_w = sum(weights)
        prediction = sum(w * c.target for w, (_, c, _) in zip(weights, top_k)) / total_w
    else:
        prediction = sum(c.target for _, c, _ in top_k) / k

    targets = [c.target for _, c, _ in top_k]
    pred_std = statistics.stdev(targets) if len(targets) > 1 else 0.0

    neighbors = [
        Neighbor(case_id=c.case_id, distance=round(d, 3), target=c.target, features=c.features)
        for d, c, _ in top_k
    ]

    # Aggregate per-feature distance contribution
    feat_contrib_sum: dict[str, float] = {}
    for _, _, contrib in top_k:
        for k_feat, v in contrib.items():
            feat_contrib_sum[k_feat] = feat_contrib_sum.get(k_feat, 0.0) + v

    return KNNPrediction(
        predicted_value=round(prediction, 2),
        predicted_std=round(pred_std, 2),
        n_neighbors_used=len(top_k),
        neighbors=neighbors,
        confidence_band=(round(prediction - pred_std, 2), round(prediction + pred_std, 2)),
        feature_distance_breakdown=feat_contrib_sum,
    )


# ============== Cross-validation ==============
def loo_evaluate(cases: list[TrainingCase], specs: list[FeatureSpec],
                  k: int = 5) -> dict[str, float]:
    """Leave-one-out cross-validation. Returns MAE, MAPE, RMSE."""
    if len(cases) < 2:
        return {"mae": 0.0, "mape": 0.0, "rmse": 0.0, "n_folds": 0}

    abs_errors = []
    pct_errors = []
    sq_errors = []
    for i in range(len(cases)):
        train = cases[:i] + cases[i + 1:]
        test = cases[i]
        pred = knn_predict(test.features, train, specs, k=k)
        err = pred.predicted_value - test.target
        abs_errors.append(abs(err))
        if test.target > 0:
            pct_errors.append(abs(err) / test.target * 100)
        sq_errors.append(err ** 2)

    return {
        "mae": round(sum(abs_errors) / len(abs_errors), 2),
        "mape": round(sum(pct_errors) / len(pct_errors), 2) if pct_errors else 0.0,
        "rmse": round(math.sqrt(sum(sq_errors) / len(sq_errors)), 2),
        "n_folds": len(cases),
    }


# ============== Feature importance via correlation ==============
def numeric_feature_correlations(cases: list[TrainingCase],
                                    specs: list[FeatureSpec]) -> dict[str, float]:
    """Pearson correlation between each numeric feature and target."""
    out = {}
    for spec in specs:
        if spec.kind != "numeric":
            continue
        xs = [float(c.features[spec.name]) for c in cases]
        ys = [c.target for c in cases]
        n = len(xs)
        if n < 2:
            continue
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
        denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
        if denom_x > 0 and denom_y > 0:
            r = num / (denom_x * denom_y)
            out[spec.name] = round(r, 3)
    return out


def categorical_feature_mean_diff(cases: list[TrainingCase],
                                      specs: list[FeatureSpec]) -> dict[str, dict[str, float]]:
    """For each categorical feature, mean target per category."""
    out = {}
    for spec in specs:
        if spec.kind != "categorical":
            continue
        groups: dict[str, list[float]] = {}
        for c in cases:
            val = c.features.get(spec.name)
            if val is None:
                continue
            groups.setdefault(str(val), []).append(c.target)
        out[spec.name] = {k: round(sum(v) / len(v), 2) for k, v in groups.items() if v}
    return out
