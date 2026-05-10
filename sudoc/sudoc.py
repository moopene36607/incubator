"""sudoc — 台灣 1-5 人小型律師事務所 民事起訴狀 AI 草稿產生器

Usage:
    python sudoc.py samples/sample_input.json
    python sudoc.py samples/sample_input.json --out lawsuit.md
    python sudoc.py samples/sample_input.json --no-ai     # skeleton only

輸入案情 JSON,輸出符合司法院民事訴訟法第 244 條格式的繁中民事起訴狀草稿。

設計重點:
- 純函式組裝書狀骨架(當事人欄、訴之聲明、狀末等格式硬規定)
- AI 只負責「事實及理由」段落的法律論述 + 自動引用相關民法條文
- 草稿明確標注「需律師審閱」— 規避無律師資格代擬書狀的法律疑慮

ANTHROPIC_API_KEY 只在生成「事實及理由」時必要(--no-ai 跳過)。
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

from civil_law_refs import LawArticle, for_case_type, lookup


REASONING_SYSTEM = """你是台灣執業律師助理,協助起草「民事起訴狀」中的「事實及理由」段落。
你的目標是幫小型事務所律師快速產出可審閱、可修改的草稿,**不是**最終定稿。

## 寫作風格

- 繁體中文,法律書面語,**第三人稱、過去式**(例:「原告於民國 114 年 8 月 15 日交付……」)
- 段落分項清楚:用「一、」「二、」「三、」分段
- 每段聚焦單一事實或主張,避免長段混合
- 法律術語精準:用「給付遲延」而非「拖欠」;用「催告」而非「提醒」
- 引用條文格式:「依民法第 478 條規定……」(條號 + 「規定」)
- 金額一律寫:「新臺幣參拾萬元整(NT$300,000)」(中文大寫 + 阿拉伯數字)
- 日期寫民國紀年:「民國 114 年 8 月 15 日」(西元 - 1911 = 民國)

## 結構建議

1. **第一段**:法律關係之發生(契約成立、原因事實)
2. **第二段**:約定內容 + 履行情形
3. **第三段**:被告違約 / 不履行 + 原告催告事實
4. **第四段**:法律主張 + 援引條文 + 結論性請求

## 援引條文規則

- 只用 user message 中提供的「相關民法條文」清單
- 每段最多引用 2-3 條,避免堆砌
- 引用時要交代「為何適用」(例:「兩造間既成立消費借貸契約,被告自應依民法第 478 條規定返還借款」)

## 絕對禁止

- 不要憑空虛構條文號碼(只用提供的清單)
- 不要編造當事人沒陳述的事實
- 不要做最終法律意見(用「應依」「請求」「主張」等審慎措辭,不寫「被告必敗訴」)
- 不要包含完整書狀(訴之聲明、狀末等)— 只回「事實及理由」段落本文

## 輸出格式

