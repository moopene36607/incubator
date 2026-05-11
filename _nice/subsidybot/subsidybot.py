"""subsidybot — 台灣補助通 RAG Q&A

Usage:
    python subsidybot.py samples/sample_query.json
    python subsidybot.py samples/sample_query.json --out answer.md
    python subsidybot.py samples/sample_query.json --no-ai     # 純條件匹配清單

設計重點:
- 補助方案資料庫(`subsidies_db.py`)+ 條件匹配(`retrieval.py`)為純函式
- AI 只負責「對話式回答 + 引用整合」,絕不憑空編補助
- 嚴格規定 AI 只能 cite 從 retrieval 給出的 corpus,not in retrieval = not allowed
- 答覆末段必標「最後核實:請查官方公告」+ 各方案官網連結

ANTHROPIC_API_KEY 在 AI 模式必要(--no-ai 跳過,只列匹配清單)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from retrieval import MatchResult, UserProfile, match_programs
from subsidies_db import SubsidyProgram, all_programs


ANSWER_SYSTEM = """你是台灣補助諮詢助理。你的工作是根據使用者的條件 + 問題,
從**只能** cite 提供的補助方案 corpus 給出專業且實用的回覆。

## 你的角色

- **不是政府官員**,不能保證審查結果
- **不是律師 / 會計師**,不下個案專業判斷
- **是中介層 AI**:幫使用者快速比對符合的補助 + 提供初步建議

## 嚴格規則

1. **絕對只 cite 提供的 corpus**:不在 corpus 中的補助方案、金額、條件 — **絕對不能提**
2. **不編造截止日 / 金額 / 利率**:corpus 沒寫的就說「請查官方公告」
3. **答覆結構**:
   - 開頭一句直接回應問題
   - 列出 1-3 個最符合的方案,每個方案分:
     * 方案名稱 + 主管機關
     * 為什麼符合(從 matched_reasons 引用)
     * 核心金額 / 條件
     * 申請文件
     * **必標**官網連結 + last_updated
   - 若有「接近符合」(soft_match)的,也提一下,並說明差什麼
   - 結尾必加:「以上資訊截至 {corpus 各方案 last_updated 中最新者},申請前請以官方最新公告為準」

## 寫作風格

- 繁體中文,口語但專業
- 第二人稱對話(「您可以…」「建議您先準備…」)
- 不空泛 hype(避免「太棒了」「絕佳機會」)
- 量化資訊優先(金額 / 利率 / 比率 / 期限)

## 輸出格式

