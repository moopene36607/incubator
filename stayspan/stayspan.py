"""stayspan — 台灣 SME 員工 retention 時間分析 CLI(Survival Analysis).

純函式做所有 KM curve + cohort 比較(survival.py)。LLM 只負責:
  ① 用老闆易懂的話解釋 Kaplan-Meier 曲線意義
  ② 指出最危險 cohort(誰最容易離職)+ 高危時點(幾月內)
  ③ 給 4-5 條具體留任行動建議(訓練 / 加薪 / 1-on-1 / 角色轉換)
  ④ 計算預估「省下的招聘 / 培訓成本」

LLM 永不算 NT$ / 留任率 / hazard ratio。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from survival import (
    CohortSurvival,
    HazardComparison,
    SurvivalAnalysis,
    analyze,
    load_csv,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣中小企業 HR / People Operations 顧問。

    輸入:
      - 公司 employee retention 資料的純函式分析(KM 曲線 + cohort 比較 +
        hazard ratio)

    工作:
      1. 用 150-200 字解釋現況:
         - 中位數留任(median tenure)是 X 月,意思是「半數員工會在 X 月離職」
         - 12 月留任率 Y% — 一年內有 (100-Y)% 員工離職
         - 哪個維度差異最大(部門 vs 職級 vs 績效)
      2. 找出「最危險 cohort」(12 月留任率最低)+「最穩定 cohort」(最高)
         - 用具體部門 / 績效等說明
         - 估算「離職成本」:每位 NT$50-100K(招聘 + 培訓 + 上手期失能)
      3. 4-5 條具體留任行動建議(優先順序 #1 最關鍵):
         - 高危 cohort 的針對性 intervention(訓練 / 加薪 / 角色轉換 / 1-on-1)
         - 早期警示信號(離職前 1-3 月通常觀察到什麼)
         - 入職前 6 月為何最危險 + 6 月留任活動
      4. 警示:Sample 小(< 30 員工)結論信賴度有限,要持續累積資料

    硬規則:
      - 你**絕不**重算 NT$ / 留任率 — 直接引用 analysis
      - 不勸老闆「立刻開除低績效」— 留任目標應該是「轉換 / 培訓」優先
      - 不歧視性別 / 年齡 — 純看績效 / 部門 / 職級
      - 用台灣繁體中文 + 在地用語(留任 / 招聘 / 培訓 / 1-on-1 / 績效)

    回覆 JSON:
    {
      "executive_summary": "150-200 字現況解釋",
      "most_at_risk_cohort": {
        "description": "...",
        "survival_12mo": ...,
        "estimated_annual_loss_ntd": ...,
        "reasoning": "..."
      },
      "most_stable_cohort": {
        "description": "...",
        "survival_12mo": ...,
        "reasoning": "..."
      },
      "action_recommendations": [
        {"priority": 1, "target_cohort": "...", "action": "...", "expected_impact": "..."},
        ...
      ],
      "early_warning_signals": ["..."],
      "important_caveats": ["..."]
    }
""").strip()


# === Display helpers ===
LEVEL_BADGE = {
    "Engineering": "👨‍💻 Engineering",
    "Marketing": "📢 Marketing",
    "Sales": "💼 Sales",
    "Ops": "⚙️ Ops",
    "Junior": "Junior",
    "Mid": "Mid",
    "Senior": "Senior",
    "Low": "Low",
    "High": "High",
}


def ai_explain(records_count: int, analysis: SurvivalAnalysis) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "n_employees": records_count,
        "n_left": analysis.n_left,
        "n_still": analysis.n_still,
        "median_tenure_months": analysis.overall_median_tenure,
        "overall_survival_12mo": analysis.overall_survival_12mo,
        "overall_survival_24mo": analysis.overall_survival_24mo,
        "overall_survival_36mo": analysis.overall_survival_36mo,
        "by_department": [
            {
                "group": c.group_value,
                "n_employees": c.n_employees,
                "n_left": c.n_left,
                "survival_12mo": c.survival_12mo,
                "survival_24mo": c.survival_24mo,
                "median_tenure": c.median_tenure,
            }
            for c in analysis.by_department
        ],
        "by_level": [
            {
                "group": c.group_value,
                "n_employees": c.n_employees,
                "n_left": c.n_left,
                "survival_12mo": c.survival_12mo,
                "median_tenure": c.median_tenure,
            }
            for c in analysis.by_level
        ],
        "by_performance": [
            {
                "group": c.group_value,
                "n_employees": c.n_employees,
                "n_left": c.n_left,
                "survival_12mo": c.survival_12mo,
                "median_tenure": c.median_tenure,
            }
            for c in analysis.by_performance
        ],
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


