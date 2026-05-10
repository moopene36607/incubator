"""bizradar — 台灣 SME 客戶 / 廠商風險評估 CLI(graph + entity resolution).

純函式做所有圖譜分析 + 風險計分(graph_analyzer.py)。LLM 只負責:
  ① 為純函式找出的 risk signals 寫人話解釋(老闆易懂)
  ② 給具體的「合作條件設定建議」(預收 % / 票期 / 上限金額)
  ③ 若 director_network 有風險,寫「故事」幫老闆理解
     (e.g. 為何「董事 X 也在解散公司 Y 任職」是危險訊號)

LLM 永遠不算 risk score。

模式:
  --no-ai  純函式輸出(免 API key)
  full     加上 Claude 解釋與建議
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from graph_analyzer import RiskAssessment, RiskSignal, assess, find_company_by_corp_id


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣中小企業客戶 / 廠商風險顧問。

    輸入:
      - target company 完整 profile(統編 / 設立日 / 資本 / 董監事 / 業務狀態)
      - 純函式計算的 risk_score(0-100) + risk_level + 一連串 risk_signals
      - director_network(目標公司董事在哪些其他公司任職)
      - address_collisions(共用地址的其他公司)

    工作:
      1. 寫一段 100-200 字的「故事化解釋」說明為什麼這家公司風險是 [risk_level]
         - 若董事跨多家公司 → 用故事方式說明連結網路的意義(別只是列 signals)
         - 若有共用地址 → 解釋這通常代表什麼(關聯企業 / 空殼)
         - 若公司本身有訴訟 / 新聞 → 指出時間與金額
      2. 給「合作條件設定建議」:具體 5-7 項(預收 % / 票期 / 首單上限 /
         驗收條件 / 違約金條款 / 是否需擔保品 / 是否需第三方擔保)
      3. 寫「進一步盡職調查清單」(老闆可以額外做的查證:
         例「打電話到 XX 商業同業公會問」「Google 該董事姓名 + 倒帳 / 違約」)

    硬規則:
      - 你**絕不**改寫或重算 risk_score — 那是純函式工作
      - 你**絕不**僅憑直覺猜測「他可能是好人 / 壞人」— 一切都引用具體 signal
      - 不勸用戶提告 / 不勸用戶完全拒絕往來(由用戶判斷)
      - 用台灣繁體中文 + 在地用語(統編 / 董事 / 訴訟 / 票期 / 預收 / 違約金)

    回覆 JSON:
    {
      "story_narrative": "100-200 字故事化解釋...",
      "cooperation_terms": [
        {"item": "首單上限", "recommendation": "...", "reason": "..."},
        ...
      ],
      "due_diligence_checklist": ["...", "...", "..."],
      "red_flags": ["..."],
      "green_flags": ["..."]
    }
""").strip()


# --- 風險等級顯示 ---

LEVEL_BADGE = {
    "LOW": "🟢 LOW",
    "MEDIUM": "🟡 MEDIUM",
    "HIGH": "🟠 HIGH",
    "CRITICAL": "🔴 CRITICAL",
}

SEVERITY_BADGE = {
    "low": "ⓘ",
    "medium": "⚠️",
    "high": "🔶",
    "critical": "🔴",
}


def render_no_ai_report(ra: RiskAssessment) -> str:
    c = ra.company
    parts = [f"# bizradar 客戶 / 廠商風險評估報告\n"]
    parts.append(f"**模式**: 純函式 graph 分析(免 API key)\n")
    parts.append("## 目標公司基本資料\n")
    parts.append(f"- **公司名稱**: {c['name_zh']}")
    parts.append(f"- **統一編號**: {c['corp_id']}")
    parts.append(f"- **設立日期**: {c['established_date']}")
    parts.append(f"- **實收資本**: NT$ {c['capital_amount']:,}")
    parts.append(f"- **註冊地址**: {c['registered_address']}")
    parts.append(f"- **業務狀態**: {c['business_status']}")
    parts.append(f"- **產業**: {c['industry']}")
    parts.append(f"- **董監事**: {', '.join(c['directors'])}")
    parts.append("")

    parts.append("## 風險評估摘要\n")
    parts.append(f"- **風險分數**: {ra.risk_score} / 100")
    parts.append(f"- **風險等級**: {LEVEL_BADGE[ra.risk_level]}")
    parts.append(f"- **建議**: {ra.summary}")
    parts.append("")

    parts.append(f"## 風險訊號 (共 {len(ra.signals)} 條)\n")
    if not ra.signals:
        parts.append("無 — 公司基本面良好。")
    else:
        for s in ra.signals:
            parts.append(f"### {SEVERITY_BADGE[s.severity]} [{s.severity.upper()}] `{s.code}` (+{s.score})")
            parts.append(f"- {s.description}")
            parts.append("")

    if ra.director_network:
        parts.append("## 董監事關係網路(Graph 分析)\n")
        parts.append("目標公司董監事在其他公司的任職紀錄:\n")
        for director, others in ra.director_network.items():
            parts.append(f"### {director}")
            for other in others:
                status_badge = "✓ 營業中" if other["business_status"] == "營業中" else "🔴 " + other["business_status"]
                parts.append(f"- → **{other['name_zh']}** (統編 {other['corp_id']}, {status_badge})")
                parts.append(f"  - 設立: {other['established_date']} / 資本: NT$ {other['capital_amount']:,} / 產業: {other['industry']}")
                if other["lawsuits"]:
                    parts.append(f"  - 訴訟紀錄: {len(other['lawsuits'])} 件")
                if other["news_negative"]:
                    parts.append(f"  - 負評新聞: {len(other['news_negative'])} 篇")
            parts.append("")
    else:
        parts.append("## 董監事關係網路\n")
        parts.append("董監事未跨任職其他公司(或在 corpus 中無此紀錄)。")
        parts.append("")

    if ra.address_collisions:
        parts.append("## 共用地址檢查\n")
        for other in ra.address_collisions:
            parts.append(f"- ⚠️ 與【{other['name_zh']}】(統編 {other['corp_id']}, {other['business_status']})共用註冊地址")
        parts.append("")

    parts.append("---")
    parts.append("*純函式模式無 AI 建議。AI 模式會給具體合作條件 + 盡職調查清單。*")
    parts.append("*bizradar 僅供參考。重大決策請洽律師 / 會計師 / 徵信社。*")
    return "\n".join(parts)


