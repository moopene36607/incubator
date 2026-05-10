"""hirepath — 中小企業「招專員 vs 外包」全週期 ROI 對照 CLI.

純函式做所有金額計算(comparator.py)。LLM 只負責:
  ① 用老闆易懂的話解釋 cost 分布(雇主負擔 / hidden cost)
  ② 評估 4 個 non-cost factors(品質 / 速度 / 機密性 / 規模化能力)
  ③ 給最終建議:招專員 / 外包 / 混合(短期外包 + 長期內化)
  ④ 給「決策觸發條件」(若未來 X 改變則重新評估)

LLM 永遠不算 NT$。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from comparator import (
    Comparison,
    HireProfile,
    OutsourceProfile,
    compare,
    compute_hire_total_cost,
    compute_outsource_total_cost,
    horizon_sensitivity,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣中小企業 5-30 人公司的 fractional COO 顧問,專長 HR / outsourcing 決策。

    輸入:
      - role 需求描述(用戶自由文字)
      - 兩方案 cost breakdown(純函式算的,LLM 不要重算)
      - comparison + horizon_sensitivity
      - qualitative_signals(純函式發現的警示)

    你的工作:
      1. 用老闆易懂的話解釋 baseline cost 結果(< 150 字):
         - 為什麼月薪 NT$X 變成 effective NT$Y(指出健保 / 勞保 / 勞退 / 三節 / 年終 / 重招風險佔比)
         - 月薪 vs 外包月費的「明面差距」與「實際差距」
      2. 評估 4 個 non-cost factors,每個給 1-5 分:
         - 品質控制(專員 vs 外包)
         - 速度 / 響應時間(緊急任務時)
         - 機密性 / IP 保護(若涉及客戶資料 / 商業機密)
         - 規模化能力(業務量上升時,專員 vs 外包誰更好擴展)
      3. 最終建議:
         - 純成本層面(基於 comparator 數字)
         - 整體層面(成本 + non-cost factors)
         - 三選一:招專員 / 外包 / 混合(短期外包驗證需求 + 第 18 個月內化)
      4. 列「決策觸發條件」(未來若以下任一條件發生則重新評估):
         - 業務量翻倍 / 萎縮
         - 外包廠商漲價超過 X%
         - 公司預計 2 年內擴張到 Y 人以上

    硬規則:
      - 你**絕不**重算金額;直接引用 comparator 數字
      - 你**絕不**勸老闆「無條件選便宜的」— 提醒 non-cost factors
      - 不勸 over-hiring / 不勸 over-outsourcing
      - 用台灣繁體中文 + 在地用語(健保 / 勞保 / 勞退 / 三節 / 年終 / 外包)

    回覆 JSON:
    {
      "cost_explanation": "...",
      "non_cost_factors": {
        "quality": {"hire_score": 4, "outsource_score": 3, "reasoning": "..."},
        "speed": {"hire_score": 5, "outsource_score": 3, "reasoning": "..."},
        "confidentiality": {"hire_score": 5, "outsource_score": 2, "reasoning": "..."},
        "scalability": {"hire_score": 2, "outsource_score": 5, "reasoning": "..."}
      },
      "final_recommendation": {
        "scheme": "招專員 / 外包 / 混合",
        "reasoning": "...",
        "first_concrete_step": "..."
      },
      "decision_triggers": ["未來若 X 發生則重新評估...", "..."]
    }
""").strip()


def ai_explain(
    role_brief: str,
    hire_summary: dict,
    outsource_summary: dict,
    comparison: Comparison,
    sensitivity: list[dict],
) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "role_brief": role_brief,
        "hire_summary": hire_summary,
        "outsource_summary": outsource_summary,
        "comparison": {
            "hire_total": comparison.hire_total,
            "outsource_total": comparison.outsource_total,
            "delta": comparison.delta,
            "cheaper_scheme": comparison.cheaper_scheme,
            "delta_pct": comparison.delta_pct,
            "monthly_savings": comparison.monthly_savings,
            "breakeven_horizon_years": comparison.breakeven_horizon_years,
            "qualitative_signals": comparison.qualitative_signals,
        },
        "horizon_sensitivity": sensitivity,
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


