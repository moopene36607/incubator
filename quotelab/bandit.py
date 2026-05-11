"""quotelab — Multi-armed Bandit / Thompson Sampling 報價最佳化(純函式 / no LLM).

每個 (case_type, tier) 組合是一個 arm:
  - 觀察:歷次報該 tier 是否成交(accepted/rejected)
  - 信念:Beta(1 + n_accepted, 1 + n_rejected) — 接受機率的 posterior 分布
  - 預期報酬:tier 代表價格 × posterior 接受機率
  - 決策:每個新 case 用 Thompson Sampling 從各 arm posterior 抽樣,
    挑 expected revenue 最高的 tier

100% stdlib(random + math + statistics + dataclass)。
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field


# ===== Tier representative prices(domain knowledge,可由 SaaS 自動 calibrate)=====
TIER_PRICES_BY_CASE_TYPE = {
    "LOGO_DESIGN": {"LOW": 3000, "MID": 6000, "HIGH": 12000, "PREMIUM": 20000},
    "WEB_DESIGN": {"LOW": 15000, "MID": 30000, "HIGH": 60000, "PREMIUM": 100000},
    "COPYWRITING": {"LOW": 2000, "MID": 5000, "HIGH": 10000, "PREMIUM": 18000},
    "VIDEO_EDIT": {"LOW": 5000, "MID": 12000, "HIGH": 25000, "PREMIUM": 40000},
    "CONSULTING_HOUR": {"LOW": 1500, "MID": 3000, "HIGH": 6000, "PREMIUM": 12000},
}


TIERS = ("LOW", "MID", "HIGH", "PREMIUM")
TIER_LABEL_ZH = {"LOW": "保守", "MID": "標準", "HIGH": "進階", "PREMIUM": "頂級"}


@dataclass
class QuoteRecord:
    """歷史報價紀錄。"""
    case_id: str
    case_type: str               # LOGO_DESIGN / WEB_DESIGN / ...
    tier_quoted: str             # LOW / MID / HIGH / PREMIUM
    quote_ntd: int
    accepted: bool               # 成交 / 沒成交
    client_notes: str = ""


@dataclass
class ArmStats:
    case_type: str
    tier: str
    representative_price: int    # 該 tier 的代表性價格
    n_quoted: int                # 報過幾次該 tier
    n_accepted: int
    n_rejected: int
    accept_prob_mean: float      # Beta(1+s, 1+f) 的均值 = (1+s)/(2+n)
    accept_prob_lower95: float   # 95% CI 下界(Wilson interval)
    accept_prob_upper95: float
    expected_revenue: float      # accept_prob_mean × representative_price


def _beta_posterior(n_accepted: int, n_rejected: int) -> tuple[float, float, float]:
    """Beta(1+s, 1+f) 的均值 + 95% CI 大致範圍。

    用 (1+s)/(2+n) 為均值;用 Wald-like CI 簡化避免外部依賴。
    """
    n = n_accepted + n_rejected
    alpha = 1 + n_accepted
    beta = 1 + n_rejected
    mean = alpha / (alpha + beta)
    # Variance for Beta = αβ / ((α+β)²(α+β+1))
    variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
    std = variance ** 0.5
    # ±1.96 std for 95% CI (approximate; exact would use percent point function)
    lower = max(0.0, mean - 1.96 * std)
    upper = min(1.0, mean + 1.96 * std)
    return mean, lower, upper


def compute_arm_stats(history: list[QuoteRecord], case_type: str) -> list[ArmStats]:
    """對指定 case_type,計算各 tier 的 ArmStats。"""
    tier_prices = TIER_PRICES_BY_CASE_TYPE.get(case_type, {})
    stats: list[ArmStats] = []
    for tier in TIERS:
        rec_tier = [r for r in history if r.case_type == case_type and r.tier_quoted == tier]
        n_accepted = sum(1 for r in rec_tier if r.accepted)
        n_rejected = sum(1 for r in rec_tier if not r.accepted)
        n_quoted = n_accepted + n_rejected
        mean, lower, upper = _beta_posterior(n_accepted, n_rejected)
        price = tier_prices.get(tier, 0)
        stats.append(ArmStats(
            case_type=case_type,
            tier=tier,
            representative_price=price,
            n_quoted=n_quoted,
            n_accepted=n_accepted,
            n_rejected=n_rejected,
            accept_prob_mean=round(mean, 4),
            accept_prob_lower95=round(lower, 4),
            accept_prob_upper95=round(upper, 4),
            expected_revenue=round(mean * price, 0),
        ))
    return stats


# ===== Thompson Sampling decision =====
@dataclass
class TierRecommendation:
    """為新 case 推薦的 tier。"""
    case_type: str
    recommended_tier: str
    recommended_price: int
    expected_revenue: float
    expected_accept_prob: float
    runner_up_tier: str
    runner_up_expected_revenue: float
    confidence_score: float                  # 0-1,top 2 arms expected_revenue 差距佔比
    rationale: str
    arm_stats: list[ArmStats]


def _beta_sample(n_accepted: int, n_rejected: int, rng: random.Random) -> float:
    """Sample from Beta(1+s, 1+f) using ratio of gammas trick.

    Python stdlib doesn't have betavariate? Actually random.betavariate does exist.
    """
    return rng.betavariate(1 + n_accepted, 1 + n_rejected)


def thompson_sample_recommendation(
    history: list[QuoteRecord],
    case_type: str,
    n_samples: int = 1000,
    seed: int | None = 42,
) -> TierRecommendation:
    """用 Thompson sampling 跑多次,選出最常被挑中的 tier。

    每次 sampling: 對每個 tier 從 Beta posterior 抽 p_accept 樣本,計算 expected revenue,
    挑最高那個 tier。重複 n_samples 次,選最常勝出的 tier。
    """
    rng = random.Random(seed)
    arm_stats = compute_arm_stats(history, case_type)
    tier_prices = TIER_PRICES_BY_CASE_TYPE.get(case_type, {})

    # Run n_samples Thompson sampling rounds
    tier_wins: dict[str, int] = {t: 0 for t in TIERS}
    for _ in range(n_samples):
        best_tier = None
        best_ev = -1
        for s in arm_stats:
            p_sample = _beta_sample(s.n_accepted, s.n_rejected, rng)
            ev = p_sample * s.representative_price
            if ev > best_ev:
                best_ev = ev
                best_tier = s.tier
        if best_tier:
            tier_wins[best_tier] += 1

    # Pick most-wins tier as recommendation
    sorted_tiers = sorted(tier_wins.items(), key=lambda x: -x[1])
    rec_tier = sorted_tiers[0][0]
    runner_up = sorted_tiers[1][0] if len(sorted_tiers) > 1 else rec_tier

    rec_stat = next(s for s in arm_stats if s.tier == rec_tier)
    runner_up_stat = next(s for s in arm_stats if s.tier == runner_up)

    # Confidence = win count ratio
    total_wins = sum(tier_wins.values())
    rec_wins = tier_wins[rec_tier]
    confidence = round(rec_wins / total_wins, 4) if total_wins > 0 else 0.0

    rationale = (
        f"在 {n_samples} 次 Thompson sampling 中,{rec_tier} tier 勝出 {rec_wins} 次 "
        f"({confidence*100:.1f}%);其期望收益 NT$ {rec_stat.expected_revenue:,.0f} "
        f"= 接受率 {rec_stat.accept_prob_mean*100:.1f}% × 價格 NT$ {rec_stat.representative_price:,}。"
    )
    if rec_stat.n_quoted < 5:
        rationale += f" ⚠️ 該 tier 樣本數僅 {rec_stat.n_quoted},結果不確定性高,建議多試驗幾次再判斷。"

    return TierRecommendation(
        case_type=case_type,
        recommended_tier=rec_tier,
        recommended_price=rec_stat.representative_price,
        expected_revenue=rec_stat.expected_revenue,
        expected_accept_prob=rec_stat.accept_prob_mean,
        runner_up_tier=runner_up,
        runner_up_expected_revenue=runner_up_stat.expected_revenue,
        confidence_score=confidence,
        rationale=rationale,
        arm_stats=arm_stats,
    )


# ===== Portfolio-level summary =====
@dataclass
class PortfolioSummary:
    n_total_quotes: int
    n_accepted: int
    overall_acceptance_rate: float
    total_revenue_actual_ntd: int
    n_unique_case_types: int
    most_profitable_case_type: str | None
    most_profitable_revenue: int
    underutilized_tier_warning: list[str]   # tiers with too few samples


def compute_portfolio_summary(history: list[QuoteRecord]) -> PortfolioSummary:
    n_total = len(history)
    n_accepted = sum(1 for r in history if r.accepted)
    overall_rate = round(n_accepted / n_total, 4) if n_total else 0.0
    total_revenue = sum(r.quote_ntd for r in history if r.accepted)
    case_types = set(r.case_type for r in history)

    # Revenue by case_type
    revenue_by_type: dict[str, int] = {}
    for r in history:
        if r.accepted:
            revenue_by_type[r.case_type] = revenue_by_type.get(r.case_type, 0) + r.quote_ntd
    if revenue_by_type:
        most_profitable = max(revenue_by_type.items(), key=lambda x: x[1])
        most_profitable_type = most_profitable[0]
        most_profitable_revenue = most_profitable[1]
    else:
        most_profitable_type = None
        most_profitable_revenue = 0

    # Underutilized tier warning(any tier < 3 samples in any case_type)
    warnings: list[str] = []
    for ct in case_types:
        for tier in TIERS:
            n_t = sum(1 for r in history if r.case_type == ct and r.tier_quoted == tier)
            if n_t < 3:
                warnings.append(f"{ct} × {tier} 只有 {n_t} 筆 — bandit 需更多 exploration")

    return PortfolioSummary(
        n_total_quotes=n_total,
        n_accepted=n_accepted,
        overall_acceptance_rate=overall_rate,
        total_revenue_actual_ntd=total_revenue,
        n_unique_case_types=len(case_types),
        most_profitable_case_type=most_profitable_type,
        most_profitable_revenue=most_profitable_revenue,
        underutilized_tier_warning=warnings,
    )
