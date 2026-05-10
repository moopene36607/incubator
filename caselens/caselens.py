"""caselens — 台灣法院判決書個人版檢索 + 賠償區間預估 CLI.

兩階段檢索:
  Stage 1: 純函式 keyword Jaccard 相似度(retriever.py)— 過濾 top 8 候選
  Stage 2: Claude re-rank by 法律相關性(注意「方向 / 角色」/「過失方比例」/
           「傷勢輕重」這些 keyword 無法捕捉的法律語意)→ top 3

最後 LLM 用 top 3 案件預估本案賠償區間 + 列出影響因子。

LLM 永遠不算 NT$(都引用案件 compensation_amount)。
LLM 永遠不下「我替你打官司能贏」這種斷論。

模式:
  --no-ai  純函式 Stage 1 retrieval + 純函式 compensation stats(免 API key)
  full     加上 Stage 2 LLM re-rank + 法律解釋
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from retriever import (
    Candidate,
    CompensationStats,
    compute_compensation_stats,
    extract_legal_keywords,
    find_top_k_candidates,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣法律研究助理(非執業律師)。

    輸入:
      - 使用者的車禍情境描述(自由文字)
      - 純函式 keyword 檢索找出的 Top 8 候選案件(已附 keyword_score)

    工作:
      1. Stage 2 LLM Re-rank: 重新評估 Top 8 候選的「**法律相關性**」(不只是 keyword 重疊):
         - 角色方向(原告被告) — 例「我被追撞」≠「我追撞別人」即使都有「追撞」keyword
         - 違規類型嚴重度(酒駕 / 闖紅燈 / 逆向 / 未禮讓 vs 一般未注意)
         - 過失比例(原告 0% vs 50%+ 對賠償結果差很多)
         - 傷勢輕重(輕傷 / 骨折 / 粉碎性骨折 / 重傷)
      2. 選出 Top 3 最相關案件,寫:
         - 為什麼跟使用者情境相似(具體引用案件事實)
         - 從這個判例可以學到什麼(過失比例參考 / 賠償項目參考 / 加重 / 減輕因子)
      3. 預估本案賠償區間(引用 Top 3 案件的賠償金額 + 純函式中位數 / 範圍,**不要重算**):
         - 低估區間 / 中位數 / 高估區間
         - 賠償組成項目(醫療費 / 工作損失 / 精神慰撫金 / 車輛維修 / 看護費)
      4. 給「實務 takeaway」(對使用者做下一步有幫助的具體建議):
         - 蒐集證據清單(警察報告 / 醫療收據 / 工作損失證明)
         - 三方調解 vs 訴訟取捨
         - 律師費用估算

    硬規則:
      - 你**絕不**保證「會贏」或「會輸」— 只說「實務上常見的處理方式」
      - 你**絕不**重算 compensation_amount — 直接引用案件中已有的金額
      - 不勸完全提告 / 不勸完全不提告 — 由使用者判斷
      - 用台灣繁體中文 + 法律在地用語(過失比例 / 精神慰撫金 / 強制險 / 商業險 / 調解)

    回覆 JSON:
    {
      "reranked_top_3": [
        {"case_id": "...", "relevance_score": 0.85, "why_relevant": "..."},
        ...
      ],
      "predicted_compensation_range": {
        "low_estimate": 100000,
        "mid_estimate": 250000,
        "high_estimate": 450000,
        "reasoning": "..."
      },
      "predicted_responsibility_split": {
        "plaintiff_likely_pct": 10,
        "defendant_likely_pct": 90,
        "reasoning": "..."
      },
      "aggravating_factors": ["..."],     // 提高賠償 / 降低己方過失的因素
      "mitigating_factors": ["..."],      // 降低賠償 / 提高己方過失的因素
      "evidence_checklist": ["..."],
      "next_steps_recommendation": "100-200 字實務建議"
    }
""").strip()


