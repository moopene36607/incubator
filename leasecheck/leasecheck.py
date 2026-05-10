"""leasecheck — 台灣住宅租賃合約 AI 審約 CLI.

純函式做所有風險分數計算 (analyzer.py),LLM 只負責:
  ① 從合約段落中精確抽出對應條款全文 (structured extraction)
  ② 為每條紅色 / 黃色條款寫人話解釋 + 房客可用的談判話術

LLM 永遠不算分。

模式:
  --no-ai  純 keyword 比對 (免 API key)
  full     LLM 結構化抽取 + 寫談判話術
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from analyzer import (
    ClauseHit,
    RiskAssessment,
    assess_risk,
    group_by_category,
    keyword_extract,
    merge_hits,
)
from clauses_db import CLAUSES, ClauseSpec, get_clause_by_code


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣租屋顧問,協助房客審閱住宅租賃合約。

    輸入會給你:
      - lease_full_text: 完整合約原文
      - target_clauses: 你需要從合約中比對的條款規範清單(每條含 code / category /
        risk_level / common_phrasing / keywords)

    工作:
      1. 對每一條 target_clauses,在 lease_full_text 中找對應的條款句子。
         - 若合約中有命中 → 抽出該句完整文字 (matched_text)
         - 若合約中沒有對應條款 → 不要勉強匹配,直接 skip(不要回傳 false positive)
      2. 為每筆 hit 寫:
         - explanation_for_renter (50-100 字,房客易讀,引用具體合約句)
         - negotiation_script (1-2 句,房客可以原話跟房東說的台詞)

    硬規則:
      - 你**絕不**算 risk_score 或推測 risk_level — 那是純函式工作,直接引用提供的 risk_level
      - 你**絕不**編造合約裡沒寫的條款。如果合約沒寫「電費每度 6 元」就不要列為 hit
      - 不要勸房客直接放棄 / 不要勸房客提告。只給談判 / 修改建議
      - 用台灣繁體中文 + 在地用語(押金 / 修繕 / 解約 / 報稅)

    回覆 JSON:
    {
      "hits": [
        {
          "code": "DEPOSIT_OVER_2MTH",
          "matched_text": "押金為新台幣肆萬伍仟元(相當於三個月租金)",
          "explanation_for_renter": "...",
          "negotiation_script": "..."
        },
        ...
      ],
      "overall_advice": "1-2 段給房客的整體建議 (本份合約紅色條款比例高 / 你重點該談哪 3 件事 / 簽前是否該再諮詢)"
    }
""").strip()


