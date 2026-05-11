"""carepen — 長照居服員語音逐字稿 → LTCIS 服務記錄草稿 AI 助手

Usage:
    # AI 模式:從逐字稿產生
    python carepen.py --transcript samples/sample_transcript.txt --case samples/case_metadata.json

    # 無 AI 模式:已有結構化 JSON 直接渲染
    python carepen.py --structured samples/sample_structured.json

    # 輸出到檔案
    python carepen.py --transcript ... --case ... --out output.md

設計重點:
- 純函式渲染 (LTCIS 格式) 從不交給 AI
- AI 只負責語意理解 + 把口語逐字稿結構化成 LTCIS 服務代碼
- 居服員每筆紀錄最後仍需人工確認 + 督導簽核 (法規要求)

ANTHROPIC_API_KEY 只在 --transcript 模式必需。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ltcis_codes import SERVICE_CODES, ServiceCode, all_codes_table, lookup_by_code


@dataclass
class ServiceLine:
    code: str
    quantity: int
    description: str  # 居服員實際提供內容詳述


@dataclass
class VitalSigns:
    body_temp_c: float | None = None
    blood_pressure: str | None = None  # "收縮/舒張", e.g. "140/90"
    pulse_bpm: int | None = None
    blood_sugar_mgdl: int | None = None
    notes: str = ""


@dataclass
class StructuredRecord:
    service_lines: list[ServiceLine]
    case_status_observations: str    # 個案狀況描述 (情緒 / 食慾 / 排便 / 活動 / 睡眠)
    vital_signs: VitalSigns
    abnormal_events: str             # 異常事件 — 跌倒 / 出血 / 呼吸異常 / 通報內容
    follow_up_notes: str             # 後續注意事項 / 給督導參考
    raw_transcript_excerpt: str      # 原始逐字稿節錄 (供查核)


STRUCTURE_SYSTEM = """你是台灣長期照顧服務的居服員紀錄助理。使用者會傳給你一段居服員口語逐字稿
(可能來自 Whisper 語音辨識),你的任務是把它轉換為長照支付制度 (LTCIS) 規定格式
的結構化服務記錄。

## 可用服務代碼 (LTCIS 居家服務)

{codes_table}

## 輸出格式

請輸出 JSON,**不要**包裹在 code fence,**不要**有其他文字解釋:

```
{{
  "service_lines": [
    {{ "code": "BA04", "quantity": 1, "description": "詳細描述居服員實際做的事" }}
  ],
  "case_status_observations": "個案狀況綜合觀察 (情緒 / 食慾 / 排便 / 活動 / 睡眠 / 自述等)",
  "vital_signs": {{
    "body_temp_c": 36.5 或 null,
    "blood_pressure": "140/90" 或 null,
    "pulse_bpm": 72 或 null,
    "blood_sugar_mgdl": 110 或 null,
    "notes": "備註,例如「血壓略高,已通報主要照顧者」"
  }},
  "abnormal_events": "異常事件描述 — 沒有就空字串",
  "follow_up_notes": "後續注意事項 / 給督導參考"
}}
```

## 規則

