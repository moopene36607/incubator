"""hoadon — Vietnamese VAT calculation + Decree 70 daily batch logic.

Pure functions only — no I/O, no LLM. Easy to unit test.

Rates (as of 2026-05; verify against latest Bộ Tài chính / Tổng cục Thuế):
  - F&B services (8%): temporary reduced VAT rate per Resolution 142/2024/QH15 + extensions
  - Standard goods (10%): default VAT rate
  - Decree 70 batch threshold: items priced under 50,000 VND can be aggregated
    into a single daily summary invoice instead of issuing individual ones.

Source: Decree 123/2020/ND-CP + Decree 70/2025/ND-CP amendments
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


# Decree 70: items below this VND threshold per transaction may be aggregated
BATCH_AGGREGATION_THRESHOLD_VND = Decimal("50000")

# VAT rates (verify current values before production use)
VAT_RATE_FB = Decimal("0.08")        # F&B services — reduced rate
VAT_RATE_STANDARD = Decimal("0.10")  # standard goods/services
VAT_RATE_EXEMPT = Decimal("0.00")    # exempt categories


@dataclass
class SaleLine:
    item_name: str
    quantity: int
    unit_price_vnd: Decimal
    category: str = "fb"  # "fb" | "standard" | "exempt"
    note: str = ""


@dataclass
class CategorizedSales:
    individual_invoices: list[SaleLine]   # ≥ 50,000 VND/unit — must issue individual invoice
    batch_aggregated: list[SaleLine]      # < 50,000 VND/unit — eligible for daily summary


@dataclass
class InvoiceTotals:
    gross_revenue: Decimal       # gross before tax (sum of unit_price × qty)
    vat_total: Decimal           # total VAT collected
    net_revenue: Decimal         # gross excluding VAT (assuming prices include VAT — Vietnamese standard)
    individual_count: int        # number of items needing individual invoices
    batch_count: int             # number of items eligible for batch aggregation


def _q(value: Decimal) -> Decimal:
    """Round to nearest VND."""
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def vat_rate_for(category: str) -> Decimal:
    return {
        "fb": VAT_RATE_FB,
        "standard": VAT_RATE_STANDARD,
        "exempt": VAT_RATE_EXEMPT,
    }.get(category, VAT_RATE_STANDARD)


def categorize_per_decree70(lines: list[SaleLine]) -> CategorizedSales:
    """Split sales lines per Decree 70 batching rules."""
    individual: list[SaleLine] = []
    batch: list[SaleLine] = []
    for line in lines:
        if line.unit_price_vnd >= BATCH_AGGREGATION_THRESHOLD_VND:
            individual.append(line)
        else:
            batch.append(line)
    return CategorizedSales(individual_invoices=individual, batch_aggregated=batch)


def calc_totals(lines: list[SaleLine]) -> InvoiceTotals:
    """Compute totals across all lines.

    Vietnamese F&B retail prices are typically VAT-inclusive — the customer
    sees one number on the menu. We split the inclusive total back out into
    gross-excluding-VAT and VAT amount per line based on each line's category.
    """
    if not lines:
        raise ValueError("Empty sales lines.")

    gross_inclusive = Decimal("0")
    vat_total = Decimal("0")
    net_excluding = Decimal("0")

    for line in lines:
        line_total_inclusive = Decimal(line.unit_price_vnd) * Decimal(line.quantity)
        rate = vat_rate_for(line.category)
        # price = net × (1 + rate)  →  net = price / (1 + rate)
        line_net = line_total_inclusive / (Decimal("1") + rate)
        line_vat = line_total_inclusive - line_net

        gross_inclusive += line_total_inclusive
        vat_total += line_vat
        net_excluding += line_net

    categorized = categorize_per_decree70(lines)

    return InvoiceTotals(
        gross_revenue=_q(gross_inclusive),
        vat_total=_q(vat_total),
        net_revenue=_q(net_excluding),
        individual_count=len(categorized.individual_invoices),
        batch_count=len(categorized.batch_aggregated),
    )
