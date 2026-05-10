"""liftlab — 行銷投放因果效應估計(Pearl backdoor adjustment,純函式 / no LLM / no I/O).

責任:
  - 從月度行銷 + 營收資料,估「**高廣告投放對營收的因果效應**」(ATE)
  - 對比:
      Naive ATE(直接平均差) — 包含 confounder bias
      Adjusted ATE(stratified backdoor adjustment) — 控制 confounders 後的真實因果
  - 拆解 confounder bias contribution

DAG 假設:
    season ──┐
    holiday ─┼──> ad_spend ──> revenue
    new_prd ─┘          └──> revenue (直接)
    season ───────────────> revenue
    holiday ──────────────> revenue
    new_prd ──────────────> revenue

Confounders(共因 — 同時影響 ad_spend 與 revenue):
  - is_peak_season(老闆旺季傾向多投廣告 + 旺季營收自然高)
  - is_holiday_promo(節慶有 promo,老闆投更多 + 營收高)
  - launched_new_product(新品月投更多廣告 + 新品本身帶營收)

Backdoor adjustment(Pearl 1995):
  ATE = Σ_z [E[Y | T=1, Z=z] - E[Y | T=0, Z=z]] × P(Z=z)

100% stdlib;只用 statistics + dataclass + itertools。
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from itertools import product


@dataclass
class MonthlyRecord:
    month: str                       # "2024-01"
    ad_spend_ntd: int                # 該月廣告花費
    revenue_ntd: int                 # 該月營收
    is_peak_season: bool             # 旺季(Q4 / 春節 / 母親節 / 暑假 ...)
    is_holiday_promo: bool           # 該月有大檔促銷(11/11 / 雙 12 / 春節檔)
    launched_new_product: bool       # 該月有上新品


# === Treatment 定義 ===
HIGH_AD_THRESHOLD = 30000             # ≥ NT$30K = high (T=1), 否則 low (T=0)


def is_treated(record: MonthlyRecord) -> bool:
    return record.ad_spend_ntd >= HIGH_AD_THRESHOLD


def load_csv(path: str) -> list[MonthlyRecord]:
    records: list[MonthlyRecord] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(MonthlyRecord(
                month=row["month"].strip(),
                ad_spend_ntd=int(row["ad_spend_ntd"]),
                revenue_ntd=int(row["revenue_ntd"]),
                is_peak_season=row["is_peak_season"].strip().lower() in ("true", "1", "y", "yes"),
                is_holiday_promo=row["is_holiday_promo"].strip().lower() in ("true", "1", "y", "yes"),
                launched_new_product=row["launched_new_product"].strip().lower() in ("true", "1", "y", "yes"),
            ))
    return records


# === Naive ATE: 不控制 confounders ===
@dataclass
class NaiveEstimate:
    n_treated: int
    n_control: int
    mean_revenue_treated: int
    mean_revenue_control: int
    naive_ate: int                   # 平均差


def compute_naive_ate(records: list[MonthlyRecord]) -> NaiveEstimate:
    treated = [r.revenue_ntd for r in records if is_treated(r)]
    control = [r.revenue_ntd for r in records if not is_treated(r)]
    if not treated or not control:
        return NaiveEstimate(
            n_treated=len(treated), n_control=len(control),
            mean_revenue_treated=int(statistics.mean(treated)) if treated else 0,
            mean_revenue_control=int(statistics.mean(control)) if control else 0,
            naive_ate=0,
        )
    mt = statistics.mean(treated)
    mc = statistics.mean(control)
    return NaiveEstimate(
        n_treated=len(treated),
        n_control=len(control),
        mean_revenue_treated=int(mt),
        mean_revenue_control=int(mc),
        naive_ate=int(mt - mc),
    )


# === Backdoor-adjusted ATE: 分層估計 ===
@dataclass
class StratumEstimate:
    stratum_key: tuple[bool, bool, bool]   # (peak_season, holiday_promo, new_product)
    n_treated: int
    n_control: int
    n_total: int
    mean_revenue_treated: int | None
    mean_revenue_control: int | None
    stratum_ate: int | None                # diff 內;若 stratum 內 missing 一邊則為 None
    weight: float                          # P(Z=z) = n_total / total


@dataclass
class AdjustedEstimate:
    total_records: int
    strata: list[StratumEstimate]
    adjusted_ate: int                      # 加權平均
    n_valid_strata: int                    # 兩邊都有資料的 strata 數
    confounders: tuple[str, ...]


CONFOUNDER_NAMES = ("is_peak_season", "is_holiday_promo", "launched_new_product")


def _stratum_key(r: MonthlyRecord) -> tuple[bool, bool, bool]:
    return (r.is_peak_season, r.is_holiday_promo, r.launched_new_product)


def compute_backdoor_adjusted_ate(records: list[MonthlyRecord]) -> AdjustedEstimate:
    """ATE = Σ_z [E[Y|T=1, Z=z] - E[Y|T=0, Z=z]] × P(Z=z)。"""
    # 按 stratum 分群
    strata_map: dict[tuple[bool, bool, bool], list[MonthlyRecord]] = {}
    for r in records:
        strata_map.setdefault(_stratum_key(r), []).append(r)

    total = len(records)
    strata: list[StratumEstimate] = []
    weighted_sum_ate = 0.0
    total_weight_for_valid = 0.0

    # 也輸出無資料的可能 strata(用於 sanity 顯示)
    all_possible_keys = list(product([False, True], repeat=3))
    for key in all_possible_keys:
        bucket = strata_map.get(key, [])
        if not bucket:
            strata.append(StratumEstimate(
                stratum_key=key, n_treated=0, n_control=0, n_total=0,
                mean_revenue_treated=None, mean_revenue_control=None,
                stratum_ate=None, weight=0.0,
            ))
            continue
        treated = [r.revenue_ntd for r in bucket if is_treated(r)]
        control = [r.revenue_ntd for r in bucket if not is_treated(r)]
        weight = len(bucket) / total
        if treated and control:
            mt = statistics.mean(treated)
            mc = statistics.mean(control)
            ate = mt - mc
            weighted_sum_ate += ate * weight
            total_weight_for_valid += weight
            strata.append(StratumEstimate(
                stratum_key=key, n_treated=len(treated), n_control=len(control),
                n_total=len(bucket),
                mean_revenue_treated=int(mt),
                mean_revenue_control=int(mc),
                stratum_ate=int(ate),
                weight=round(weight, 4),
            ))
        else:
            strata.append(StratumEstimate(
                stratum_key=key, n_treated=len(treated), n_control=len(control),
                n_total=len(bucket),
                mean_revenue_treated=int(statistics.mean(treated)) if treated else None,
                mean_revenue_control=int(statistics.mean(control)) if control else None,
                stratum_ate=None,
                weight=round(weight, 4),
            ))

    # 把不全的 strata 權重歸零後 normalize
    if total_weight_for_valid > 0:
        adjusted = weighted_sum_ate / total_weight_for_valid
    else:
        adjusted = 0.0

    return AdjustedEstimate(
        total_records=total,
        strata=strata,
        adjusted_ate=int(adjusted),
        n_valid_strata=sum(1 for s in strata if s.stratum_ate is not None),
        confounders=CONFOUNDER_NAMES,
    )


# === Confounder bias decomposition ===
@dataclass
class ConfounderBias:
    confounder: str
    # P(Z=1 | T=1) - P(Z=1 | T=0) — 治療組的 confounder 偏多多少
    prevalence_diff: float
    # 該 confounder 引起的「outcome inflation」≈ prevalence_diff × E[Y|Z=1] - E[Y|Z=0]
    estimated_bias_ntd: int
    interpretation: str


def compute_confounder_bias(records: list[MonthlyRecord]) -> list[ConfounderBias]:
    """估每個 confounder 對 naive ATE 的 bias 貢獻。

    簡化版:用 prevalence diff × outcome diff 的 product 估計。
    """
    treated = [r for r in records if is_treated(r)]
    control = [r for r in records if not is_treated(r)]
    if not treated or not control:
        return []

    out: list[ConfounderBias] = []
    for conf_name in CONFOUNDER_NAMES:
        # 不同 treatment 組的 confounder prevalence
        p_t = sum(1 for r in treated if getattr(r, conf_name)) / len(treated)
        p_c = sum(1 for r in control if getattr(r, conf_name)) / len(control)
        prevalence_diff = p_t - p_c

        # 該 confounder = 1 vs 0 的 outcome diff
        y_z1 = [r.revenue_ntd for r in records if getattr(r, conf_name)]
        y_z0 = [r.revenue_ntd for r in records if not getattr(r, conf_name)]
        if not y_z1 or not y_z0:
            continue
        outcome_diff = statistics.mean(y_z1) - statistics.mean(y_z0)

        bias = prevalence_diff * outcome_diff

        if abs(bias) < 1000:
            interp = f"{conf_name} 對 naive ATE 的 bias 貢獻很小(< NT$1,000)"
        elif bias > 0:
            interp = (
                f"高 ads 月**比**低 ads 月**多** {prevalence_diff*100:.0f}% 在 {conf_name}=True 的時段;"
                f"{conf_name}=True 月份營收**平均高** NT$ {int(outcome_diff):,}。"
                f"這推升 naive ATE 約 NT$ {int(bias):,}(虛假效應)。"
            )
        else:
            interp = (
                f"高 ads 月**比**低 ads 月**少** {abs(prevalence_diff)*100:.0f}% 在 {conf_name}=True 的時段;"
                f"這壓低 naive ATE 約 NT$ {int(bias):,}(實際因果反而被低估)。"
            )

        out.append(ConfounderBias(
            confounder=conf_name,
            prevalence_diff=round(prevalence_diff, 3),
            estimated_bias_ntd=int(bias),
            interpretation=interp,
        ))

    # 排序 by |bias| descending
    out.sort(key=lambda c: abs(c.estimated_bias_ntd), reverse=True)
    return out


# === Top-level summary ===
@dataclass
class CausalAnalysis:
    naive: NaiveEstimate
    adjusted: AdjustedEstimate
    bias_decomp: list[ConfounderBias]
    inflation_factor: float        # naive / adjusted
    verdict: str


def analyze(records: list[MonthlyRecord]) -> CausalAnalysis:
    naive = compute_naive_ate(records)
    adjusted = compute_backdoor_adjusted_ate(records)
    bias = compute_confounder_bias(records)

    if adjusted.adjusted_ate != 0:
        infl = naive.naive_ate / adjusted.adjusted_ate
    else:
        infl = 0.0

    if abs(naive.naive_ate) < 5000:
        verdict = "ad spend 看不出對營收有顯著效應(naive ATE 已接近 0)。"
    elif abs(infl) > 2:
        verdict = (
            f"⚠️ Naive ATE 顯示高 ads 月多賺 NT$ {naive.naive_ate:,}/月,"
            f"但 backdoor-adjusted ATE 只有 NT$ {adjusted.adjusted_ate:,}/月 "
            f"({infl:.1f}x inflation)。**老闆過去 {naive.n_treated + naive.n_control} 個月** "
            f"以為廣告貢獻很大,實際 confounders(季節 / 節慶 / 新品)貢獻了大半。"
        )
    elif abs(infl) > 1.3:
        verdict = (
            f"Naive ATE NT$ {naive.naive_ate:,}/月略高於真實因果 NT$ {adjusted.adjusted_ate:,}/月 "
            f"({infl:.1f}x)。Confounders 有些貢獻但廣告本身效應仍正。"
        )
    elif 0.7 <= abs(infl) <= 1.3:
        verdict = (
            f"Naive ATE NT$ {naive.naive_ate:,}/月跟 adjusted ATE NT$ {adjusted.adjusted_ate:,}/月接近。"
            f"廣告投放與 confounders 沒有顯著相關;naive 估計可信。"
        )
    else:
        verdict = (
            f"Adjusted ATE NT$ {adjusted.adjusted_ate:,}/月 **高於** naive 估計 NT$ {naive.naive_ate:,};"
            f"廣告實際效應被 confounders 抵銷掉一部分,可能是「投了廣告但同時遇到淡季」。"
        )

    return CausalAnalysis(
        naive=naive,
        adjusted=adjusted,
        bias_decomp=bias,
        inflation_factor=round(infl, 2),
        verdict=verdict,
    )
