"""seatplan — 婚禮 / 喜宴座位編排 CSP / Simulated Annealing CLI.

純函式做 CSP optimization (csp.py)。LLM 負責:
  ① 為每桌寫「人話 narrative」(這桌是誰 / 為什麼這樣安排)
  ② 檢視座位 + 給新人 / 婚禮顧問建議(換座位 / 加桌 / 微調)
  ③ 列「潛在風險點」(某桌可能話題太硬 / 太冷 / 文化禁忌)

LLM 永不重新分配座位(那是 CSP 工作)。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from csp import (
    CostBreakdown,
    Guest,
    SeatPlanResult,
    Table,
    TablePlan,
    solve,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣婚禮顧問,專長賓客座位編排與大型宴會社交動態。

    輸入:
      - 純函式 CSP 找出的 seating plan(每桌 guests + groups breakdown)
      - cost_breakdown(violations + cohesion bonus + preferred mismatch)

    工作:
      1. 為每桌寫 60-100 字 narrative,**講故事方式說明**:
         - 這桌的「主題」(新人主桌 / 家族桌 / 同事桌 / 同學桌)
         - 重點賓客介紹(VIP / 主管 / 家族長輩)
         - 預期的桌上氛圍(熱絡 / 嚴肅 / 懷舊 / 商務)
         - 若有跨 group 安排(如新郎家族桌有新娘的人),解釋為什麼這樣 OK
      2. 列「潛在風險點」(3-5 條):
         - 哪一桌話題可能尷尬(陌生 group 同桌)
         - 哪些座位需要新人 / 司儀特別關照
         - 飲酒 / 文化禁忌(VIP 長輩附近不要安排酗酒朋友)
      3. 給新人 / 婚禮顧問「最終調整建議」(2-3 條):
         - 是否該手動 swap 2 個人讓某桌更和諧
         - 是否該補座位卡 / 名牌
         - 司儀 / 流程上的提醒

    硬規則:
      - 你**絕不**重新分配座位 — CSP solver 的工作
      - 你**絕不**評論賓客個人(只看 group / VIP / relations)
      - 用台灣婚禮業在地用語(主桌 / 包桌 / 圓桌 / 婚宴流程 / 司儀)

    回覆 JSON:
    {
      "per_table_narratives": [
        {"table_id": "T01", "narrative": "...", "highlights": ["..."]},
        ...
      ],
      "risk_points": ["...", "..."],
      "final_adjustments": ["...", "..."]
    }
""").strip()


def ai_explain(plan: SeatPlanResult, wedding_info: dict) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "wedding_info": wedding_info,
        "tables": [
            {
                "table_id": tp.table_id,
                "table_name": tp.table_name,
                "is_vip": tp.is_vip,
                "n_seated": tp.n_seated,
                "capacity": tp.capacity,
                "groups_breakdown": tp.groups_at_table,
                "guests": [
                    {
                        "guest_id": g.guest_id,
                        "name": g.name,
                        "group": g.group,
                        "is_vip": g.is_vip,
                        "notes": g.notes,
                    }
                    for g in tp.assigned_guests
                ],
            }
            for tp in plan.table_plans
        ],
        "cost_breakdown": {
            "avoid_violations": plan.cost_breakdown.avoid_violations,
            "must_pair_violations": plan.cost_breakdown.must_pair_violations,
            "vip_misplaced": plan.cost_breakdown.vip_misplaced,
            "capacity_overflow": plan.cost_breakdown.capacity_overflow,
            "group_cohesion_bonus": plan.cost_breakdown.group_cohesion_bonus,
            "preferred_group_mismatch": plan.cost_breakdown.preferred_group_mismatch,
            "total_cost": plan.cost_breakdown.total_cost,
        },
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def render_no_ai_report(plan: SeatPlanResult, wedding_info: dict) -> str:
    parts = ["# seatplan 婚禮座位編排報告\n"]
    parts.append("**模式**: 純函式 CSP + Simulated Annealing(免 API key)\n")
    parts.append("## 婚禮資訊\n")
    parts.append(f"- 新人: {wedding_info.get('couple', '')}")
    parts.append(f"- 場地: {wedding_info.get('venue', '')}")
    parts.append(f"- 日期: {wedding_info.get('date', '')}")
    parts.append(f"- 賓客: {plan.n_total_guests} 位 / 桌數: {plan.n_total_tables} / 總容量: {plan.total_capacity}")
    parts.append("")

    cb = plan.cost_breakdown
    parts.append("## CSP 優化結果\n")
    parts.append(f"- **初始 cost**: {plan.optimization_log.initial_cost:.0f}")
    parts.append(f"- **最終 cost**: {plan.optimization_log.final_cost:.0f}")
    parts.append(f"- **改善次數**: {len(plan.optimization_log.improvement_steps)}(SA iter={plan.optimization_log.iterations_run})")
    parts.append("")
    parts.append("### Cost Breakdown(較低越好)\n")
    parts.append("| 維度 | 違反數量 | 說明 |")
    parts.append("|---|---|---|")
    parts.append(f"| 不能同桌違反 | {cb.avoid_violations} | 對 |")
    parts.append(f"| 必同桌違反 | {cb.must_pair_violations} | 對 |")
    parts.append(f"| VIP 不在 VIP 桌 | {cb.vip_misplaced} | 人 |")
    parts.append(f"| 容量超過 | {cb.capacity_overflow} | 人次 |")
    parts.append(f"| 同 group 同桌(bonus) | {cb.group_cohesion_bonus} | 對(越多越好)|")
    parts.append(f"| Preferred group 不符 | {cb.preferred_group_mismatch} | 人 |")
    parts.append("")

    parts.append(f"## 座位編排 ({plan.n_total_tables} 桌)\n")
    for tp in plan.table_plans:
        vip_badge = " ⭐ VIP 主桌" if tp.is_vip else ""
        parts.append(f"### {tp.table_name} ({tp.n_seated}/{tp.capacity}){vip_badge}\n")
        if tp.groups_at_table:
            group_summary = " / ".join(f"{g}: {n}" for g, n in tp.groups_at_table.items())
            parts.append(f"**Group 分布**: {group_summary}\n")
        parts.append("| 座位 | 賓客 | Group | VIP | 備註 |")
        parts.append("|---|---|---|---|---|")
        for i, g in enumerate(tp.assigned_guests, 1):
            vip = "⭐" if g.is_vip else ""
            parts.append(f"| {i} | {g.name} | {g.group} | {vip} | {g.notes or '-'} |")
        parts.append("")

    parts.append("---")
    parts.append("*純函式模式無 AI narrative。AI 模式會為每桌寫故事化 narrative + 風險點 + 最終調整建議。*")
    parts.append("*seatplan 是輔助工具,**最終座位決策**由新人 / 婚禮顧問確認;熟識度 / 文化禁忌仍需人工微調。*")
    return "\n".join(parts)


