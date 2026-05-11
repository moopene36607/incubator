"""storehunt — Optimal Stopping for Taiwan store-rental decisions (pure stdlib).

Classical secretary problem: N candidates seen sequentially, must accept/reject
each immediately (no go-back). Optimal policy:
  - Observe first floor(N/e) ≈ 37% candidates (observation phase)
  - Record threshold = max score in observation phase
  - After phase, accept first candidate with score > threshold
  - This achieves P(pick best) ≈ 1/e ≈ 37%

Real-world adjustments for store-hunting:
  - Multi-attribute score (location / rent / size / deposit / contract)
  - Time pressure: as remaining slots → 0, lower threshold (don't end empty-handed)
  - Sunk cost: if search has dragged on > expected, reduce threshold

All math 100% stdlib. LLM never recomputes scores or thresholds.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from enum import Enum


class Verdict(Enum):
    STRONG_ACCEPT = "STRONG_ACCEPT"           # well above threshold + low remaining
    ACCEPT = "ACCEPT"                          # above threshold, normal phase
    CONTINUE_OBSERVATION = "CONTINUE_OBSERVATION"   # still in observation phase
    WAIT_FOR_BETTER = "WAIT_FOR_BETTER"        # below threshold, more options remain
    RELUCTANT_ACCEPT = "RELUCTANT_ACCEPT"      # below threshold, but time pressure
    RECONSIDER = "RECONSIDER"                  # weird state (e.g., no observations yet)


@dataclass
class StoreAttributes:
    """Multi-attribute features of a candidate store. All scores 0-100."""
    name: str
    location_score: float           # 人流 / 鄰近商家 / 競爭密度
    rent_score: float               # 月租金合理性 (低 = 高分)
    size_score: float               # 坪數 / 隔間實用性
    deposit_score: float            # 押金合理性 (含 key-money / 轉讓費)
    contract_score: float           # 合約彈性 (短租 / 提前解約 / 漲價條款)


# Default weights for store-rental scoring (餐飲業向)
DEFAULT_WEIGHTS = {
    "location": 0.30,
    "rent": 0.25,
    "size": 0.20,
    "deposit": 0.10,
    "contract": 0.15,
}


def composite_score(s: StoreAttributes, weights: dict[str, float] | None = None) -> float:
    """Weighted composite 0-100 score. Pure function."""
    w = weights or DEFAULT_WEIGHTS
    return round(
        s.location_score * w["location"] +
        s.rent_score * w["rent"] +
        s.size_score * w["size"] +
        s.deposit_score * w["deposit"] +
        s.contract_score * w["contract"],
        2,
    )


@dataclass
class SearchState:
    """User's current store-search state."""
    seen_stores: list[StoreAttributes]                # already viewed (in chronological order)
    estimated_total_stores: int                       # how many stores user expects to view total
    current_store: StoreAttributes                    # the one user is considering NOW
    search_weeks_elapsed: float                       # how long the search has been
    expected_search_weeks: float                      # original budget
    user_must_decide: bool = False                     # landlord saying "decide within 24h"
    weights: dict[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())


# ============== Pure-function core ==============
def observation_phase_size(n_total: int) -> int:
    """Classic secretary rule: observe floor(N/e) candidates."""
    return max(1, math.floor(n_total / math.e))


def observation_threshold(seen: list[StoreAttributes], n_observation: int,
                           weights: dict[str, float]) -> float:
    """Max score in the observation phase."""
    if not seen:
        return 0.0
    observed = seen[:n_observation]
    if not observed:
        return 0.0
    return max(composite_score(s, weights) for s in observed)


def best_so_far(seen: list[StoreAttributes], weights: dict[str, float]) -> tuple[StoreAttributes | None, float]:
    """Best store seen so far (any phase)."""
    if not seen:
        return None, 0.0
    best = max(seen, key=lambda s: composite_score(s, weights))
    return best, composite_score(best, weights)


def time_pressure_adjustment(state: SearchState) -> float:
    """Threshold reduction multiplier in [0.7, 1.0] based on remaining time / slots.

    1.0 = no pressure (normal threshold)
    0.7 = high pressure (accept 70% of threshold)
    """
    n_seen = len(state.seen_stores)
    n_remaining = max(0, state.estimated_total_stores - n_seen - 1)  # -1 for current
    fraction_remaining = n_remaining / max(state.estimated_total_stores, 1)

    week_overrun = state.search_weeks_elapsed / max(state.expected_search_weeks, 1)

    # Pressure increases as remaining → 0 and overrun → ∞
    pressure = 0.0
    if fraction_remaining < 0.2:
        pressure += 0.15
    if fraction_remaining < 0.1:
        pressure += 0.10
    if week_overrun > 1.0:
        pressure += min(0.10, (week_overrun - 1.0) * 0.5)
    if state.user_must_decide:
        pressure += 0.05

    return round(max(0.7, 1.0 - pressure), 3)


