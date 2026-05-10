"""sudoc — 民法條文 reference seed (供 prototype RAG 使用).

僅收錄民事起訴狀最常引用的條文(借款返還、買賣價金、租金、損害賠償、
不當得利等基礎案由)。實際產品需擴充至全民法 + 民事訴訟法 + 民事執行法。

Source: 中華民國 民法 (現行版本) — 全國法規資料庫 https://law.moj.gov.tw/
本資料於 2026-05 仍適用。實際送狀前請確認最新條文。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class LawArticle:
    code: str             # e.g. "民法 474"
    title: str            # e.g. "消費借貸之定義"
    body: str             # 條文全文
    typical_use: str      # 通常援引情境(供 LLM 判斷是否引用)


_ARTICLES: list[LawArticle] = [
    LawArticle(
        code="民法 474",
        title="消費借貸契約",
        body=(
            "稱消費借貸者,謂當事人一方移轉金錢或其他代替物之所有權於他方,"
            "而約定他方以種類、品質、數量相同之物返還之契約。"
            "當事人之一方對他方負金錢或其他代替物之給付義務而約定變更為消費借貸者,"
            "亦成立消費借貸。"
        ),
        typical_use="主張兩造間成立消費借貸契約 — 借款返還訴訟必引",
    ),
    LawArticle(
        code="民法 478",
        title="消費借貸之返還",
        body=(
            "借用人應於約定期限內,返還與借用物種類、品質、數量相同之物。"
            "未定返還期限者,借用人得隨時返還,貸與人亦得定一個月以上之相當期限催告返還。"
        ),
        typical_use="主張被告依約應返還借款 — 借款返還訴訟核心條文",
    ),
    LawArticle(
        code="民法 203",
        title="法定利率",
        body="應付利息之債務,其利率未經約定,亦無法律可據者,週年利率為百分之五。",
        typical_use="計算法定遲延利息週年 5% — 任何金錢債務遲延請求皆引用",
    ),
    LawArticle(
        code="民法 229",
        title="給付遲延",
        body=(
            "給付有確定期限者,債務人自期限屆滿時起,負遲延責任。"
            "給付無確定期限者,債務人於債權人得請求給付時,經其催告而未為給付,"
            "自受催告時起,負遲延責任。"
            "其經債權人起訴而送達訴狀,或依督促程序送達支付命令,或為其他相類之行為者,"
            "與催告有同一之效力。"
        ),
        typical_use="主張被告負給付遲延責任 — 利息起算依據",
    ),
    LawArticle(
        code="民法 233",
        title="遲延利息",
        body=(
            "遲延之債務,以支付金錢為標的者,債權人得請求依法定利率計算之遲延利息。"
            "但約定利率較高者,仍從其約定利率。"
            "對於利息,無須支付遲延利息。"
            "前二項情形,債權人證明有其他損害者,並得請求賠償。"
        ),
        typical_use="請求法定遲延利息 — 通常與第 203 條搭配引用",
    ),
    LawArticle(
        code="民法 184",
        title="侵權行為",
        body=(
            "因故意或過失,不法侵害他人之權利者,負損害賠償責任。"
            "故意以背於善良風俗之方法,加損害於他人者亦同。"
            "違反保護他人之法律,致生損害於他人者,負賠償責任。"
            "但能證明其行為無過失者,不在此限。"
        ),
        typical_use="侵權行為損害賠償訴訟主要依據(車禍、人身傷害、名譽毀損等)",
    ),
    LawArticle(
        code="民法 179",
        title="不當得利",
        body=(
            "無法律上之原因而受利益,致他人受損害者,應返還其利益。"
            "雖有法律上之原因,而其後已不存在者,亦同。"
        ),
        typical_use="主張被告無法律上原因受領金錢 — 誤匯款返還、買賣解除返還價金等",
    ),
    LawArticle(
        code="民法 227",
        title="不完全給付",
        body=(
            "因可歸責於債務人之事由,致為不完全給付者,債權人得依關於給付遲延或給付不能之規定行使其權利。"
            "因不完全給付而生前項以外之損害者,債權人並得請求賠償。"
        ),
        typical_use="買賣 / 承攬瑕疵或不符合約 — 損害賠償依據",
    ),
    LawArticle(
        code="民法 421",
        title="租賃契約",
        body=(
            "稱租賃者,謂當事人約定,一方以物租與他方使用收益,他方支付租金之契約。"
            "前項租金,得以金錢或租賃物之孳息充之。"
        ),
        typical_use="租金欠款返還訴訟必引",
    ),
    LawArticle(
        code="民法 440",
        title="支付租金遲延之效力",
        body=(
            "承租人租金支付有遲延者,出租人得定相當期限,催告承租人支付租金,"
            "如承租人於其期限內不為支付,出租人得終止契約。"
            "租賃物為房屋者,遲付租金之總額,非達二個月之租額,不得依前項之規定終止契約。"
            "其租金約定於每期開始時支付者,並應於遲延給付逾二個月時,始得終止契約。"
        ),
        typical_use="出租人欠租終止契約訴訟",
    ),
    LawArticle(
        code="民事訴訟法 244",
        title="起訴狀應記載事項",
        body=(
            "起訴,應以訴狀表明下列各款事項,提出於法院為之:"
            "一、當事人及法定代理人。"
            "二、訴訟標的及其原因事實。"
            "三、應受判決事項之聲明。"
            "訴狀內宜記載因定法院管轄及其適用程序所必要之事項、"
            "證據方法及其他準備言詞辯論之事項;"
            "其經兩造合意者,並宜記載之。"
        ),
        typical_use="起訴狀格式法定依據 — 律師基礎引用",
    ),
]


_BY_CODE: dict[str, LawArticle] = {a.code: a for a in _ARTICLES}


def lookup(code: str) -> LawArticle | None:
    return _BY_CODE.get(code.strip())


def all_articles() -> list[LawArticle]:
    return list(_ARTICLES)


def for_case_type(case_type: str) -> Iterable[LawArticle]:
    """Return articles most likely relevant to a given case type."""
    keywords_by_case = {
        "loan": ("消費借貸", "返還", "法定利率", "遲延"),
        "rent": ("租賃", "租金", "遲延"),
        "tort": ("侵權行為",),
        "unjust_enrichment": ("不當得利",),
        "breach": ("不完全給付", "遲延", "返還"),
    }
    keywords = keywords_by_case.get(case_type, ())
    if not keywords:
        return list(_ARTICLES)
    return [a for a in _ARTICLES if any(k in a.typical_use or k in a.title for k in keywords)]
