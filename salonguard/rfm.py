"""salonguard — RFM 計算 + 流失風險評分 (純函式,no I/O, no LLM).

責任:
  - 對每位客戶計算 R(最近)/F(頻率)/M(金額)
  - 計算個人化回訪間隔(該客戶自身歷史的平均間隔)
  - 計算流失風險分數(基於 recency / avg_interval 比值,加 monetary / frequency 權重)
  - 輸出分級:active / watch / warning / high / lost

LLM 在另一個檔案做「為高風險客戶寫個人化挽回訊息」,純函式只算分數。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable


@dataclass
class Visit:
    customer_name: str
    visit_date: date
    service: str
    price_twd: int


@dataclass
class CustomerRFM:
    name: str
    recency_days: int           # 距今 N 天前最後到店
    frequency: int              # 過去 N 個月內到店次數
    monetary_twd: float         # 平均客單價
    avg_interval_days: float    # 該客戶歷史平均回訪間隔(< 2 次到店則 None)
    risk_score: float           # 0-100,愈高愈危險
    risk_level: str             # "active" | "watch" | "warning" | "high" | "lost"
    visit_count: int            # 同 frequency,留個別欄位方便排序
    last_visit_date: date
    last_service: str
    last_price_twd: int
    full_history: list[Visit] = field(default_factory=list)


# 風險閾值(基於 recency / avg_interval ratio)
RISK_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (1.0, "active"),    # ratio < 1.0 = 還在正常間隔內
    (1.3, "watch"),     # 1.0-1.3 = 稍微久了,觀察
    (1.8, "warning"),   # 1.3-1.8 = 警示
    (3.0, "high"),      # 1.8-3.0 = 高風險
    (float("inf"), "lost"),  # >= 3.0 = 已流失
)


def _ratio_to_level(ratio: float) -> str:
    for threshold, label in RISK_THRESHOLDS:
        if ratio < threshold:
            return label
    return "lost"


def _ratio_to_base_score(ratio: float) -> float:
    """把 ratio 映射成 0-100 分數;線性方便,但加平緩處理極端值。"""
    if ratio < 0.5:
        return 0.0
    if ratio < 1.0:
        return (ratio - 0.5) * 20  # 0.5~1.0 → 0~10 分
    if ratio < 3.0:
        return 10 + (ratio - 1.0) * 40  # 1.0~3.0 → 10~90 分
    return min(100.0, 90 + (ratio - 3.0) * 5)


def compute_rfm(visits: list[Visit], customer_name: str, today: date,
                lookback_months: int = 12) -> CustomerRFM | None:
    """計算單一客戶的 RFM + 風險評分。

    若客戶在 lookback_months 內無任何到店紀錄,回 None(這種客戶已被歸入歷史)。
    """
    customer_visits = sorted(
        (v for v in visits if v.customer_name == customer_name),
        key=lambda v: v.visit_date,
    )
    if not customer_visits:
        return None

    # 截掉 lookback 範圍外的 — 但保留最後一次決定 recency
    last_visit = customer_visits[-1]
    in_range = [v for v in customer_visits
                if (today - v.visit_date).days <= lookback_months * 30]
    if not in_range:
        in_range = [last_visit]  # 至少保留最後一次

    recency_days = (today - last_visit.visit_date).days
    frequency = len(in_range)
    monetary = sum(v.price_twd for v in in_range) / max(1, frequency)

    # 平均回訪間隔(用 in_range 中相鄰兩次間隔均值)
    intervals = [
        (in_range[i + 1].visit_date - in_range[i].visit_date).days
        for i in range(len(in_range) - 1)
    ]
    avg_interval = sum(intervals) / len(intervals) if intervals else 60.0  # 預設 60 天

    # 計算 ratio
    if avg_interval == 0:
        avg_interval = 60.0
    ratio = recency_days / avg_interval

    # 基本風險分數
    score = _ratio_to_base_score(ratio)

    # 修正:高客單價 +5 分(失之可惜)
    if monetary >= 2500:
        score += 5
    elif monetary >= 1500:
        score += 2

    # 修正:過去頻率高(>= 6 次/年)+ 5 分(老客戶突然不來更可疑)
    if frequency >= 6:
        score += 5

    score = min(100.0, max(0.0, score))
    level = _ratio_to_level(ratio)

    # 客單價 / 頻率加分後若進入下一級則升級
    if score >= 80 and level not in ("high", "lost"):
        level = "high"
    elif score >= 60 and level == "warning":
        level = "high"

    return CustomerRFM(
        name=customer_name,
        recency_days=recency_days,
        frequency=frequency,
        monetary_twd=round(monetary, 0),
        avg_interval_days=round(avg_interval, 1),
        risk_score=round(score, 1),
        risk_level=level,
        visit_count=frequency,
        last_visit_date=last_visit.visit_date,
        last_service=last_visit.service,
        last_price_twd=last_visit.price_twd,
        full_history=in_range,
    )


def compute_all(visits: list[Visit], today: date,
                lookback_months: int = 12) -> list[CustomerRFM]:
    names = sorted({v.customer_name for v in visits})
    results = [compute_rfm(visits, name, today, lookback_months) for name in names]
    return [r for r in results if r is not None]


def rank_by_risk(rfm_list: list[CustomerRFM]) -> list[CustomerRFM]:
    """依風險分數降序排序。"""
    return sorted(rfm_list, key=lambda r: -r.risk_score)


def filter_by_level(rfm_list: list[CustomerRFM],
                    levels: Iterable[str] = ("warning", "high")) -> list[CustomerRFM]:
    """只取指定風險等級的客戶。"""
    targets = set(levels)
    return [r for r in rfm_list if r.risk_level in targets]
