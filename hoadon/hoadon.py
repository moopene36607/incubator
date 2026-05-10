"""hoadon — Hộ kinh doanh F&B daily e-invoice batch generator (Decree 70 compliant).

Usage:
    python hoadon.py samples/sample_input.json
    python hoadon.py samples/sample_input.json --out invoice.md
    python hoadon.py --freetext samples/sample_input_freetext.txt --shop samples/shop_config.json

Hai chế độ vận hành:
  1. JSON đầu vào có cấu trúc — không cần API key (đi thẳng qua tax_rules)
  2. Đầu vào tự do (ghi nhớ giọng nói / sổ tay viết tay) — Claude phân tích
     thành danh sách bán hàng có cấu trúc, rồi tổng hợp như chế độ 1.

Tuân thủ Nghị định 70/2025/NĐ-CP: tự động phân loại các giao dịch
< 50.000 VND vào hóa đơn tổng hợp hàng ngày, các giao dịch >= 50.000 VND
được liệt kê riêng để xuất hóa đơn từng giao dịch.

Cần ANTHROPIC_API_KEY chỉ khi dùng --freetext.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from vat_rules import (
    BATCH_AGGREGATION_THRESHOLD_VND,
    CategorizedSales,
    InvoiceTotals,
    SaleLine,
    calc_totals,
    categorize_per_decree70,
    vat_rate_for,
)


PARSE_SYSTEM = """Bạn là trợ lý kế toán tự động cho quán ăn / cà phê / nhà hàng nhỏ tại Việt Nam.

Người dùng sẽ gửi ghi chú bán hàng tự do (ghi âm chuyển văn bản, hoặc chụp ảnh sổ tay).
Hãy trích xuất danh sách bán hàng theo dạng JSON với các trường:

{
  "lines": [
    {
      "item_name": "Tên món bằng tiếng Việt",
      "quantity": <số nguyên>,
      "unit_price_vnd": <số, đồng VN>,
      "category": "fb" | "standard" | "exempt",
      "note": "ghi chú thêm nếu có"
    }
  ]
}

Quy tắc:
- "fb" cho đồ ăn / đồ uống tại quán (VAT 8% theo Nghị quyết 142/2024/QH15)
- "standard" cho hàng hóa khác (VAT 10%)
- "exempt" chỉ dùng khi rõ ràng được miễn VAT (gạo thô, rau quả tươi chưa chế biến v.v.)
- Đơn giá phải là giá đã bao gồm VAT (giá khách trả trên menu) — đó là chuẩn F&B Việt Nam
- Nếu thiếu thông tin nào, đặt giá trị hợp lý nhất theo ngữ cảnh và ghi chú trong "note"
- Trả về JSON thuần, không có chữ giải thích nào khác

