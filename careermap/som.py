"""Self-Organizing Map (Kohonen 1982) -- pure stdlib.

Unsupervised competitive-learning network that maps high-dimensional input
vectors onto a low-dimensional (typically 2D) topological grid. Similar
inputs end up mapping to nearby grid cells.

Training (online stochastic):
  For epoch t in 0..T:
    eta(t)    = eta_0   * exp(-t / tau_eta)
    sigma(t)  = sigma_0 * exp(-t / tau_sigma)
    For each input x:
      BMU  c  = argmin_i ||w_i - x||²
      For each neuron j on the grid:
        h(c, j, t) = exp(-||pos(c) - pos(j)||² / (2 sigma(t)²))
        w_j      <- w_j + eta(t) * h(c, j, t) * (x - w_j)

After training, each grid cell carries a representative weight vector
and (by majority vote across training samples that mapped to it) a label.

Pure stdlib: math + random + statistics + dataclasses + collections.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import fmean


Vector = list[float]


# ============================ helpers ================================ #


def _vec_sub(a: Vector, b: Vector) -> Vector:
    return [ai - bi for ai, bi in zip(a, b)]


def _vec_norm_sq(a: Vector) -> float:
    return sum(x * x for x in a)


def _vec_dist_sq(a: Vector, b: Vector) -> float:
    s = 0.0
    for ai, bi in zip(a, b):
        d = ai - bi
        s += d * d
    return s


def _vec_dist(a: Vector, b: Vector) -> float:
    return math.sqrt(_vec_dist_sq(a, b))


# ============================ SOM model ============================== #


@dataclass
class SOM:
    grid_h: int
    grid_w: int
    input_dim: int
    weights: list[list[Vector]]    # weights[r][c] is a vector
    feature_names: list[str] = field(default_factory=list)
    # Diagnostics (filled after fitting):
    label_grid: list[list[str | None]] = field(default_factory=list)
    label_distribution: list[list[Counter]] = field(default_factory=list)
    quantisation_error: float = 0.0
    epochs_used: int = 0


def init_som(
    grid_h: int, grid_w: int, input_dim: int,
    init_low: float = 0.2, init_high: float = 0.8, seed: int = 42,
) -> SOM:
    """Initialise SOM weights uniformly in [init_low, init_high]."""
    rng = random.Random(seed)
    weights = [
        [
            [rng.uniform(init_low, init_high) for _ in range(input_dim)]
            for _ in range(grid_w)
        ]
        for _ in range(grid_h)
    ]
    return SOM(
        grid_h=grid_h,
        grid_w=grid_w,
        input_dim=input_dim,
        weights=weights,
        feature_names=[],
        label_grid=[[None] * grid_w for _ in range(grid_h)],
        label_distribution=[[Counter() for _ in range(grid_w)] for _ in range(grid_h)],
    )


def find_bmu(som: SOM, x: Vector) -> tuple[int, int]:
    """Best Matching Unit: grid cell whose weight vector is closest to x."""
    best = (0, 0)
    best_d = float("inf")
    for r in range(som.grid_h):
        for c in range(som.grid_w):
            d = _vec_dist_sq(som.weights[r][c], x)
            if d < best_d:
                best_d = d
                best = (r, c)
    return best


def _neighbourhood(r1: int, c1: int, r2: int, c2: int, sigma: float) -> float:
    """Gaussian neighbourhood h(BMU, neuron) given grid distance and sigma."""
    if sigma < 1e-9:
        return 1.0 if (r1, c1) == (r2, c2) else 0.0
    d2 = (r1 - r2) * (r1 - r2) + (c1 - c2) * (c1 - c2)
    return math.exp(-d2 / (2.0 * sigma * sigma))


def fit_som(
    som: SOM, X: list[Vector],
    epochs: int = 50,
    eta_0: float = 0.5,
    sigma_0: float | None = None,
    seed: int = 42,
) -> SOM:
    """Online SOM training.

    Hyperparameters:
      eta_0    -- initial learning rate
      sigma_0  -- initial neighbourhood radius (defaults to grid_h / 2)

    eta and sigma both decay exponentially with epoch.
    """
    if not X:
        raise ValueError("fit_som 需要至少 1 個 training input")
    rng = random.Random(seed)
    if sigma_0 is None:
        sigma_0 = max(som.grid_h, som.grid_w) / 2.0
    tau_eta = epochs / 4.0
    tau_sigma = epochs / math.log(max(sigma_0, 1.0) + 1.0)

    n = len(X)
    for t in range(epochs):
        eta = eta_0 * math.exp(-t / tau_eta)
        sigma = sigma_0 * math.exp(-t / tau_sigma)

        order = list(range(n))
        rng.shuffle(order)

        for idx in order:
            x = X[idx]
            br, bc = find_bmu(som, x)
            for r in range(som.grid_h):
                for c in range(som.grid_w):
                    h = _neighbourhood(br, bc, r, c, sigma)
                    if h < 1e-6:
                        continue
                    scale = eta * h
                    w = som.weights[r][c]
                    for d in range(som.input_dim):
                        w[d] += scale * (x[d] - w[d])

    som.epochs_used = epochs
    return som


def assign_labels(som: SOM, X: list[Vector], y: list[str]) -> None:
    """Tag each grid cell by majority vote of training samples that map to it."""
    grid_h, grid_w = som.grid_h, som.grid_w
    counters: list[list[Counter]] = [[Counter() for _ in range(grid_w)] for _ in range(grid_h)]
    for x, label in zip(X, y):
        r, c = find_bmu(som, x)
        counters[r][c][label] += 1
    som.label_distribution = counters
    grid: list[list[str | None]] = []
    for r in range(grid_h):
        row: list[str | None] = []
        for c in range(grid_w):
            if counters[r][c]:
                row.append(counters[r][c].most_common(1)[0][0])
            else:
                row.append(None)
        grid.append(row)
    som.label_grid = grid


def quantisation_error(som: SOM, X: list[Vector]) -> float:
    """Mean distance between each input and its BMU weight vector."""
    if not X:
        return 0.0
    total = 0.0
    for x in X:
        r, c = find_bmu(som, x)
        total += _vec_dist(som.weights[r][c], x)
    return total / len(X)


def topographic_error(som: SOM, X: list[Vector]) -> float:
    """Fraction of inputs whose 1st and 2nd BMU are NOT grid neighbours.

    Diagnostic for whether the SOM preserves topology well. Low is good.
    """
    if not X:
        return 0.0
    misses = 0
    for x in X:
        # Find top-2 closest cells.
        top: list[tuple[float, int, int]] = []
        for r in range(som.grid_h):
            for c in range(som.grid_w):
                d = _vec_dist_sq(som.weights[r][c], x)
                top.append((d, r, c))
        top.sort()
        (_, r1, c1), (_, r2, c2) = top[0], top[1]
        d_grid = abs(r1 - r2) + abs(c1 - c2)
        if d_grid > 1:
            misses += 1
    return misses / len(X)


# ============================ prediction ============================ #


@dataclass
class PredictionResult:
    bmu_row: int
    bmu_col: int
    bmu_label: str | None
    bmu_distance: float           # to BMU weight vector
    label_distribution: dict[str, int]  # at the BMU
    nearby_cells: list[tuple[int, int, str | None, float]]
    # ALL cells ranked by distance to input (r, c, label, distance).
    # The first labeled entry is the "best labeled recommendation".
    best_labeled_row: int | None = None
    best_labeled_col: int | None = None
    best_labeled_label: str | None = None
    best_labeled_distance: float | None = None


def predict(som: SOM, x: Vector) -> PredictionResult:
    """Return BMU + label + every-cell ranking sorted by distance to input.

    If the BMU lands on an unlabeled cell (no training sample mapped there),
    the caller can read `best_labeled_label` to get the nearest labeled
    recommendation -- this is the natural fallback when the SOM has dead
    cells between trained regions.
    """
    br, bc = find_bmu(som, x)
    bmu_label = som.label_grid[br][bc] if som.label_grid else None
    bmu_dist = _vec_dist(som.weights[br][bc], x)
    label_dist = dict(som.label_distribution[br][bc]) if som.label_distribution else {}

    all_cells: list[tuple[int, int, str | None, float]] = []
    for r in range(som.grid_h):
        for c in range(som.grid_w):
            d = _vec_dist(som.weights[r][c], x)
            lab = som.label_grid[r][c] if som.label_grid else None
            all_cells.append((r, c, lab, d))
    all_cells.sort(key=lambda t: t[3])

    # Exclude BMU itself from "nearby" list; keep top 8.
    nearby = [cell for cell in all_cells if (cell[0], cell[1]) != (br, bc)][: 8]

    best_labeled = None
    for r, c, lab, d in all_cells:
        if lab is not None:
            best_labeled = (r, c, lab, d)
            break

    return PredictionResult(
        bmu_row=br,
        bmu_col=bc,
        bmu_label=bmu_label,
        bmu_distance=bmu_dist,
        label_distribution=label_dist,
        nearby_cells=nearby,
        best_labeled_row=best_labeled[0] if best_labeled else None,
        best_labeled_col=best_labeled[1] if best_labeled else None,
        best_labeled_label=best_labeled[2] if best_labeled else None,
        best_labeled_distance=best_labeled[3] if best_labeled else None,
    )


# ============================ feature normalisation ================== #


def fit_minmax_scaler(X: list[Vector]) -> tuple[Vector, Vector]:
    """Per-feature min/max for [0, 1] scaling."""
    n = len(X)
    if n == 0:
        return [], []
    p = len(X[0])
    mins = list(X[0])
    maxs = list(X[0])
    for x in X:
        for j in range(p):
            if x[j] < mins[j]:
                mins[j] = x[j]
            if x[j] > maxs[j]:
                maxs[j] = x[j]
    return mins, maxs


def apply_minmax(X: list[Vector], mins: Vector, maxs: Vector) -> list[Vector]:
    out: list[Vector] = []
    for x in X:
        scaled = []
        for j, v in enumerate(x):
            rng = maxs[j] - mins[j]
            if rng < 1e-12:
                scaled.append(0.5)
            else:
                scaled.append((v - mins[j]) / rng)
        out.append(scaled)
    return out