def llm_rerank_and_explain(user_query: str, candidates: list[Candidate]) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "user_query": user_query,
        "top_8_candidates": [
            {
                "case_id": c.case["case_id"],
                "title": c.case["title"],
                "keyword_score": c.keyword_score,
                "matched_keywords": list(c.matched_keywords),
                "summary": c.case["summary"],
                "key_factors": c.case.get("key_factors", []),
                "responsibility_split": c.case.get("responsibility_split", {}),
                "compensation_amount": c.case.get("compensation_amount"),
                "compensation_breakdown": c.case.get("compensation_breakdown", {}),
                "key_holdings": c.case.get("key_holdings", ""),
            }
            for c in candidates
        ],
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
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
    user_query: str,
    query_keywords: set[str],
    candidates: list[Candidate],
    stats: CompensationStats,
) -> str:
    parts = ["# caselens 法院判決書檢索報告\n"]
    parts.append("**模式**: 純函式 Stage 1 keyword 檢索(免 API key)\n")
    parts.append("## 使用者情境\n")
    parts.append(f"> {user_query.strip()}")
    parts.append("")
    parts.append(f"**抽出的法律關鍵字**: {', '.join(sorted(query_keywords))}")
    parts.append("")

    parts.append(f"## Stage 1 Top {len(candidates)} 候選案件(keyword Jaccard 相似度)\n")
    parts.append("⚠️ 純 keyword 檢索無法區分『角色方向』(我被追撞 vs 我追撞別人 都會匹配)。"
                 "**強烈建議**用 AI 模式做 Stage 2 法律相關性 re-rank。")
    parts.append("")
    parts.append("| 排名 | 相似度 | 案號 | 標題 | 原告/被告過失 | 賠償金額 |")
    parts.append("|---|---|---|---|---|---|")
    for i, c in enumerate(candidates, 1):
        rs = c.case.get("responsibility_split", {})
        rs_str = f"{rs.get('plaintiff', 0)}% / {rs.get('defendant', 0)}%"
        amt = c.case.get("compensation_amount", 0)
        parts.append(
            f"| #{i} | {c.keyword_score:.3f} | `{c.case['case_id']}` | "
            f"{c.case['title']} | {rs_str} | NT$ {amt:,} |"
        )
    parts.append("")

    parts.append("## Top 3 案件詳細(僅依 keyword 相似度排序)\n")
    for i, c in enumerate(candidates[:3], 1):
        case = c.case
        parts.append(f"### #{i} `{case['case_id']}` — {case['title']}")
        parts.append(f"- **法院**: {case['court']} / **判決日**: {case['judgment_date']}")
        parts.append(f"- **案件摘要**: {case['summary']}")
        rs = case.get("responsibility_split", {})
        parts.append(f"- **過失比例**: 原告 {rs.get('plaintiff', 0)}% / 被告 {rs.get('defendant', 0)}%")
        parts.append(f"- **賠償金額**: NT$ {case.get('compensation_amount', 0):,}")
        breakdown = case.get("compensation_breakdown", {})
        if breakdown:
            parts.append(f"- **賠償組成**:")
            for k, v in breakdown.items():
                parts.append(f"  - {k}: NT$ {v:,}")
        parts.append(f"- **判決要旨**: {case.get('key_holdings', '')}")
        parts.append("")

    parts.append("## 純函式 Top 3 賠償統計\n")
    parts.append(f"- **賠償金額範圍**: NT$ {stats.min_amount:,} - NT$ {stats.max_amount:,}")
    parts.append(f"- **中位數**: NT$ {stats.median_amount:,}")
    parts.append(f"- **平均**: NT$ {stats.avg_amount:,}")
    parts.append(f"- **原告 0% 過失案件**: {stats.plaintiff_full_no_fault_count} / 3")
    parts.append(f"- **原告部分過失案件**: {stats.plaintiff_partial_fault_count} / 3")
    parts.append(f"- **原告主因案件**: {stats.plaintiff_major_fault_count} / 3")
    parts.append("")
    parts.append("---")
    parts.append("*純函式模式無法律解釋。AI 模式會做 Stage 2 re-rank + 預估本案賠償區間 + 實務建議。*")
    parts.append("*caselens 不是法律意見。實際案件請洽律師。重大爭議可先洽法扶基金會免費諮詢。*")
    return "\n".join(parts)


