"""mitsumori — 日本町工場向け 小ロット見積書 AI 自動生成。

Usage:
    python mitsumori.py samples/sample_input.json
    python mitsumori.py samples/sample_input.json --out quote.md

入力 JSON に発行元/顧客情報・案件・部品リスト・レートシートを記載すると、
価格計算 (pricing.py 純粋関数) を行い、Claude が日本のビジネス文体で
見積書 markdown を生成する。

ANTHROPIC_API_KEY は備考・特記事項を AI 生成する場合のみ必須。--no-ai で省略可。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from pricing import LineItem, QuoteTotals, RateSheet, calc_quote


REMARKS_SYSTEM = """あなたは日本の中小製造業の見積担当者です。提示された案件情報をもとに、
見積書の「特記事項」欄に書く文章を生成してください。

ルール:
- 日本語のビジネス文体 (です・ます調) で 3〜6 行程度
- 必要に応じて以下の項目を含める: 材料調達リードタイム、品質基準 (JIS / ISO)、
  検査方法、付帯費用 (送料・梱包費)、量産時の単価変動、図面の解釈に関する確認事項、
  支払い条件の補足
- 項目は箇条書き「・」で出力
- 確実でない情報は記載しない (推測で「JIS Z 2331 準拠」などと書かない)
- 見積書本体に既に記載されている納期・支払い条件は重複させない

