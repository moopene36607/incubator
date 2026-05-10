"""vetnote — 台灣獸醫診所 中文 SOAP 病歷草稿 AI 助手

Usage:
    python vetnote.py samples/sample_input.json
    python vetnote.py samples/sample_input.json --out record.md
    python vetnote.py samples/sample_input.json --no-ai  # 骨架版

設計重點:
- 純函式組裝 SOAP 框架 (病患標頭 / 簽核欄 / 免責聲明)
- AI 只負責 4 段 (S/O/A/P) 的醫療文字撰寫
- AI **絕不開具體藥物劑量** (劑量需獸醫師依個體判斷)
- AI **絕不下確定診斷** (只能 differential + working assessment)
- 病歷草稿明確標注「需獸醫師審閱簽署」 (動保法 + 獸醫師法要求)

ANTHROPIC_API_KEY 在生成 SOAP 時必要 (--no-ai 跳過)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from soap_categories import COMMON_CATEGORIES, ChiefComplaintCategory, lookup


SOAP_SYSTEM = """你是台灣獸醫診所的病歷助理,協助獸醫師快速產出 SOAP 病歷草稿。
你的目標是幫獸醫師壓縮 30-50 份/天的文書時間,**不是**取代獸醫專業判斷。

## 寫作風格

- 繁體中文,獸醫醫療書面語 (例:「腹部觸診示中度痛感」、「皮膚張力延遲」、「TPR 39.2/108/28」)
- 第三人稱,過去式 / 現在式混用 (S 用主訴飼主敘述、O 用「示」「觀察」、A 用「考慮」、P 用「建議」)
- 4 段嚴格分開:**S** (Subjective)、**O** (Objective)、**A** (Assessment)、**P** (Plan)
- 縮寫使用台灣獸醫慣例:TPR、CRT、PE、CBC、UA、AUS、AXR、CCL、IVDD、HD、FHV、FCV 等

## 內容要求

- **S (Subjective)**:主訴、發病時間、症狀演變 (OPQRST 適用時)、相關病史 (過去病史、用藥、飲食改變、誤食、預防醫療紀錄)、飼主敘述
- **O (Objective)**:用戶提供的客觀數據:TPR、體重 (對照前次)、PE 異常發現、實驗室數據、影像學描述。**只寫使用者提供的數值,不要編造任何數字**
- **A (Assessment)**:
  - 列 3-5 項鑑別診斷 (Differential diagnoses),由可能性高到低
  - 說明「目前工作診斷 (Working dx)」+ 支持的證據 (來自 O 段)
  - 用「考慮」「待排除」「可能」「未排除」等審慎措辭,**絕對不下定論**
- **P (Plan)**:
  - 進一步檢查 (workup):列出建議下單項目,如 CBC、biochem、imaging、SNAP test 等
  - 治療計畫:**只寫藥物類別**,如「靜脈輸液矯正脫水」、「止吐劑 (antiemetic)」、「胃腸黏膜保護」、「抗生素 (有細菌感染證據時)」。**絕不寫具體藥名與劑量** (例不可寫 "metoclopramide 0.5 mg/kg IV q8h")
  - 飼主衛教重點 (1-3 點)
  - 回診計畫 (例:「24 小時後 re-eval / 治療無改善請即返診」)

## 嚴格規則

- 不要編造任何使用者沒提供的數字 (TPR、體重、實驗室數據、影像學發現等)
- 不要寫具體藥名與劑量 (這是獸醫師職責)
- 不要下確定診斷 — A 段必須使用「考慮」「待排除」「初步診斷」等用語
- 用戶提供的鑑別診斷分類提示僅供參考,實際 differential 應結合 case 細節
- 直接輸出 markdown 格式 SOAP 4 段,**不要**前後標題或解說

## 輸出格式

