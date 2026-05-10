"""laobao — 台灣 SOHO 勞報單 + 二代健保自動算 + 勞報單草稿產生

Usage:
    python laobao.py samples/sample_input.json
    python laobao.py samples/sample_input.json --out receipt.md

Reads a JSON file describing the payment, optionally uses Claude to classify
ambiguous 所得類別, runs the calculation in tax_rules.py, and outputs a
human-readable 勞報單草稿 in markdown.

ANTHROPIC_API_KEY is only required when income_type is set to "auto".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from tax_rules import INCOME_CATEGORIES, CalcInput, CalcResult, calculate


CLASSIFY_SYSTEM = """你是台灣稅務專員,專門判斷一筆收入屬於哪個所得類別,以決定扣繳辦法。

回傳 JSON 物件,只包含這些欄位:
{
  "income_type": "9A" | "9B" | "50",
  "confidence": "high" | "medium" | "low",
  "reasoning": "一句中文說明"
}

判斷規則:
- 9A 執行業務所得: 自由業者(設計、工程師、文案、譯者、顧問、講師)以獨立業務身分提供勞務、無僱傭關係。
- 9B 稿費: 著作人就其著作所領取的稿費、版稅、撰稿費,具有 著作權法 上的著作。
- 50 薪資所得: 雇傭關係下的勞務,即使是兼職、工讀、PT,只要受雇主指揮監督就算。

模糊狀況:
- 「公司請我接案做網站」如果是獨立完成、按件計酬、無上下班 → 9A
- 「公司請我接案做網站」但需配合公司排班、用公司設備 → 50
- 「在 Medium / 出版社寫文章領稿費」 → 9B
- 「企業內訓講師費」 → 9A(獨立勞務)
- 「家教」 → 50(雇傭關係下的薪資)

只回 JSON,不要其他文字。"""


def llm_classify(description: str) -> tuple[str, str, str]:
    """Returns (income_type, confidence, reasoning)."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=[
            {"type": "text", "text": CLASSIFY_SYSTEM, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": f"請判斷以下情境屬於哪個所得類別:\n\n{description}"}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM did not return JSON: {text!r}")
    parsed = json.loads(text[start : end + 1])
    return parsed["income_type"], parsed["confidence"], parsed["reasoning"]


def format_receipt(payload: dict[str, Any], result: CalcResult, classify_meta: dict[str, str] | None) -> str:
    payer = payload.get("payer", {})
    payee = payload.get("payee", {})
    description = payload.get("description", "(未提供)")
    income_type_label = INCOME_CATEGORIES.get(result.income_type, "未知類別")

    lines: list[str] = []
    lines.append("# 勞報單草稿 / 勞務報酬計算")
    lines.append("")
    lines.append(f"**給付對象**: {payee.get('name', '(未填)')}")
    if payee.get("id"):
        lines.append(f"**對象身分證 / 統編**: {payee['id']}")
    lines.append(f"**付款方**: {payer.get('name', '(未填)')}{(' / 統編 ' + payer['tax_id']) if payer.get('tax_id') else ''}")
    lines.append(f"**勞務內容**: {description}")
    lines.append("")
    lines.append("## 金額拆解")
    lines.append("")
    lines.append(f"| 項目 | 金額 (NT$) |")
    lines.append(f"|------|-----------:|")
    lines.append(f"| 收入總額 (gross) | {int(result.gross_amount):,} |")
    lines.append(f"| 所得稅扣繳 | -{int(result.income_tax_withheld):,} |")
    lines.append(f"| 二代健保補充保費 | -{int(result.nhi_supplement_withheld):,} |")
    lines.append(f"| **實領金額** | **{int(result.net_to_payee):,}** |")
    lines.append("")
    lines.append(f"付款方應代扣 + 代繳合計: **NT${int(result.payer_must_remit):,}**")
    lines.append("")
    lines.append(f"## 所得類別")
    lines.append("")
    lines.append(f"**{result.income_type}** — {income_type_label}")

    if classify_meta:
        lines.append("")
        lines.append(f"_AI 自動判斷信心: {classify_meta['confidence']} — {classify_meta['reasoning']}_")

    lines.append("")
    lines.append("## 計算說明")
    lines.append("")
    for note in result.notes:
        lines.append(f"- {note}")

    lines.append("")
    lines.append("## 勞報單樣式 (給付款公司用)")
    lines.append("")
    lines.append("```")
    lines.append("─" * 50)
    lines.append("            勞 務 報 酬 單")
    lines.append("─" * 50)
    lines.append(f"  付款公司   {payer.get('name', ''):<30}")
    lines.append(f"  公司統編   {payer.get('tax_id', ''):<30}")
    lines.append(f"  受領人     {payee.get('name', ''):<30}")
    lines.append(f"  身分證號   {payee.get('id', ''):<30}")
    lines.append(f"  地址       {payee.get('address', ''):<30}")
    lines.append(f"  勞務內容   {description[:30]}")
    lines.append(f"  所得類別   {result.income_type} {income_type_label[:14]}")
    lines.append("─" * 50)
    lines.append(f"  給付總額         NT$ {int(result.gross_amount):>10,}")
    lines.append(f"  扣繳所得稅 (10%) NT$ {int(result.income_tax_withheld):>10,}")
    lines.append(f"  補充保費 (2.11%) NT$ {int(result.nhi_supplement_withheld):>10,}")
    lines.append(f"  實付金額         NT$ {int(result.net_to_payee):>10,}")
    lines.append("─" * 50)
    lines.append("  受領人簽章: ____________________")
    lines.append("  日期:       ____________________")
    lines.append("─" * 50)
    lines.append("```")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*由 laobao 產生。費率以 2026-05 公告為準,實際申報前請再次核對最新稅法及健保署費率。*")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="輸入 JSON 檔路徑")
    parser.add_argument("--out", type=Path, help="輸出檔案路徑(預設 stdout)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到檔案 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))

    income_type = payload.get("income_type", "auto")
    classify_meta: dict[str, str] | None = None

    if income_type == "auto":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: income_type=auto 需要 ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        description = payload.get("description", "")
        if not description:
            print("error: income_type=auto 時必須提供 description 欄位", file=sys.stderr)
            return 2
        income_type, confidence, reasoning = llm_classify(description)
        classify_meta = {"confidence": confidence, "reasoning": reasoning}

    payee = payload.get("payee", {})
    inp = CalcInput(
        amount=Decimal(str(payload["amount"])),
        income_type=income_type,
        is_union_insured=bool(payee.get("is_union_insured", False)),
        is_resident=bool(payee.get("is_resident", True)),
        cumulative_9b_this_year=Decimal(str(payload.get("cumulative_9b_this_year", 0))),
    )

    result = calculate(inp)
    receipt = format_receipt(payload, result, classify_meta)

    if args.out:
        args.out.write_text(receipt, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(receipt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
