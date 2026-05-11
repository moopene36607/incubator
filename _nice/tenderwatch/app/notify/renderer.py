"""Render daily reports.

Two surfaces:
  * markdown report — long-form, owner reads in dashboard / email digest
  * LINE alert      — plain text, ≤2KB, only score >= 70

Both are pure functions over dict matches so they can be unit-tested without
touching the DB.
"""

from __future__ import annotations

from typing import Any

LINE_ALERT_THRESHOLD = 70


def _score_icon(score: int) -> str:
    if score >= 80:
        return "🔥"
    if score >= 60:
        return "✅"
    return "🟡"


def render_markdown_report(
    profile: dict[str, Any],
    *,
    today: str,
    passed_matches: list[dict],
    failed_matches: list[dict],
) -> str:
    lines: list[str] = []
    company = profile.get("company_name", "")
    lines.append(f"# {company} — 政府標案 AI 警示報告")
    lines.append("")
    lines.append(f"**監控日期**: {today}    "
                 f"**公司能力**: {profile.get('capability_description', '')[:60]}")
    lines.append("")
    lines.append(f"**今日新公告**: 通過硬條件 **{len(passed_matches)}** 件 / "
                 f"不適合 **{len(failed_matches)}** 件")
    lines.append("")

    if passed_matches:
        ranked = sorted(passed_matches, key=lambda m: -(m.get("llm_score") or 0))
        lines.append("## 🎯 高匹配度標案（依 AI 分數排序）")
        lines.append("")
        for m in ranked:
            score = m.get("llm_score") or 0
            icon = _score_icon(score)
            lines.append(f"### {icon} [{score}/100] {m['title']}  `{m['case_no']}`")
            lines.append("")
            lines.append(f"- **機關**: {m.get('agency', '')} / "
                         f"**預算**: NT${m.get('budget_twd', 0):,} / "
                         f"**截止**: {m.get('deadline_date', '')}")
            lines.append(f"- **類別**: {m.get('category', '')} / "
                         f"**地區**: {m.get('location', '')}")
            level = m.get("llm_match_level")
            if level:
                lines.append(f"- **匹配級別**: {level}")
            for p in m.get("llm_key_match_points") or []:
                lines.append(f"  - ✓ {p}")
            for g in m.get("llm_key_gaps") or []:
                lines.append(f"  - △ {g}")
            rec = m.get("llm_recommendation")
            if rec:
                lines.append(f"- **建議**: **{rec}**")
            lines.append("")

    if failed_matches:
        lines.append("## ❌ 過濾掉的標案（不符合硬條件）")
        lines.append("")
        for m in failed_matches:
            lines.append(f"- `{m['case_no']}` {m.get('title', '')} "
                         f"({m.get('agency', '')}, NT${m.get('budget_twd', 0):,})")
            for r in m.get("fail_reasons") or []:
                lines.append(f"    ✗ {r}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*由 tenderwatch 自動產生於 {today}。"
                 "硬條件 100% 純函式可重現,LLM 只負責 semantic match scoring。*")
    return "\n".join(lines) + "\n"


def render_line_alert(profile: dict[str, Any], *, scored_matches: list[dict]) -> str:
    company = profile.get("company_name", "")
    high = [m for m in scored_matches if (m.get("llm_score") or 0) >= LINE_ALERT_THRESHOLD]
    if not high:
        return f"📭 {company} 今日 0 件高匹配標案,辛苦了"

    high.sort(key=lambda m: -(m.get("llm_score") or 0))
    lines = [f"🔥 {company} 標案警示 — 今日 {len(high)} 件高匹配"]
    for m in high:
        score = m.get("llm_score") or 0
        lines.append("")
        lines.append(f"⭐ [{score}/100] {m['title']}")
        lines.append(f"   {m.get('agency', '')} | "
                     f"NT${m.get('budget_twd', 0):,} | "
                     f"截止 {m.get('deadline_date', '')}")
        first_point = (m.get("llm_key_match_points") or [None])[0]
        if first_point:
            lines.append(f"   ✓ {first_point}")
        lines.append(f"   案號: {m['case_no']}")
    return "\n".join(lines)