def render_no_ai_report(a: SurvivalAnalysis) -> str:
    parts = ["# stayspan 員工留任時間分析報告\n"]
    parts.append("**模式**: 純函式 Kaplan-Meier 留任曲線(免 API key)\n")
    parts.append(f"## 資料概況\n")
    parts.append(f"- **員工總數**: {a.n_total}")
    parts.append(f"- **已離職**: {a.n_left}({a.n_left*100//a.n_total}%)")
    parts.append(f"- **在職(censored)**: {a.n_still}({a.n_still*100//a.n_total}%)")
    parts.append("")

    parts.append("## 整體 KM 留任曲線\n")
    parts.append(f"- **中位數留任**: {a.overall_median_tenure or '> 觀察期'} 月")
    parts.append(f"- **12 月留任率**: **{a.overall_survival_12mo*100:.1f}%**(=一年內離職率 {(1-a.overall_survival_12mo)*100:.1f}%)")
    parts.append(f"- **24 月留任率**: {a.overall_survival_24mo*100:.1f}%")
    parts.append(f"- **36 月留任率**: {a.overall_survival_36mo*100:.1f}%")
    parts.append("")
    parts.append("### KM 曲線細節(只列 event 時間)\n")
    parts.append("| 時間 (月) | At Risk | Events | 累積留任率 |")
    parts.append("|---|---|---|---|")
    for p in a.overall_km:
        parts.append(f"| {p.time_months} | {p.n_at_risk} | {p.n_events} | {p.survival_prob:.4f} |")
    parts.append("")

    parts.append("## 各部門留任比較(危險→穩定)\n")
    parts.append("| 部門 | n | 已離 | S(12) | S(24) | 中位數 |")
    parts.append("|---|---|---|---|---|---|")
    for c in a.by_department:
        median_str = f"{c.median_tenure} 月" if c.median_tenure is not None else "> 觀察期"
        parts.append(f"| {c.group_value} | {c.n_employees} | {c.n_left} | {c.survival_12mo*100:.1f}% | {c.survival_24mo*100:.1f}% | {median_str} |")
    parts.append("")

    parts.append("## 各職級留任比較\n")
    parts.append("| 職級 | n | 已離 | S(12) | S(24) | 中位數 |")
    parts.append("|---|---|---|---|---|---|")
    for c in a.by_level:
        median_str = f"{c.median_tenure} 月" if c.median_tenure is not None else "> 觀察期"
        parts.append(f"| {c.group_value} | {c.n_employees} | {c.n_left} | {c.survival_12mo*100:.1f}% | {c.survival_24mo*100:.1f}% | {median_str} |")
    parts.append("")

    parts.append("## 各績效等級留任比較(最有預測力)\n")
    parts.append("| 績效 | n | 已離 | S(12) | S(24) | 中位數 |")
    parts.append("|---|---|---|---|---|---|")
    for c in a.by_performance:
        median_str = f"{c.median_tenure} 月" if c.median_tenure is not None else "> 觀察期"
        parts.append(f"| {c.group_value} | {c.n_employees} | {c.n_left} | {c.survival_12mo*100:.1f}% | {c.survival_24mo*100:.1f}% | {median_str} |")
    parts.append("")

    parts.append("## Hazard Comparisons\n")
    if a.dept_hazard:
        parts.append(f"- **部門**: {a.dept_hazard.interpretation}")
    if a.level_hazard:
        parts.append(f"- **職級**: {a.level_hazard.interpretation}")
    if a.perf_hazard:
        parts.append(f"- **績效**: {a.perf_hazard.interpretation}")
    parts.append("")
    parts.append("---")
    parts.append("*純函式模式無 AI 建議與離職成本估算。AI 模式會給 4-5 條具體留任行動 + 高危 cohort + 早期警示信號。*")
    parts.append("*stayspan 提供 retention 風險指引,**不建議用作個別員工開除依據**。整體 cohort 趨勢才是政策設計用途。*")
    return "\n".join(parts)


