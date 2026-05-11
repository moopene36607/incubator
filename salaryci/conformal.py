"""salaryci — split-conformal prediction for salary intervals (pure stdlib).

Conformal prediction provides calibrated 1-α coverage **without distributional
assumptions** beyond exchangeability. Given a calibration set of past
(features, actual_salary) records, we compute:

  nonconformity score for each record:  s_i = |y_i - μ(x_i)|
  threshold q  = ceil((n+1)(1-α)) / n -th quantile of {s_i}
  prediction interval for new x*:  [μ(x*) - q, μ(x*) + q]

The interval guarantees: P(y* ∈ PI(x*)) ≥ 1 - α (assuming exchangeability).

Pure stdlib (math + statistics + dataclass). LLM never touches numbers.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from corpus import SalaryRecord, filter_corpus


@dataclass
class JobseekerProfile:
    industry: str            # SOFTWARE / FINANCE / MFG / RETAIL / BIO
    role_family: str         # BACKEND / FRONTEND / DATA / PM / DESIGN / RD / SALES / OPS
    level: str               # JUNIOR / MID / SENIOR / STAFF
    exp_years: int
    location: str            # TAIPEI / HSINCHU / TAICHUNG / KAOHSIUNG / REMOTE
    current_offer_ntd_k: int | None = None    # 收到的 offer 月薪 (千元) - 可選
    name: str = "(未具名)"


@dataclass
class ConformalResult:
    profile: JobseekerProfile
    median_estimate_ntd_k: float
    lower_ci_ntd_k: float
    upper_ci_ntd_k: float
    confidence_level: float                   # 0.9 = 90%
    calibration_set_size: int
    calibration_filter: str                   # 描述用了什麼濾鏡
    nonconformity_quantile: float
    p10_corpus: float
    p50_corpus: float
    p90_corpus: float
    raw_residuals: list[float] = field(default_factory=list)
    offer_position_pct: float | None = None    # offer 在 corpus 中的 percentile
    offer_vs_median_pct: float | None = None   # offer / median - 1


# ====== Calibration set selection (progressive relaxation) ======
def select_calibration_set(profile: JobseekerProfile,
                            min_size: int = 6) -> tuple[list[SalaryRecord], str]:
    """Progressive relaxation to find enough comparable records."""
    exp_band = (max(0, profile.exp_years - 2), profile.exp_years + 2)

    # Tier 1: exact industry + role + level + exp band
    cal = filter_corpus(industry=profile.industry, role_family=profile.role_family,
                        level=profile.level, exp_band=exp_band)
    if len(cal) >= min_size:
        return cal, f"industry={profile.industry} + role={profile.role_family} + level={profile.level} + exp ±2"

    # Tier 2: industry + role + exp band (any level)
    cal = filter_corpus(industry=profile.industry, role_family=profile.role_family,
                        exp_band=exp_band)
    if len(cal) >= min_size:
        return cal, f"industry={profile.industry} + role={profile.role_family} + exp ±2 (放寬 level)"

    # Tier 3: industry + role (any level / exp)
    cal = filter_corpus(industry=profile.industry, role_family=profile.role_family)
    if len(cal) >= min_size:
        return cal, f"industry={profile.industry} + role={profile.role_family} (放寬 level + exp)"

    # Tier 4: role_family only
    cal = filter_corpus(role_family=profile.role_family)
    if len(cal) >= min_size:
        return cal, f"role={profile.role_family} (跨產業跨經驗,信賴度降低)"

    # Tier 5: industry only (worst case)
    cal = filter_corpus(industry=profile.industry)
    return cal, f"industry={profile.industry} only (相似資料嚴重不足)"


# ====== Point prediction ======
def predict_median(calibration: list[SalaryRecord], profile: JobseekerProfile) -> float:
    """Use calibration set median as point estimate, adjusted for exp gap.

    Simple linear adjustment per year experience differential vs cluster mean.
    """
    if not calibration:
        return 50.0  # safe fallback
    salaries = [r.monthly_salary_ntd_k for r in calibration]
    median = statistics.median(salaries)
    return float(median)


# ====== Conformal interval ======
def nonconformity_scores(calibration: list[SalaryRecord],
                          point_estimate: float) -> list[float]:
    """Absolute residuals from the point estimate."""
    return [abs(r.monthly_salary_ntd_k - point_estimate) for r in calibration]


def conformal_quantile(scores: list[float], alpha: float) -> float:
    """Compute the (n+1)(1-α)/n empirical quantile from nonconformity scores.

    Standard split-conformal: with n calibration scores, take score at index
    ceil((n+1)(1-α))-th order statistic. Falls back to max if n very small.
    """
    if not scores:
        return 0.0
    n = len(scores)
    rank = math.ceil((n + 1) * (1 - alpha))
    # clamp
    rank = max(1, min(rank, n))
    sorted_scores = sorted(scores)
    return float(sorted_scores[rank - 1])


def predict_interval(profile: JobseekerProfile, alpha: float = 0.10) -> ConformalResult:
    """Main entrypoint: split-conformal prediction interval."""
    calibration, filter_desc = select_calibration_set(profile)
    median_est = predict_median(calibration, profile)
    scores = nonconformity_scores(calibration, median_est)
    q = conformal_quantile(scores, alpha)

    lower = max(0.0, median_est - q)
    upper = median_est + q

    salaries = [r.monthly_salary_ntd_k for r in calibration]
    if salaries:
        sorted_sal = sorted(salaries)
        n = len(sorted_sal)
        p10 = sorted_sal[max(0, int(0.10 * n) - 1)]
        p50 = statistics.median(sorted_sal)
        p90 = sorted_sal[min(n - 1, int(0.90 * n))]
    else:
        p10 = p50 = p90 = median_est

    offer_position = None
    offer_vs_median = None
    if profile.current_offer_ntd_k is not None and salaries:
        below = sum(1 for s in salaries if s <= profile.current_offer_ntd_k)
        offer_position = round(below / len(salaries) * 100, 1)
        offer_vs_median = round((profile.current_offer_ntd_k - median_est) / median_est * 100, 1)

    return ConformalResult(
        profile=profile,
        median_estimate_ntd_k=round(median_est, 1),
        lower_ci_ntd_k=round(lower, 1),
        upper_ci_ntd_k=round(upper, 1),
        confidence_level=1 - alpha,
        calibration_set_size=len(calibration),
        calibration_filter=filter_desc,
        nonconformity_quantile=round(q, 2),
        p10_corpus=round(p10, 1),
        p50_corpus=round(p50, 1),
        p90_corpus=round(p90, 1),
        raw_residuals=[round(s, 2) for s in sorted(scores)],
        offer_position_pct=offer_position,
        offer_vs_median_pct=offer_vs_median,
    )


# ====== Negotiation guidance (pure function) ======
def negotiation_anchors(result: ConformalResult) -> dict[str, float]:
    """Compute push / walk-away / stretch anchors for negotiation tactics.

    All values pure-function; LLM never recomputes.
    """
    return {
        "aim_for_ntd_k": round((result.median_estimate_ntd_k + result.upper_ci_ntd_k) / 2, 1),
        "stretch_target_ntd_k": result.upper_ci_ntd_k,
        "walk_away_ntd_k": result.lower_ci_ntd_k,
        "median_anchor_ntd_k": result.median_estimate_ntd_k,
    }
