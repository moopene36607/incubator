"""tenderwatch — 台灣政府標案 AI 即時警示

Usage:
    # 結構化 JSON(免 API key,只跑硬條件過濾)
    python tenderwatch.py --tenders samples/sample_tenders.json \\
        --profile samples/sample_user_profile.json --no-ai

    # 完整 AI semantic match(需 API key)
    python tenderwatch.py --tenders samples/sample_tenders.json \\
        --profile samples/sample_user_profile.json --out report.md

設計重點:
- 硬條件過濾(資本額 / 預算 / 截止日 / 類別 / 認證)100% 純函式
- LLM 只對通過硬條件的標案做 semantic match scoring
- LLM 的 score 不影響硬條件,只影響排序

ANTHROPIC_API_KEY 在 AI 模式必要。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from tender_filter import (
    FilterResult,
    Tender,
    UserProfile,
    _days_until,
    filter_all,
)


SCORING_SYSTEM = """你是台灣政府標案匹配助理。我會給你「公司能力描述」+「標案內容」,
你的任務是評估「這家公司能不能順利執行這個標案」並給 0-100 分。

## 評分 rubric

- **90-100**: 公司核心能力 80%+ 直接命中,過去做過幾乎一樣的案。
- **70-89**: 公司能力 60%+ 命中,需要 minor extension 但可勝任。
- **50-69**: 部分相關,需要找合作夥伴或新進員工才能完整 deliver。
- **30-49**: 邊緣相關,風險高,不建議投標。
- **0-29**: 跟公司方向幾乎無關。

## 輸出格式 (只回 JSON,不要其他文字)

```json
{
  "score": <0-100 整數>,
  "match_level": "high | medium | low | none",
  "key_match_points": ["...具體匹配點 1", "...點 2"],
  "key_gaps": ["...缺少的能力 1", "...缺少 2"],
  "recommendation": "建議投標 | 建議找夥伴後投標 | 不建議投標"
}
```

## 規則