```markdown
## S — 主觀
(內容)

## O — 客觀
(內容)

## A — 評估
**鑑別診斷**:
1. ...
2. ...
3. ...

**工作診斷**:...

## P — 計畫
**進一步檢查**:
- ...

**治療**:
- ...

**飼主衛教**:
- ...

**回診**:...
```
"""


def render_patient_header(patient: dict[str, Any], visit: dict[str, Any]) -> list[str]:
    out: list[str] = []
    out.append("# 動物病歷 (SOAP)")
    out.append("")
    out.append("## 病患基本資料")
    out.append("")
    out.append(f"- **病患姓名**: {patient.get('name', '(未填)')}")
    out.append(f"- **物種 / 品種**: {patient.get('species', '')} / {patient.get('breed', '')}")
    age = patient.get("age", {})
    age_str = f"{age.get('years', 0)} 歲 {age.get('months', 0)} 個月" if isinstance(age, dict) else str(age)
    out.append(f"- **年齡**: {age_str}")
    out.append(f"- **性別 / 結紮**: {patient.get('sex', '')} / {patient.get('neuter_status', '未提供')}")
    out.append(f"- **體重**: {patient.get('current_weight_kg', '?')} kg"
               + (f"(前次 {patient.get('previous_weight_kg')} kg)" if patient.get("previous_weight_kg") else ""))
    out.append(f"- **晶片號**: {patient.get('chip_id', '(未植入 / 未填)')}")
    if patient.get("owner_name"):
        out.append(f"- **飼主**: {patient['owner_name']}")
    out.append("")
    out.append("## 就診資訊")
    out.append("")
    out.append(f"- **就診日期**: {visit.get('visit_date', date.today().isoformat())}")
    out.append(f"- **就診類型**: {visit.get('visit_type', '一般門診')}")
    out.append(f"- **承辦獸醫師**: {visit.get('vet_name', '(待簽核)')}")
    out.append(f"- **主訴大類**: {visit.get('chief_complaint_category_label') or visit.get('chief_complaint_category', '(未指定)')}")
    out.append("")
    return out


def render_skeleton_soap(category: ChiefComplaintCategory | None) -> str:
    cat_hint = (f" (參考 {category.chinese} 類別)" if category else "")
    return (
        f"## S — 主觀\n(請填入:主訴、發病時間、症狀演變、相關病史、飼主敘述){cat_hint}\n\n"
        f"## O — 客觀\n(請填入:TPR、體重、PE 異常發現、實驗室數據、影像學)\n\n"
        f"## A — 評估\n**鑑別診斷**:\n1. ...\n2. ...\n3. ...\n\n**工作診斷**:...\n\n"
        f"## P — 計畫\n**進一步檢查**:- ...\n\n**治療**:- ...\n\n"
        f"**飼主衛教**:- ...\n\n**回診**:...\n"
    )


def ai_generate_soap(payload: dict[str, Any], category: ChiefComplaintCategory | None) -> str:
    import anthropic

    cat_block = ""
    if category:
        cat_block = (
            f"\n\n## 主訴大類提示 (僅供 grounding,不限制最終 differential)\n\n"
            f"類別: {category.chinese} ({category.english})\n"
            f"常見鑑別診斷: {', '.join(category.common_etiologies)}\n"
            f"必記錄欄位 (O 段): {', '.join(category.must_record_in_o)}\n"
            f"通常下單檢查: {', '.join(category.typical_workup)}\n"
            f"治療類別 (僅類別,不開劑量): {', '.join(category.treatment_categories)}\n"
        )

    user = (
        "## 本次就診資料\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
        + cat_block
        + "\n\n請根據以上資料撰寫 SOAP 4 段 (markdown 格式)。"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=[{"type": "text", "text": SOAP_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def render_signature(visit: dict[str, Any]) -> list[str]:
    out: list[str] = []
    out.append("---")
    out.append("")
    out.append("## 簽核")
    out.append("")
    out.append(f"- [ ] **承辦獸醫師審閱簽名**: {visit.get('vet_name', '________')}  日期 ________")
    out.append("- [ ] 已輸入 PIMS (毛孩管家 / 獸易通 / 其他)")
    out.append("")
    out.append("---")
    out.append("")
    out.append("> ⚠️ **本病歷為 AI 自動產生之草稿,僅供獸醫師審閱起點。實際診斷、用藥、劑量、處置必須由執業獸醫師依個別病例判斷後親自確認簽署。AI 不取代獸醫師專業判斷。**")
    out.append("")
    out.append(f"*vetnote prototype 自動產生於 {date.today().isoformat()}*")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="本次就診 JSON")
    parser.add_argument("--out", type=Path, help="輸出檔案 (省略 stdout)")
    parser.add_argument("--no-ai", action="store_true", help="不呼叫 AI,輸出骨架")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    patient = payload["patient"]
    visit = payload["visit"]
    cat_code = visit.get("chief_complaint_category_code", "")
    category = lookup(cat_code) if cat_code else None
    if cat_code and category is None:
        print(f"warn: 主訴代碼 {cat_code!r} 不在已知清單,改 fallback", file=sys.stderr)

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,輸出骨架版", file=sys.stderr)

    soap = ai_generate_soap(payload, category) if use_ai else render_skeleton_soap(category)

    out_lines: list[str] = []
    out_lines.extend(render_patient_header(patient, visit))
    out_lines.append(soap)
    out_lines.append("")
    out_lines.extend(render_signature(visit))
    output = "\n".join(out_lines) + "\n"

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