def render_full_report(ra: RiskAssessment, ai: dict) -> str:
    c = ra.company
    parts = [f"# bizradar 客戶 / 廠商風險評估報告\n"]
    parts.append(f"**模式**: 純函式 graph 分析 + AI 顧問解釋與建議\n")
    parts.append("## 目標公司基本資料\n")
    parts.append(f"- **公司名稱**: {c['name_zh']}")
    parts.append(f"- **統一編號**: {c['corp_id']}")
    parts.append(f"- **設立日期**: {c['established_date']}")
    parts.append(f"- **實收資本**: NT$ {c['capital_amount']:,}")
    parts.append(f"- **註冊地址**: {c['registered_address']}")
    parts.append(f"- **業務狀態**: {c['business_status']}")
    parts.append(f"- **產業**: {c['industry']}")
    parts.append(f"- **董監事**: {', '.join(c['directors'])}")
    parts.append("")

    parts.append("## 風險評估摘要\n")
    parts.append(f"- **風險分數**: {ra.risk_score} / 100")
    parts.append(f"- **風險等級**: {LEVEL_BADGE[ra.risk_level]}")
    parts.append("")
    parts.append("### 故事化解釋\n")
    parts.append(ai.get("story_narrative", ""))
    parts.append("")

    if ai.get("red_flags"):
        parts.append("### 🔴 紅旗訊號\n")
        for f in ai["red_flags"]:
            parts.append(f"- {f}")
        parts.append("")
    if ai.get("green_flags"):
        parts.append("### 🟢 正面訊號\n")
        for f in ai["green_flags"]:
            parts.append(f"- {f}")
        parts.append("")

    parts.append(f"## 風險訊號 (共 {len(ra.signals)} 條,純函式計算)\n")
    for s in ra.signals:
        parts.append(f"### {SEVERITY_BADGE[s.severity]} [{s.severity.upper()}] `{s.code}` (+{s.score})")
        parts.append(f"- {s.description}")
        parts.append("")

    if ra.director_network:
        parts.append("## 董監事關係網路(Graph 分析)\n")
        for director, others in ra.director_network.items():
            parts.append(f"### {director}")
            for other in others:
                status_badge = "✓ 營業中" if other["business_status"] == "營業中" else "🔴 " + other["business_status"]
                parts.append(f"- → **{other['name_zh']}** (統編 {other['corp_id']}, {status_badge})")
                parts.append(f"  - 設立: {other['established_date']} / 資本: NT$ {other['capital_amount']:,}")
                if other["lawsuits"]:
                    parts.append(f"  - 訴訟紀錄: {len(other['lawsuits'])} 件")
                if other["news_negative"]:
                    parts.append(f"  - 負評新聞: {len(other['news_negative'])} 篇")
            parts.append("")

    parts.append("## 合作條件建議(AI 顧問)\n")
    for term in ai.get("cooperation_terms", []):
        parts.append(f"### {term['item']}")
        parts.append(f"- **建議**: {term['recommendation']}")
        parts.append(f"- **理由**: {term['reason']}")
        parts.append("")

    parts.append("## 進一步盡職調查清單\n")
    for item in ai.get("due_diligence_checklist", []):
        parts.append(f"- {item}")
    parts.append("")

    parts.append("---")
    parts.append("*bizradar 提供風險指引,不是正式法律 / 徵信意見。重大決策請洽律師 / 會計師 / 徵信社。*")
    return "\n".join(parts)


def ai_explain(ra: RiskAssessment) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "company": ra.company,
        "risk_score": ra.risk_score,
        "risk_level": ra.risk_level,
        "signals": [
            {
                "code": s.code,
                "severity": s.severity,
                "score": s.score,
                "description": s.description,
                "evidence": s.evidence,
            }
            for s in ra.signals
        ],
        "director_network": {
            d: [
                {
                    "name_zh": c["name_zh"],
                    "corp_id": c["corp_id"],
                    "business_status": c["business_status"],
                    "established_date": c["established_date"],
                    "lawsuit_count": len(c["lawsuits"]),
                    "negative_news_count": len(c["news_negative"]),
                }
                for c in others
            ]
            for d, others in ra.director_network.items()
        },
        "address_collisions": [
            {"name_zh": c["name_zh"], "corp_id": c["corp_id"], "status": c["business_status"]}
            for c in ra.address_collisions
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


def main() -> None:
    p = argparse.ArgumentParser(description="bizradar — 台灣 SME 客戶 / 廠商風險評估")
    p.add_argument("--db", required=True, help="companies_db.json 路徑")
    p.add_argument("--corp-id", required=True, help="要查詢的目標公司統編")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    db = json.loads(Path(args.db).read_text(encoding="utf-8"))
    ra = assess(db, args.corp_id)
    if ra is None:
        sys.exit(f"找不到統編 {args.corp_id} 的公司")

    if args.no_ai:
        report = render_no_ai_report(ra)
    else:
        ai = ai_explain(ra)
        report = render_full_report(ra, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