def render_full_report(a: SurvivalAnalysis, ai: dict) -> str:
    parts = ["# stayspan 員工留任時間分析報告\n"]
    parts.append("**模式**: 純函式 Kaplan-Meier + AI HR 顧問\n")
    parts.append(f"## 資料概況\n")
    parts.append(f"- **員工總數**: {a.n_total} / 已離職 {a.n_left} / 在職 {a.n_still}")
    parts.append("")

    parts.append("## Executive Summary\n")
    parts.append(ai.get("executive_summary", ""))
    parts.append("")

    parts.append("## 整體留任數字\n")
    parts.append(f"- **中位數留任**: {a.overall_median_tenure or '> 觀察期'} 月")
    parts.append(f"- **12 月留任率**: **{a.overall_survival_12mo*100:.1f}%**")
    parts.append(f"- **24 月留任率**: {a.overall_survival_24mo*100:.1f}%")
    parts.append(f"- **36 月留任率**: {a.overall_survival_36mo*100:.1f}%")
    parts.append("")

    parts.append("### KM 曲線\n")
    parts.append("| 時間 (月) | At Risk | Events | 累積留任率 |")
    parts.append("|---|---|---|---|")
    for p in a.overall_km:
        parts.append(f"| {p.time_months} | {p.n_at_risk} | {p.n_events} | {p.survival_prob:.4f} |")
    parts.append("")

    if ai.get("most_at_risk_cohort"):
        cohort = ai["most_at_risk_cohort"]
        parts.append("## 🔴 最危險 cohort\n")
        parts.append(f"- **描述**: {cohort.get('description', '')}")
        parts.append(f"- **12 月留任率**: {cohort.get('survival_12mo', 0)*100:.1f}%")
        parts.append(f"- **預估年度離職成本**: NT$ {cohort.get('estimated_annual_loss_ntd', 0):,}")
        parts.append(f"- {cohort.get('reasoning', '')}")
        parts.append("")
    if ai.get("most_stable_cohort"):
        cohort = ai["most_stable_cohort"]
        parts.append("## 🟢 最穩定 cohort\n")
        parts.append(f"- **描述**: {cohort.get('description', '')}")
        parts.append(f"- **12 月留任率**: {cohort.get('survival_12mo', 0)*100:.1f}%")
        parts.append(f"- {cohort.get('reasoning', '')}")
        parts.append("")

    parts.append("## 各維度留任比較\n")
    parts.append("### 部門")
    parts.append("| 部門 | n | 已離 | S(12) | S(24) | 中位數 |")
    parts.append("|---|---|---|---|---|---|")
    for c in a.by_department:
        median_str = f"{c.median_tenure} 月" if c.median_tenure is not None else "> 觀察期"
        parts.append(f"| {c.group_value} | {c.n_employees} | {c.n_left} | {c.survival_12mo*100:.1f}% | {c.survival_24mo*100:.1f}% | {median_str} |")
    parts.append("\n### 績效等級(最有預測力)")
    parts.append("| 績效 | n | 已離 | S(12) | S(24) | 中位數 |")
    parts.append("|---|---|---|---|---|---|")
    for c in a.by_performance:
        median_str = f"{c.median_tenure} 月" if c.median_tenure is not None else "> 觀察期"
        parts.append(f"| {c.group_value} | {c.n_employees} | {c.n_left} | {c.survival_12mo*100:.1f}% | {c.survival_24mo*100:.1f}% | {median_str} |")
    parts.append("")

    parts.append("## 具體留任行動建議\n")
    for item in ai.get("action_recommendations", []):
        parts.append(f"### #{item.get('priority', '?')} 目標:{item.get('target_cohort', '?')}")
        parts.append(f"- **行動**: {item.get('action', '')}")
        parts.append(f"- **預期效果**: {item.get('expected_impact', '')}")
        parts.append("")

    if ai.get("early_warning_signals"):
        parts.append("## ⚠️ 早期警示信號\n")
        for s in ai["early_warning_signals"]:
            parts.append(f"- {s}")
        parts.append("")

    if ai.get("important_caveats"):
        parts.append("## 重要 caveats\n")
        for c in ai["important_caveats"]:
            parts.append(f"- {c}")
        parts.append("")

    parts.append("---")
    parts.append("*stayspan 提供 retention 風險指引,**不建議用作個別員工開除依據**。整體 cohort 趨勢才是政策設計用途。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="stayspan — SME 員工留任時間分析")
    p.add_argument("csv", help="員工資料 CSV")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    records = load_csv(args.csv)
    a = analyze(records)

    if args.no_ai:
        report = render_no_ai_report(a)
    else:
        ai = ai_explain(len(records), a)
        report = render_full_report(a, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