直接輸出「事實及理由」本文,markdown,從「一、」開始,**不要**前後標題或解說。
"""


def _arabic_to_chinese_currency(amount: Decimal) -> str:
    """簡易中文大寫金額轉換 — 處理 0 ~ 兆級數字。

    規則:
      - 跳過 chunk 內的 leading zero(「30」→「參拾」非「零參拾」)
      - 非零數字之間若有 0 補「零」(「3030」→「參仟零參拾」)
      - trailing zero 不補
    Prototype 簡易版,實務跨萬位單位的 0 處理仍需專門 lib。
    """
    digit_map = {"0": "零", "1": "壹", "2": "貳", "3": "參", "4": "肆",
                 "5": "伍", "6": "陸", "7": "柒", "8": "捌", "9": "玖"}
    n = int(amount)
    if n == 0:
        return "零元整"

    def chunk_to_chinese(chunk: int) -> str:
        if chunk == 0:
            return ""
        sub_units = ["仟", "佰", "拾", ""]
        s = str(chunk).rjust(4, "0")  # 0–9999 padded to 4 digits
        result = ""
        started = False
        for i, digit in enumerate(s):
            if digit != "0":
                result += digit_map[digit] + sub_units[i]
                started = True
            elif started and any(c != "0" for c in s[i + 1 :]):
                if not result.endswith("零"):
                    result += "零"
        return result

    units: list[tuple[int, str]] = [
        (10**12, "兆"), (10**8, "億"), (10**4, "萬"), (1, ""),
    ]
    parts: list[str] = []
    for value, name in units:
        chunk = (n // value) % 10000
        if chunk == 0:
            continue
        parts.append(chunk_to_chinese(chunk) + name)
    return "".join(parts) + "元整"


def _roc_year(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"民國 {int(y) - 1911} 年 {int(m)} 月 {int(d)} 日"


def render_demand(payload: dict[str, Any]) -> list[str]:
    """訴之聲明 — 由結構化資料純函式組裝,不交給 AI。"""
    demand = payload["demand"]
    lines: list[str] = []
    principal = Decimal(str(demand["principal_amount_twd"]))
    delay_start = demand.get("delay_start_date")
    interest_rate = demand.get("interest_rate", "5")

    p_chinese = _arabic_to_chinese_currency(principal)
    p_roc = _roc_year(delay_start) if delay_start else ""

    lines.append(
        f"一、被告應給付原告新臺幣 {p_chinese}({principal:,} 元),"
        + (f"及自 {p_roc} 起至清償日止,按年息百分之 {interest_rate} 計算之利息。" if delay_start else "。")
    )
    lines.append("二、訴訟費用由被告負擔。")
    if demand.get("provisional_execution", True):
        lines.append("三、原告願供擔保,請准宣告假執行。")
    return lines


def ai_generate_reasoning(payload: dict[str, Any], articles: list[LawArticle]) -> str:
    import anthropic

    facts = payload.get("fact_summary", "")
    articles_block = "\n\n".join(
        f"### {a.code} {a.title}\n{a.body}\n*典型援引情境*:{a.typical_use}"
        for a in articles
    )
    user = (
        f"## 案情摘要\n\n{facts}\n\n"
        f"## 相關民法條文(只用以下這些,不要憑空援引其他條文)\n\n{articles_block}\n\n"
        f"請為上述案情起草「事實及理由」段落。"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=[{"type": "text", "text": REASONING_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def render_skeleton_reasoning(payload: dict[str, Any]) -> str:
    """不開 AI 時的骨架(留 placeholder 給律師填寫)。"""
    return (
        "一、(請填入:法律關係之發生 — 契約成立、原因事實)\n\n"
        "二、(請填入:約定內容 + 履行情形)\n\n"
        "三、(請填入:被告違約 / 不履行 + 原告催告事實)\n\n"
        "四、(請填入:法律主張 + 援引民法條文 + 結論性請求)\n"
    )


def render_full_complaint(payload: dict[str, Any], reasoning: str) -> str:
    today = date.today().isoformat()
    plaintiff = payload["plaintiff"]
    defendant = payload["defendant"]
    case = payload["case"]
    court = case.get("court", "臺灣臺北地方法院")
    court_section = case.get("court_section", "民事庭")
    cause = case.get("cause_of_action", "返還借款")
    filing_date_iso = case.get("filing_date", today)

    out: list[str] = []

    # ------- header -------
    out.append("# 民事起訴狀")
    out.append("")
    out.append(f"**案號**:(由法院填載)    **承辦股別**:(由法院填載)")
    out.append("")

    # ------- parties -------
    out.append("## 當事人")
    out.append("")
    out.append("| 角色 | 姓名 | 身分證字號 | 地址 |")
    out.append("|------|------|------------|------|")
    out.append(f"| **原告** | {plaintiff['name']} | {plaintiff.get('id_number', '(略)')} | {plaintiff['address']} |")
    if plaintiff.get("attorney"):
        atty = plaintiff["attorney"]
        out.append(f"| 訴訟代理人 | {atty['name']} 律師 | (略) | {atty.get('firm_address', '同上')} |")
    out.append(f"| **被告** | {defendant['name']} | {defendant.get('id_number', '(略)')} | {defendant['address']} |")
    out.append("")

    # ------- subject -------
    out.append(f"為 **{cause}** 事提起訴訟事:")
    out.append("")

    # ------- prayer for relief -------
    out.append("## 訴之聲明")
    out.append("")
    for line in render_demand(payload):
        out.append(line)
        out.append("")

    # ------- facts and reasoning -------
    out.append("## 事實及理由")
    out.append("")
    out.append(reasoning)
    out.append("")

    # ------- exhibits -------
    out.append("## 證物")
    out.append("")
    for i, ex in enumerate(payload.get("exhibits", []), 1):
        out.append(f"原證 {i}:{ex}")
    out.append("")

    # ------- closing -------
    out.append("## 謹狀")
    out.append("")
    out.append(f"**{court}  {court_section}  公鑒**")
    out.append("")
    out.append(f"中華民國 {int(filing_date_iso.split('-')[0]) - 1911} 年 "
               f"{int(filing_date_iso.split('-')[1])} 月 "
               f"{int(filing_date_iso.split('-')[2])} 日")
    out.append("")
    out.append(f"具狀人  原告  **{plaintiff['name']}**(簽名 / 蓋章)")
    if plaintiff.get("attorney"):
        out.append(f"訴訟代理人  **{plaintiff['attorney']['name']} 律師**(簽名 / 蓋章)")
    out.append("")

    # ------- legal disclaimer -------
    out.append("---")
    out.append("")
    out.append("> ⚠️ **本書狀為 AI 自動產生之草稿,僅供律師審閱起點。送狀前必須由執業律師逐字審閱、修改、確認簽章,並依個案具體事實調整。本工具不取代律師專業判斷。**")
    out.append("")
    out.append(f"*sudoc prototype 自動產生於 {today}*")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="案情 JSON")
    parser.add_argument("--out", type=Path, help="輸出檔案(省略 stdout)")
    parser.add_argument("--no-ai", action="store_true",
                        help="不呼叫 LLM,輸出骨架供律師手填")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    case_type = payload.get("case", {}).get("case_type", "loan")
    relevant_articles = list(for_case_type(case_type))

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,改輸出骨架版", file=sys.stderr)

    reasoning = ai_generate_reasoning(payload, relevant_articles) if use_ai else render_skeleton_reasoning(payload)
    output = render_full_complaint(payload, reasoning)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
