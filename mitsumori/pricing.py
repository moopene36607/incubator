"""mitsumori — 価格計算ロジック (純粋関数, no I/O, no LLM).

中小製造業の小ロット見積もりに必要な計算:
  単価 = (材料費 + 加工費 + 段取り費按分) × (1 + 利益率)
  合計 = Σ 単価 × 数量
  税込 = 合計 + 消費税

意図的にシンプルに保ち、各町工場が自社のレートシートを config で差し替えられる
構造にしてある。実運用時はマシンチャージ表 / 材料相場表を入れ替えるだけ。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


CONSUMPTION_TAX_RATE = Decimal("0.10")  # 2026 年現在の標準税率


@dataclass
class LineItem:
    part_name: str
    material: str
    thickness_mm: float
    quantity: int
    processes: list[str]
    material_jpy_per_unit: Decimal
    machining_minutes_per_unit: Decimal
    remarks: str = ""


@dataclass
class RateSheet:
    machining_jpy_per_min: Decimal
    setup_jpy: Decimal
    margin_rate: Decimal


@dataclass
class LineQuote:
    item: LineItem
    material_total: Decimal
    machining_total: Decimal
    setup_apportioned: Decimal
    subtotal_before_margin: Decimal
    margin_amount: Decimal
    unit_price: Decimal      # 顧客提示用 (税抜単価)
    line_total: Decimal      # 顧客提示用 (税抜小計)


@dataclass
class QuoteTotals:
    lines: list[LineQuote]
    subtotal_excl_tax: Decimal
    consumption_tax: Decimal
    total_incl_tax: Decimal


def _round100(value: Decimal) -> Decimal:
    """町工場の慣習として 100 円単位で丸める。"""
    return (value / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 100


def _round1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calc_quote(items: list[LineItem], rates: RateSheet) -> QuoteTotals:
    if not items:
        raise ValueError("items が空です。")

    total_qty = sum(i.quantity for i in items)
    if total_qty == 0:
        raise ValueError("数量合計が 0 です。")

    lines: list[LineQuote] = []

    for item in items:
        material_total = item.material_jpy_per_unit * item.quantity
        machining_per_unit = item.machining_minutes_per_unit * rates.machining_jpy_per_min
        machining_total = machining_per_unit * item.quantity

        # 段取り費は数量比例で按分
        setup_apportioned = rates.setup_jpy * Decimal(item.quantity) / Decimal(total_qty)

        subtotal_before_margin = material_total + machining_total + setup_apportioned
        margin_amount = subtotal_before_margin * rates.margin_rate
        line_total = _round100(subtotal_before_margin + margin_amount)
        unit_price = _round1(line_total / item.quantity)

        lines.append(LineQuote(
            item=item,
            material_total=_round1(material_total),
            machining_total=_round1(machining_total),
            setup_apportioned=_round1(setup_apportioned),
            subtotal_before_margin=_round1(subtotal_before_margin),
            margin_amount=_round1(margin_amount),
            unit_price=unit_price,
            line_total=line_total,
        ))

    subtotal = sum((line.line_total for line in lines), Decimal("0"))
    tax = _round1(subtotal * CONSUMPTION_TAX_RATE)
    total = subtotal + tax

    return QuoteTotals(
        lines=lines,
        subtotal_excl_tax=subtotal,
        consumption_tax=tax,
        total_incl_tax=total,
    )
