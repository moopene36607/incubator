"""Metropolis-Hastings MCMC for Bayesian logistic demand modelling.

Model (民宿 / B&B booking demand):

    logit P(book_i = 1)
      = alpha
        + beta_price   * log(price_i / baseline_price)
        + beta_weekend * is_weekend_i
        + beta_holiday * is_holiday_i

Priors (informative, encoded as N(mu, sigma)):
    alpha          ~ Normal(0.0,  2.0)
    beta_price     ~ Normal(-2.0, 1.5)   # demand falls with price
    beta_weekend   ~ Normal(0.8,  0.5)
    beta_holiday   ~ Normal(1.2,  0.5)

Posterior sampled by Metropolis-Hastings random-walk on the joint vector
theta = (alpha, beta_price, beta_weekend, beta_holiday) in log-posterior space.

Pure stdlib: math + random + statistics + dataclasses.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import fmean, pstdev


# =============================== priors ================================ #


@dataclass(frozen=True)
class NormalPrior:
    mu: float
    sigma: float

    def log_pdf(self, x: float) -> float:
        d = x - self.mu
        return -0.5 * (d * d) / (self.sigma * self.sigma) - math.log(self.sigma) - 0.5 * math.log(2.0 * math.pi)


DEFAULT_PRIORS: dict[str, NormalPrior] = {
    "alpha":        NormalPrior(0.0,  2.0),
    "beta_price":   NormalPrior(-2.0, 1.5),
    "beta_weekend": NormalPrior(0.8,  0.5),
    "beta_holiday": NormalPrior(1.2,  0.5),
}


# =============================== data ================================== #


@dataclass(frozen=True)
class Booking:
    price: float
    is_weekend: int          # 0 or 1
    is_holiday: int          # 0 or 1
    booked: int              # 0 or 1


# =========================== likelihood / posterior ==================== #


def sigmoid(z: float) -> float:
    """Numerically-stable logistic."""
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


def logit_predict(
    theta: dict[str, float], price: float, is_weekend: int, is_holiday: int,
    baseline_price: float,
) -> float:
    log_ratio = math.log(price / baseline_price) if price > 0 else 0.0
    z = (theta["alpha"]
         + theta["beta_price"] * log_ratio
         + theta["beta_weekend"] * is_weekend
         + theta["beta_holiday"] * is_holiday)
    return sigmoid(z)


def log_likelihood(
    theta: dict[str, float], data: list[Booking], baseline_price: float,
) -> float:
    """Sum_i [ y_i * log(p_i) + (1 - y_i) * log(1 - p_i) ]."""
    s = 0.0
    for b in data:
        p = logit_predict(theta, b.price, b.is_weekend, b.is_holiday, baseline_price)
        # clamp for numerical safety
        p = min(max(p, 1e-12), 1.0 - 1e-12)
        if b.booked == 1:
            s += math.log(p)
        else:
            s += math.log(1.0 - p)
    return s


def log_prior(theta: dict[str, float], priors: dict[str, NormalPrior]) -> float:
    return sum(priors[k].log_pdf(theta[k]) for k in priors)


def log_posterior(
    theta: dict[str, float], data: list[Booking],
    priors: dict[str, NormalPrior], baseline_price: float,
) -> float:
    return log_prior(theta, priors) + log_likelihood(theta, data, baseline_price)


# =============================== MCMC =================================== #


@dataclass
class MCMCResult:
    samples: list[dict[str, float]]
    accepted: int
    proposed: int
    burn_in: int
    thin: int

    def acceptance_rate(self) -> float:
        return self.accepted / max(self.proposed, 1)

    def posterior_mean(self, param: str) -> float:
        return fmean(s[param] for s in self.samples)

    def posterior_std(self, param: str) -> float:
        vals = [s[param] for s in self.samples]
        return pstdev(vals) if len(vals) >= 2 else 0.0

    def credible_interval(self, param: str, level: float = 0.95) -> tuple[float, float]:
        """Equal-tailed (alpha/2, 1-alpha/2) credible interval from posterior samples."""
        vals = sorted(s[param] for s in self.samples)
        n = len(vals)
        alpha = 1.0 - level
        lo_idx = int(math.floor(alpha / 2.0 * n))
        hi_idx = int(math.ceil((1.0 - alpha / 2.0) * n)) - 1
        lo_idx = max(0, min(n - 1, lo_idx))
        hi_idx = max(0, min(n - 1, hi_idx))
        return (vals[lo_idx], vals[hi_idx])


def run_mh(
    data: list[Booking],
    baseline_price: float,
    n_iter: int = 5000,
    burn_in: int = 1000,
    thin: int = 2,
    proposal_sigma: dict[str, float] | None = None,
    init: dict[str, float] | None = None,
    priors: dict[str, NormalPrior] | None = None,
    seed: int = 42,
) -> MCMCResult:
    """Metropolis-Hastings random-walk sampler.

    proposal_sigma: per-parameter random-walk step size. Defaults tuned for
    these priors; the user can adjust if acceptance rate is far from ~0.25.
    """
    rng = random.Random(seed)
    if priors is None:
        priors = DEFAULT_PRIORS
    if proposal_sigma is None:
        proposal_sigma = {
            "alpha":        0.30,
            "beta_price":   0.40,
            "beta_weekend": 0.20,
            "beta_holiday": 0.20,
        }
    if init is None:
        init = {k: priors[k].mu for k in priors}

    theta = dict(init)
    lp = log_posterior(theta, data, priors, baseline_price)

    samples: list[dict[str, float]] = []
    accepted = 0
    proposed = 0

    for it in range(n_iter):
        # Propose a step jointly (Gaussian random walk).
        cand = {k: theta[k] + rng.gauss(0.0, proposal_sigma[k]) for k in theta}
        lp_cand = log_posterior(cand, data, priors, baseline_price)

        log_alpha = lp_cand - lp
        u = rng.random()
        proposed += 1
        if math.log(u + 1e-300) < log_alpha:
            theta = cand
            lp = lp_cand
            accepted += 1

        if it >= burn_in and ((it - burn_in) % thin == 0):
            samples.append(dict(theta))

    return MCMCResult(
        samples=samples,
        accepted=accepted,
        proposed=proposed,
        burn_in=burn_in,
        thin=thin,
    )


# ========================= revenue optimisation ======================= #


@dataclass
class PricePoint:
    price: float
    book_prob_mean: float
    book_prob_low: float
    book_prob_high: float
    expected_revenue_mean: float
    expected_revenue_low: float
    expected_revenue_high: float


def sweep_prices(
    result: MCMCResult,
    is_weekend: int,
    is_holiday: int,
    baseline_price: float,
    price_grid: list[float],
    credible_level: float = 0.90,
) -> list[PricePoint]:
    """For each candidate price, compute posterior-mean book_prob and expected revenue."""
    out: list[PricePoint] = []
    alpha_tail = (1.0 - credible_level) / 2.0
    for price in price_grid:
        bp_samples: list[float] = []
        rev_samples: list[float] = []
        for s in result.samples:
            p = logit_predict(s, price, is_weekend, is_holiday, baseline_price)
            bp_samples.append(p)
            rev_samples.append(p * price)

        bp_samples.sort()
        rev_samples.sort()
        n = len(bp_samples)
        lo_idx = int(math.floor(alpha_tail * n))
        hi_idx = int(math.ceil((1.0 - alpha_tail) * n)) - 1
        lo_idx = max(0, min(n - 1, lo_idx))
        hi_idx = max(0, min(n - 1, hi_idx))

        out.append(PricePoint(
            price=price,
            book_prob_mean=fmean(bp_samples),
            book_prob_low=bp_samples[lo_idx],
            book_prob_high=bp_samples[hi_idx],
            expected_revenue_mean=fmean(rev_samples),
            expected_revenue_low=rev_samples[lo_idx],
            expected_revenue_high=rev_samples[hi_idx],
        ))
    return out


def optimal_price(points: list[PricePoint]) -> PricePoint:
    """Pick the price with maximum posterior-mean expected revenue."""
    return max(points, key=lambda p: p.expected_revenue_mean)
