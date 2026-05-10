"""cashpilot — 台灣中小企業現金流 Monte-Carlo 模擬器(純函式,no I/O, no LLM).

責任:
  - 接受公司 profile(起始現金、月固定成本、月營收 mean+std、應收回收天數
    分布、大客戶倒帳機率、可選的「假設接大單」情境)
  - 跑 N 次 12 個月模擬
  - 統計現金破洞機率 + P10/P50/P90 餘額 + 最壞月份分布

設計守則:
  - 100% pure stdlib(只用 random + statistics),不依賴 numpy / scipy
  - 所有金額單位 NT$,所有時間單位「月」
  - 每次模擬隨機抽:月營收、應收回收延遲、大客戶倒帳事件、變動成本
  - LLM(cashpilot.py)只解釋結果,絕不重算數字

模擬邏輯:
  - 月營收 ~ Normal(monthly_revenue_mean, monthly_revenue_std),clip ≥ 0
  - 每月新增應收 = 該月營收;依「平均收款天數」分布在後續月份回收
  - 大客戶倒帳:每月伯努利機率 big_customer_default_prob_per_month
    若觸發 → 該月後續應收 × default_loss_rate 沒收回
  - 月支出 = 固定成本 + 變動成本(營收 × variable_cost_ratio)
  - 月底現金 = 上月底現金 + 該月實收 - 該月支出
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field


@dataclass
class CompanyProfile:
    name: str
    starting_cash: int                  # 起始銀行存款
    monthly_revenue_mean: int           # 月營收均值
    monthly_revenue_std: int            # 月營收標準差(波動程度)
    monthly_fixed_cost: int             # 固定成本(房租 / 薪資 / 軟體訂閱)
    variable_cost_ratio: float          # 變動成本佔營收比例(原料 / 包裝 / 物流)
    ar_collection_days_mean: int        # 平均應收回收天數
    ar_collection_days_std: int         # 應收天數標準差
    big_customer_default_prob_per_year: float  # 大客戶整年倒帳機率(0-1)
    default_loss_ratio: float           # 倒帳發生時當月應收損失比例(0-1)
    simulation_months: int = 12         # 模擬月數(預設 12)
    # 可選:本期是否要接「大訂單」情境
    big_deal_amount: int = 0            # 大單金額(0 表示不接)
    big_deal_collection_days: int = 60  # 大單票期(天)
    big_deal_extra_variable_cost: int = 0  # 接大單帶來的一次性變動成本(原料 / 加班)


@dataclass
class SimResult:
    """一次完整 12 月模擬的結果。"""
    monthly_cash_balance: list[int]      # 每月底現金餘額 (length = simulation_months)
    monthly_revenue_actual: list[int]    # 該月實收(現金 in)
    monthly_expense_actual: list[int]    # 該月支出(現金 out)
    cash_negative_first_month: int       # 第幾個月開始現金 < 0(0 = 未發生)
    min_cash_balance: int
    end_cash: int
    big_deal_taken: bool


@dataclass
class MonteCarloSummary:
    n_iterations: int
    simulation_months: int
    big_deal_taken: bool
    prob_cash_negative_any_month: float
    prob_cash_negative_by_month: list[float]  # 每月 prob 累積
    p10_min_cash: int
    p50_min_cash: int
    p90_min_cash: int
    p10_end_cash: int
    p50_end_cash: int
    p90_end_cash: int
    avg_end_cash: int
    avg_min_cash: int
    worst_month_distribution: dict[int, int]  # 哪個月最壞,計數
    starting_cash: int


def _sample_normal_clipped(rng: random.Random, mean: int, std: int, min_value: int = 0) -> int:
    """從 Normal(mean, std) 抽一個,clip 到 ≥ min_value。"""
    v = rng.gauss(mean, std)
    return max(min_value, int(round(v)))


def _sample_ar_distribution(rng: random.Random, mean_days: int, std_days: int) -> dict[int, float]:
    """產出該月營收的「分月回收比例」字典 {month_offset: ratio}。

    例:60 天平均回收 → 回收主要落在 month+2,部分 month+1 和 month+3
    """
    sampled_days = max(0, rng.gauss(mean_days, std_days))
    # 簡化:大部分集中在「平均 days」對應月,但分散到鄰近 2 個月
    avg_month = sampled_days / 30.0
    floor_m = int(avg_month)
    ceil_m = floor_m + 1
    frac = avg_month - floor_m
    # 分散:floor 月拿 (1-frac), ceil 月拿 frac
    out: dict[int, float] = {}
    if floor_m == 0:
        # 0 < days <= 30 表示當月內全部收回(or 部分當月部分下月)
        out[0] = 1.0 - frac
        out[1] = frac
    else:
        out[floor_m] = 1.0 - frac
        out[ceil_m] = frac
    return out


def run_single_simulation(profile: CompanyProfile, rng: random.Random) -> SimResult:
    """跑一次完整 12 月模擬。"""
    months = profile.simulation_months
    monthly_cash = [0] * months
    monthly_rev_actual = [0] * months
    monthly_exp_actual = [0] * months
    cash = profile.starting_cash

    # outstanding_ar: dict[future_month_index] = NT$ to collect
    outstanding_ar: dict[int, int] = {}

    # 將 big deal 視為第 0 月的額外營收(已賣出,但票期延後收)
    if profile.big_deal_amount > 0:
        big_deal_collect_month = max(1, int(round(profile.big_deal_collection_days / 30.0)))
        outstanding_ar[big_deal_collect_month] = (
            outstanding_ar.get(big_deal_collect_month, 0) + profile.big_deal_amount
        )

    # 大客戶倒帳:整年機率攤到每月
    monthly_default_prob = 1 - (1 - profile.big_customer_default_prob_per_year) ** (1 / 12)

    for m in range(months):
        # 1. 該月新生營收(non-big-deal 業務)
        rev_this_month = _sample_normal_clipped(
            rng, profile.monthly_revenue_mean, profile.monthly_revenue_std
        )
        # 2. 該月應收分布
        ar_dist = _sample_ar_distribution(
            rng, profile.ar_collection_days_mean, profile.ar_collection_days_std
        )
        for offset, ratio in ar_dist.items():
            target_month = m + offset
            if target_month < months:
                outstanding_ar[target_month] = outstanding_ar.get(target_month, 0) + int(
                    rev_this_month * ratio
                )
        # 3. 該月實收 = 已到期應收
        collected = outstanding_ar.pop(m, 0)
        # 4. 大客戶倒帳事件
        if rng.random() < monthly_default_prob and collected > 0:
            loss = int(collected * profile.default_loss_ratio)
            collected -= loss
        # 5. 月支出
        variable_cost = int(rev_this_month * profile.variable_cost_ratio)
        if m == 0:
            variable_cost += profile.big_deal_extra_variable_cost  # 接大單第一個月額外成本
        expense = profile.monthly_fixed_cost + variable_cost

        cash = cash + collected - expense
        monthly_cash[m] = cash
        monthly_rev_actual[m] = collected
        monthly_exp_actual[m] = expense

    first_neg = 0
    for i, c in enumerate(monthly_cash, start=1):
        if c < 0:
            first_neg = i
            break

    return SimResult(
        monthly_cash_balance=monthly_cash,
        monthly_revenue_actual=monthly_rev_actual,
        monthly_expense_actual=monthly_exp_actual,
        cash_negative_first_month=first_neg,
        min_cash_balance=min(monthly_cash),
        end_cash=monthly_cash[-1],
        big_deal_taken=profile.big_deal_amount > 0,
    )


def run_monte_carlo(profile: CompanyProfile, n_iterations: int = 2000, seed: int | None = 42) -> MonteCarloSummary:
    """跑 N 次 12 月模擬,回傳統計摘要。"""
    rng = random.Random(seed)
    results: list[SimResult] = []
    for _ in range(n_iterations):
        results.append(run_single_simulation(profile, rng))

    months = profile.simulation_months
    # 計算「現金為負」的機率(任一月 + 每月累積)
    any_neg = sum(1 for r in results if r.cash_negative_first_month > 0) / n_iterations
    cum_by_month: list[float] = []
    for m in range(1, months + 1):
        cnt = sum(1 for r in results if r.cash_negative_first_month and r.cash_negative_first_month <= m)
        cum_by_month.append(round(cnt / n_iterations, 4))

    min_cashes = sorted(r.min_cash_balance for r in results)
    end_cashes = sorted(r.end_cash for r in results)

    def percentile(arr: list[int], p: int) -> int:
        idx = int(len(arr) * p / 100)
        idx = max(0, min(len(arr) - 1, idx))
        return arr[idx]

    worst_month_dist: dict[int, int] = {}
    for r in results:
        worst_month = r.monthly_cash_balance.index(r.min_cash_balance) + 1
        worst_month_dist[worst_month] = worst_month_dist.get(worst_month, 0) + 1

    return MonteCarloSummary(
        n_iterations=n_iterations,
        simulation_months=months,
        big_deal_taken=profile.big_deal_amount > 0,
        prob_cash_negative_any_month=round(any_neg, 4),
        prob_cash_negative_by_month=cum_by_month,
        p10_min_cash=percentile(min_cashes, 10),
        p50_min_cash=percentile(min_cashes, 50),
        p90_min_cash=percentile(min_cashes, 90),
        p10_end_cash=percentile(end_cashes, 10),
        p50_end_cash=percentile(end_cashes, 50),
        p90_end_cash=percentile(end_cashes, 90),
        avg_end_cash=int(statistics.mean(r.end_cash for r in results)),
        avg_min_cash=int(statistics.mean(r.min_cash_balance for r in results)),
        worst_month_distribution=worst_month_dist,
        starting_cash=profile.starting_cash,
    )


# --- 風險等級 + 摘要 ---

def classify_risk(summary: MonteCarloSummary) -> dict:
    """純函式風險分檔(LLM 永不算)。"""
    p_neg = summary.prob_cash_negative_any_month

    if p_neg < 0.05:
        level = "LOW"
        verdict = f"現金破洞機率 {p_neg*100:.1f}% < 5%,財務體質穩健。"
    elif p_neg < 0.15:
        level = "MEDIUM"
        verdict = (
            f"現金破洞機率 {p_neg*100:.1f}%(中等)。建議檢視應收帳款 + 預備備援"
            f"信用額度,P10 最低餘額 NT${summary.p10_min_cash:,}。"
        )
    elif p_neg < 0.35:
        level = "HIGH"
        verdict = (
            f"現金破洞機率 {p_neg*100:.1f}%(高),三分之一以上情境會出問題。"
            f"建議:① 加速應收回收 ② 砍非必要變動成本 ③ 找銀行談備援信用額度 "
            f"NT${abs(summary.p10_min_cash):,}+。"
        )
    else:
        level = "CRITICAL"
        verdict = (
            f"⚠️ 現金破洞機率 {p_neg*100:.1f}%(嚴重),超過三分之一情境會破洞。"
            f"**強烈建議**:① 立即停止接收長票期大單 ② 緊急融資談判 ③ 評估"
            f"非戰略員工 / 成本砍除 ④ 與會計師 / 顧問會診。"
        )

    return {
        "risk_level": level,
        "prob_cash_negative_any_month": p_neg,
        "verdict": verdict,
    }


def compare_scenarios(without: MonteCarloSummary, with_deal: MonteCarloSummary) -> dict:
    """比較「不接大單」vs「接大單」兩情境的差異。"""
    delta_p_neg = with_deal.prob_cash_negative_any_month - without.prob_cash_negative_any_month
    delta_p50_end = with_deal.p50_end_cash - without.p50_end_cash
    delta_p10_min = with_deal.p10_min_cash - without.p10_min_cash

    return {
        "delta_prob_cash_negative": round(delta_p_neg, 4),
        "delta_p50_end_cash": delta_p50_end,
        "delta_p10_min_cash": delta_p10_min,
        "verdict": (
            f"接大單後現金破洞機率變化 {delta_p_neg*100:+.1f}%;"
            f"年末 P50 預估餘額變化 NT${delta_p50_end:+,};"
            f"最壞 10% 情境下最低餘額變化 NT${delta_p10_min:+,}。"
        ),
    }