Ví dụ:
Input: "Hôm nay bán 25 phở bò 65k, 18 phở gà 60k, 40 trà đá 10k, 12 cafe sữa đá 25k"
Output: {"lines": [
  {"item_name":"Phở bò","quantity":25,"unit_price_vnd":65000,"category":"fb","note":""},
  {"item_name":"Phở gà","quantity":18,"unit_price_vnd":60000,"category":"fb","note":""},
  {"item_name":"Trà đá","quantity":40,"unit_price_vnd":10000,"category":"fb","note":""},
  {"item_name":"Cà phê sữa đá","quantity":12,"unit_price_vnd":25000,"category":"fb","note":""}
]}
"""


def fmt_vnd(amount: Decimal) -> str:
    return f"{int(amount):,} VND".replace(",", ".")


def llm_parse_freetext(text: str) -> list[SaleLine]:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[{"type": "text", "text": PARSE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Hãy trích xuất danh sách bán hàng từ ghi chú sau:\n\n{text}"}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM không trả về JSON hợp lệ:\n{raw}")
    parsed = json.loads(raw[start : end + 1])
    return [
        SaleLine(
            item_name=l["item_name"],
            quantity=int(l["quantity"]),
            unit_price_vnd=Decimal(str(l["unit_price_vnd"])),
            category=l.get("category", "fb"),
            note=l.get("note", ""),
        )
        for l in parsed["lines"]
    ]


def lines_from_json(payload: dict[str, Any]) -> list[SaleLine]:
    return [
        SaleLine(
            item_name=l["item_name"],
            quantity=int(l["quantity"]),
            unit_price_vnd=Decimal(str(l["unit_price_vnd"])),
            category=l.get("category", "fb"),
            note=l.get("note", ""),
        )
        for l in payload["lines"]
    ]


def render_daily_invoice(
    shop: dict[str, Any],
    business_date: str,
    lines: list[SaleLine],
    categorized: CategorizedSales,
    totals: InvoiceTotals,
) -> str:
    out: list[str] = []
    out.append("# HÓA ĐƠN ĐIỆN TỬ TỔNG HỢP HÀNG NGÀY")
    out.append("## (Per Nghị định 70/2025/NĐ-CP — Daily Summary E-Invoice)")
    out.append("")
    out.append(f"**Ngày lập**: {business_date}    "
               f"**Số hóa đơn**: HĐ-{business_date.replace('-', '')}-001")
    out.append("")
    out.append("## Thông tin hộ kinh doanh / Business")
    out.append("")
    out.append(f"- **Tên hộ kinh doanh**: {shop.get('business_name', '(chưa nhập)')}")
    out.append(f"- **Mã số thuế (MST)**: {shop.get('tax_code', '(chưa nhập)')}")
    out.append(f"- **Địa chỉ**: {shop.get('address', '(chưa nhập)')}")
    out.append(f"- **Người đại diện**: {shop.get('owner_name', '(chưa nhập)')}    "
               f"📞 {shop.get('phone', '')}")
    out.append("")

    # ------------------------------------------------------------------
    # Section 1: Items requiring individual invoices (≥ 50,000 VND/unit)
    # ------------------------------------------------------------------
    if categorized.individual_invoices:
        out.append("## ⚠️ Phần A — Giao dịch ≥ 50.000 VND (CẦN xuất hóa đơn riêng)")
        out.append("")
        out.append("Per Nghị định 70, các mặt hàng có đơn giá từ 50.000 VND trở lên")
        out.append("KHÔNG được tổng hợp vào hóa đơn ngày — phải xuất hóa đơn cho từng giao dịch.")
        out.append("")
        out.append("| # | Tên hàng | Đơn giá | SL | Thành tiền | VAT% |")
        out.append("|---|----------|--------:|---:|-----------:|------:|")
        for i, line in enumerate(categorized.individual_invoices, 1):
            line_total = line.unit_price_vnd * line.quantity
            rate_pct = int(vat_rate_for(line.category) * 100)
            out.append(
                f"| {i} | {line.item_name} | {fmt_vnd(line.unit_price_vnd)} | "
                f"{line.quantity} | {fmt_vnd(line_total)} | {rate_pct}% |"
            )
        out.append("")

    # ------------------------------------------------------------------
    # Section 2: Items eligible for daily summary aggregation (< 50,000 VND)
    # ------------------------------------------------------------------
    if categorized.batch_aggregated:
        out.append("## ✅ Phần B — Giao dịch < 50.000 VND (được tổng hợp)")
        out.append("")
        out.append("Các mặt hàng dưới đây được tổng hợp vào hóa đơn điện tử ngày này")
        out.append("theo điều khoản Nghị định 70 cho phép F&B / bán lẻ.")
        out.append("")
        out.append("| # | Tên hàng | Đơn giá | SL | Thành tiền | VAT% |")
        out.append("|---|----------|--------:|---:|-----------:|------:|")
        for i, line in enumerate(categorized.batch_aggregated, 1):
            line_total = line.unit_price_vnd * line.quantity
            rate_pct = int(vat_rate_for(line.category) * 100)
            out.append(
                f"| {i} | {line.item_name} | {fmt_vnd(line.unit_price_vnd)} | "
                f"{line.quantity} | {fmt_vnd(line_total)} | {rate_pct}% |"
            )
        out.append("")

    # ------------------------------------------------------------------
    # Totals
    # ------------------------------------------------------------------
    out.append("## Tổng kết doanh thu ngày")
    out.append("")
    out.append("| Khoản mục | Số tiền |")
    out.append("|-----------|--------:|")
    out.append(f"| Doanh thu (đã bao gồm VAT) | {fmt_vnd(totals.gross_revenue)} |")
    out.append(f"| Doanh thu thuần (chưa VAT) | {fmt_vnd(totals.net_revenue)} |")
    out.append(f"| Tổng VAT | {fmt_vnd(totals.vat_total)} |")
    out.append(f"| **Số mặt hàng cần xuất hóa đơn riêng** | **{totals.individual_count} loại** |")
    out.append(f"| **Số mặt hàng được gộp vào HĐ tổng hợp** | **{totals.batch_count} loại** |")
    out.append("")

    out.append("## Bước tiếp theo")
    out.append("")
    out.append("1. Kiểm tra danh sách Phần A — xuất hóa đơn riêng cho từng giao dịch ≥ 50.000 VND.")
    out.append("2. Phần B sẽ tự động được kết xuất sang định dạng XML và đẩy lên cổng VNPT/MISA.")
    out.append("3. Lưu lại bản này để đối chiếu sổ kế toán cuối tháng và quyết toán thuế cuối năm.")
    out.append("")

    out.append("---")
    out.append("")
    out.append(f"*Tự động sinh bởi hoadon — phiên bản prototype. "
               f"Ngưỡng tổng hợp: {fmt_vnd(BATCH_AGGREGATION_THRESHOLD_VND)} (Nghị định 70/2025).*")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", nargs="?", type=Path, help="JSON đầu vào (cấu trúc)")
    parser.add_argument("--freetext", type=Path, help="File văn bản tự do (cần API key)")
    parser.add_argument("--shop", type=Path, help="JSON cấu hình thông tin hộ kinh doanh (kèm với --freetext)")
    parser.add_argument("--out", type=Path, help="File kết quả (mặc định: stdout)")
    args = parser.parse_args()

    if args.freetext:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: --freetext yêu cầu ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        if not args.freetext.exists():
            print(f"error: không tìm thấy {args.freetext}", file=sys.stderr)
            return 2
        text = args.freetext.read_text(encoding="utf-8")
        lines = llm_parse_freetext(text)
        shop_payload: dict[str, Any] = {}
        if args.shop and args.shop.exists():
            shop_payload = json.loads(args.shop.read_text(encoding="utf-8")).get("shop", {})
        payload_date = date.today().isoformat()
    else:
        if not args.input or not args.input.exists():
            print(f"error: cần đường dẫn JSON hợp lệ", file=sys.stderr)
            return 2
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        lines = lines_from_json(payload)
        shop_payload = payload.get("shop", {})
        payload_date = payload.get("business_date", date.today().isoformat())

    categorized = categorize_per_decree70(lines)
    totals = calc_totals(lines)
    invoice = render_daily_invoice(shop_payload, payload_date, lines, categorized, totals)

    if args.out:
        args.out.write_text(invoice, encoding="utf-8")
        print(f"Đã ghi ra {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(invoice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