出力は特記事項の本文のみ。前後の解説や見出しは不要。"""


@dataclass
class Company:
    name: str
    address: str
    tel: str
    email: str
    representative_title: str
    representative_name: str
    license_number: str = ""  # 適格請求書発行事業者登録番号 (T で始まる 13 桁)
    fax: str = ""


@dataclass
class Customer:
    company: str
    department: str
    contact: str


@dataclass
class QuoteHeader:
    subject: str
    quote_number: str
    issue_date: str
    valid_until: str
    delivery_terms: str
    payment_terms: str
    delivery_location: str


def parse_payload(payload: dict[str, Any]) -> tuple[Company, Customer, QuoteHeader, list[LineItem], RateSheet]:
    c = payload["company"]
    company = Company(
        name=c["name"], address=c["address"], tel=c["tel"], email=c["email"],
        representative_title=c["representative_title"], representative_name=c["representative_name"],
        license_number=c.get("license_number", ""), fax=c.get("fax", ""),
    )
    cu = payload["customer"]
    customer = Customer(company=cu["company"], department=cu["department"], contact=cu["contact"])

    q = payload["quote"]
    today = date.today().isoformat()
    header = QuoteHeader(
        subject=q["subject"],
        quote_number=q.get("quote_number", f"M-{today.replace('-', '')}-001"),
        issue_date=q.get("issue_date", today),
        valid_until=q["valid_until"],
        delivery_terms=q["delivery_terms"],
        payment_terms=q["payment_terms"],
        delivery_location=q["delivery_location"],
    )

    items = [
        LineItem(
            part_name=i["part_name"],
            material=i["material"],
            thickness_mm=float(i["thickness_mm"]),
            quantity=int(i["quantity"]),
            processes=list(i["processes"]),
            material_jpy_per_unit=Decimal(str(i["material_jpy_per_unit"])),
            machining_minutes_per_unit=Decimal(str(i["machining_minutes_per_unit"])),
            remarks=i.get("remarks", ""),
        )
        for i in payload["items"]
    ]

    r = payload["rates"]
    rates = RateSheet(
        machining_jpy_per_min=Decimal(str(r["machining_jpy_per_min"])),
        setup_jpy=Decimal(str(r["setup_jpy"])),
        margin_rate=Decimal(str(r["margin_rate"])),
    )
    return company, customer, header, items, rates


def ai_remarks(subject: str, items: list[LineItem]) -> str:
    import anthropic

    client = anthropic.Anthropic()
    item_summary = "\n".join(
        f"・{i.part_name} / {i.material} t{i.thickness_mm}mm / 数量 {i.quantity} / 工程 {','.join(i.processes)}"
        for i in items
    )
    user_msg = f"件名: {subject}\n\n部品情報:\n{item_summary}\n\n上記案件の特記事項を生成してください。"
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": REMARKS_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def fmt_jpy(amount: Decimal) -> str:
    return f"¥{int(amount):,}"


def render_quote(
    company: Company, customer: Customer, header: QuoteHeader,
    totals: QuoteTotals, ai_generated_remarks: str | None,
) -> str:
    lines: list[str] = []

    lines.append("# 御 見 積 書")
    lines.append("")
    lines.append(f"**No.** {header.quote_number}    **発行日** {header.issue_date}")
    lines.append("")
    lines.append(f"{customer.company}")
    lines.append(f"{customer.department}  {customer.contact}")
    lines.append("")
    lines.append("平素より格別のご高配を賜り、誠にありがとうございます。")
    lines.append("下記の通りお見積もり申し上げますので、ご検討の程よろしくお願い申し上げます。")
    lines.append("")
    lines.append(f"## 件名: {header.subject}")
    lines.append("")
    lines.append(f"**御見積金額  {fmt_jpy(totals.total_incl_tax)} (税込) / {fmt_jpy(totals.subtotal_excl_tax)} (税抜)**")
    lines.append("")

    lines.append("## 明細")
    lines.append("")
    lines.append("| # | 品名 | 材質 / 板厚 | 数量 | 単価 (税抜) | 小計 (税抜) |")
    lines.append("|---|------|-------------|------:|----------:|----------:|")
    for idx, line in enumerate(totals.lines, 1):
        item = line.item
        material_str = f"{item.material} t{item.thickness_mm}mm"
        lines.append(
            f"| {idx} | {item.part_name} | {material_str} | {item.quantity:,} | "
            f"{fmt_jpy(line.unit_price)} | {fmt_jpy(line.line_total)} |"
        )
    lines.append("")

    lines.append("### 工程・備考")
    lines.append("")
    for idx, line in enumerate(totals.lines, 1):
        item = line.item
        lines.append(f"- **#{idx} {item.part_name}**: 工程 = {' / '.join(item.processes)}")
        if item.remarks:
            lines.append(f"    - 備考: {item.remarks}")
    lines.append("")

    lines.append("## 金額内訳")
    lines.append("")
    lines.append("| 項目 | 金額 |")
    lines.append("|------|-----:|")
    lines.append(f"| 小計 (税抜) | {fmt_jpy(totals.subtotal_excl_tax)} |")
    lines.append(f"| 消費税 (10%) | {fmt_jpy(totals.consumption_tax)} |")
    lines.append(f"| **合計 (税込)** | **{fmt_jpy(totals.total_incl_tax)}** |")
    lines.append("")

    lines.append("## 取引条件")
    lines.append("")
    lines.append(f"- **納期**: {header.delivery_terms}")
    lines.append(f"- **お支払い条件**: {header.payment_terms}")
    lines.append(f"- **納品場所**: {header.delivery_location}")
    lines.append(f"- **見積有効期限**: {header.valid_until}")
    lines.append("")

    if ai_generated_remarks:
        lines.append("## 特記事項")
        lines.append("")
        lines.append(ai_generated_remarks)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**【発行者】**")
    lines.append("")
    lines.append(f"{company.name}")
    if company.license_number:
        lines.append(f"適格請求書発行事業者登録番号: {company.license_number}")
    lines.append(f"{company.address}")
    lines.append(f"TEL: {company.tel}" + (f"  FAX: {company.fax}" if company.fax else ""))
    lines.append(f"Email: {company.email}")
    lines.append("")
    lines.append(f"{company.representative_title}  {company.representative_name}  ㊞")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="見積案件 JSON ファイル")
    parser.add_argument("--out", type=Path, help="出力先ファイル (省略時 stdout)")
    parser.add_argument("--no-ai", action="store_true", help="AI 特記事項生成を省略")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: ファイルが見つかりません: {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    company, customer, header, items, rates = parse_payload(payload)
    totals = calc_quote(items, rates)

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設定 — 特記事項の AI 生成はスキップされます。", file=sys.stderr)

    remarks = ai_remarks(header.subject, items) if use_ai else None
    output = render_quote(company, customer, header, totals, remarks)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