- 只用「公司能力描述」與「標案內容」中的事實,不要編造公司沒提到的能力
- key_match_points 與 key_gaps 必須引用標案描述中的具體詞彙(技術 / 產業 / 服務內容)
- score 70+ 才回 "high",30-69 是 "medium / low",30- 是 "none"
"""


@dataclass
class SemanticScore:
    score: int
    match_level: str
    key_match_points: list[str]
    key_gaps: list[str]
    recommendation: str


def llm_score_tender(profile: UserProfile, tender: Tender) -> SemanticScore:
    import anthropic

    payload = {
        "公司能力描述": profile.capability_description,
        "公司資本額": profile.capital_twd,
        "公司員工數": profile.employee_count,
        "標案名稱": tender.title,
        "標案類別": tender.category,
        "標案描述": tender.description,
        "預算 NT$": tender.budget_twd,
        "主管機關": tender.agency,
    }
    user_msg = (
        f"請評估匹配度:\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": SCORING_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON: {raw}")
    parsed = json.loads(raw[start : end + 1])
    return SemanticScore(
        score=int(parsed["score"]),
        match_level=parsed.get("match_level", "low"),
        key_match_points=list(parsed.get("key_match_points", [])),
        key_gaps=list(parsed.get("key_gaps", [])),
        recommendation=parsed.get("recommendation", "(待評估)"),
    )


def load_tenders(path: Path) -> list[Tender]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        Tender(
            case_no=t["case_no"], title=t["title"], agency=t["agency"],
            category=t["category"], budget_twd=int(t["budget_twd"]),
            posted_date=t["posted_date"], deadline_date=t["deadline_date"],
            description=t["description"],
            required_capital_twd=int(t.get("required_capital_twd", 0)),
            required_certs=tuple(t.get("required_certs", [])),
            location=t.get("location", "全國"),
        )
        for t in payload["tenders"]
    ]


def load_profile(path: Path) -> UserProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return UserProfile(
        company_name=payload["company_name"],
        capital_twd=int(payload["capital_twd"]),
        employee_count=int(payload["employee_count"]),
        capability_description=payload["capability_description"],
        min_tender_budget_twd=int(payload.get("min_tender_budget_twd", 0)),
        max_tender_budget_twd=payload.get("max_tender_budget_twd"),
        excluded_categories=tuple(payload.get("excluded_categories", [])),
        iso_certifications=tuple(payload.get("iso_certifications", [])),
        minimum_days_to_deadline=int(payload.get("minimum_days_to_deadline", 7)),
    )


def render_report(profile: UserProfile, today: date,
                  passed: list[FilterResult], failed: list[FilterResult],
                  scored: list[tuple[FilterResult, SemanticScore]] | None) -> str:
    out: list[str] = []
    out.append(f"# {profile.company_name} — 政府標案 AI 警示報告")
    out.append("")
    out.append(f"**監控日期**: {today.isoformat()}    "
               f"**公司能力**: {profile.capability_description[:60]}...")
    out.append("")
    out.append(f"**今日新公告**: {len(passed) + len(failed)} 件 → "
               f"通過硬條件 **{len(passed)}** 件 / 不適合 **{len(failed)}** 件")
    out.append("")

    if scored:
        # 依 score 降序排
        scored_sorted = sorted(scored, key=lambda x: -x[1].score)
        out.append("## 🎯 高匹配度標案(建議優先評估)")
        out.append("")
        for fr, s in scored_sorted:
            t = fr.tender
            days = _days_until(t.deadline_date, today)
            icon = "🔥" if s.score >= 80 else ("✅" if s.score >= 60 else "🟡")
            out.append(f"### {icon} [{s.score}/100] {t.title}")
            out.append("")
            out.append(f"- **案號**: `{t.case_no}` / **機關**: {t.agency}")
            out.append(f"- **預算**: NT${t.budget_twd:,} / **截止**: {t.deadline_date} (剩 {days} 天)")
            out.append(f"- **類別**: {t.category} / **地區**: {t.location}")
            out.append(f"- **匹配級別**: {s.match_level}")
            if s.key_match_points:
                out.append(f"- **核心匹配點**:")
                for p in s.key_match_points:
                    out.append(f"  - ✓ {p}")
            if s.key_gaps:
                out.append(f"- **能力缺口**:")
                for g in s.key_gaps:
                    out.append(f"  - △ {g}")
            out.append(f"- **建議**: **{s.recommendation}**")
            out.append("")

    if not scored:
        out.append("## 通過硬條件的標案(僅列清單,未做 semantic match)")
        out.append("")
        for fr in passed:
            t = fr.tender
            days = _days_until(t.deadline_date, today)
            out.append(f"- `{t.case_no}` **{t.title}** / "
                       f"{t.agency} / NT${t.budget_twd:,} / 剩 {days} 天")
        out.append("")

    if failed:
        out.append("## ❌ 過濾掉的標案(不符合硬條件)")
        out.append("")
        for fr in failed:
            t = fr.tender
            out.append(f"- `{t.case_no}` {t.title} ({t.agency}, NT${t.budget_twd:,})")
            for r in fr.fail_reasons:
                out.append(f"    ✗ {r}")
        out.append("")

    out.append("---")
    out.append("")
    out.append(f"*由 tenderwatch 自動產生於 {today.isoformat()}。"
               f"硬條件過濾 100% 純函式可重現,LLM 只負責 semantic match scoring。*")
    return "\n".join(out) + "\n"


def render_line_alert(profile: UserProfile,
                      scored: list[tuple[FilterResult, SemanticScore]] | None) -> str:
    """產生最緊急的 LINE 推播文字 — 只列 score >= 70 的高匹配標案。"""
    if not scored:
        return ""
    high = [(fr, s) for fr, s in scored if s.score >= 70]
    if not high:
        return f"📭 {profile.company_name} 今日新公告 0 件高匹配標案,辛苦了"
    high.sort(key=lambda x: -x[1].score)
    lines = [f"🔥 {profile.company_name} 標案警示 — 今日 {len(high)} 件高匹配"]
    for fr, s in high:
        t = fr.tender
        lines.append("")
        lines.append(f"⭐ [{s.score}/100] {t.title}")
        lines.append(f"   {t.agency} | NT${t.budget_twd:,} | 截止 {t.deadline_date}")
        if s.key_match_points:
            lines.append(f"   ✓ {s.key_match_points[0]}")
        lines.append(f"   案號: {t.case_no}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenders", type=Path, required=True, help="標案 JSON 檔")
    parser.add_argument("--profile", type=Path, required=True, help="公司 capability profile JSON")
    parser.add_argument("--today", help="模擬今日日期 YYYY-MM-DD(default 系統日期)")
    parser.add_argument("--out", type=Path, help="markdown 輸出路徑")
    parser.add_argument("--out-line", type=Path, help="LINE 推播純文字輸出路徑")
    parser.add_argument("--no-ai", action="store_true", help="只跑硬條件過濾,不呼叫 LLM")
    args = parser.parse_args()

    if not args.tenders.exists() or not args.profile.exists():
        print("error: 找不到 --tenders 或 --profile", file=sys.stderr)
        return 2

    tenders = load_tenders(args.tenders)
    profile = load_profile(args.profile)
    today = (date.fromisoformat(args.today) if args.today else date.today())

    passed, failed = filter_all(tenders, profile, today)

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,改用 --no-ai 模式", file=sys.stderr)

    scored: list[tuple[FilterResult, SemanticScore]] | None = None
    if use_ai and passed:
        print(f"info: 對 {len(passed)} 件通過硬條件的標案做 semantic match...", file=sys.stderr)
        scored = [(fr, llm_score_tender(profile, fr.tender)) for fr in passed]

    report = render_report(profile, today, passed, failed, scored)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"已寫入 markdown: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)

    if args.out_line and scored is not None:
        line_text = render_line_alert(profile, scored)
        args.out_line.write_text(line_text, encoding="utf-8")
        print(f"已寫入 LINE 推播: {args.out_line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