直接輸出 markdown 答覆,**不**包前後解說、不重複用戶問題。
"""


def fmt_amount(amount: int) -> str:
    if amount == 0:
        return "非金錢補助(培訓 / 顧問)"
    if amount >= 10000:
        return f"NT${amount:,}"
    return f"NT${amount}"


def render_corpus_for_llm(matches: list[MatchResult]) -> str:
    """將 retrieval 結果序列化成 LLM 可讀的 markdown corpus。"""
    sections: list[str] = []
    for tier_label, tier_status in [
        ("✅ 完全符合條件 (fully_eligible)", "fully_eligible"),
        ("🟡 部分符合 / 接近符合 (soft_match)", "soft_match"),
        ("❌ 明確不符合 (ineligible)", "ineligible"),
    ]:
        tier_matches = [m for m in matches if m.status == tier_status]
        if not tier_matches:
            continue
        sections.append(f"## {tier_label}\n")
        for m in tier_matches:
            p = m.program
            block = [
                f"### {p.code} — {p.name_zh}",
                f"- 主管機關: {p.agency}",
                f"- 類型: {p.category}",
                f"- 上限: {fmt_amount(p.max_amount_twd)}",
                f"- 利率/條款: {p.interest_terms}",
                f"- 資格摘要: {p.eligibility_summary}",
                f"- 申請期: {p.application_deadline}",
                f"- 必備文件: {', '.join(p.required_documents)}",
                f"- 官網: {p.official_url}",
                f"- last_updated: {p.last_updated}",
            ]
            if m.matched_reasons:
                block.append(f"- 為何符合: {'; '.join(m.matched_reasons)}")
            if m.failed_reasons:
                block.append(f"- 為何不符合: {'; '.join(m.failed_reasons)}")
            sections.append("\n".join(block))
            sections.append("")
    return "\n".join(sections)


def llm_answer(profile: UserProfile, question: str, matches: list[MatchResult]) -> str:
    import anthropic

    profile_dict = {
        "age": profile.age,
        "gender": profile.gender,
        "is_new_immigrant": profile.is_new_immigrant,
        "has_business_registered": profile.has_business_registered,
        "business_age_years": profile.business_age_years,
        "employee_count": profile.employee_count,
        "industry": profile.industry,
        "capital_twd": profile.capital_twd,
        "free_text": profile.free_text,
    }
    user = (
        f"## 使用者問題\n\n{question}\n\n"
        f"## 使用者條件\n\n```json\n{json.dumps(profile_dict, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 補助方案 corpus(retrieval 已比對好)\n\n{render_corpus_for_llm(matches)}\n\n"
        "請依規則為使用者撰寫答覆。"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=[{"type": "text", "text": ANSWER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def render_skeleton_answer(profile: UserProfile, question: str,
                           matches: list[MatchResult]) -> str:
    out: list[str] = []
    out.append(f"# 補助查詢結果(無 AI 答覆,純清單)")
    out.append("")
    out.append(f"**問題**: {question}")
    out.append("")
    full = [m for m in matches if m.status == "fully_eligible"]
    soft = [m for m in matches if m.status == "soft_match"]
    bad = [m for m in matches if m.status == "ineligible"]

    if full:
        out.append("## ✅ 完全符合")
        out.append("")
        for m in full:
            out.append(f"- **{m.program.name_zh}** — {fmt_amount(m.program.max_amount_twd)} "
                       f"({m.program.agency})")
        out.append("")
    if soft:
        out.append("## 🟡 接近符合")
        out.append("")
        for m in soft:
            reasons = "; ".join(m.failed_reasons) if m.failed_reasons else "資料未填,建議補資料"
            out.append(f"- **{m.program.name_zh}** — 差: {reasons}")
        out.append("")
    if bad:
        out.append("## ❌ 不符合")
        out.append("")
        for m in bad:
            out.append(f"- **{m.program.name_zh}** — 原因: {'; '.join(m.failed_reasons)}")
        out.append("")
    return "\n".join(out) + "\n"


def render_full_report(profile: UserProfile, question: str, body: str,
                       matches: list[MatchResult]) -> str:
    today = date.today().isoformat()
    out: list[str] = []
    out.append(f"# 台灣補助諮詢報告")
    out.append("")
    out.append(f"**諮詢日**: {today}    **問題**: {question}")
    out.append("")
    out.append("## 用戶條件")
    out.append("")
    rows = [
        ("年齡", str(profile.age) if profile.age else "未填"),
        ("性別", profile.gender or "未填"),
        ("已設立公司 / 商業", "是" if profile.has_business_registered else "否"),
        ("事業設立年限", f"{profile.business_age_years} 年" if profile.business_age_years else "—"),
        ("員工數", str(profile.employee_count) if profile.employee_count else "未填"),
        ("行業", profile.industry or "未填"),
    ]
    for k, v in rows:
        out.append(f"- {k}: {v}")
    out.append("")
    out.append("---")
    out.append("")
    out.append(body)
    out.append("")
    out.append("---")
    out.append("")
    out.append(f"*由 subsidybot 自動產生於 {today}。corpus 限定 8 個常見補助方案,"
               f"實際更多方案請至 [創業台灣](https://startup.taiwan.gov.tw/) 查詢。"
               f"申請前請務必確認最新官方公告。*")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="user profile + question JSON")
    parser.add_argument("--out", type=Path, help="輸出 markdown 路徑")
    parser.add_argument("--no-ai", action="store_true", help="不呼叫 AI,輸出純條件匹配清單")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    profile_data = payload["profile"]
    profile = UserProfile(
        age=profile_data.get("age"),
        gender=profile_data.get("gender"),
        is_new_immigrant=bool(profile_data.get("is_new_immigrant", False)),
        has_business_registered=bool(profile_data.get("has_business_registered", False)),
        business_age_years=profile_data.get("business_age_years"),
        employee_count=profile_data.get("employee_count"),
        industry=profile_data.get("industry"),
        capital_twd=profile_data.get("capital_twd"),
        free_text=profile_data.get("free_text", ""),
    )
    question = payload.get("question", "請推薦適合的補助方案")
    matches = match_programs(profile)

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,輸出純清單版", file=sys.stderr)

    if use_ai:
        body = llm_answer(profile, question, matches)
        report = render_full_report(profile, question, body, matches)
    else:
        report = render_skeleton_answer(profile, question, matches)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