def render_full_report(
    user_query: str,
    query_keywords: set[str],
    candidates: list[Candidate],
    ai: dict,
) -> str:
    parts = ["# caselens 法院判決書檢索報告\n"]
    parts.append("**模式**: 純函式 Stage 1 檢索 + Claude Stage 2 法律 re-rank\n")
    parts.append("## 使用者情境\n")
    parts.append(f"> {user_query.strip()}")
    parts.append("")
    parts.append(f"**抽出的法律關鍵字**: {', '.join(sorted(query_keywords))}")
    parts.append("")

    # Top 3 re-ranked
    reranked = ai.get("reranked_top_3", [])
    case_lookup = {c.case["case_id"]: c.case for c in candidates}

    parts.append("## Stage 2 LLM Re-ranked Top 3 案件\n")
    for i, r in enumerate(reranked, 1):
        case = case_lookup.get(r["case_id"])
        if not case:
            continue
        parts.append(f"### #{i} `{r['case_id']}` — {case['title']}")
        parts.append(f"- **法律相關性**: {r.get('relevance_score', 0):.2f}")
        parts.append(f"- **為什麼相似**: {r.get('why_relevant', '')}")
        parts.append(f"- **法院**: {case['court']} / **判決日**: {case['judgment_date']}")
        parts.append(f"- **案件摘要**: {case['summary']}")
        rs = case.get("responsibility_split", {})
        parts.append(f"- **過失比例**: 原告 {rs.get('plaintiff', 0)}% / 被告 {rs.get('defendant', 0)}%")
        parts.append(f"- **賠償金額**: NT$ {case.get('compensation_amount', 0):,}")
        breakdown = case.get("compensation_breakdown", {})
        if breakdown:
            parts.append(f"- **賠償組成**:")
            for k, v in breakdown.items():
                parts.append(f"  - {k}: NT$ {v:,}")
        parts.append(f"- **判決要旨**: {case.get('key_holdings', '')}")
        parts.append("")

    # 賠償預估
    parts.append("## 本案賠償區間預估\n")
    comp = ai.get("predicted_compensation_range", {})
    if comp:
        parts.append(f"- **低估**: NT$ {comp.get('low_estimate', 0):,}")
        parts.append(f"- **中位**: NT$ {comp.get('mid_estimate', 0):,}")
        parts.append(f"- **高估**: NT$ {comp.get('high_estimate', 0):,}")
        parts.append(f"- **依據**: {comp.get('reasoning', '')}")
        parts.append("")
    split = ai.get("predicted_responsibility_split", {})
    if split:
        parts.append("## 本案過失比例預估\n")
        parts.append(f"- **預估原告過失**: {split.get('plaintiff_likely_pct', 0)}%")
        parts.append(f"- **預估被告過失**: {split.get('defendant_likely_pct', 0)}%")
        parts.append(f"- **依據**: {split.get('reasoning', '')}")
        parts.append("")

    if ai.get("aggravating_factors"):
        parts.append("## 🔼 加重 / 對你有利的因素\n")
        for f in ai["aggravating_factors"]:
            parts.append(f"- {f}")
        parts.append("")
    if ai.get("mitigating_factors"):
        parts.append("## 🔽 減輕 / 對你不利的因素\n")
        for f in ai["mitigating_factors"]:
            parts.append(f"- {f}")
        parts.append("")

    if ai.get("evidence_checklist"):
        parts.append("## 蒐證清單\n")
        for f in ai["evidence_checklist"]:
            parts.append(f"- {f}")
        parts.append("")

    if ai.get("next_steps_recommendation"):
        parts.append("## 下一步實務建議\n")
        parts.append(ai["next_steps_recommendation"])
        parts.append("")

    parts.append("---")
    parts.append("*caselens 不是法律意見。本工具僅供研究參考。實際案件請洽律師或法扶基金會(諮詢專線 412-8518)。*")
    parts.append("*三方調解優先於訴訟,可洽各縣市政府調解委員會。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="caselens — 台灣法院判決書個人版檢索 + 賠償區間預估")
    p.add_argument("--db", required=True, help="cases_db.json 路徑")
    p.add_argument("--query", required=True, help="使用者情境描述 .txt 路徑")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--top-k", type=int, default=8, help="Stage 1 retrieval top-k(預設 8)")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 Stage 1 (免 API key)")
    args = p.parse_args()

    db = json.loads(Path(args.db).read_text(encoding="utf-8"))
    user_query = Path(args.query).read_text(encoding="utf-8")

    query_keywords = extract_legal_keywords(user_query)
    candidates = find_top_k_candidates(query_keywords, db["cases"], k=args.top_k)

    if args.no_ai:
        top3_cases = [c.case for c in candidates[:3]]
        stats = compute_compensation_stats(top3_cases)
        report = render_no_ai_report(user_query, query_keywords, candidates, stats)
    else:
        ai = llm_rerank_and_explain(user_query, candidates)
        report = render_full_report(user_query, query_keywords, candidates, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