@dataclass
class Decision:
    verdict: Verdict
    current_score: float
    threshold: float
    threshold_adjusted: float
    n_seen: int
    n_observation_phase: int
    n_remaining_estimated: int
    best_seen_so_far: tuple[str, float]
    theoretical_p_best: float          # secretary rule baseline ~1/e if all conditions met
    reasoning_signals: list[str] = field(default_factory=list)


def decide(state: SearchState) -> Decision:
    """Main entrypoint: pure-function decision."""
    weights = state.weights
    current = composite_score(state.current_store, weights)
    n_seen = len(state.seen_stores)
    n_obs = observation_phase_size(state.estimated_total_stores)
    threshold = observation_threshold(state.seen_stores, n_obs, weights)
    adjustment = time_pressure_adjustment(state)
    threshold_adj = round(threshold * adjustment, 2)

    best_store, best_score = best_so_far(state.seen_stores, weights)
    best_name = best_store.name if best_store else "(無)"

    # remaining 估計 (excluding current)
    n_remaining = max(0, state.estimated_total_stores - n_seen - 1)

    signals = []
    if n_seen < n_obs:
        # Still in observation phase — never accept
        verdict = Verdict.CONTINUE_OBSERVATION
        signals.append(f"還在觀察期 (已看 {n_seen}/{n_obs} 間,前 {n_obs} 間建議只觀察不下訂)")
        signals.append(f"觀察期完後門檻 ≈ 觀察期最高分(目前 {threshold:.1f})")
    else:
        signals.append(f"觀察期 (前 {n_obs} 間) 已結束,門檻定為 {threshold:.1f}")
        if adjustment < 1.0:
            signals.append(f"⏰ 時間壓力調整: 門檻 × {adjustment:.2f} = {threshold_adj:.1f}")

        if current >= threshold_adj * 1.10:
            verdict = Verdict.STRONG_ACCEPT
            signals.append(f"當前分數 {current:.1f} ≥ 調整後門檻 × 1.10 ({threshold_adj * 1.10:.1f}),強烈建議簽")
        elif current >= threshold_adj:
            verdict = Verdict.ACCEPT
            signals.append(f"當前分數 {current:.1f} ≥ 調整後門檻 {threshold_adj:.1f},通過 secretary 條件")
        elif n_remaining <= 3 and current >= threshold_adj * 0.85:
            verdict = Verdict.RELUCTANT_ACCEPT
            signals.append(f"只剩 ~{n_remaining} 間,當前 {current:.1f} 雖低於門檻 {threshold_adj:.1f}, 但已接近最後機會")
        elif current < threshold_adj * 0.7:
            verdict = Verdict.RECONSIDER
            signals.append(f"當前分數 {current:.1f} 顯著低於門檻 {threshold_adj:.1f},強烈不建議")
        else:
            verdict = Verdict.WAIT_FOR_BETTER
            signals.append(f"當前 {current:.1f} 低於門檻 {threshold_adj:.1f},還剩 ~{n_remaining} 間可繼續看")
            if best_store and current < best_score:
                signals.append(f"已看過 {best_name} 分數 {best_score:.1f} 比這間還高,且 secretary 規則禁回頭 — 注意已錯過")

    # P(this is the best) — secretary rule baseline
    # ≈ 1/e if you follow optimal stopping rule perfectly
    p_best = round(1.0 / math.e, 3)

    return Decision(
        verdict=verdict,
        current_score=current,
        threshold=round(threshold, 2),
        threshold_adjusted=threshold_adj,
        n_seen=n_seen,
        n_observation_phase=n_obs,
        n_remaining_estimated=n_remaining,
        best_seen_so_far=(best_name, round(best_score, 2)),
        theoretical_p_best=p_best,
        reasoning_signals=signals,
    )


# ============== Helpers ==============
def all_scores_breakdown(state: SearchState) -> list[tuple[str, float, dict[str, float]]]:
    """For display: per-store breakdown of scores."""
    out = []
    for s in state.seen_stores + [state.current_store]:
        breakdown = {
            "location": s.location_score,
            "rent": s.rent_score,
            "size": s.size_score,
            "deposit": s.deposit_score,
            "contract": s.contract_score,
        }
        out.append((s.name, composite_score(s, state.weights), breakdown))
    return out


def what_if_more_stores(state: SearchState, additional: int) -> tuple[float, float]:
    """If user planned to see `additional` more stores, what would observation
    phase size and current threshold ratio change?"""
    new_total = state.estimated_total_stores + additional
    new_obs = observation_phase_size(new_total)
    return float(new_obs), round(state.threshold if hasattr(state, 'threshold') else 0, 2)
