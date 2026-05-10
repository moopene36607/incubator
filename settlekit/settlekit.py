"""settlekit — 한국 1인 크리에이터 협찬 합의서 + 정산서 AI 자동 생성

Usage:
    python settlekit.py samples/sample_input.json
    python settlekit.py samples/sample_input.json --out-dir output/

브랜드 협찬 deal 정보 (JSON) 를 입력하면:
  ① KFTC 광고 표시 의무 + 표준 약관 반영한 협찬 합의서 (Claude 생성)
  ② 사업소득 3.3% 원천징수 자동 계산된 정산서 (순수 함수)
두 markdown 파일을 출력한다.

ANTHROPIC_API_KEY 는 합의서 생성 시에만 필요. --no-ai 로 정산서만 생성 가능.
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

from settlement import SettlementInput, SettlementResult, calc_settlement


CONTRACT_SYSTEM = """당신은 한국 1인 크리에이터와 광고주 사이의 브랜드 협찬 합의서를 작성하는 법무 어시스턴트입니다.
공정거래위원회 (KFTC) 의 「추천·보증 등에 관한 표시·광고 심사지침」을 준수하는 합의서 초안을 한국어로 작성하세요.

다음 구조를 반드시 따르세요:

# 협찬 광고 합의서

본 합의서는 다음 양 당사자 간에 체결됩니다.

**「갑」** (광고주):
- 회사명 / 사업자등록번호 / 주소 / 담당자

**「을」** (크리에이터):
- 성명 / 채널명 / 사업자번호 (있는 경우) / 연락처

## 제1조 (목적)
양 당사자가 합의한 광고 콘텐츠 제작·게시에 관한 권리 및 의무 규정.

## 제2조 (광고 콘텐츠)
- 플랫폼 (YouTube / Instagram / Threads 등)
- 콘텐츠 형식 (메인 비디오 / 릴스 / 커뮤니티 게시물 등)
- 분량 / 길이 / 노출 지속 시간
- 게시 일정

## 제3조 (광고비 및 지급 조건)
- 총 광고비 (₩, VAT 별도/포함 명시)
- 지급 시기 및 방식
- 원천징수 (사업소득 3.3%) 적용 여부
- 사업자 등록자의 경우 세금계산서 발행 의무

## 제4조 (KFTC 표시·광고 의무) — 매우 중요
- 「광고」 또는 「유료 광고 포함」 표기 의무 명시
- 본문 첫 줄 또는 영상 시작 5초 이내에 표시
- #광고 #협찬 #PR 등 해시태그 사용 규정
- 표시 누락 시 손해배상 책임

## 제5조 (콘텐츠 활용 범위 및 저작권)
- 「갑」의 2차 활용 범위 (사내 / SNS / 광고 등)
- 활용 기간 (1 년 / 2 년 / 영구)
- 「을」의 원저작자 표기

## 제6조 (수정 요청 및 검수)
- 검수 횟수 (보통 1–2 회)
- 수정 마감일
- 추가 수정 시 비용 별도

## 제7조 (비밀유지)
- 본 합의 내용 및 「갑」 의 영업비밀 보호

## 제8조 (위약 및 손해배상)
- 「을」 미게시 시 위약금 (보통 광고비의 1–2 배)
- 「갑」 일방적 취소 시 보상 (계약 시점부터 진행 단계별 차등)
- KFTC 표시 누락 / 부정 광고 시 책임

## 제9조 (분쟁 해결)
- 합의 우선
- 관할 법원 (서울중앙지방법원 권장)

## 제10조 (기타)
- 본 합의서의 효력 발생일
- 양 당사자 서명·날인

