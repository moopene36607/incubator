"""Taiwan 勞務報酬 / 二代健保補充保費 calculation rules.

Pure functions — no I/O, no LLM. Easy to unit test.

References (rates as of 2026-05; verify against latest 健保署 / 財政部 announcements):
  - 二代健保補充保費費率: 2.11%
  - 二代健保補充保費起扣門檻 (單次給付): NT$20,000
  - 所得稅 10% 扣繳起扣門檻 (9A/9B 單次給付): NT$20,010
  - 50 類別 (薪資所得) 扣繳免稅額 (114年度): NT$94,000 起
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


# Rate constants (review annually — sources commented above)
NHI_SUPPLEMENT_RATE = Decimal("0.0211")
NHI_TRIGGER_THRESHOLD = Decimal("20000")
INCOME_TAX_WITHHOLDING_RATE = Decimal("0.10")
INCOME_TAX_TRIGGER_THRESHOLD_9A_9B = Decimal("20010")
SALARY_50_MONTHLY_EXEMPTION_2025 = Decimal("94000")


# Income categories from 各類所得扣繳率標準
INCOME_CATEGORIES = {
    "9A": "執行業務所得 — 一般執行業務者(律師、會計師、建築師、自由作家、譯者等獨立勞務)",
    "9B": "稿費 — 著作人之著作權所得;同年度未滿 NT$180,000 部分免稅",
    "50": "薪資所得 — 雇傭關係下的勞務,正職/兼職員工適用",
}


@dataclass
class CalcInput:
    amount: Decimal
    income_type: str  # "9A" | "9B" | "50"
    is_union_insured: bool = False  # 工會投保者免扣補充保費
    is_resident: bool = True         # 中華民國境內居住者; non-resident has different rules
    cumulative_9b_this_year: Decimal = Decimal("0")  # 9B 累計判斷免稅額用


@dataclass
class CalcResult:
    gross_amount: Decimal
    income_type: str
    income_tax_withheld: Decimal
    nhi_supplement_withheld: Decimal
    net_to_payee: Decimal
    payer_must_remit: Decimal
    notes: list[str]


def _q(value: Decimal) -> Decimal:
    """Round to nearest NT dollar (no cents)."""
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calculate(inp: CalcInput) -> CalcResult:
    notes: list[str] = []
    gross = Decimal(inp.amount)

    if inp.income_type not in INCOME_CATEGORIES:
        raise ValueError(f"Unknown income_type {inp.income_type!r}; expected one of {list(INCOME_CATEGORIES)}")

    if not inp.is_resident:
        notes.append("⚠️ 非居住者扣繳率不同(通常 18% 或 20%),本工具尚未實作,請查 各類所得扣繳率標準。")

    # --- Income tax withholding ---
    income_tax = Decimal("0")
    if inp.income_type in ("9A", "9B"):
        if gross >= INCOME_TAX_TRIGGER_THRESHOLD_9A_9B:
            income_tax = _q(gross * INCOME_TAX_WITHHOLDING_RATE)
            notes.append(
                f"單次給付 NT${gross:,} ≥ NT${INCOME_TAX_TRIGGER_THRESHOLD_9A_9B:,} 起扣門檻,"
                f"扣繳 10% 所得稅 NT${income_tax:,}。"
            )
        else:
            notes.append(
                f"單次給付 NT${gross:,} 未達 NT${INCOME_TAX_TRIGGER_THRESHOLD_9A_9B:,} 起扣門檻,"
                f"免扣繳所得稅(收款人仍須年度結算申報)。"
            )

        if inp.income_type == "9B":
            tax_free_remaining = max(Decimal("180000") - inp.cumulative_9b_this_year, Decimal("0"))
            tax_free_used = min(tax_free_remaining, gross)
            if tax_free_used > 0:
                notes.append(
                    f"9B 稿費年度免稅額剩餘 NT${tax_free_remaining:,},本筆使用 NT${tax_free_used:,};"
                    f"超出部分才需年度合併申報。"
                )

    elif inp.income_type == "50":
        # 薪資所得簡化:單次低於每月免稅額 (~NT$94,000) 不扣繳;否則按薪資所得扣繳辦法
        if gross < SALARY_50_MONTHLY_EXEMPTION_2025:
            notes.append(
                f"薪資所得 NT${gross:,} 未達 NT${SALARY_50_MONTHLY_EXEMPTION_2025:,} 月免稅額(114年度),"
                f"免扣繳所得稅(實務上仍可由公司用 5% 預扣或填免扣繳)。"
            )
        else:
            income_tax = _q(gross * Decimal("0.05"))
            notes.append(
                "薪資所得超過月免稅額,採 5% 簡化扣繳示範值;真實計算請參考 薪資所得扣繳辦法。"
            )

    # --- NHI supplement (二代健保補充保費) ---
    nhi = Decimal("0")
    if inp.is_union_insured:
        notes.append("收款人為 工會投保者,免扣繳二代健保補充保費。")
    elif gross >= NHI_TRIGGER_THRESHOLD:
        nhi = _q(gross * NHI_SUPPLEMENT_RATE)
        notes.append(
            f"單次給付 NT${gross:,} ≥ NT${NHI_TRIGGER_THRESHOLD:,} 補充保費起扣門檻,"
            f"扣繳 2.11% 補充保費 NT${nhi:,}。"
        )
    else:
        notes.append(
            f"單次給付 NT${gross:,} 未達 NT${NHI_TRIGGER_THRESHOLD:,} 起扣門檻,免扣補充保費。"
        )

    net = gross - income_tax - nhi
    payer_remit = income_tax + nhi

    return CalcResult(
        gross_amount=gross,
        income_type=inp.income_type,
        income_tax_withheld=income_tax,
        nhi_supplement_withheld=nhi,
        net_to_payee=_q(net),
        payer_must_remit=_q(payer_remit),
        notes=notes,
    )