def render_full_report(plan: SeatPlanResult, wedding_info: dict, ai: dict) -> str:
    parts = ["# seatplan 婚禮座位編排報告\n"]
    parts.append("**模式**: 純函式 CSP / SA + AI 婚禮顧問解讀\n")
    parts.append("## 婚禮資訊\n")
    parts.append(f"- 新人: {wedding_info.get('couple', '')}")
    parts.append(f"- 場地: {wedding_info.get('venue', '')}")
    parts.append(f"- 日期: {wedding_info.get('date', '')}")
    parts.append(f"- 賓客: {plan.n_total_guests} 位 / 桌數: {plan.n_total_tables}")
    parts.append("")

    cb = plan.cost_breakdown
    parts.append("## CSP 優化摘要\n")
    parts.append(f"- 初始 cost {plan.optimization_log.initial_cost:.0f} → 最終 **{plan.optimization_log.final_cost:.0f}**(改善 {len(plan.optimization_log.improvement_steps)} 次)")
    parts.append(f"- 不能同桌違反: **{cb.avoid_violations}** / 必同桌違反: **{cb.must_pair_violations}** / VIP 不在 VIP 桌: **{cb.vip_misplaced}**")
    parts.append(f"- 同 group 同桌 bonus: **{cb.group_cohesion_bonus}** 對 / preferred 不符: **{cb.preferred_group_mismatch}** 人")
    parts.append("")

    narratives = {n["table_id"]: n for n in ai.get("per_table_narratives", [])}

    parts.append(f"## 座位編排 ({plan.n_total_tables} 桌)\n")
    for tp in plan.table_plans:
        vip_badge = " ⭐ VIP 主桌" if tp.is_vip else ""
        parts.append(f"### {tp.table_name} ({tp.n_seated}/{tp.capacity}){vip_badge}\n")
        narr = narratives.get(tp.table_id, {})
        if narr.get("narrative"):
            parts.append(f"**Narrative**: {narr['narrative']}\n")
        if narr.get("highlights"):
            parts.append("**重點**:")
            for h in narr["highlights"]:
                parts.append(f"- {h}")
            parts.append("")
        parts.append("| 座位 | 賓客 | Group | VIP | 備註 |")
        parts.append("|---|---|---|---|---|")
        for i, g in enumerate(tp.assigned_guests, 1):
            vip = "⭐" if g.is_vip else ""
            parts.append(f"| {i} | {g.name} | {g.group} | {vip} | {g.notes or '-'} |")
        parts.append("")

    if ai.get("risk_points"):
        parts.append("## ⚠️ 潛在風險點\n")
        for r in ai["risk_points"]:
            parts.append(f"- {r}")
        parts.append("")

    if ai.get("final_adjustments"):
        parts.append("## 🎯 最終調整建議\n")
        for a in ai["final_adjustments"]:
            parts.append(f"- {a}")
        parts.append("")

    parts.append("---")
    parts.append("*seatplan 是輔助工具,**最終座位決策**由新人 / 婚禮顧問確認;熟識度 / 文化禁忌仍需人工微調。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="seatplan — 婚禮座位編排 CSP / SA")
    p.add_argument("json_path", help="wedding.json (含 wedding_info + tables + guests)")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--max-iter", type=int, default=8000, help="SA 最大 iterations(預設 8000)")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    wedding_info = data.get("wedding_info", {})
    tables = [Table(**t) for t in data["tables"]]
    guests = [Guest(**g) for g in data["guests"]]

    plan = solve(guests, tables, max_iter=args.max_iter)

    if args.no_ai:
        report = render_no_ai_report(plan, wedding_info)
    else:
        ai = ai_explain(plan, wedding_info)
        report = render_full_report(plan, wedding_info, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
