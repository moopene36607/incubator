"""propvision — 房屋估價計算邏輯(純函式).

估價公式:
  base_price = region_avg_price_per_ping × size_ping  (行政區實價均價基準)
  × age_factor          (屋齡折舊,每年 -1.3%,bottom 0.55)
  × floor_factor        (樓層,1F / 4F / 頂樓不受歡迎,中層加分)
  × orientation_factor  (朝向,南向 / 東南向最佳)
  × renovation_factor   (裝修評分 1-10,映射到 0.85-1.15)
  × (1 + adjustments)   (加減分,如電梯 / 車位 / 嫌惡設施 / 學區 等;累計上限 ±0.15)

最後 ±8% 為市場議價區間。所有計算純函式,LLM 永不算錢。

LLM 只負責:
  1. 從室內照片描述抽取結構化裝修評分(renovation_score 1-10)
  2. 從照片描述抽取明顯特徵(漏水 / 油煙 / 採光不足 / 新裝潢 等)
  3. 為估價結果寫人性化「為什麼這個價」的說明
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HouseInput:
    region: str                         # 行政區 (台北市大安區、新北市板橋區 等)
    region_avg_price_per_ping: int      # 該行政區實價登錄近 6 個月均價 NT$/坪
    size_ping: float                    # 坪數
    age_years: int                      # 屋齡(年)
    floor: int                          # 所在樓層
    total_floors: int                   # 總樓層
    orientation: str                    # "南向" | "東南向" | "東向" | "西南向" | "西向" | "北向" | "西北向" | "東北向" | "未知"
    has_elevator: bool = True
    has_parking: bool = False           # 含獨立車位
    near_mrt_meters: int | None = None  # 距捷運站幾公尺
    nearby_school_district: str = ""    # 學區(空白表示無加分)
    nearby_dislike_facilities: tuple[str, ...] = ()  # 嫌惡設施(殯儀館、垃圾場、夜市…)
    renovation_score: int = 5           # 裝修評分 1-10(AI 從照片推估)
    renovation_notes: tuple[str, ...] = ()  # AI 觀察到的具體裝修狀況(供解釋用)


@dataclass
class PricingBreakdown:
    base_price: int
    after_age: int
    after_floor: int
    after_orientation: int
    after_renovation: int
    after_adjustments: int
    final_midpoint: int
    range_low: int
    range_high: int
    age_factor: float
    floor_factor: float
    orientation_factor: float
    renovation_factor: float
    total_adjustment_pct: float
    adjustment_explanations: list[tuple[str, float, str]] = field(default_factory=list)
    # (key, delta, label) — e.g. ("ELEVATOR", +0.02, "有電梯")


# ----------- 各 factor 純函式 -----------
def _age_factor(age_years: int) -> float:
    """屋齡折舊:每年 -1.3%,floor 0.55(超過 35 年起進入價格底)。"""
    return max(0.55, 1.0 - age_years * 0.013)


def _floor_factor(floor: int, total_floors: int) -> float:
    """樓層調整:
    - 1F:有店面潛力但住宅較不受歡迎(-3%)
    - 4F:傳統忌諱(-2%)
    - 頂樓:漏水風險(-3%)
    - 中層(3-8F, 非頂):基準
    - 中高層(9F-中):微加(+2%)
    """
    if total_floors <= 0:
        return 1.0
    if floor == 1:
        return 0.97
    if floor == 4:
        return 0.98
    if floor == total_floors:
        return 0.97
    if 9 <= floor < total_floors - 1:
        return 1.02
    return 1.0


_ORIENTATION_FACTORS: dict[str, float] = {
    "南向":     1.03,
    "東南向":   1.03,
    "東向":     1.01,
    "西南向":   1.00,
    "西向":     0.97,
    "北向":     0.96,
    "西北向":   0.95,
    "東北向":   0.99,
    "未知":     1.00,
}


def _orientation_factor(orientation: str) -> float:
    return _ORIENTATION_FACTORS.get(orientation, 1.00)


def _renovation_factor(score: int) -> float:
    """裝修評分 1-10 → 0.85-1.15 區間。"""
    score = max(1, min(10, score))
    return 0.85 + (score - 1) / 9 * 0.30


_ADJUSTMENT_TABLE: dict[str, tuple[float, str]] = {
    "ELEVATOR_PLUS":     (+0.02, "有電梯"),
    "NO_ELEVATOR_OLD":   (-0.05, "5 樓以上無電梯"),
    "PARKING":           (+0.05, "含獨立車位"),
    "MRT_300M":          (+0.06, "近捷運站(300 公尺內)"),
    "MRT_500M":          (+0.03, "近捷運站(500 公尺內)"),
    "SCHOOL_DISTRICT":   (+0.04, "明星學區"),
    "DISLIKE_FACILITY":  (-0.05, "鄰近嫌惡設施"),
    "TWO_DISLIKE_FACILITY":  (-0.08, "鄰近多項嫌惡設施"),
}

ADJUSTMENT_LIMITS = (-0.15, +0.15)


def _gather_adjustments(inp: HouseInput) -> list[tuple[str, float, str]]:
    out: list[tuple[str, float, str]] = []
    if inp.has_elevator and inp.floor > 5:
        d, label = _ADJUSTMENT_TABLE["ELEVATOR_PLUS"]
        out.append(("ELEVATOR_PLUS", d, label))
    if not inp.has_elevator and inp.floor >= 5:
        d, label = _ADJUSTMENT_TABLE["NO_ELEVATOR_OLD"]
        out.append(("NO_ELEVATOR_OLD", d, label))
    if inp.has_parking:
        d, label = _ADJUSTMENT_TABLE["PARKING"]
        out.append(("PARKING", d, label))
    if inp.near_mrt_meters is not None:
        if inp.near_mrt_meters <= 300:
            d, label = _ADJUSTMENT_TABLE["MRT_300M"]
            out.append(("MRT_300M", d, label))
        elif inp.near_mrt_meters <= 500:
            d, label = _ADJUSTMENT_TABLE["MRT_500M"]
            out.append(("MRT_500M", d, label))
    if inp.nearby_school_district:
        d, label = _ADJUSTMENT_TABLE["SCHOOL_DISTRICT"]
        out.append(("SCHOOL_DISTRICT", d, f"{label}: {inp.nearby_school_district}"))
    if len(inp.nearby_dislike_facilities) >= 2:
        d, label = _ADJUSTMENT_TABLE["TWO_DISLIKE_FACILITY"]
        out.append(("TWO_DISLIKE_FACILITY", d,
                    f"{label}: {', '.join(inp.nearby_dislike_facilities)}"))
    elif len(inp.nearby_dislike_facilities) == 1:
        d, label = _ADJUSTMENT_TABLE["DISLIKE_FACILITY"]
        out.append(("DISLIKE_FACILITY", d,
                    f"{label}: {inp.nearby_dislike_facilities[0]}"))
    return out


def _round_10000(value: float) -> int:
    """房屋估值通常以萬元為單位,四捨五入到萬。"""
    return int(round(value / 10000) * 10000)


def calc_valuation(inp: HouseInput) -> PricingBreakdown:
    base = inp.region_avg_price_per_ping * inp.size_ping
    age_f = _age_factor(inp.age_years)
    after_age = base * age_f
    floor_f = _floor_factor(inp.floor, inp.total_floors)
    after_floor = after_age * floor_f
    orient_f = _orientation_factor(inp.orientation)
    after_orient = after_floor * orient_f
    reno_f = _renovation_factor(inp.renovation_score)
    after_reno = after_orient * reno_f

    adjustments = _gather_adjustments(inp)
    total_adj = sum(d for _, d, _ in adjustments)
    total_adj = max(ADJUSTMENT_LIMITS[0], min(ADJUSTMENT_LIMITS[1], total_adj))
    final_mid = after_reno * (1 + total_adj)
    range_low = final_mid * 0.92
    range_high = final_mid * 1.08

    return PricingBreakdown(
        base_price=_round_10000(base),
        after_age=_round_10000(after_age),
        after_floor=_round_10000(after_floor),
        after_orientation=_round_10000(after_orient),
        after_renovation=_round_10000(after_reno),
        after_adjustments=_round_10000(final_mid),
        final_midpoint=_round_10000(final_mid),
        range_low=_round_10000(range_low),
        range_high=_round_10000(range_high),
        age_factor=round(age_f, 3),
        floor_factor=round(floor_f, 3),
        orientation_factor=round(orient_f, 3),
        renovation_factor=round(reno_f, 3),
        total_adjustment_pct=round(total_adj * 100, 1),
        adjustment_explanations=adjustments,
    )
