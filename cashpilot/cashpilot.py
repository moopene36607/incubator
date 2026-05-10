"""cashpilot — 中小企業現金流 Monte-Carlo 模擬器 CLI.

純函式做 2000 次 Monte-Carlo 模擬(simulator.py),LLM 只負責:
  ① 為純函式統計結果寫人話解釋(中小企業老闆易讀)
  ② 給 3-5 條具體可執行建議(縮短應收 / 砍變動成本 / 找信用額度 / 拒大單)
  ③ 比較「不接 vs 接大單」兩情境的差異 + 取捨建議

LLM 永遠不算機率 / NT$。

模式:
  --no-ai  純函式模擬 + 統計輸出
  full     加上 Claude 解釋與建議
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import asdict
from pathlib import Path

from simulator import (
    CompanyProfile,
    MonteCarloSummary,
    classify_risk,
    compare_scenarios,
    run_monte_carlo,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣中小企業財務顧問,專長現金流風險管理。

    輸入:
      - 公司 profile(營收、成本、應收天數、起始現金等)
      - Monte-Carlo 統計(2000 次模擬,純函式計算的「現金破洞機率」+ 各百分位餘額)
      - 可能附帶「接大單情境」vs「不接大單情境」對照

    工作:
      1. 用老闆看得懂的中文解釋 baseline 風險(< 100 字)
      2. 若有大單情境,寫:
         - 接 vs 不接 對 cash 的影響(引用具體 NT$ 差異)
         - 你的建議:接 / 接但要條件 / 不要接 三選一,並說明理由
      3. 3-5 條具體可執行建議,優先順序排序。涵蓋:
         - 應收帳款管理(調短票期 / 客票貼現 / 應收承購)
         - 變動成本管理(可砍項 + 不能砍項)
         - 信用額度(銀行 RC / 中信銀 SME LOC / 商業承兌)
         - 接案策略(婉拒長票期 + 重定價反映 cost-of-capital)

    硬規則:
      - 你**絕不**重算機率 / 百分位數 / NT$ — 直接引用 summary 數字
      - 你**絕不**推銷特定銀行 / 保險公司 / SaaS 產品(可舉「中信銀 SME LOC」這種一般化例子)
      - 建議聚焦中小企業可立即執行的事,**不要建議 IPO / VC 募資**
      - 用台灣繁體中文 + 在地用語(營運週轉金 / 應收 / 票期 / 中信 / 兆豐 / 銀行融資)

    回覆 JSON:
    {
      "baseline_explanation": "...",
      "big_deal_decision": "推薦 / 條件式推薦 / 不推薦 + 理由",  // 若無大單情境此欄為 null
      "action_items": [
        {"priority": 1, "category": "應收", "action": "...", "expected_impact": "..."},
        ...
      ],
      "warning_signals": ["未來 3 個月若出現 X,需要立刻 ...", "..."]
    }
""").strip()


def ai_explain(
    profile_dict: dict,
    baseline_summary: MonteCarloSummary,
    deal_summary: MonteCarloSummary | None,
    comparison: dict | None,
) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "profile": profile_dict,
        "baseline_summary": _summary_to_dict(baseline_summary),
        "baseline_risk": classify_risk(baseline_summary),
        "deal_summary": _summary_to_dict(deal_summary) if deal_summary else None,
        "deal_risk": classify_risk(deal_summary) if deal_summary else None,
        "comparison": comparison,
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def _summary_to_dict(s: MonteCarloSummary) -> dict:
    return {
        "n_iterations": s.n_iterations,
        "prob_cash_negative_any_month": s.prob_cash_negative_any_month,
        "prob_cash_negative_by_month": s.prob_cash_negative_by_month,
        "p10_min_cash": s.p10_min_cash,
        "p50_min_cash": s.p50_min_cash,
        "p90_min_cash": s.p90_min_cash,
        "p10_end_cash": s.p10_end_cash,
        "p50_end_cash": s.p50_end_cash,
        "p90_end_cash": s.p90_end_cash,
        "avg_end_cash": s.avg_end_cash,
        "avg_min_cash": s.avg_min_cash,
        "worst_month_distribution": s.worst_month_distribution,
        "starting_cash": s.starting_cash,
    }


def render_summary_block(label: str, summary: MonteCarloSummary, risk: dict) -> list[str]:
    parts = [f"## {label}\n"]
    parts.append(f"- **現金破洞機率(12 個月內任一月)**: **{summary.prob_cash_negative_any_month*100:.1f}%**")
    parts.append(f"- **風險等級**: `{risk['risk_level']}`")
    parts.append(f"- **P10 / P50 / P90 最低餘額**: NT$ {summary.p10_min_cash:,} / {summary.p50_min_cash:,} / {summary.p90_min_cash:,}")
    parts.append(f"- **P10 / P50 / P90 年底餘額**: NT$ {summary.p10_end_cash:,} / {summary.p50_end_cash:,} / {summary.p90_end_cash:,}")
    parts.append(f"- **平均年底餘額**: NT$ {summary.avg_end_cash:,}")
    parts.append("")
    parts.append("**逐月現金破洞累積機率**:")
    parts.append("| 月份 | 累積 prob |")
    parts.append("|---|---|")
    for i, p in enumerate(summary.prob_cash_negative_by_month, start=1):
        parts.append(f"| 第 {i} 月底 | {p*100:.1f}% |")
    parts.append("")
    parts.append(f"**最壞月份分布(2000 sim 中 min cash 落在哪個月)**:")
    sorted_dist = sorted(summary.worst_month_distribution.items(), key=lambda x: -x[1])
    for m, count in sorted_dist[:6]:
        parts.append(f"- 第 {m} 月: {count} 次 ({count/summary.n_iterations*100:.1f}%)")
    parts.append("")
    return parts


