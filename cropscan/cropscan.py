"""cropscan — 台灣作物病蟲害 AI 辨識 + 防治建議

Usage:
    # 結構化 JSON 輸入(免 API key)
    python cropscan.py samples/sample_input.json --no-ai

    # 自由文字病徵描述 + AI 比對 corpus(需 API key)
    python cropscan.py samples/sample_input.json --out diagnosis.md

設計重點:
- 防治建議資料 100% 純函式從 corpus 出(不交給 LLM 編造農藥名)
- AI 只負責「使用者描述 → 比對 corpus 病害 → 給 Top 3 候選 + 信心分數」
- AI 不確定時直接建議聯絡農改場(透明標 confidence)
- 嚴格只用 corpus 中的台灣許可農藥(避免推薦違法 / 過期 / 國外藥劑)

ANTHROPIC_API_KEY 在 AI 模式必要。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pest_db import (
    PEST_DB,
    PestEntry,
    extension_station,
    for_crop,
    lookup,
)


DIAGNOSIS_SYSTEM = """你是台灣農業病蟲害辨識助理。使用者會給你「作物名稱 + 病徵描述」(可能是
拍照後的文字描述或自己觀察),你的任務是從**提供的 corpus 病害清單**中比對最可能的 1-3 個候選。

## 輸出格式(只回 JSON,不要其他文字)

```json
{
  "candidates": [
    {
      "code": "<corpus 中的 code,只用提供的>",
      "confidence": 0-100,
      "match_symptoms": ["...與 corpus common_symptoms 重疊的關鍵字"],
      "user_severity_estimate": "輕 | 中 | 重 | 不確定"
    },
    ...
  ],
  "uncertainty_note": "若 top1 confidence < 60 或症狀模糊,寫一句要農民聯絡農改場的提醒"
}
```

## 規則

- **絕對只用提供 corpus 中的 code**,不在 corpus 中的病害一律不要編造
- 最多列 3 個候選,依 confidence 降序
- confidence 評分:
  * 80+ 高:症狀明顯命中 3+ 個 corpus 關鍵字 + 作物匹配
  * 60-79 中高:命中 2 個關鍵字
  * 40-59 中:命中 1 個關鍵字或作物部分匹配
  * < 40 低:症狀模糊,強烈建議聯絡農改場
- user_severity_estimate 依使用者描述比對 severity_indicators(輕 / 中 / 重)
- 若所有 candidate confidence < 50 → 仍要列出 top 1-2,但 uncertainty_note 必須警示

## 嚴格禁止

