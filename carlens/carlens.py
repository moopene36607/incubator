"""carlens — 台灣中古車多源資料一致性檢查 CLI(multi-modal fusion).

純函式做所有一致性檢查 + risk score(inspector.py)。LLM 只負責:
  ① 把多個 signals 串成「故事化解釋」(老闆易懂)
  ② 評估「同款車款參考價」vs 賣方開價的合理性
  ③ 給「該不該買 / 該怎麼買」具體決策建議
  ④ 列「進一步盡職調查清單」(原廠檢查 / VIN 鑑識 / 司法院車籍查詢)

LLM 永不算 risk_score。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from inspector import Assessment, CarProfile, assess


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣中古車買賣顧問,專長詐騙風險識別。

    輸入:
      - 車輛完整 profile(make / model / declared_year / declared_mileage_km /
        賣方宣稱 / 視覺特徵 / 配備清單 / 開價)
      - 純函式計算的 risk_score + risk_level + 一連串 risk signals(含 evidence)

    工作:
      1. 寫一段 100-200 字「故事化解釋」串連多個 signals:
         - 不要只列 signals;**講故事**:「這台車表面看 18 年 4 萬 km 一手車,
           但 X + Y + Z 證據組合起來,看起來像 ___(調表 / 事故重組 / 泡水車)」
         - 引用具體 evidence(內裝磨耗等級、底盤塗裝、引擎室狀態等)
      2. 評估開價合理性:該車款 / 年式 / 行照里程的市場行情 vs 賣方開價
         - 若風險高,合理價應比市場低 10-30%
         - 列出「乾淨同款車」的市場價估算區間
      3. 最終建議三選一:
         - 不建議購買(風險過高)
         - 議價條件式購買(列出議價空間 + 必要保證條款)
         - 可購買但需鑑定後(列出原廠檢查項目)
      4. 列「進一步盡職調查清單」(具體可做的查證):
         - 原廠 / 公正第三方檢查項目
         - VIN 車身碼鑑識
         - 司法院車籍查詢(看是否事故車登記)
         - 強制險 / 商業險紀錄查詢
         - 同款車市價比對(8891 / 比比看)

    硬規則:
      - 你**絕不**重算 risk_score 或新增「沒在 signals 裡」的問題
      - 你**絕不**斷言「這車主就是詐騙」— 用語為「強烈暗示」「可能」
      - 不勸用戶提告(無證據時)— 只給「降低風險 / 拒絕往來」建議
      - 用台灣繁體中文 + 在地用語(行照 / 中古車 / 監理站 / 8891)

    回覆 JSON:
    {
      "story_narrative": "100-200 字故事化解釋...",
      "price_evaluation": {
        "asking_price": ...,
        "market_clean_range_low": ...,
        "market_clean_range_high": ...,
        "fair_price_given_risk": ...,
        "reasoning": "..."
      },
      "purchase_recommendation": {
        "decision": "不建議購買 / 議價條件式購買 / 可購買但需鑑定後",
        "reasoning": "...",
        "specific_terms": ["..."]
      },
      "due_diligence_checklist": ["..."]
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


def ai_explain(a: Assessment) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "car": a.car.__dict__,
        "risk_score": a.risk_score,
        "risk_level": a.risk_level,
        "signals": [
            {
                "code": s.code,
                "severity": s.severity,
                "score": s.score,
                "description": s.description,
                "evidence": s.evidence,
                "confidence": s.confidence,
            }
            for s in a.signals
        ],
        "summary": a.summary,
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


def render_no_ai_report(a: Assessment) -> str:
    car = a.car
    parts = ["# carlens 中古車一致性檢查報告\n"]
    parts.append("**模式**: 純函式多源資料比對(免 API key)\n")
    parts.append("## 車輛基本資料\n")
    parts.append(f"- **車款**: {car.make} {car.model}")
    parts.append(f"- **宣稱年式**: {car.declared_year}")
    parts.append(f"- **行照里程**: {car.declared_mileage_km:,} km")
    parts.append(f"- **開價**: NT$ {car.asking_price_ntd:,}")
    parts.append(f"- **賣方宣稱**: {'無事故 / ' if car.declared_no_accident else ''}{'無泡水' if car.declared_no_flood else ''}")
    parts.append(f"- **配備**: {', '.join(car.equipment_features) if car.equipment_features else '-'}")
    parts.append("")

    parts.append("## 觀察資料(多源)\n")
    parts.append(f"- **內裝磨耗**: {car.interior_wear_level}/10 — {car.interior_wear_notes}")
    parts.append(f"- **引擎室**: {car.engine_bay_state} — {car.engine_bay_notes}")
    parts.append(f"- **底盤**: {car.undercarriage_state} — {car.undercarriage_notes}")
    parts.append(f"- **車身漆面**: {car.body_paint_consistency} — {car.body_paint_notes}")
    parts.append(f"- **輪胎**: 剩餘 {car.tire_estimated_remaining_pct}%, {car.tire_brand_year}")
    parts.append(f"- **車身號碼**: {car.vin_plate_state} — {car.vin_plate_notes}")
    parts.append("")

    parts.append("## 風險評估摘要\n")
    parts.append(f"- **風險分數**: {a.risk_score} / 100")
    parts.append(f"- **風險等級**: {LEVEL_BADGE[a.risk_level]}")
    parts.append(f"- **建議**: {a.summary}")
    parts.append("")

    parts.append(f"## 風險訊號 (共 {len(a.signals)} 條)\n")
    if not a.signals:
        parts.append("無異常 — 多源資料一致。")
    else:
        for s in a.signals:
            parts.append(f"### {SEVERITY_BADGE[s.severity]} [{s.severity.upper()}] `{s.code}` (+{s.score})")
            parts.append(f"- {s.description}")
            if s.evidence:
                parts.append(f"- 證據: `{json.dumps(s.evidence, ensure_ascii=False)}`")
            parts.append("")

    parts.append("---")
    parts.append("*純函式模式無 AI 解釋與市場行情評估。AI 模式會給故事化解釋 + 議價空間 + 盡職調查清單。*")
    parts.append("*carlens 僅做風險指引,不保證偵測所有詐欺。重大交易請帶車到原廠檢查 / 公正第三方鑑定。*")
    return "\n".join(parts)


def render_full_report(a: Assessment, ai: dict) -> str:
    car = a.car
    parts = ["# carlens 中古車一致性檢查報告\n"]
    parts.append("**模式**: 純函式多源比對 + AI 顧問解釋與建議\n")
    parts.append("## 車輛基本資料\n")
    parts.append(f"- **車款**: {car.make} {car.model}")
    parts.append(f"- **宣稱年式**: {car.declared_year} / **行照里程**: {car.declared_mileage_km:,} km")
    parts.append(f"- **開價**: NT$ {car.asking_price_ntd:,}")
    parts.append(f"- **賣方宣稱**: {'無事故 / ' if car.declared_no_accident else ''}{'無泡水' if car.declared_no_flood else ''}")
    parts.append("")

    parts.append("## 風險評估摘要\n")
    parts.append(f"- **風險分數**: {a.risk_score} / 100")
    parts.append(f"- **風險等級**: {LEVEL_BADGE[a.risk_level]}")
    parts.append("")

    parts.append("## 故事化解釋(AI 顧問)\n")
    parts.append(ai.get("story_narrative", ""))
    parts.append("")

    parts.append("## 開價合理性\n")
    pe = ai.get("price_evaluation", {})
    parts.append(f"- **賣方開價**: NT$ {pe.get('asking_price', car.asking_price_ntd):,}")
    parts.append(f"- **乾淨同款車市場估算區間**: NT$ {pe.get('market_clean_range_low', 0):,} - NT$ {pe.get('market_clean_range_high', 0):,}")
    parts.append(f"- **依風險調整的合理價**: NT$ {pe.get('fair_price_given_risk', 0):,}")
    parts.append(f"- **依據**: {pe.get('reasoning', '')}")
    parts.append("")

    parts.append("## 風險訊號 (純函式計算)\n")
    for s in a.signals:
        parts.append(f"### {SEVERITY_BADGE[s.severity]} [{s.severity.upper()}] `{s.code}` (+{s.score})")
        parts.append(f"- {s.description}")
        parts.append("")

    parts.append("## 最終建議\n")
    rec = ai.get("purchase_recommendation", {})
    parts.append(f"- **決策**: **{rec.get('decision', '')}**")
    parts.append(f"- **理由**: {rec.get('reasoning', '')}")
    if rec.get("specific_terms"):
        parts.append(f"- **具體條件**:")
        for t in rec["specific_terms"]:
            parts.append(f"  - {t}")
    parts.append("")

    parts.append("## 進一步盡職調查清單\n")
    for item in ai.get("due_diligence_checklist", []):
        parts.append(f"- {item}")
    parts.append("")

    parts.append("---")
    parts.append("*carlens 僅做風險指引,不保證偵測所有詐欺。重大交易請帶車到原廠檢查 / 公正第三方鑑定。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="carlens — 中古車一致性檢查 + 詐騙風險評估")
    p.add_argument("profile", help="car_profile.json")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    data = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    car = CarProfile(**data)
    a = assess(car)

    if args.no_ai:
        report = render_no_ai_report(a)
    else:
        ai = ai_explain(a)
        report = render_full_report(a, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
