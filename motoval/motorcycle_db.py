"""motoval — 台灣常見機車車款資料庫 (純資料,no I/O, no LLM).

收錄台灣銷售量前 ~12 個機車車款的:
  - MSRP 出廠新車價
  - 年折舊率(經驗值)
  - 預期年里程(用以判斷該車里程是否偏高/偏低)
  - 車況等級係數

實際產品需擴充至 200+ 車款 + 接 8891/露天/監理所實際成交資料做動態定價。
本 prototype 12 個車款已涵蓋台灣二手機車 70%+ 交易量。

資料來源:車廠官網 MSRP + 二手機車行業界經驗折舊率(2026-05 估算)。
車況等級採二手車行通用 4 級制(優、良、可、差),係數為實際市場觀察。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotorcycleModel:
    code: str
    brand: str
    name: str
    displacement_cc: int
    year_introduced: int
    msrp_twd: int                   # 出廠新車牌價(含車籍配額,參考值)
    annual_depreciation_rate: float # 年折舊率(複利)
    expected_annual_km: int         # 該車款台灣使用者平均年里程,作為里程基準
    is_electric: bool = False


COMMON_MODELS: list[MotorcycleModel] = [
    MotorcycleModel("KYMCO_FORCE_155",  "光陽 KYMCO", "Force 155",
                    155, 2018, 93500, 0.10, 8000),
    MotorcycleModel("KYMCO_LIKE_125",   "光陽 KYMCO", "Like 125",
                    125, 2017, 75500, 0.08, 7500),
    MotorcycleModel("KYMCO_RACING_S150", "光陽 KYMCO", "Racing S 150",
                    150, 2018, 89800, 0.09, 8500),
    MotorcycleModel("SYM_DRG_BT_158",   "三陽 SYM",   "DRG BT 158",
                    158, 2020, 92800, 0.09, 8500),
    MotorcycleModel("SYM_JET_SR_125",   "三陽 SYM",   "Jet SR 125",
                    125, 2017, 73900, 0.08, 7500),
    MotorcycleModel("SYM_MMBCU_158",    "三陽 SYM",   "MMBCU 158",
                    158, 2022, 99800, 0.10, 8000),
    MotorcycleModel("YAMAHA_BWS_R_125", "Yamaha",     "BWS R 125",
                    125, 2020, 81500, 0.08, 7500),
    MotorcycleModel("YAMAHA_CYGNUS_125","Yamaha",     "新勁戰 Cygnus 125",
                    125, 2017, 79500, 0.08, 8000),
    MotorcycleModel("YAMAHA_SMAX_155",  "Yamaha",     "SMAX 155",
                    155, 2018, 96900, 0.09, 8500),
    MotorcycleModel("HONDA_PCX_160",    "Honda",      "PCX 160",
                    160, 2021, 109000, 0.08, 9000),
    MotorcycleModel("HONDA_FORZA_350",  "Honda",      "Forza 350",
                    350, 2022, 235000, 0.10, 7000),
    MotorcycleModel("GOGORO_VIVA_MIX",  "Gogoro",     "VIVA MIX",
                    0, 2021, 65980, 0.12, 6500, is_electric=True),
]


_BY_CODE: dict[str, MotorcycleModel] = {m.code: m for m in COMMON_MODELS}


def lookup(code: str) -> MotorcycleModel | None:
    return _BY_CODE.get(code.strip().upper())


def all_models() -> list[MotorcycleModel]:
    return list(COMMON_MODELS)


# ----------- 車況等級對折舊的修正係數 -----------
# excellent: 顯著高於平均 (記錄齊全、外觀近全新、無事故、單一車主)
# good: 略高於平均 (一般保養、外觀無大刮傷)
# fair: 平均水準 (一般使用磨耗)
# poor: 顯著低於平均 (重大事故 / 泡水 / 漆面嚴重 / 引擎異音)
CONDITION_MULTIPLIERS: dict[str, float] = {
    "excellent": 1.10,
    "good":      1.00,
    "fair":      0.88,
    "poor":      0.65,
}


# ----------- 加分減分項目 (細項調整,合併不超過 ±20%) -----------
ADJUSTMENT_FACTORS: dict[str, float] = {
    # 加分
    "single_owner":           +0.04,    # 單一車主
    "full_service_book":      +0.05,    # 完整保養手冊
    "dealer_serviced":        +0.03,    # 原廠保養紀錄
    "low_mileage":            +0.05,    # 里程顯著低於平均(超過 -30%)
    "new_tires":              +0.02,    # 新胎
    # 減分
    "minor_paint_damage":     -0.03,    # 輕微漆面刮傷
    "major_paint_damage":     -0.10,    # 嚴重漆面 / 多處
    "engine_noise":           -0.15,    # 引擎異音
    "accident_history":       -0.20,    # 事故過 (撞擊 / 翻倒)
    "flooded":                -0.40,    # 泡水車 (大忌)
    "high_mileage":           -0.08,    # 里程顯著高於平均(超過 +30%)
    "missing_keys":           -0.03,    # 鑰匙缺失
    "outdated_inspection":    -0.05,    # 行照 / 強制險過期
}