- 不要編造 corpus 沒有的病害名 / 農藥名
- 不要給「使用 XX 農藥」的具體建議(那是純函式從 corpus 出)
- 不要說「絕對是 XX 病」 — 用「最可能」「疑似」等審慎措辭
"""


def build_corpus_for_llm(crop: str) -> str:
    """為特定作物建構 LLM 可讀的病害 corpus(供 prompt 用)。"""
    entries = for_crop(crop)
    if not entries:
        entries = list(PEST_DB)  # fallback: 全部
    sections: list[str] = []
    for p in entries:
        sections.append(
            f"### `{p.code}` — {p.crop} / {p.disease_name}\n"
            f"病原: {p.pathogen_or_pest}\n"
            f"常見症狀: {' / '.join(p.common_symptoms)}\n"
            f"嚴重度判斷:\n"
            + "\n".join(f"  - {k}: {v}" for k, v in p.severity_indicators.items())
        )
    return "\n\n".join(sections)


def llm_diagnose(crop: str, symptoms: str) -> dict[str, Any]:
    import anthropic

    corpus = build_corpus_for_llm(crop)
    user_msg = (
        f"作物: {crop}\n\n"
        f"病徵描述: {symptoms}\n\n"
        f"--- 可選 corpus 病害(請只用以下 code) ---\n\n{corpus}\n\n"
        f"請給 Top 3 候選 JSON。"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=[{"type": "text", "text": DIAGNOSIS_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON: {raw}")
    return json.loads(raw[start : end + 1])


def render_no_ai_diagnosis(crop: str, symptoms: str) -> dict[str, Any]:
    """無 AI 時的純函式 baseline — 簡單關鍵字 overlap 比對。"""
    entries = for_crop(crop)
    if not entries:
        entries = list(PEST_DB)

    keyword_hits: list[tuple[PestEntry, int, list[str]]] = []
    for p in entries:
        matched = [kw for kw in p.common_symptoms if kw in symptoms]
        if matched:
            keyword_hits.append((p, len(matched), matched))
    keyword_hits.sort(key=lambda x: -x[1])

    candidates = []
    for p, hits, matched in keyword_hits[:3]:
        confidence = min(85, 30 + hits * 18)  # 純規則對應到 confidence
        candidates.append({
            "code": p.code,
            "confidence": confidence,
            "match_symptoms": matched,
            "user_severity_estimate": "不確定",
        })

    uncertainty_note = ""
    if not candidates:
        uncertainty_note = "無 corpus 病害符合,強烈建議拍照聯絡農改場。"
    elif candidates[0]["confidence"] < 60:
        uncertainty_note = "症狀關鍵字命中少,建議聯絡農改場確認。"

    return {"candidates": candidates, "uncertainty_note": uncertainty_note}


def render_diagnosis_report(crop: str, symptoms: str, region: str,
                            llm_result: dict[str, Any]) -> str:
    today = date.today().isoformat()
    out: list[str] = []
    out.append(f"# 田間病蟲害 AI 辨識報告")
    out.append("")
    out.append(f"**辨識日期**: {today}    **作物**: {crop}    **農地區域**: {region}")
    out.append("")
    out.append("## 使用者描述")
    out.append("")
    out.append(f"> {symptoms}")
    out.append("")

    candidates = llm_result.get("candidates", [])
    if not candidates:
        out.append("## ❌ 無法判斷")
        out.append("")
        out.append("Corpus 中無符合症狀的病害。**強烈建議拍照聯絡農改場。**")
    else:
        out.append(f"## 🎯 候選病害(Top {len(candidates)})")
        out.append("")
        for i, c in enumerate(candidates, 1):
            entry = lookup(c["code"])
            if entry is None:
                continue
            conf = c.get("confidence", 0)
            sev = c.get("user_severity_estimate", "不確定")
            icon = "🔥" if conf >= 80 else ("✅" if conf >= 60 else "🟡")
            out.append(f"### {icon} 候選 {i}: {entry.disease_name}({conf}/100 信心)")
            out.append("")
            out.append(f"- **作物**: {entry.crop}")
            out.append(f"- **病原 / 害蟲**: {entry.pathogen_or_pest}")
            out.append(f"- **嚴重度推估**: **{sev}**")
            if c.get("match_symptoms"):
                out.append(f"- **症狀命中**: {' / '.join(c['match_symptoms'])}")
            out.append("")
            out.append(f"**典型症狀**:")
            for s in entry.common_symptoms:
                out.append(f"  - {s}")
            out.append("")
            out.append(f"**嚴重度判斷標準**:")
            for k, v in entry.severity_indicators.items():
                out.append(f"  - {k}: {v}")
            out.append("")
            out.append(f"**台灣許可防治方法**(來自 corpus,純函式):")
            for t in entry.taiwan_legal_treatments:
                out.append(f"  - {t}")
            out.append("")
            out.append(f"- **採收安全期**: {entry.safety_period_days} 天")
            out.append("- **預防 / 田間管理**:")
            for tip in entry.prevention_tips:
                out.append(f"  - {tip}")
            out.append("")
            out.append(f"⚠️ **何時必聯絡農改場**:{entry.consult_when}")
            out.append("")

    note = llm_result.get("uncertainty_note", "")
    if note:
        out.append("## ⚠️ AI 不確定提醒")
        out.append("")
        out.append(note)
        out.append("")

    # 區域農改場聯絡
    station, phone = extension_station(region)
    out.append("## 📞 您區域的農改場聯絡")
    out.append("")
    out.append(f"- **{station}**")
    out.append(f"- **電話**: {phone}")
    out.append("")

    out.append("---")
    out.append("")
    out.append(f"*由 cropscan 自動產生於 {today}。辨識結果僅供參考,實際用藥前請依採收安全期、"
               f"自家作物品種、當地氣候狀況再次確認。嚴重病例請聯絡農改場。*")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="案例 JSON 路徑")
    parser.add_argument("--out", type=Path, help="輸出 markdown 路徑")
    parser.add_argument("--no-ai", action="store_true", help="只跑純函式 keyword 比對")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    crop = payload["crop"]
    symptoms = payload["symptom_description"]
    region = payload.get("region", "中部")

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,改用純函式 keyword 比對", file=sys.stderr)

    if use_ai:
        result = llm_diagnose(crop, symptoms)
    else:
        result = render_no_ai_diagnosis(crop, symptoms)

    report = render_diagnosis_report(crop, symptoms, region, result)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
