"""Quantile Regression via subgradient descent on pinball loss.

Koenker & Bassett (1978). For a quantile level tau in (0, 1) and prediction yhat,
the pinball (check) loss on a single sample is:

    L_tau(y, yhat) = max(tau * (y - yhat), (tau - 1) * (y - yhat))
                   = (y - yhat) * tau         if y >= yhat
                   = (yhat - y) * (1 - tau)   if y < yhat

Minimising expected pinball loss over predictions yhat(x) recovers the
conditional tau-quantile Q_tau(Y | X = x). Train one linear model per
quantile level via subgradient descent. The pinball loss is non-smooth at
y = yhat; the subgradient is well-defined and convex so vanilla GD converges.

Pure-stdlib (math + statistics + dataclasses + random + collections).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import fmean, pstdev


# ---------------------------- feature encoding ---------------------------- #


@dataclass
class FeatureEncoder:
    """Numeric z-score standardisation + categorical one-hot (drop-first)."""

    numeric_features: list[str]
    categorical_features: list[str]
    numeric_mean: dict[str, float] = field(default_factory=dict)
    numeric_std: dict[str, float] = field(default_factory=dict)
    categorical_levels: dict[str, list[str]] = field(default_factory=dict)
    expanded_names: list[str] = field(default_factory=list)

    def fit(self, rows: list[dict]) -> None:
        for f in self.numeric_features:
            vals = [float(r[f]) for r in rows]
            self.numeric_mean[f] = fmean(vals)
            # Guard against zero-variance numeric feature; falling back to 1.0 keeps
            # the standardised feature at (x - mu) without dividing by zero. This is
            # a numerical safeguard, not a fallback behaviour the user sees.
            s = pstdev(vals)
            self.numeric_std[f] = s if s > 1e-12 else 1.0

        for f in self.categorical_features:
            seen = []
            seen_set = set()
            for r in rows:
                v = r[f]
                if v not in seen_set:
                    seen.append(v)
                    seen_set.add(v)
            # Drop first level as reference category (one-hot encoding for linear model).
            self.categorical_levels[f] = seen[1:]

        names: list[str] = []
        for f in self.numeric_features:
            names.append(f)
        for f in self.categorical_features:
            for level in self.categorical_levels[f]:
                names.append(f"{f}={level}")
        self.expanded_names = names

    def transform(self, row: dict) -> list[float]:
        x: list[float] = []
        for f in self.numeric_features:
            v = float(row[f])
            x.append((v - self.numeric_mean[f]) / self.numeric_std[f])
        for f in self.categorical_features:
            v = row[f]
            for level in self.categorical_levels[f]:
                x.append(1.0 if v == level else 0.0)
        return x


# ----------------------------- pinball loss ------------------------------ #


def pinball_loss_one(y: float, yhat: float, tau: float) -> float:
    diff = y - yhat
    if diff >= 0:
        return tau * diff
    return (tau - 1.0) * diff


def pinball_loss_mean(y: list[float], yhat: list[float], tau: float) -> float:
    if not y:
        return 0.0
    return fmean(pinball_loss_one(yi, yhi, tau) for yi, yhi in zip(y, yhat))


# ----------------------------- model ------------------------------------ #


@dataclass
class QuantileModel:
    """One linear model per quantile level. coefficients[tau] = (b0, beta_vector)."""

    tau_levels: list[float]
    intercepts: dict[float, float]
    coefs: dict[float, list[float]]
    feature_names: list[str]
    n_iter_used: dict[float, int]
    final_loss: dict[float, float]


def _predict_linear(b0: float, beta: list[float], x: list[float]) -> float:
    s = b0
    for bi, xi in zip(beta, x):
        s += bi * xi
    return s


def fit_quantile(
    X: list[list[float]],
    y: list[float],
    feature_names: list[str],
    tau_levels: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9),
    lr: float = 0.05,
    max_iter: int = 2000,
    tol: float = 1e-6,
    seed: int = 42,
) -> QuantileModel:
    """Fit one quantile regressor per tau via subgradient descent on pinball loss.

    Subgradient w.r.t. yhat for L_tau(y, yhat):
        if y > yhat:  dL/dyhat = -tau
        if y < yhat:  dL/dyhat = 1 - tau
        if y == yhat: in [tau - 1, tau]; pick 0 for convergence

    Chain rule: dL/db0 = dL/dyhat, dL/dbeta_j = dL/dyhat * x_j.
    """
    if not X:
        raise ValueError("fit_quantile 需要至少 1 個 sample")
    n = len(X)
    p = len(X[0])
    rng = random.Random(seed)

    intercepts: dict[float, float] = {}
    coefs: dict[float, list[float]] = {}
    n_iter_used: dict[float, int] = {}
    final_loss: dict[float, float] = {}

    for tau in tau_levels:
        # Initialise intercept to tau-th sample quantile (good starting point).
        sorted_y = sorted(y)
        idx = max(0, min(n - 1, int(tau * (n - 1))))
        b0 = sorted_y[idx]
        beta = [0.0] * p

        prev_loss = float("inf")
        last_iter = 0
        for it in range(max_iter):
            # Compute gradient over full batch (small-data; no need for SGD).
            grad_b0 = 0.0
            grad_beta = [0.0] * p
            for i in range(n):
                yhat = _predict_linear(b0, beta, X[i])
                diff = y[i] - yhat
                if diff > 0:
                    g = -tau
                elif diff < 0:
                    g = 1.0 - tau
                else:
                    g = 0.0
                grad_b0 += g
                for j in range(p):
                    grad_beta[j] += g * X[i][j]
            grad_b0 /= n
            for j in range(p):
                grad_beta[j] /= n

            b0 -= lr * grad_b0
            for j in range(p):
                beta[j] -= lr * grad_beta[j]

            # Convergence on mean pinball loss.
            preds = [_predict_linear(b0, beta, X[i]) for i in range(n)]
            cur_loss = pinball_loss_mean(y, preds, tau)
            last_iter = it + 1
            if abs(prev_loss - cur_loss) < tol:
                break
            prev_loss = cur_loss

        intercepts[tau] = b0
        coefs[tau] = beta
        n_iter_used[tau] = last_iter
        final_loss[tau] = prev_loss

    return QuantileModel(
        tau_levels=list(tau_levels),
        intercepts=intercepts,
        coefs=coefs,
        feature_names=list(feature_names),
        n_iter_used=n_iter_used,
        final_loss=final_loss,
    )


# ----------------------------- prediction -------------------------------- #


@dataclass
class QuantilePrediction:
    quantiles: dict[float, float]   # tau -> predicted rent
    feature_contributions: dict[float, list[tuple[str, float, float]]]
    # tau -> [(name, value, beta * value)] sorted by |contribution| desc.


def predict_quantiles(model: QuantileModel, x: list[float]) -> QuantilePrediction:
    """Predict all tau-quantile levels for one feature vector. Enforces monotonicity.

    Crossing-prevention: independent training per tau can produce crossing
    (e.g. Q_0.9 < Q_0.5). We sort the raw predictions ascending and re-map to
    the requested tau order so the output is monotone non-decreasing in tau.
    """
    raw = {}
    contribs: dict[float, list[tuple[str, float, float]]] = {}
    for tau in model.tau_levels:
        b0 = model.intercepts[tau]
        beta = model.coefs[tau]
        yhat = _predict_linear(b0, beta, x)
        raw[tau] = yhat
        per_feat = [(model.feature_names[j], x[j], beta[j] * x[j]) for j in range(len(beta))]
        per_feat.sort(key=lambda t: -abs(t[2]))
        contribs[tau] = per_feat

    sorted_taus = sorted(raw.keys())
    sorted_preds = sorted(raw[t] for t in sorted_taus)  # monotone non-decreasing
    fixed = {t: p for t, p in zip(sorted_taus, sorted_preds)}
    return QuantilePrediction(quantiles=fixed, feature_contributions=contribs)


def check_coverage(
    model: QuantileModel,
    X: list[list[float]],
    y: list[float],
    tau: float,
) -> float:
    """Empirical fraction of y_i <= predicted Q_tau(x_i). Should approach tau."""
    if not X:
        return 0.0
    b0 = model.intercepts[tau]
    beta = model.coefs[tau]
    hits = 0
    for i, yi in enumerate(y):
        yhat = _predict_linear(b0, beta, X[i])
        if yi <= yhat:
            hits += 1
    return hits / len(y)


def coverage_report(
    model: QuantileModel,
    X: list[list[float]],
    y: list[float],
) -> dict[float, float]:
    return {tau: check_coverage(model, X, y, tau) for tau in model.tau_levels}


# --------------------------- band-based negotiation --------------------- #


@dataclass
class NegotiationAnchors:
    walk_away: float    # P10  -- 房客 below this = 撿到便宜 / 房東 below = 賠錢
    fair_low: float     # P25
    median: float       # P50
    fair_high: float    # P75
    ceiling: float      # P90  -- 房客 above = 被坑 / 房東 above = 議價空間


def negotiation_anchors(pred: QuantilePrediction) -> NegotiationAnchors:
    q = pred.quantiles
    return NegotiationAnchors(
        walk_away=q[0.1],
        fair_low=q[0.25],
        median=q[0.5],
        fair_high=q[0.75],
        ceiling=q[0.9],
    )


def classify_offer(actual_rent: float, anchors: NegotiationAnchors) -> tuple[str, str]:
    """Return (label, action_hint) for a tenant facing an offer at `actual_rent`."""
    if actual_rent <= anchors.walk_away:
        return ("🟢 撿到便宜", "可立刻簽 + 鎖約 1-2 年防漲")
    if actual_rent <= anchors.fair_low:
        return ("🟢 合理偏低", "可接受, 不必硬議價")
    if actual_rent <= anchors.fair_high:
        return ("🟡 行情價區間", "正常市場價, 可微議 NT$500-1000")
    if actual_rent <= anchors.ceiling:
        return ("🟠 偏高", "建議議價 5-10% 或換物件")
    return ("🔴 超出行情", "強烈建議重新議價或拒簽; 房東開超天花板")