def llm_extract(lease_text: str) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()

    target_payload = [
        {
            "code": c.code,
            "category": c.category,
            "risk_level": c.risk_level,
            "description_zh": c.description_zh,
            "common_phrasing": c.common_phrasing,
            "keywords": list(c.keywords),
        }
        for c in CLAUSES
    ]
    payload = {
        "lease_full_text": lease_text,
        "target_clauses": target_payload,
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def _llm_to_hits(ai: dict) -> list[ClauseHit]:
    hits: list[ClauseHit] = []
    for h in ai.get("hits", []):
        spec = get_clause_by_code(h.get("code", ""))
        if spec is None:
            continue
        hits.append(ClauseHit(
            code=spec.code,
            risk_level=spec.risk_level,
            matched_text=h.get("matched_text", ""),
            source="llm",
        ))
    return hits


# --- Render ---

RISK_BADGE = {"red": "🔴 紅色 (違法 / 嚴重不利)", "yellow": "🟡 黃色 (可談 / 模糊不利)", "green": "🟢 綠色 (合理 / 合法)"}
LEVEL_BADGE = {"LOW": "🟢 LOW", "MEDIUM": "🟡 MEDIUM", "HIGH": "🟠 HIGH", "CRITICAL": "🔴 CRITICAL"}


def render_no_ai_report(
    lease_path: str,
    hits: list[ClauseHit],
    risk: RiskAssessment,
) -> str:
    parts: list[str] = []
    parts.append(f"# leasecheck 租賃合約審閱報告\n")
    parts.append(f"**合約檔案**: `{lease_path}`")
    parts.append(f"**模式**: 純函式 keyword 比對(免 API key)\n")
    parts.append("## 風險摘要\n")
    parts.append(f"- **風險分數**: {risk.risk_score} / 100")
    parts.append(f"- **風險等級**: {LEVEL_BADGE[risk.risk_level]}")
    parts.append(f"- **紅色條款**: {risk.red_count} 條")
    parts.append(f"- **黃色條款**: {risk.yellow_count} 條")
    parts.append(f"- **綠色條款**: {risk.green_count} 條")
    parts.append(f"- **建議**: {risk.summary}")
    parts.append("")

    by_cat = group_by_category(hits)
    for cat in sorted(by_cat.keys()):
        parts.append(f"## {cat}\n")
        for h in by_cat[cat]:
            spec = get_clause_by_code(h.code)
            if spec is None:
                continue
            parts.append(f"### {RISK_BADGE[spec.risk_level]} — `{h.code}`")
            parts.append(f"- **合約原文片段**: 「{h.matched_text}」")
            if h.matched_keywords:
                parts.append(f"- **命中關鍵字**: {', '.join(h.matched_keywords)}")
            parts.append(f"- **法律依據**: {spec.legal_basis}")
            parts.append(f"- **這條代表什麼**: {spec.description_zh}")
            parts.append(f"- **怎麼跟房東談**: {spec.negotiation_tip}")
            parts.append("")
    parts.append("---")
    parts.append("*純函式模式無 AI 解釋。對每條紅色條款的詳細談判建議,請開啟 AI 模式。*")
    parts.append("*本工具不是法律意見。重大爭議請洽法扶基金會或律師。*")
    return "\n".join(parts)


def render_full_report(
    lease_path: str,
    hits: list[ClauseHit],
    risk: RiskAssessment,
    ai: dict,
) -> str:
    ai_by_code = {h["code"]: h for h in ai.get("hits", [])}
    parts: list[str] = []
    parts.append(f"# leasecheck 租賃合約審閱報告\n")
    parts.append(f"**合約檔案**: `{lease_path}`")
    parts.append(f"**模式**: AI 結構化抽取 + 純函式風險評分\n")
    parts.append("## 風險摘要\n")
    parts.append(f"- **風險分數**: {risk.risk_score} / 100")
    parts.append(f"- **風險等級**: {LEVEL_BADGE[risk.risk_level]}")
    parts.append(f"- **紅色條款**: {risk.red_count} 條")
    parts.append(f"- **黃色條款**: {risk.yellow_count} 條")
    parts.append(f"- **綠色條款**: {risk.green_count} 條")
    parts.append(f"- **建議**: {risk.summary}")
    parts.append("")
    parts.append("## 整體建議\n")
    parts.append(ai.get("overall_advice", ""))
    parts.append("")

    by_cat = group_by_category(hits)
    for cat in sorted(by_cat.keys()):
        parts.append(f"## {cat}\n")
        for h in by_cat[cat]:
            spec = get_clause_by_code(h.code)
            if spec is None:
                continue
            ai_entry = ai_by_code.get(h.code, {})
            parts.append(f"### {RISK_BADGE[spec.risk_level]} — `{h.code}`")
            matched_text = ai_entry.get("matched_text") or h.matched_text
            parts.append(f"- **合約原文**: 「{matched_text}」")
            parts.append(f"- **法律依據**: {spec.legal_basis}")
            parts.append(f"- **這條代表什麼**: " + (
                ai_entry.get("explanation_for_renter") or spec.description_zh
            ))
            parts.append(f"- **可用談判話術**: " + (
                ai_entry.get("negotiation_script") or spec.negotiation_tip
            ))
            parts.append("")
    parts.append("---")
    parts.append("*leasecheck 提供合約風險指引,不是正式法律意見。重大爭議請洽法扶基金會或律師。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="leasecheck — 台灣租屋合約 AI 審約")
    p.add_argument("lease", help="合約純文字檔 (.txt)")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    lease_text = Path(args.lease).read_text(encoding="utf-8")

    keyword_hits = keyword_extract(lease_text)

    if args.no_ai:
        hits = keyword_hits
        risk = assess_risk(hits)
        report = render_no_ai_report(args.lease, hits, risk)
    else:
        ai = llm_extract(lease_text)
        llm_hits = _llm_to_hits(ai)
        hits = merge_hits(keyword_hits, llm_hits)
        risk = assess_risk(hits)
        report = render_full_report(args.lease, hits, risk, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
