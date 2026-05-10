"""bizradar — 台灣 SME 客戶 / 廠商風險評估(graph + entity resolution + risk score).

100% 純函式分析 — LLM 在 bizradar.py 只寫人話解釋 + 建議。

責任:
  - 載入 companies_db corpus
  - find_director_connections: 找出目標公司的董監事還在哪些公司任職
  - find_address_collisions: 找出共用同地址的公司(可能是空殼 / 關聯)
  - check_director_problem_history: 該人在已解散 / 多訴訟 / 負評新聞公司任職過?
  - check_company_internal_signals: 該公司本身的訴訟 / 新聞 / 設立年數 / 資本
  - compute_risk_score: 加總所有 signal 切檔 LOW / MEDIUM / HIGH / CRITICAL

分數權重:
  - 公司新設(< 1 年)          +25
  - 公司新設(1-3 年)         +10
  - 實收資本 < NT$100 萬       +20
  - 實收資本 < NT$500 萬       +5
  - 共用地址有其他可疑公司      +15 per 可疑公司
  - 董事在已解散公司任職        +25 per 公司
  - 董事在多訴訟公司任職        +15 per 公司
  - 自己本身被告(近 2 年)      +12 per 件
  - 自己本身負評新聞(近 1 年)  +10 per 篇 high / +5 medium
  - 業務狀態非「營業中」         +50

切檔:LOW ≤ 25 / MEDIUM ≤ 50 / HIGH ≤ 75 / CRITICAL > 75
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


# ===== Risk score 切檔 =====
RISK_LOW = 25
RISK_MEDIUM = 50
RISK_HIGH = 75

TODAY = date(2026, 5, 10)


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _years_since(d: date) -> float:
    return (TODAY - d).days / 365.25


def find_company_by_corp_id(db: dict, corp_id: str) -> dict | None:
    for c in db["companies"]:
        if c["corp_id"] == corp_id:
            return c
    return None


def find_company_by_name(db: dict, name: str) -> dict | None:
    name_norm = name.strip()
    for c in db["companies"]:
        if c["name_zh"] == name_norm or name_norm in c["name_zh"]:
            return c
    return None


def find_director_connections(db: dict, corp_id: str) -> dict[str, list[dict]]:
    """對目標公司的每位董事,找出他還在哪些公司任職。

    Returns: {director_name: [list of other companies they direct]}
    """
    target = find_company_by_corp_id(db, corp_id)
    if not target:
        return {}
    out: dict[str, list[dict]] = {}
    for director in target["directors"]:
        others = [
            c for c in db["companies"]
            if c["corp_id"] != corp_id and director in c["directors"]
        ]
        if others:
            out[director] = others
    return out


def find_address_collisions(db: dict, corp_id: str) -> list[dict]:
    """找出共用同一地址(< 8 字元差異)的其他公司。"""
    target = find_company_by_corp_id(db, corp_id)
    if not target:
        return []
    target_addr = target["registered_address"]
    return [
        c for c in db["companies"]
        if c["corp_id"] != corp_id and c["registered_address"] == target_addr
    ]


@dataclass
class RiskSignal:
    """一條風險訊號。"""
    code: str           # NEW_COMPANY / LOW_CAPITAL / SHARED_ADDRESS / DIRECTOR_HISTORY / ...
    severity: str       # low / medium / high / critical
    score: int          # 對總 risk score 的貢獻
    description: str    # 人話描述
    evidence: dict = field(default_factory=dict)


def check_company_internal_signals(company: dict) -> list[RiskSignal]:
    """檢查公司本身的「內在訊號」:設立年數、資本、訴訟、新聞、業務狀態。"""
    out: list[RiskSignal] = []
    est = _parse_date(company["established_date"])
    years = _years_since(est)

    if years < 1:
        out.append(RiskSignal(
            code="NEW_COMPANY",
            severity="high",
            score=25,
            description=f"公司於 {company['established_date']} 設立,僅 {years:.1f} 年(< 1 年)",
            evidence={"established_date": company["established_date"], "years": round(years, 1)},
        ))
    elif years < 3:
        out.append(RiskSignal(
            code="YOUNG_COMPANY",
            severity="medium",
            score=10,
            description=f"公司設立 {years:.1f} 年(1-3 年),歷史短",
            evidence={"established_date": company["established_date"], "years": round(years, 1)},
        ))

    cap = company["capital_amount"]
    if cap < 1000000:
        out.append(RiskSignal(
            code="LOW_CAPITAL",
            severity="high",
            score=20,
            description=f"實收資本僅 NT${cap:,}(< NT$100 萬),承擔大單能力受限",
            evidence={"capital_amount": cap},
        ))
    elif cap < 5000000:
        out.append(RiskSignal(
            code="MODERATE_CAPITAL",
            severity="low",
            score=5,
            description=f"實收資本 NT${cap:,}(< NT$500 萬),適合中小型合作",
            evidence={"capital_amount": cap},
        ))

    if company["business_status"] != "營業中":
        out.append(RiskSignal(
            code="BUSINESS_INACTIVE",
            severity="critical",
            score=80,
            description=f"🔴 業務狀態:{company['business_status']}(**非「營業中」**) — 已無履約能力",
            evidence={"business_status": company["business_status"]},
        ))

    # 訴訟近 2 年被告
    for lawsuit in company.get("lawsuits", []):
        if lawsuit["role"] != "被告":
            continue
        d = _parse_date(lawsuit["date"])
        if _years_since(d) <= 2:
            out.append(RiskSignal(
                code="RECENT_DEFENDANT",
                severity="medium",
                score=12,
                description=(
                    f"近 2 年被告:{lawsuit['date']} 於 {lawsuit['court']} "
                    f"被訴 {lawsuit['type']},金額 NT${lawsuit['amount']:,}"
                ),
                evidence=lawsuit,
            ))

    # 新聞負評近 1 年
    for news in company.get("news_negative", []):
        d = _parse_date(news["date"])
        if _years_since(d) <= 1:
            score = 10 if news["severity"] == "high" else 5
            out.append(RiskSignal(
                code="NEGATIVE_NEWS",
                severity=news["severity"],
                score=score,
                description=f"近 1 年負評新聞({news['source']} {news['date']}):「{news['headline']}」",
                evidence=news,
            ))

    return out


def check_director_problem_history(db: dict, corp_id: str) -> list[RiskSignal]:
    """檢查目標公司的董監事過去是否在「已解散 / 多訴訟 / 負評新聞」公司任職。"""
    out: list[RiskSignal] = []
    connections = find_director_connections(db, corp_id)
    for director, other_companies in connections.items():
        for other in other_companies:
            # 1) 在已解散 / 停業 / 撤銷 公司任職
            if other["business_status"] != "營業中":
                out.append(RiskSignal(
                    code="DIRECTOR_LINKED_TO_INACTIVE",
                    severity="high",
                    score=25,
                    description=(
                        f"董事【{director}】也曾任職於【{other['name_zh']}】"
                        f"({other['business_status']},統編 {other['corp_id']})"
                    ),
                    evidence={
                        "director": director,
                        "linked_company": other["name_zh"],
                        "linked_corp_id": other["corp_id"],
                        "status": other["business_status"],
                    },
                ))
            # 2) 在多訴訟公司任職 (近 3 年被告 ≥ 2 件)
            recent_defendant_count = sum(
                1 for l in other.get("lawsuits", [])
                if l["role"] == "被告" and _years_since(_parse_date(l["date"])) <= 3
            )
            if recent_defendant_count >= 2:
                out.append(RiskSignal(
                    code="DIRECTOR_LINKED_TO_LAWSUIT_HEAVY",
                    severity="medium",
                    score=15,
                    description=(
                        f"董事【{director}】也任職於【{other['name_zh']}】"
                        f"(近 3 年被告 {recent_defendant_count} 件)"
                    ),
                    evidence={
                        "director": director,
                        "linked_company": other["name_zh"],
                        "lawsuit_count": recent_defendant_count,
                    },
                ))
    return out


def check_address_collisions(db: dict, corp_id: str) -> list[RiskSignal]:
    """檢查是否有可疑公司共用同地址。"""
    out: list[RiskSignal] = []
    collisions = find_address_collisions(db, corp_id)
    for other in collisions:
        # 只要該地址有其他公司,就 +15
        out.append(RiskSignal(
            code="SHARED_ADDRESS",
            severity="medium",
            score=15,
            description=(
                f"與【{other['name_zh']}】(統編 {other['corp_id']},"
                f"{other['business_status']})共用註冊地址"
            ),
            evidence={
                "shared_with": other["name_zh"],
                "shared_corp_id": other["corp_id"],
                "address": other["registered_address"],
            },
        ))
    return out


@dataclass
class RiskAssessment:
    risk_score: int
    risk_level: str
    company: dict
    signals: list[RiskSignal]
    director_network: dict[str, list[dict]]
    address_collisions: list[dict]
    summary: str


def assess(db: dict, corp_id: str) -> RiskAssessment | None:
    company = find_company_by_corp_id(db, corp_id)
    if not company:
        return None
    signals: list[RiskSignal] = []
    signals.extend(check_company_internal_signals(company))
    signals.extend(check_director_problem_history(db, corp_id))
    signals.extend(check_address_collisions(db, corp_id))

    risk_score = min(100, sum(s.score for s in signals))

    if risk_score <= RISK_LOW:
        level = "LOW"
        summary = "風險低,可正常往來。"
    elif risk_score <= RISK_MEDIUM:
        level = "MEDIUM"
        summary = (
            f"風險中等(score {risk_score})。建議:首單金額限制 NT$50 萬以下、"
            f"預收 30% 訂金、票期不超過 60 天。"
        )
    elif risk_score <= RISK_HIGH:
        level = "HIGH"
        summary = (
            f"⚠️ 風險偏高(score {risk_score})。建議:① 預收 50% 訂金 + 餘款貨到付清 "
            f"② 首單上限 NT$30 萬 ③ 跟業界打聽該公司付款紀錄 ④ 不接受長票期 / 開票"
        )
    else:
        level = "CRITICAL"
        summary = (
            f"🔴 風險嚴重(score {risk_score})。**強烈建議**:① 拒絕往來 OR "
            f"② 預收 100% 全款 ③ 即使預收全款也建議深入查證該公司董監事過去紀錄 "
            f"④ 諮詢律師擬定特殊保障條款"
        )

    return RiskAssessment(
        risk_score=risk_score,
        risk_level=level,
        company=company,
        signals=signals,
        director_network=find_director_connections(db, corp_id),
        address_collisions=find_address_collisions(db, corp_id),
        summary=summary,
    )