def render_no_ai_report(
    role_brief: str,
    hire_p: HireProfile,
    out_p: OutsourceProfile,
    hire_s: dict,
    out_s: dict,
    c: Comparison,
    sens: list[dict],
) -> str:
    parts = ["# hirepath 招專員 vs 外包 全週期 ROI 對照\n"]
    parts.append("**模式**: 純函式試算(免 API key)\n")
    parts.append("## 角色需求\n")
    parts.append(f"> {role_brief.strip()}")
    parts.append("")
    parts.append("## 評估參數\n")
    parts.append(f"- **角色**: {hire_p.role_name}")
    parts.append(f"- **評估期**: {hire_p.horizon_years} 年")
    parts.append(f"- **方案 A 招專員 月薪**: NT$ {hire_p.monthly_salary:,}")
    parts.append(f"  - 三節獎金 = 月薪 × {hire_p.annual_three_festivals} / 年")
    parts.append(f"  - 年終獎金 = 月薪 × {hire_p.annual_year_end} / 年")
    parts.append(f"  - 預估 1 年離職率: {hire_p.one_year_turnover_rate*100:.0f}%")
    parts.append(f"- **方案 B 外包 月費**: NT$ {out_p.monthly_fee:,}")
    parts.append(f"  - 老闆對接時間: {out_p.management_hours_per_month} hr/月(時薪 NT$ {out_p.owner_hourly_rate:,})")
    parts.append(f"  - 預估年切換風險: {out_p.annual_switch_risk*100:.0f}%")
    parts.append("")

    parts.append("## 方案 A:招專員(in-house)成本拆解\n")
    parts.append(f"- **{hire_p.horizon_years} 年總成本**: **NT$ {hire_s['total_cost']:,}**")
    parts.append(f"- **月化等效成本**: NT$ {hire_s['monthly_effective_cost']:,} / 月")
    parts.append(f"- **預估評估期內離職次數**: {hire_s['expected_replacements_count']}")
    parts.append("\n| 成本項 | 金額 NT$ |")
    parts.append("|---|---|")
    for k, v in hire_s["breakdown"].items():
        parts.append(f"| {k} | {v:,} |")
    parts.append("")

    parts.append("## 方案 B:外包(outsource)成本拆解\n")
    parts.append(f"- **{out_p.horizon_years} 年總成本**: **NT$ {out_s['total_cost']:,}**")
    parts.append(f"- **月化等效成本**: NT$ {out_s['monthly_effective_cost']:,} / 月")
    parts.append(f"- **預估評估期內切換廠商次數**: {out_s['expected_switches_count']}")
    parts.append("\n| 成本項 | 金額 NT$ |")
    parts.append("|---|---|")
    for k, v in out_s["breakdown"].items():
        parts.append(f"| {k} | {v:,} |")
    parts.append("")

    parts.append("## 純函式對照結論\n")
    parts.append(f"- **總成本較低方案**: **{c.cheaper_scheme}**")
    parts.append(f"- **差距**: NT$ {abs(c.delta):,} ({c.delta_pct}%)")
    parts.append(f"- **月化節省**: NT$ {c.monthly_savings:,} / 月")
    if c.breakeven_horizon_years is not None:
        parts.append(f"- **Breakeven horizon**: {c.breakeven_horizon_years} 年")
    parts.append("")
    if c.qualitative_signals:
        parts.append("### ⚠️ 警示訊號(純函式偵測)\n")
        for s in c.qualitative_signals:
            parts.append(f"- {s}")
        parts.append("")

    parts.append("## 不同 horizon 敏感度分析\n")
    parts.append("| 評估期 | 招專員 NT$ | 外包 NT$ | 較便宜 | 差距 % |")
    parts.append("|---|---|---|---|---|")
    for s in sens:
        parts.append(
            f"| {s['horizon_years']} 年 | {s['hire_total']:,} | {s['outsource_total']:,} | "
            f"{s['cheaper']} | {s['delta_pct']}% |"
        )
    parts.append("")
    parts.append("---")
    parts.append("*純函式模式僅做金額對照;**不評估品質 / 速度 / 機密性 / 規模化** 等 non-cost factors。AI 模式會給完整 4 維評估 + 最終建議 + 決策觸發條件。*")
    parts.append("*hirepath 提供決策支持,不是 HR / 法律意見。重大決策請洽會計師 / 勞動部諮詢。*")
    return "\n".join(parts)


