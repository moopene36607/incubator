"""lawmate — 台灣民眾日常法律問題 BM25 + LLM rerank CLI.

純函式做 BM25 sparse retrieval(bm25.py),LLM 做:
  ① Stage 2 法律相關性 rerank
  ② 為 top 3 條文寫「人話解釋怎麼適用」
  ③ 給應對步驟(存證信函 / 調解 / 申訴 / 訴訟)
  ④ 預估結果區間 + 警示注意事項

LLM 永不下「你一定會贏」斷論。報告底部明確「不是法律意見」。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from articles_db import Article, get_all_articles, make_search_text
from bm25 import RetrievalResult, build_index, explain_query, top_k


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣法律研究助理(非執業律師)。

    輸入:
      - 使用者的法律問題(自由文字)
      - 純函式 BM25 找出的 Top 10 候選條文(已附 keyword_score)

    工作:
      1. Stage 2 LLM Re-rank: 重新評估 Top 10 候選的「**法律相關性**」:
         - 條文與使用者問題的**實質適用性**(BM25 抓 lexical match,LLM 要看 semantic relevance)
         - 留下真正適用的 Top 3 條文,**剔除「字面相似但實質無關」的**
      2. 為 Top 3 條文寫:
         - **這條怎麼用在你的情況**(50-100 字,引用具體事實)
         - **應對步驟**(具體可執行:存證信函 / 調解 / 申訴 / 訴訟 等)
      3. 給「結果預估區間」:
         - 順利情況下可能得到什麼(金額 / 解決方式 / 時程)
         - 最壞情況可能要付出什麼
      4. 警示注意事項:
         - 時效(超過會失權)
         - 蒐證重點
         - 何時必須請律師

    硬規則:
      - 你**絕不**保證「會贏」/「會輸」— 只說「實務上常見的處理方式」
      - 你**絕不**自己編造法條 — 只引用提供的候選條文
      - 不勸用戶完全提告 / 不勸完全不提告 — 由使用者判斷
      - 用台灣繁體中文 + 在地用語(存證信函 / 鄉鎮市調解 / 勞工局申訴 / 法扶基金會)

    回覆 JSON:
    {
      "reranked_top_3": [
        {"article_id": "LSA-24", "relevance_score": 0.95, "why_relevant": "..."},
        ...
      ],
      "application_for_each_article": [
        {
          "article_id": "LSA-24",
          "how_it_applies": "...",
          "action_steps": ["...", "..."]
        },
        ...
      ],
      "predicted_outcome": {
        "best_case": "...",
        "worst_case": "...",
        "estimated_timeline": "..."
      },
      "warnings_and_caveats": ["..."]
    }
""").strip()