작성 원칙:
- 한국어 법률 문체 (격식체) 사용
- 「갑」/「을」 표기 일관성 유지
- 모든 금액은 한글 + 숫자 병기 (예: "오백만원 (₩5,000,000)")
- 추측 가능한 값은 합리적 기본값 채우되, 입력 데이터에 없는 핵심 정보는 [별도 협의] 표시
- KFTC 관련 조항은 절대 누락하지 말 것
- 마크다운 형식, 다른 해설 없이 합의서 본문만 출력
"""


def fmt_krw(amount: Decimal) -> str:
    return f"₩{int(amount):,}"


def render_settlement(payload: dict[str, Any], result: SettlementResult) -> str:
    creator = payload["creator"]
    brand = payload["brand"]
    deal = payload["deal"]
    today = date.today().isoformat()

    lines: list[str] = []
    lines.append("# 협찬 광고 정산서")
    lines.append("")
    lines.append(f"**정산일자**: {payload.get('settlement_date', today)}    "
                 f"**정산서 번호**: {payload.get('settlement_number', f'SK-{today.replace(chr(45), chr(0))}-001')}")
    lines.append("")

    lines.append("## 정산 당사자")
    lines.append("")
    lines.append(f"- **광고주 (갑)**: {brand['company']} (사업자번호 {brand['business_id']})")
    lines.append(f"- **크리에이터 (을)**: {creator['name']} ({creator.get('channel_name', '')})")
    if creator.get("business_id"):
        lines.append(f"  - 사업자번호: {creator['business_id']}")
    else:
        lines.append(f"  - 주민등록번호 뒷자리: ****{creator.get('rrn_last4', '****')} (개인 프리랜서)")
    lines.append("")

    lines.append("## 콘텐츠 인도 내역")
    lines.append("")
    lines.append("| # | 플랫폼 | 콘텐츠 | 게시일 | URL |")
    lines.append("|---|--------|--------|--------|-----|")
    for i, item in enumerate(deal.get("deliverables", []), 1):
        lines.append(f"| {i} | {item.get('platform', '')} | {item.get('description', '')} | "
                     f"{item.get('published_date', '미게시')} | {item.get('url', '-')} |")
    lines.append("")

    lines.append("## 정산 내역")
    lines.append("")
    lines.append("| 항목 | 금액 |")
    lines.append("|------|-----:|")
    lines.append(f"| 광고비 (gross) | {fmt_krw(result.gross_amount)} |")
    if result.vat > 0:
        lines.append(f"| 부가세 (10%) | +{fmt_krw(result.vat)} |")
    lines.append(f"| 원천징수세 | -{fmt_krw(result.withholding_tax)} |")
    if result.platform_fee > 0:
        lines.append(f"| MCN/플랫폼 수수료 | -{fmt_krw(result.platform_fee)} |")
    lines.append(f"| **실수령액** | **{fmt_krw(result.net_to_creator)}** |")
    lines.append("")

    lines.append("## 입금 정보")
    lines.append("")
    bank = creator.get("bank_account", {})
    lines.append(f"- **은행**: {bank.get('bank_name', '(미입력)')}")
    lines.append(f"- **계좌번호**: {bank.get('account_number', '(미입력)')}")
    lines.append(f"- **예금주**: {bank.get('holder_name', creator['name'])}")
    lines.append("")

    lines.append("## 정산 메모")
    lines.append("")
    for note in result.notes:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**확인란**")
    lines.append("")
    lines.append("- [ ] 광고주 (갑) 확인  ___________ ㊞    날짜: __________")
    lines.append("- [ ] 크리에이터 (을) 확인  ___________ ㊞    날짜: __________")
    lines.append("")
    lines.append("*settlekit prototype 자동 생성. 종합소득세 신고 자료로 그대로 활용 가능합니다.*")
    return "\n".join(lines) + "\n"


def ai_generate_contract(payload: dict[str, Any]) -> str:
    import anthropic

    client = anthropic.Anthropic()
    user_msg = (
        "다음 협찬 deal 정보를 바탕으로 합의서를 작성하세요:\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}\n```\n\n"
        "위 데이터를 기반으로 한국어 KFTC 준수 협찬 광고 합의서를 markdown 으로 작성하십시오."
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=[{"type": "text", "text": CONTRACT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="협찬 deal 정보 JSON")
    parser.add_argument("--out-dir", type=Path, help="출력 디렉토리 (省略 시 stdout)")
    parser.add_argument("--no-ai", action="store_true", help="합의서 AI 생성 생략 (정산서만 출력)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 파일을 찾을 수 없습니다: {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))

    deal = payload["deal"]
    settlement_inp = SettlementInput(
        gross_amount_krw=Decimal(str(deal["gross_amount_krw"])),
        income_type=deal.get("income_type", "freelance"),
        is_business_registered=bool(payload["creator"].get("business_id")),
        platform_fee_krw=Decimal(str(deal.get("platform_fee_krw", 0))),
    )
    settlement_result = calc_settlement(settlement_inp)
    settlement_md = render_settlement(payload, settlement_result)

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 미설정 → 합의서 AI 생성 생략, 정산서만 출력합니다.", file=sys.stderr)

    contract_md = ai_generate_contract(payload) if use_ai else None

    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "settlement.md").write_text(settlement_md, encoding="utf-8")
        print(f"정산서 작성: {args.out_dir / 'settlement.md'}", file=sys.stderr)
        if contract_md:
            (args.out_dir / "contract.md").write_text(contract_md, encoding="utf-8")
            print(f"합의서 작성: {args.out_dir / 'contract.md'}", file=sys.stderr)
    else:
        sys.stdout.write("====== 정산서 ======\n\n")
        sys.stdout.write(settlement_md)
        if contract_md:
            sys.stdout.write("\n\n====== 합의서 ======\n\n")
            sys.stdout.write(contract_md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
