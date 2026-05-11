"""Hierarchical Bayesian Empirical-Bayes Shrinkage (James–Stein style).

Two-level model:

    y_{c,i}  ~ Normal(mu_c, sigma_within^2)         level 1 (individual reviews)
    mu_c     ~ Normal(mu_global, tau_between^2)     level 2 (cell means)

A "cell" c is a (breed, brand) pairing. Given each cell's observed rating
samples we want a posterior estimate of mu_c that shrinks toward the global
mean by a degree determined by:
  • how many samples that cell has (more samples -> less shrinkage)
  • how variable individual ratings are within cells (sigma_within^2)
  • how variable cell means are across cells (tau_between^2)

Empirical-Bayes shrinkage weight (James, 1961; Efron & Morris, 1973):

    w_c       = n_c * tau^2 / (n_c * tau^2 + sigma^2)
    mu_c_hat  = w_c * y_bar_c + (1 - w_c) * mu_global
    var_c_hat = (1 - w_c) * tau^2  (Bayesian posterior variance)

Pure-stdlib: math + statistics + dataclasses + collections.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import fmean, pvariance


@dataclass(frozen=True)
class Review:
    breed: str       # e.g. "貴賓"
    brand: str       # e.g. "Hill's Science Diet"
    rating: float    # 1-5
    age_group: str = "成犬"     # "幼犬" / "成犬" / "老犬"
    weight_kg: float = 0.0
    sensitive_stomach: bool = False
    grain_free: bool = False
    months_fed: int = 1


@dataclass
class CellPosterior:
    """Posterior estimate for a single (breed, brand) cell."""
    breed: str
    brand: str
    n_samples: int
    raw_mean: float                # y_bar_c
    raw_std: float                 # sample stdev within cell (0 if n<2)
    shrunk_mean: float             # mu_c_hat (posterior mean)
    posterior_std: float           # sqrt(var_c_hat) -- credible-interval scale
    shrinkage_weight: float        # w_c in [0, 1]; 1 = trust the cell, 0 = trust the prior
    ci_low: float                  # 95% credible-interval low (shrunk_mean - 1.96 * post_std)
    ci_high: float                 # 95% credible-interval high


@dataclass
class HBModel:
    cells: dict[tuple[str, str], CellPosterior]
    mu_global: float
    sigma_within: float            # within-cell SD (pooled, biased corrected)
    tau_between: float             # between-cell SD (method of moments)
    n_total: int
    n_cells: int
    feature_names: list[str] = field(default_factory=list)
    # Per-feature group means (e.g. mean rating for sensitive_stomach=True),
    # useful for the LLM-facing prose layer:
    feature_group_means: dict[str, dict[str, float]] = field(default_factory=dict)


def _group_by_cell(reviews: list[Review]) -> dict[tuple[str, str], list[float]]:
    """Group raw rating samples by (breed, brand)."""
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in reviews:
        cells[(r.breed, r.brand)].append(r.rating)
    return cells


def _pooled_within_variance(cell_samples: dict[tuple[str, str], list[float]]) -> float:
    """Pooled within-cell variance using cells with n>=2.

    sigma^2_pooled = sum_c (n_c - 1) * s_c^2 / sum_c (n_c - 1)
    Falls back to overall variance if no cell has n>=2.
    """
    num = 0.0
    den = 0
    for samples in cell_samples.values():
        n = len(samples)
        if n < 2:
            continue
        # Use Bessel-corrected sample variance: sum (x-mean)^2 / (n-1).
        m = fmean(samples)
        ssq = sum((x - m) ** 2 for x in samples)
        num += ssq                  # already a sum of squared deviations
        den += (n - 1)
    if den == 0:
        all_y = [y for samples in cell_samples.values() for y in samples]
        if len(all_y) < 2:
            return 1.0  # arbitrary positive floor
        return pvariance(all_y)
    return num / den


def _method_of_moments_tau_squared(
    cell_means: list[tuple[float, int]],
    sigma_within_sq: float,
    mu_global: float,
) -> float:
    """Estimate between-cell variance tau^2 from observed cell means.

    Var(y_bar_c) = tau^2 + sigma^2 / n_c
    So: tau^2 = mean_c [(y_bar_c - mu_global)^2 - sigma^2 / n_c]
    Clipped at 0 (negative estimates -> no detectable between-cell variation).
    """
    if not cell_means:
        return 0.0
    accum = 0.0
    for y_bar, n in cell_means:
        accum += (y_bar - mu_global) ** 2 - sigma_within_sq / max(n, 1)
    tau_sq = accum / len(cell_means)
    return max(tau_sq, 0.0)


def fit_hb(reviews: list[Review]) -> HBModel:
    """Empirical-Bayes hierarchical fit.

    Steps:
      1. Group ratings by cell (breed, brand).
      2. Compute mu_global as the average of cell means (so giant cells
         don't dominate -- treats cells as units of inference).
      3. Pool within-cell variance from cells with n>=2.
      4. Estimate tau^2 by method of moments.
      5. Shrink each cell mean toward mu_global with weight n*tau^2/(n*tau^2+sigma^2).
      6. Compute 95% credible interval per cell.
    """
    if not reviews:
        raise ValueError("fit_hb 需要至少 1 條 review")

    cell_samples = _group_by_cell(reviews)
    cell_keys = sorted(cell_samples.keys())
    raw_means = {k: fmean(cell_samples[k]) for k in cell_keys}
    raw_ns = {k: len(cell_samples[k]) for k in cell_keys}

    # mu_global = unweighted mean of cell means (so a 30-sample cell doesn't bury a 2-sample one).
    mu_global = fmean(raw_means.values())

    sigma_sq = _pooled_within_variance(cell_samples)
    sigma_within = math.sqrt(sigma_sq)

    cell_means_with_n = [(raw_means[k], raw_ns[k]) for k in cell_keys]
    tau_sq = _method_of_moments_tau_squared(cell_means_with_n, sigma_sq, mu_global)
    tau_between = math.sqrt(tau_sq)

    cells: dict[tuple[str, str], CellPosterior] = {}
    for k in cell_keys:
        samples = cell_samples[k]
        n = raw_ns[k]
        y_bar = raw_means[k]
        raw_std = math.sqrt(pvariance(samples)) if n >= 2 else 0.0

        if tau_sq == 0.0:
            # Complete pooling: no detectable between-cell variation -> everyone is mu_global.
            w = 0.0
            post_mean = mu_global
            post_var = sigma_sq / max(n, 1)
        else:
            w = (n * tau_sq) / (n * tau_sq + sigma_sq)
            post_mean = w * y_bar + (1 - w) * mu_global
            # Posterior variance for mu_c given data (closed-form normal-normal):
            #   1/var_post = n/sigma^2 + 1/tau^2  -->  var_post = sigma^2 tau^2 / (n tau^2 + sigma^2)
            post_var = (sigma_sq * tau_sq) / (n * tau_sq + sigma_sq)

        post_std = math.sqrt(post_var)
        cells[k] = CellPosterior(
            breed=k[0],
            brand=k[1],
            n_samples=n,
            raw_mean=y_bar,
            raw_std=raw_std,
            shrunk_mean=post_mean,
            posterior_std=post_std,
            shrinkage_weight=w,
            ci_low=post_mean - 1.96 * post_std,
            ci_high=post_mean + 1.96 * post_std,
        )

    feature_group_means = _feature_group_means(reviews)

    return HBModel(
        cells=cells,
        mu_global=mu_global,
        sigma_within=sigma_within,
        tau_between=tau_between,
        n_total=len(reviews),
        n_cells=len(cells),
        feature_group_means=feature_group_means,
    )


def _feature_group_means(reviews: list[Review]) -> dict[str, dict[str, float]]:
    """Compute raw mean rating for each value of selected categorical features.

    Used purely as diagnostic context for the LLM -- no inference happens here.
    """
    groups: dict[str, dict[str, list[float]]] = {
        "age_group": defaultdict(list),
        "sensitive_stomach": defaultdict(list),
        "grain_free": defaultdict(list),
    }
    for r in reviews:
        groups["age_group"][r.age_group].append(r.rating)
        groups["sensitive_stomach"]["敏感" if r.sensitive_stomach else "正常"].append(r.rating)
        groups["grain_free"]["無穀" if r.grain_free else "含穀"].append(r.rating)
    out: dict[str, dict[str, float]] = {}
    for feat, value_map in groups.items():
        out[feat] = {v: fmean(vals) for v, vals in value_map.items() if vals}
    return out


# -------------------------- recommendation layer -------------------------- #


@dataclass
class Query:
    breed: str
    age_group: str = "成犬"
    weight_kg: float = 0.0
    sensitive_stomach: bool = False
    grain_free_preference: bool = False


@dataclass
class Recommendation:
    brand: str
    breed: str
    rank: int
    shrunk_mean: float
    posterior_std: float
    ci_low: float
    ci_high: float
    n_samples: int
    shrinkage_weight: float
    raw_mean: float
    naive_vs_shrunk_delta: float  # positive => raw_mean was over-optimistic / over-pessimistic
    rationale: str                # short, deterministic, no LLM


def recommend_for_query(
    model: HBModel,
    query: Query,
    top_k: int = 3,
    min_samples: int = 1,
) -> list[Recommendation]:
    """Rank brands for this query's breed by *posterior* (shrunk) rating.

    Ranking uses shrunk_mean (NOT raw mean), so a 1-review brand with raw=5.0
    doesn't crowd out a 30-review brand with raw=4.6.
    """
    breed = query.breed
    candidates = [
        c for (b, _), c in model.cells.items()
        if b == breed and c.n_samples >= min_samples
    ]
    if not candidates:
        return []

    # Sort by shrunk posterior mean (descending). Tie-break on n_samples (more evidence wins).
    candidates.sort(key=lambda c: (-c.shrunk_mean, -c.n_samples))
    chosen = candidates[: top_k]

    out: list[Recommendation] = []
    for rank, c in enumerate(chosen, 1):
        delta = c.raw_mean - c.shrunk_mean
        rationale = _short_rationale(c, model)
        out.append(
            Recommendation(
                brand=c.brand,
                breed=c.breed,
                rank=rank,
                shrunk_mean=c.shrunk_mean,
                posterior_std=c.posterior_std,
                ci_low=c.ci_low,
                ci_high=c.ci_high,
                n_samples=c.n_samples,
                shrinkage_weight=c.shrinkage_weight,
                raw_mean=c.raw_mean,
                naive_vs_shrunk_delta=delta,
                rationale=rationale,
            )
        )
    return out


def _short_rationale(c: CellPosterior, model: HBModel) -> str:
    """Deterministic one-line explanation per cell."""
    if c.n_samples <= 2:
        return (
            f"證據薄弱 n={c.n_samples}, 後驗已強拉向品種均值 "
            f"({model.mu_global:.2f}), shrinkage={1 - c.shrinkage_weight:.0%}"
        )
    if c.shrinkage_weight >= 0.7:
        return f"證據充足 n={c.n_samples}, 後驗主要採信原始均值 (raw={c.raw_mean:.2f})"
    return (
        f"中等證據 n={c.n_samples}, raw={c.raw_mean:.2f} 被拉向全國均值"
        f" {model.mu_global:.2f} {1 - c.shrinkage_weight:.0%}"
    )


# ---------------------- diagnostics for the report ----------------------- #


def naive_vs_shrunk_table(model: HBModel) -> list[dict]:
    """Side-by-side raw vs shrunk per cell -- shows which cells the HB model 'corrected'."""
    rows = []
    for (breed, brand), c in sorted(model.cells.items()):
        rows.append(
            {
                "breed": breed,
                "brand": brand,
                "n": c.n_samples,
                "raw_mean": c.raw_mean,
                "shrunk_mean": c.shrunk_mean,
                "delta": c.raw_mean - c.shrunk_mean,
                "shrinkage_weight": c.shrinkage_weight,
                "ci_low": c.ci_low,
                "ci_high": c.ci_high,
            }
        )
    return rows


def most_corrected_cells(model: HBModel, top_n: int = 5) -> list[dict]:
    """Cells whose raw_mean was most aggressively corrected by shrinkage."""
    rows = naive_vs_shrunk_table(model)
    rows.sort(key=lambda r: -abs(r["delta"]))
    return rows[: top_n]


def model_summary(model: HBModel) -> dict:
    return {
        "n_total_reviews": model.n_total,
        "n_cells": model.n_cells,
        "mu_global": model.mu_global,
        "sigma_within": model.sigma_within,
        "tau_between": model.tau_between,
        "icc": (model.tau_between ** 2)
                / (model.tau_between ** 2 + model.sigma_within ** 2)
                if (model.tau_between ** 2 + model.sigma_within ** 2) > 0 else 0.0,
    }