def render_full_report(
    role_brief: str,
    hire_p: HireProfile,
    out_p: OutsourceProfile,
    hire_s: dict,
    out_s: dict,
    c: Comparison,
    sens: list[dict],
    ai: dict,
) -> str:
    parts = ["# hirepath 招專員 vs 外包 全週期 ROI 對照\n"]
    parts.append("**模式**: 純函式試算 + AI fractional COO 顧問\n")
    parts.append("## 角色需求\n")
    parts.append(f"> {role_brief.strip()}")
    parts.append("")

    parts.append("## 成本拆解摘要\n")
    parts.append(f"- **方案 A (招專員)**: {hire_p.horizon_years} 年 NT$ {hire_s['total_cost']:,} / 月化 NT$ {hire_s['monthly_effective_cost']:,}")
    parts.append(f"- **方案 B (外包)**: {out_p.horizon_years} 年 NT$ {out_s['total_cost']:,} / 月化 NT$ {out_s['monthly_effective_cost']:,}")
    parts.append(f"- **純成本較低**: {c.cheaper_scheme} (差距 NT$ {abs(c.delta):,} = {c.delta_pct}%)")
    parts.append("")

    parts.append("## AI 解釋:為什麼月薪變成 effective?\n")
    parts.append(ai.get("cost_explanation", ""))
    parts.append("")

    parts.append("## Non-cost factors 評分(1-5 分)\n")
    parts.append("| 維度 | 招專員 | 外包 | 說明 |")
    parts.append("|---|---|---|---|")
    factors = ai.get("non_cost_factors", {})
    factor_labels = {
        "quality": "品質控制",
        "speed": "速度 / 響應",
        "confidentiality": "機密性 / IP",
        "scalability": "規模化能力",
    }
    for key, label in factor_labels.items():
        f = factors.get(key, {})
        parts.append(
            f"| {label} | {f.get('hire_score', '-')} | {f.get('outsource_score', '-')} | "
            f"{f.get('reasoning', '')} |"
        )
    parts.append("")

    parts.append("## 各 horizon 敏感度\n")
    parts.append("| 評估期 | 招專員 | 外包 | 較便宜 | Δ% |")
    parts.append("|---|---|---|---|---|")
    for s in sens:
        parts.append(
            f"| {s['horizon_years']} 年 | NT$ {s['hire_total']:,} | NT$ {s['outsource_total']:,} | "
            f"{s['cheaper']} | {s['delta_pct']}% |"
        )
    parts.append("")

    parts.append("## 最終建議\n")
    rec = ai.get("final_recommendation", {})
    parts.append(f"- **建議方案**: **{rec.get('scheme', '')}**")
    parts.append(f"- **理由**: {rec.get('reasoning', '')}")
    parts.append(f"- **第一個具體行動**: {rec.get('first_concrete_step', '')}")
    parts.append("")

    parts.append("## 決策觸發條件(未來重新評估的訊號)\n")
    for t in ai.get("decision_triggers", []):
        parts.append(f"- {t}")
    parts.append("")

    if c.qualitative_signals:
        parts.append("## 純函式發現的警示\n")
        for s in c.qualitative_signals:
            parts.append(f"- {s}")
        parts.append("")

    parts.append("---")
    parts.append("*hirepath 提供決策支持,不是 HR / 法律意見。實際雇用 / 簽訂外包契約前請洽會計師 / 勞動部諮詢。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="hirepath — 招專員 vs 外包 全週期 ROI 對照")
    p.add_argument("profile", help="profile JSON")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    role_brief = profile.get("role_brief", "")

    hire_fields = HireProfile.__dataclass_fields__.keys()
    out_fields = OutsourceProfile.__dataclass_fields__.keys()
    hire_dict = {k: v for k, v in profile.get("hire", {}).items() if k in hire_fields}
    out_dict = {k: v for k, v in profile.get("outsource", {}).items() if k in out_fields}
    hire_p = HireProfile(**hire_dict)
    out_p = OutsourceProfile(**out_dict)

    hire_s = compute_hire_total_cost(hire_p)
    out_s = compute_outsource_total_cost(out_p)
    c = compare(hire_s, out_s, hire_p, out_p)
    sens = horizon_sensitivity(hire_p, out_p)

    if args.no_ai:
        report = render_no_ai_report(role_brief, hire_p, out_p, hire_s, out_s, c, sens)
    else:
        ai = ai_explain(role_brief, hire_s, out_s, c, sens)
        report = render_full_report(role_brief, hire_p, out_p, hire_s, out_s, c, sens, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
