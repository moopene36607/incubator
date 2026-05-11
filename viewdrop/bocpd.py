"""viewdrop — Bayesian Online Changepoint Detection (pure stdlib).

Adams & MacKay 2007: maintain a posterior over the **run length** r_t
(= time since the most recent changepoint). At each step:

  Predictive    π_t^{(r)}     = P(x_t | r_{t-1}=r, x_{(r)})
  Growth        P(r_t = r+1)  ∝ P(r_{t-1}=r) × π × (1 - H)
  Changepoint   P(r_t = 0)    = Σ_r P(r_{t-1}=r) × π × H

H = 1/λ is the hazard (geometric prior with mean run length λ).
We approximate π using a Gaussian likelihood with empirical mean of the
last r observations (simplified from Normal-Gamma conjugate).

Output for each timestep:
  - Posterior over run lengths (truncated to keep top-K to bound memory)
  - MAP run length
  - Changepoints = timesteps where MAP run length suddenly resets to small

All math 100% stdlib. LLM never touches the posterior or detection logic.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field


# ============== Predictive likelihood ==============
def _gaussian_pdf(x: float, mu: float, sigma: float) -> float:
    """Standard Gaussian density. sigma > 0."""
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))


def predictive_prob(x: float, recent_obs: list[float],
                     prior_mu: float, prior_sigma: float,
                     obs_sigma: float) -> float:
    """Predictive P(x_t | observations from current segment).

    With known observation noise σ and empirical mean of n recent obs:
      posterior mean = sample mean (if n > 0) else prior mean
      posterior predictive std = σ × sqrt(1 + 1/(n + κ_0))  with κ_0 = (σ/σ_prior)²
    Simplified: use σ × sqrt(1 + 1/max(n, 1)) and prior for n=0.
    """
    if not recent_obs:
        post_mu = prior_mu
        post_sigma = math.sqrt(prior_sigma ** 2 + obs_sigma ** 2)
    else:
        n = len(recent_obs)
        post_mu = sum(recent_obs) / n
        post_sigma = obs_sigma * math.sqrt(1 + 1.0 / n)
    return _gaussian_pdf(x, post_mu, post_sigma)


# ============== BOCPD core ==============
@dataclass
class BOCPDResult:
    timestamps: list[int]                       # 0..T-1
    map_run_lengths: list[int]                  # MAP r at each step
    posterior_run_lengths: list[dict[int, float]]  # full posterior per step (truncated)
    changepoints: list[int]                     # detected changepoint indices
    segment_summaries: list[dict]               # mean / std per segment
    most_likely_changepoint: int | None
    most_likely_cp_confidence: float            # 0-1


def run_bocpd(data: list[float],
              hazard_lambda: float = 30.0,
              obs_sigma: float = 1.0,
              prior_mu: float = 0.0,
              prior_sigma: float = 10.0,
              cp_threshold_ratio: float = 0.4,
              max_run_length: int = 200) -> BOCPDResult:
    """Run BOCPD on a 1-D time series.

    Args:
      data: ordered time series values
      hazard_lambda: expected mean segment length (higher = rarer changepoints)
      obs_sigma: noise std of observations within a segment
      prior_mu / prior_sigma: prior on segment mean
      cp_threshold_ratio: MAP run length reset ratio that flags a changepoint
        (e.g., 0.4 means if MAP drops to < 40% of previous max → flag)
      max_run_length: truncate posterior to bound memory

    Returns:
      BOCPDResult with per-timestep MAP run-length, segment summaries,
      and most-likely changepoint.
    """
    H = 1.0 / hazard_lambda
    T = len(data)

    # Initialize: at t=0, P(r=0) = 1
    posterior: dict[int, float] = {0: 1.0}
    posterior_history: list[dict[int, float]] = []
    map_history: list[int] = []
    # Track per-run-length observation history for predictive computation
    # Approximation: at each t, we keep the global data[:t] and slice by r.

    for t in range(T):
        x = data[t]

        # Compute predictive prob for each run-length hypothesis
        # (under r_{t-1} = r, recent obs are data[t-r:t])
        new_posterior: dict[int, float] = {}
        cp_mass = 0.0

        for r, p in posterior.items():
            recent = data[max(0, t - r):t] if r > 0 else []
            pred = predictive_prob(x, recent, prior_mu, prior_sigma, obs_sigma)
            # Growth
            grow_prob = p * pred * (1 - H)
            new_posterior[r + 1] = new_posterior.get(r + 1, 0.0) + grow_prob
            # Changepoint contribution
            cp_mass += p * pred * H

        new_posterior[0] = cp_mass

        # Truncate to max_run_length
        if len(new_posterior) > max_run_length:
            # Keep top-K by mass
            sorted_items = sorted(new_posterior.items(), key=lambda kv: -kv[1])
            new_posterior = dict(sorted_items[:max_run_length])

        # Normalize
        total = sum(new_posterior.values())
        if total > 0:
            new_posterior = {r: p / total for r, p in new_posterior.items()}
        else:
            new_posterior = {0: 1.0}

        posterior = new_posterior
        posterior_history.append(dict(posterior))
        map_r = max(posterior.items(), key=lambda kv: kv[1])[0]
        map_history.append(map_r)

    # ============== Detect changepoints from MAP trajectory ==============
    changepoints: list[int] = []
    prev_max = 0
    for t, r in enumerate(map_history):
        if r > prev_max:
            prev_max = r
        # A reset = MAP run length drops significantly
        if t > 0 and r < cp_threshold_ratio * prev_max and r < map_history[t - 1] * 0.6:
            # The changepoint occurred at time t - r (approx)
            cp_estimate = max(0, t - r)
            if not changepoints or (cp_estimate - changepoints[-1]) >= 5:
                changepoints.append(cp_estimate)
            prev_max = r

    # ============== Segment summaries ==============
    segment_summaries = []
    boundaries = [0] + changepoints + [T]
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        if end <= start:
            continue
        seg_data = data[start:end]
        if len(seg_data) >= 1:
            segment_summaries.append({
                "start_idx": start,
                "end_idx": end - 1,
                "n": len(seg_data),
                "mean": round(statistics.mean(seg_data), 2),
                "std": round(statistics.stdev(seg_data), 2) if len(seg_data) > 1 else 0.0,
                "min": min(seg_data),
                "max": max(seg_data),
            })

    # ============== Most-likely changepoint ==============
    most_likely_cp = None
    most_likely_cp_conf = 0.0
    if changepoints:
        # Pick the changepoint with the biggest mean shift between adjacent segments
        best_shift = 0.0
        for cp in changepoints:
            # Find adjacent segments
            before_seg = next((s for s in segment_summaries if s["end_idx"] + 1 == cp), None)
            after_seg = next((s for s in segment_summaries if s["start_idx"] == cp), None)
            if before_seg and after_seg:
                shift = abs(before_seg["mean"] - after_seg["mean"])
                if shift > best_shift:
                    best_shift = shift
                    most_likely_cp = cp
        # Confidence = shift / pooled std
        if most_likely_cp is not None:
            pooled_std = obs_sigma
            # normalized z-score → confidence
            most_likely_cp_conf = round(min(0.99, best_shift / (pooled_std * 2)), 3)

    return BOCPDResult(
        timestamps=list(range(T)),
        map_run_lengths=map_history,
        posterior_run_lengths=posterior_history,
        changepoints=changepoints,
        segment_summaries=segment_summaries,
        most_likely_changepoint=most_likely_cp,
        most_likely_cp_confidence=most_likely_cp_conf,
    )


# ============== Helpers ==============
def estimate_obs_sigma(data: list[float], window: int = 7) -> float:
    """Rough estimate of within-segment noise from rolling std."""
    if len(data) < window * 2:
        return statistics.stdev(data) if len(data) > 1 else 1.0
    stds = []
    for i in range(0, len(data) - window):
        chunk = data[i:i + window]
        if len(chunk) > 1:
            stds.append(statistics.stdev(chunk))
    return round(statistics.median(stds), 2) if stds else 1.0
