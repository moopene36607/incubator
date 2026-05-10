"""settlekit — 한국 프리랜서 크리에이터 정산 계산 (순수 함수, no I/O, no LLM).

원천징수율 (2026 년 5 월 기준):
  - 사업소득 (3.3%) = 소득세 3% + 지방소득세 0.3%
    → 프리랜서 크리에이터의 광고 협찬료에 일반적으로 적용
  - 일시적 사업소득은 22% (소득세 20% + 지방소득세 2%) 적용 가능 — 옵션으로 지원

요건이 변경되면 상수만 수정하면 됨.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


WITHHOLDING_RATE_FREELANCE = Decimal("0.033")   # 일반적인 사업소득 (creator brand deal 표준)
WITHHOLDING_RATE_TEMPORARY = Decimal("0.220")   # 일시적 사업소득 (드물지만 일부 case)
VAT_RATE = Decimal("0.10")                       # 부가가치세 10%


@dataclass(frozen=True)
class SettlementInput:
    gross_amount_krw: Decimal
    income_type: str = "freelance"   # "freelance" | "temporary"
    is_business_registered: bool = False  # True 면 사업자등록 → VAT 별도 청구
    platform_fee_krw: Decimal = Decimal("0")  # MCN 수수료 등 차감 항목


@dataclass
class SettlementResult:
    gross_amount: Decimal
    vat: Decimal               # 사업자 등록자만 적용
    withholding_tax: Decimal
    platform_fee: Decimal
    net_to_creator: Decimal
    notes: list[str]


def _q(value: Decimal) -> Decimal:
    """원 단위 반올림."""
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calc_settlement(inp: SettlementInput) -> SettlementResult:
    notes: list[str] = []
    gross = Decimal(inp.gross_amount_krw)

    if inp.income_type == "freelance":
        rate = WITHHOLDING_RATE_FREELANCE
        notes.append(
            f"사업소득 원천징수 3.3% 적용 (소득세 3% + 지방소득세 0.3%). "
            f"세무서 신고 시 종합소득세 정산으로 환급/추가납부 대상."
        )
    elif inp.income_type == "temporary":
        rate = WITHHOLDING_RATE_TEMPORARY
        notes.append(
            f"일시적 사업소득 원천징수 22% 적용. 단발성 행사·강연 등에 한정. "
            f"본인이 사업소득 (3.3%) 인지 일시소득 (22%) 인지 세무사 확인 권장."
        )
    else:
        raise ValueError(f"Unknown income_type {inp.income_type!r}")

    # VAT — 사업자 등록 크리에이터만 발행 가능
    vat = Decimal("0")
    if inp.is_business_registered:
        vat = _q(gross * VAT_RATE)
        notes.append(
            f"사업자 등록 크리에이터 → 부가세 10% 별도 청구 가능 (₩{int(vat):,}). "
            f"광고주에게 전자세금계산서 발행 필요."
        )
    else:
        notes.append("사업자 미등록 (개인 프리랜서) → 부가세 청구 불가. 사업소득 원천징수만 적용.")

    withholding = _q(gross * rate)

    platform_fee = Decimal(inp.platform_fee_krw)
    if platform_fee > 0:
        notes.append(f"MCN/에이전시 수수료 ₩{int(platform_fee):,} 차감.")

    # 실수령액 = 광고비 + (있다면) 부가세 - 원천징수 - 플랫폼 수수료
    net = gross + vat - withholding - platform_fee

    return SettlementResult(
        gross_amount=_q(gross),
        vat=_q(vat),
        withholding_tax=_q(withholding),
        platform_fee=_q(platform_fee),
        net_to_creator=_q(net),
        notes=notes,
    )