- **絕對只用上方提供的服務代碼**。逐字稿中任何居服員實際做的事都對應到表中一個代碼。
- 一個逐字稿可能對應多個 service_lines (例:洗澡 + 翻身 + 換尿布 = 3 行)。
- description 用第三人稱、過去式、台灣居服員常用書面語 (例:「協助個案於床上完成全身擦澡並更換清潔衣物」),不是直接複製口語。
- 量化資料 (體溫 / 血壓 / 血糖) 從逐字稿中精準擷取,沒提到就用 null。**絕對不要編造數字**。
- abnormal_events 只在逐字稿明確提到異常 (跌倒、受傷、嗆咳、意識不清等) 才填,否則空字串。
- follow_up_notes 應該針對逐字稿中的可疑訊號給出建議 (例:血壓 140/90 持續 3 天 → 建議督導與家屬討論回診)。
- 不要編造逐字稿中沒提到的內容。
"""


def build_system_prompt() -> str:
    codes_table = "\n".join(
        f"- **{c.code}** ({c.category}) {c.name} — 計價單位:{c.unit};常見字眼:{', '.join(c.example_keywords)}"
        for c in all_codes_table()
    )
    return STRUCTURE_SYSTEM.format(codes_table=codes_table)


def ai_structure(transcript: str) -> StructuredRecord:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[{"type": "text", "text": build_system_prompt(), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"逐字稿:\n\n{transcript}"}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒有回 JSON:\n{raw}")
    parsed = json.loads(raw[start : end + 1])

    return StructuredRecord(
        service_lines=[
            ServiceLine(code=l["code"], quantity=int(l["quantity"]), description=l["description"])
            for l in parsed["service_lines"]
        ],
        case_status_observations=parsed.get("case_status_observations", ""),
        vital_signs=VitalSigns(
            body_temp_c=parsed.get("vital_signs", {}).get("body_temp_c"),
            blood_pressure=parsed.get("vital_signs", {}).get("blood_pressure"),
            pulse_bpm=parsed.get("vital_signs", {}).get("pulse_bpm"),
            blood_sugar_mgdl=parsed.get("vital_signs", {}).get("blood_sugar_mgdl"),
            notes=parsed.get("vital_signs", {}).get("notes", ""),
        ),
        abnormal_events=parsed.get("abnormal_events", ""),
        follow_up_notes=parsed.get("follow_up_notes", ""),
        raw_transcript_excerpt=transcript[:300] + ("..." if len(transcript) > 300 else ""),
    )


def render_record(case: dict[str, Any], record: StructuredRecord) -> str:
    out: list[str] = []
    today = date.today().isoformat()
    visit_date = case.get("visit_date", today)
    visit_time = case.get("visit_time", "")

    out.append("# 長照居家服務記錄表")
    out.append("(草稿 — 居服員確認後送督導複核)")
    out.append("")
    out.append("## 基本資料")
    out.append("")
    out.append(f"- **個案編號**: {case.get('case_id', '(未填)')}")
    out.append(f"- **個案姓名**: {case.get('case_name', '(未填)')}")
    out.append(f"- **居服單位**: {case.get('agency', '(未填)')}")
    out.append(f"- **居服員**: {case.get('caregiver_name', '(未填)')}")
    out.append(f"- **服務日期**: {visit_date}    **時段**: {visit_time or '(未填)'}")
    out.append("")

    out.append("## 服務項目")
    out.append("")
    out.append("| 項次 | 代碼 | 服務名稱 | 計量 | 詳述 |")
    out.append("|---|---|---|---:|---|")
    for i, line in enumerate(record.service_lines, 1):
        ref = lookup_by_code(line.code)
        name = ref.name if ref else "(代碼未知 — 待查)"
        unit = ref.unit if ref else ""
        qty_display = f"{line.quantity} {unit}".strip()
        out.append(f"| {i} | **{line.code}** | {name} | {qty_display} | {line.description} |")
    out.append("")

    out.append("## 個案狀況觀察")
    out.append("")
    out.append(record.case_status_observations or "(無)")
    out.append("")

    out.append("## 生命徵象")
    out.append("")
    vs = record.vital_signs
    if any([vs.body_temp_c is not None, vs.blood_pressure, vs.pulse_bpm, vs.blood_sugar_mgdl]):
        rows: list[str] = []
        if vs.body_temp_c is not None:
            rows.append(f"- **體溫**: {vs.body_temp_c} °C")
        if vs.blood_pressure:
            rows.append(f"- **血壓**: {vs.blood_pressure} mmHg")
        if vs.pulse_bpm is not None:
            rows.append(f"- **脈搏**: {vs.pulse_bpm} bpm")
        if vs.blood_sugar_mgdl is not None:
            rows.append(f"- **血糖**: {vs.blood_sugar_mgdl} mg/dL")
        out.extend(rows)
        if vs.notes:
            out.append(f"- 備註: {vs.notes}")
    else:
        out.append("(本次未量測)")
    out.append("")

    if record.abnormal_events:
        out.append("## ⚠️ 異常事件")
        out.append("")
        out.append(record.abnormal_events)
        out.append("")

    out.append("## 後續注意事項 / 給督導參考")
    out.append("")
    out.append(record.follow_up_notes or "(無特殊事項)")
    out.append("")

    out.append("---")
    out.append("")
    out.append("## 簽核")
    out.append("")
    out.append(f"- [ ] **居服員確認**: {case.get('caregiver_name', '_______')} _______ 日期 _______")
    out.append("- [ ] **督導複核**: _______ 日期 _______")
    out.append("- [ ] 已上傳衛福部 LTCIS")
    out.append("")

    out.append("---")
    out.append("")
    out.append("### 原始逐字稿節錄(供查核)")
    out.append("")
    out.append("> " + record.raw_transcript_excerpt.replace("\n", "\n> "))
    out.append("")
    out.append("*carepen prototype 自動產生。LTCIS 代碼以衛福部公告版為準,送出前請督導複核。*")
    return "\n".join(out) + "\n"


def parse_structured(payload: dict[str, Any]) -> StructuredRecord:
    return StructuredRecord(
        service_lines=[
            ServiceLine(code=l["code"], quantity=int(l["quantity"]), description=l["description"])
            for l in payload["service_lines"]
        ],
        case_status_observations=payload.get("case_status_observations", ""),
        vital_signs=VitalSigns(**payload.get("vital_signs", {})),
        abnormal_events=payload.get("abnormal_events", ""),
        follow_up_notes=payload.get("follow_up_notes", ""),
        raw_transcript_excerpt=payload.get("raw_transcript_excerpt", "(本記錄為直接結構化輸入,無逐字稿)"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcript", type=Path, help="逐字稿文字檔(需 API key)")
    parser.add_argument("--case", type=Path, help="個案資料 JSON(配合 --transcript)")
    parser.add_argument("--structured", type=Path, help="已結構化的記錄 JSON(免 API key)")
    parser.add_argument("--out", type=Path, help="輸出檔案(省略=stdout)")
    args = parser.parse_args()

    if args.structured:
        payload = json.loads(args.structured.read_text(encoding="utf-8"))
        record = parse_structured(payload["record"])
        case = payload["case"]
    elif args.transcript and args.case:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: --transcript 模式需要 ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        transcript = args.transcript.read_text(encoding="utf-8")
        case = json.loads(args.case.read_text(encoding="utf-8"))
        record = ai_structure(transcript)
    else:
        parser.print_usage(sys.stderr)
        print("\nerror: 請提供 --structured 或 --transcript + --case", file=sys.stderr)
        return 2

    output = render_record(case, record)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