def render_report(
    profile_dict: dict,
    baseline_summary: MonteCarloSummary,
    deal_summary: MonteCarloSummary | None,
    comparison: dict | None,
    ai: dict | None,
) -> str:
    parts = []
    parts.append(f"# cashpilot 現金流 Monte-Carlo 風險試算 — {profile_dict['name']}\n")
    if ai is None:
        parts.append("**模式**: 純函式 Monte-Carlo(免 API key)\n")
    else:
        parts.append("**模式**: Monte-Carlo 模擬 + AI 顧問解釋與建議\n")
    parts.append("## 公司基本資料\n")
    parts.append(f"- **起始現金**: NT$ {profile_dict['starting_cash']:,}")
    parts.append(f"- **月營收均值 / 標準差**: NT$ {profile_dict['monthly_revenue_mean']:,} ± {profile_dict['monthly_revenue_std']:,}")
    parts.append(f"- **月固定成本**: NT$ {profile_dict['monthly_fixed_cost']:,}(房租 / 薪資 / 軟體訂閱)")
    parts.append(f"- **變動成本比例**: {profile_dict['variable_cost_ratio']*100:.0f}% of 營收(原料 / 物流 / 包裝)")
    parts.append(f"- **應收平均回收**: {profile_dict['ar_collection_days_mean']} 天 ± {profile_dict['ar_collection_days_std']} 天")
    parts.append(f"- **大客戶整年倒帳機率**: {profile_dict['big_customer_default_prob_per_year']*100:.1f}%(發生時損失 {profile_dict['default_loss_ratio']*100:.0f}% 當月應收)")
    if profile_dict.get('big_deal_amount', 0) > 0:
        parts.append(f"- **(評估中)大單**: NT$ {profile_dict['big_deal_amount']:,} / 票期 {profile_dict['big_deal_collection_days']} 天 / 一次性變動成本 NT$ {profile_dict['big_deal_extra_variable_cost']:,}")
    parts.append("")

    parts.extend(render_summary_block(
        "Baseline 情境(現有業務)",
        baseline_summary,
        classify_risk(baseline_summary),
    ))

    if deal_summary is not None:
        parts.extend(render_summary_block(
            "情境 B:接大單後",
            deal_summary,
            classify_risk(deal_summary),
        ))
        parts.append("## 情境對照\n")
        parts.append(f"- {comparison['verdict']}")
        parts.append("")

    if ai is None:
        parts.append("## 純函式風險判定\n")
        parts.append(classify_risk(baseline_summary)["verdict"])
        if deal_summary:
            parts.append("")
            parts.append("**接大單後**: " + classify_risk(deal_summary)["verdict"])
        parts.append("")
        parts.append("---")
        parts.append("*純函式模式無個人化建議。AI 模式會給 3-5 條具體可執行建議 + 接 / 不接大單決策。*")
        return "\n".join(parts)

    # AI mode
    parts.append("## AI 顧問解釋\n")
    parts.append(ai.get("baseline_explanation", ""))
    parts.append("")
    if ai.get("big_deal_decision"):
        parts.append("## 大單決策建議\n")
        parts.append(ai["big_deal_decision"])
        parts.append("")
    parts.append("## 具體行動建議(優先順序排序)\n")
    for item in ai.get("action_items", []):
        parts.append(f"### #{item['priority']} [{item['category']}] {item['action']}")
        parts.append(f"- **預期影響**: {item['expected_impact']}")
        parts.append("")
    if ai.get("warning_signals"):
        parts.append("## 未來需要警覺的訊號\n")
        for w in ai["warning_signals"]:
            parts.append(f"- {w}")
        parts.append("")
    parts.append("---")
    parts.append("*cashpilot 提供現金流風險試算,不是正式財務顧問建議。重大決策請洽會計師 / 銀行貸款專員。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="cashpilot — 中小企業現金流 Monte-Carlo")
    p.add_argument("profile", help="公司 profile JSON")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--n-iter", type=int, default=2000, help="Monte-Carlo 次數(預設 2000)")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    profile_dict = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    valid_fields = set(CompanyProfile.__dataclass_fields__.keys())
    clean = {k: v for k, v in profile_dict.items() if k in valid_fields}

    # Baseline 不含 big deal
    base_args = {**clean, "big_deal_amount": 0, "big_deal_collection_days": 60, "big_deal_extra_variable_cost": 0}
    base_profile = CompanyProfile(**base_args)
    baseline_summary = run_monte_carlo(base_profile, n_iterations=args.n_iter, seed=42)

    deal_summary = None
    comparison = None
    if profile_dict.get("big_deal_amount", 0) > 0:
        with_deal_profile = CompanyProfile(**clean)
        deal_summary = run_monte_carlo(with_deal_profile, n_iterations=args.n_iter, seed=42)
        comparison = compare_scenarios(baseline_summary, deal_summary)

    ai = None
    if not args.no_ai:
        ai = ai_explain(profile_dict, baseline_summary, deal_summary, comparison)

    report = render_report(profile_dict, baseline_summary, deal_summary, comparison, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