def ai_rerank_and_explain(user_query: str, candidates: list[Article], scores: dict[str, float]) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "user_query": user_query,
        "top_10_candidates": [
            {
                "article_id": a.article_id,
                "law_source": a.law_source,
                "article_number": a.article_number,
                "title": a.title,
                "text": a.text,
                "keywords": list(a.keywords),
                "scenarios": list(a.scenarios),
                "application_hint": a.application_hint,
                "bm25_score": scores.get(a.article_id, 0),
            }
            for a in candidates
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


def render_no_ai_report(user_query: str, results: list[RetrievalResult],
                        article_map: dict[str, Article], term_hits: list) -> str:
    parts = ["# lawmate 法律條文 BM25 檢索報告\n"]
    parts.append("**模式**: 純函式 BM25 sparse retrieval(免 API key)\n")
    parts.append(f"## 使用者問題\n")
    parts.append(f"> {user_query.strip()}\n")

    parts.append("## Stage 1 BM25 Top 10 候選條文\n")
    parts.append("⚠️ BM25 是 lexical 搜尋(字面比對),無法判斷『字面相似但實質無關』。**強烈建議**用 AI 模式做 Stage 2 法律相關性 rerank。\n")
    parts.append("| 排名 | BM25 score | 條文 | 標題 | 法源 |")
    parts.append("|---|---|---|---|---|")
    for r in results:
        a = article_map.get(r.doc_id)
        if a:
            parts.append(f"| #{r.rank} | {r.score:.2f} | `{a.article_id}` | {a.title} | {a.law_source} {a.article_number} |")
    parts.append("")

    parts.append(f"## Top 5 條文詳細\n")
    for r in results[:5]:
        a = article_map.get(r.doc_id)
        if not a:
            continue
        parts.append(f"### #{r.rank} `{a.article_id}` — {a.title}")
        parts.append(f"- **法源**: {a.law_source} {a.article_number}")
        parts.append(f"- **BM25 score**: {r.score:.2f}")
        parts.append(f"- **條文內容**: {a.text}")
        parts.append(f"- **關鍵字**: {', '.join(a.keywords)}")
        parts.append(f"- **適用情境**: {' / '.join(a.scenarios)}")
        parts.append(f"- **如何引用**: {a.application_hint}")
        parts.append("")

    parts.append("## Query 拆解 — 命中的關鍵 token(IDF 高 = 越 discriminative)\n")
    parts.append("| Token | DF | IDF | 命中文件數 |")
    parts.append("|---|---|---|---|")
    for h in term_hits[:6]:
        parts.append(f"| `{h.query_term}` | {h.df} | {h.idf:.2f} | {len(h.matched_doc_ids)} |")
    parts.append("")

    parts.append("---")
    parts.append("*純函式模式無 AI 法律解釋與應對步驟。AI 模式會做 Stage 2 rerank + 解釋怎麼用 + 給具體步驟 + 預估結果。*")
    parts.append("*lawmate 不是法律意見。實際案件請洽律師或法扶基金會(諮詢專線 412-8518)。*")
    return "\n".join(parts)


def render_full_report(user_query: str, results: list[RetrievalResult],
                        article_map: dict[str, Article], ai: dict) -> str:
    parts = ["# lawmate 法律條文 BM25 檢索報告\n"]
    parts.append("**模式**: 純函式 BM25 + Claude Stage 2 法律 re-rank + 應對步驟\n")
    parts.append(f"## 使用者問題\n")
    parts.append(f"> {user_query.strip()}\n")

    # Top 3 re-ranked
    reranked = ai.get("reranked_top_3", [])
    applications = {a["article_id"]: a for a in ai.get("application_for_each_article", [])}

    parts.append("## Stage 2 LLM Re-ranked Top 3 條文\n")
    for i, r in enumerate(reranked, 1):
        article = article_map.get(r["article_id"])
        if not article:
            continue
        app = applications.get(r["article_id"], {})
        parts.append(f"### #{i} `{article.article_id}` — {article.title}")
        parts.append(f"- **法源**: {article.law_source} {article.article_number}")
        parts.append(f"- **法律相關性**: {r.get('relevance_score', 0):.2f}")
        parts.append(f"- **為什麼適用你的情況**: {r.get('why_relevant', '')}")
        parts.append("")
        parts.append(f"**條文內容**: {article.text}")
        parts.append("")
        if app.get("how_it_applies"):
            parts.append(f"**怎麼用在你的情況**: {app['how_it_applies']}")
            parts.append("")
        if app.get("action_steps"):
            parts.append("**應對步驟**:")
            for step in app["action_steps"]:
                parts.append(f"- {step}")
            parts.append("")

    # Predicted outcome
    if ai.get("predicted_outcome"):
        out = ai["predicted_outcome"]
        parts.append("## 結果預估\n")
        parts.append(f"- **順利情況**: {out.get('best_case', '')}")
        parts.append(f"- **最壞情況**: {out.get('worst_case', '')}")
        parts.append(f"- **預估時程**: {out.get('estimated_timeline', '')}")
        parts.append("")

    # Warnings
    if ai.get("warnings_and_caveats"):
        parts.append("## ⚠️ 注意事項\n")
        for w in ai["warnings_and_caveats"]:
            parts.append(f"- {w}")
        parts.append("")

    parts.append("---")
    parts.append("*lawmate 不是法律意見。實際案件請洽律師或法扶基金會(諮詢專線 412-8518)。*")
    parts.append("*重大爭議建議先到鄉鎮市公所調解委員會(免費)再考慮訴訟。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="lawmate — 台灣民眾日常法律條文 BM25 檢索")
    p.add_argument("--query", required=True, help="使用者法律問題(自然語言)")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--top-k", type=int, default=10, help="Stage 1 BM25 top-k(預設 10)")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    articles = get_all_articles()
    article_map = {a.article_id: a for a in articles}
    docs = [(a.article_id, make_search_text(a)) for a in articles]
    idx = build_index(docs)

    results = top_k(args.query, idx, k=args.top_k)
    term_hits = explain_query(args.query, idx, top_n=8)

    if args.no_ai:
        report = render_no_ai_report(args.query, results, article_map, term_hits)
    else:
        candidates = [article_map[r.doc_id] for r in results if r.doc_id in article_map]
        scores_map = {r.doc_id: r.score for r in results}
        ai = ai_rerank_and_explain(args.query, candidates, scores_map)
        report = render_full_report(args.query, results, article_map, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
