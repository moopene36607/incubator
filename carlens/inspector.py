"""carlens — 台灣中古車多源資料一致性檢查(純函式,no I/O, no LLM).

責任:把多個來源的資訊(照片描述特徵 + 行照 + 賣方宣稱 + 車款 baseline)
做交叉比對,找出**詐騙紅旗**:
  1. 行照里程 vs 內裝磨耗 — 調表車最常見徵兆
  2. 年式 vs 配備版本 — 偽造年式
  3. 引擎室油漆 vs 「無事故」宣稱
  4. 底盤生鏽 vs 「無泡水」宣稱
  5. 車身漆面一致性 — 局部重噴 = 修補事故
  6. 輪胎磨耗 vs 行照里程
  7. 車身號碼真偽

每個 check 回傳 RiskSignal(code / severity / score / 證據 / 解釋)。
**LLM 永不算 score** — 累加 + 分檔在 `assess()` 純函式。

風險分檔: LOW ≤ 20 / MEDIUM ≤ 45 / HIGH ≤ 75 / CRITICAL > 75
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ===== Risk thresholds =====
RISK_LOW = 20
RISK_MEDIUM = 45
RISK_HIGH = 75


# ===== Per-km wear baselines (Taiwan 中古車市場通用值) =====
# 內裝磨耗等級(0=新車狀態,10=極度磨損)對應里程基線
EXPECTED_WEAR_BY_MILEAGE = {
    10000: (0, 2),
    30000: (1, 3),
    50000: (2, 4),
    80000: (3, 6),
    120000: (5, 8),
    180000: (7, 9),
    250000: (8, 10),
}


def expected_wear_range_for_km(km: int) -> tuple[int, int]:
    """根據里程查詢「合理內裝磨耗區間」(0-10 scale)。"""
    sorted_keys = sorted(EXPECTED_WEAR_BY_MILEAGE.keys())
    for k in sorted_keys:
        if km <= k:
            return EXPECTED_WEAR_BY_MILEAGE[k]
    return EXPECTED_WEAR_BY_MILEAGE[sorted_keys[-1]]


@dataclass
class CarProfile:
    """一輛車的完整 profile,由 CLI 從用戶上傳的多源資料組裝。"""
    listing_id: str
    make: str                                # 例「Toyota」
    model: str                               # 例「Camry」
    declared_year: int                       # 賣方/行照宣稱年式
    declared_mileage_km: int                 # 行照里程(km)
    declared_no_accident: bool               # 賣方宣稱無事故
    declared_no_flood: bool                  # 賣方宣稱無泡水
    asking_price_ntd: int                    # 開價

    # === 視覺特徵(prototype: 用文字描述代替真實 vision)===
    interior_wear_level: int                 # 0-10,內裝磨耗
    interior_wear_notes: str                 # 自由文字說明
    engine_bay_state: str                    # "原廠未動" / "局部重噴" / "全面重噴" / "改裝痕跡"
    engine_bay_notes: str
    undercarriage_state: str                 # "正常" / "輕度生鏽" / "嚴重生鏽" / "新塗裝可疑"
    undercarriage_notes: str
    body_paint_consistency: str              # "全車一致" / "局部色差" / "明顯重噴痕跡"
    body_paint_notes: str
    tire_estimated_remaining_pct: int        # 輪胎剩餘里程百分比(0-100)
    tire_brand_year: str                     # 輪胎品牌 + 出廠週次
    vin_plate_state: str                     # "原廠" / "可疑(字體不一致 / 修補痕跡)" / "缺失"
    vin_plate_notes: str

    # === 配備清單(用來比對年式)===
    equipment_features: list[str] = field(default_factory=list)
    # 例 ["LED 大燈", "Apple CarPlay", "盲點偵測"] — 用來檢驗是否符合宣稱年式

    seller_notes: str = ""


@dataclass
class RiskSignal:
    code: str
    severity: str                            # low / medium / high / critical
    score: int                               # 0-30 累加分數
    description: str
    evidence: dict = field(default_factory=dict)
    confidence: str = "high"                 # high / medium / low — 此 signal 的可信度


# ===== 維度檢查純函式 =====

def check_mileage_vs_wear(p: CarProfile) -> RiskSignal | None:
    """行照里程 vs 內裝磨耗一致性檢查 — 調表車最常見徵兆。

    用 hi + 1 / lo - 1 作為「顯著偏離」門檻;更大的偏離權重提高。
    """
    lo, hi = expected_wear_range_for_km(p.declared_mileage_km)
    if lo <= p.interior_wear_level <= hi:
        return None
    if p.interior_wear_level > hi + 2:
        score, severity = 30, "critical"
    elif p.interior_wear_level > hi:
        score, severity = 25, "high"
    elif p.interior_wear_level < lo - 1:
        return RiskSignal(
            code="MILEAGE_TOO_HIGH_FOR_WEAR",
            severity="medium",
            score=10,
            description=(
                f"行照里程 {p.declared_mileage_km:,} km 對應的合理內裝磨耗區間為 {lo}-{hi}/10,"
                f"但實際內裝磨耗只有 {p.interior_wear_level}/10。可能是內裝整新(隱藏歷史)。"
            ),
            evidence={
                "declared_mileage_km": p.declared_mileage_km,
                "expected_wear_range": [lo, hi],
                "observed_wear_level": p.interior_wear_level,
            },
        )
    else:
        return None
    return RiskSignal(
        code="MILEAGE_TOO_LOW_FOR_WEAR",
        severity=severity,
        score=score,
        description=(
            f"行照里程 {p.declared_mileage_km:,} km 對應的合理內裝磨耗區間為 {lo}-{hi}/10,"
            f"但實際觀察內裝磨耗 {p.interior_wear_level}/10,**顯著高於預期**。"
            f"這是**調表車最典型的徵兆** — 賣方可能將實際里程從 ~80,000+ km 調回 {p.declared_mileage_km:,} km。"
        ),
        evidence={
            "declared_mileage_km": p.declared_mileage_km,
            "expected_wear_range": [lo, hi],
            "observed_wear_level": p.interior_wear_level,
            "interior_wear_notes": p.interior_wear_notes,
        },
    )


def check_year_vs_equipment(p: CarProfile) -> RiskSignal | None:
    """年式 vs 配備版本一致性 — 偽造年式徵兆。

    簡化的時代特徵:
      Apple CarPlay 標配最早約 2018+
      盲點偵測標配最早約 2016+
      LED 大燈標配最早約 2015+
      ADAS / 360 環景最早約 2019+
    """
    era_features_minimum_year = {
        "Apple CarPlay": 2018,
        "Android Auto": 2018,
        "盲點偵測": 2016,
        "LED 大燈": 2015,
        "360 環景": 2019,
        "ADAS": 2019,
        "自動煞車": 2017,
    }
    anachronisms = []
    for feat in p.equipment_features:
        for ev_feat, min_year in era_features_minimum_year.items():
            if ev_feat in feat and p.declared_year < min_year:
                anachronisms.append((feat, min_year))
                break
    if anachronisms:
        return RiskSignal(
            code="YEAR_VS_EQUIPMENT_MISMATCH",
            severity="high",
            score=20,
            description=(
                f"宣稱年式 {p.declared_year} 但配備含時代不符特徵:"
                + ", ".join(f"{feat}(原廠標配 ≥{yr})" for feat, yr in anachronisms)
                + "。可能是後加裝(可解釋)或行照年式偽造(嚴重)。"
            ),
            evidence={
                "declared_year": p.declared_year,
                "anachronistic_features": anachronisms,
            },
            confidence="medium",
        )
    return None


def check_engine_bay_vs_accident(p: CarProfile) -> RiskSignal | None:
    """引擎室油漆狀態 vs 「無事故」宣稱。"""
    suspicious_states = ("局部重噴", "全面重噴", "改裝痕跡")
    if p.declared_no_accident and p.engine_bay_state in suspicious_states:
        score = 22 if p.engine_bay_state in ("全面重噴", "改裝痕跡") else 15
        return RiskSignal(
            code="ENGINE_BAY_CONTRADICTS_NO_ACCIDENT",
            severity="high",
            score=score,
            description=(
                f"賣方宣稱『無事故』,但引擎室狀態為「{p.engine_bay_state}」。"
                f"引擎室重噴通常代表前方碰撞修復或結構件矯正。**這與『無事故』直接矛盾**。"
            ),
            evidence={
                "engine_bay_state": p.engine_bay_state,
                "engine_bay_notes": p.engine_bay_notes,
            },
        )
    return None


def check_undercarriage_vs_flood(p: CarProfile) -> RiskSignal | None:
    """底盤生鏽 / 新塗裝 vs 「無泡水」宣稱。"""
    if p.declared_no_flood:
        if p.undercarriage_state == "嚴重生鏽":
            return RiskSignal(
                code="UNDERCARRIAGE_HEAVY_RUST",
                severity="high",
                score=25,
                description=(
                    f"賣方宣稱『無泡水』,但底盤『嚴重生鏽』。**台灣車除非長期沿海或泡水,"
                    f"否則 5-10 年車不應嚴重生鏽**。"
                ),
                evidence={"undercarriage_notes": p.undercarriage_notes},
            )
        if p.undercarriage_state == "新塗裝可疑":
            return RiskSignal(
                code="UNDERCARRIAGE_FRESH_PAINT_SUSPICIOUS",
                severity="high",
                score=20,
                description=(
                    f"底盤『新塗裝可疑』 — 中古車底盤重新塗裝通常是為了掩蓋生鏽 / 泡水痕跡。"
                    f"與『無泡水』宣稱矛盾。"
                ),
                evidence={"undercarriage_notes": p.undercarriage_notes},
            )
    return None


def check_body_paint_consistency(p: CarProfile) -> RiskSignal | None:
    """車身漆面一致性 — 局部重噴 = 修補事故。"""
    if p.body_paint_consistency == "局部色差":
        return RiskSignal(
            code="BODY_PAINT_PARTIAL_MISMATCH",
            severity="medium",
            score=10,
            description=(
                f"車身漆面『局部色差』 — 常見於板金修補。"
                f"輕度修補不一定是事故,但需要賣方說明清楚。"
            ),
            evidence={"body_paint_notes": p.body_paint_notes},
        )
    if p.body_paint_consistency == "明顯重噴痕跡":
        return RiskSignal(
            code="BODY_PAINT_REPAINT",
            severity="high",
            score=18,
            description=(
                f"車身『明顯重噴痕跡』 — 強烈暗示曾發生事故修復。"
                f"與賣方『無事故』宣稱可能矛盾,需深入查證。"
            ),
            evidence={"body_paint_notes": p.body_paint_notes},
        )
    return None


def check_tire_wear_vs_mileage(p: CarProfile) -> RiskSignal | None:
    """輪胎磨耗 vs 行照里程 — 輪胎一般 6-8 萬 km 換一次。"""
    expected_tire_remaining = 100 - (p.declared_mileage_km % 70000) / 700  # very rough
    if p.tire_estimated_remaining_pct < 20 and p.declared_mileage_km < 30000:
        return RiskSignal(
            code="TIRE_HEAVILY_WORN_VS_LOW_MILEAGE",
            severity="medium",
            score=12,
            description=(
                f"輪胎剩餘 {p.tire_estimated_remaining_pct}% 偏低,但行照里程僅 {p.declared_mileage_km:,} km。"
                f"輪胎磨耗對應 ≥ 5 萬 km 的實際里程。**強烈暗示調表**。"
            ),
            evidence={
                "tire_remaining_pct": p.tire_estimated_remaining_pct,
                "declared_mileage_km": p.declared_mileage_km,
                "tire_brand_year": p.tire_brand_year,
            },
        )
    return None


def check_vin_plate(p: CarProfile) -> RiskSignal | None:
    """車身號碼牌真偽。"""
    if p.vin_plate_state == "可疑(字體不一致 / 修補痕跡)":
        return RiskSignal(
            code="VIN_PLATE_SUSPICIOUS",
            severity="critical",
            score=30,
            description=(
                f"⚠️ 車身號碼牌『可疑』 — 字體不一致 / 修補痕跡通常是車身大修(結構件更換)"
                f"或**贓車 / 拼裝車**。**強烈建議**到原廠 / 監理站做車身碼鑑識。"
            ),
            evidence={"vin_plate_notes": p.vin_plate_notes},
        )
    if p.vin_plate_state == "缺失":
        return RiskSignal(
            code="VIN_PLATE_MISSING",
            severity="critical",
            score=30,
            description=(
                f"⚠️ 車身號碼牌『缺失』 — **絕對不要購買**。可能是贓車或重大事故拼裝。"
            ),
            evidence={},
        )
    return None


# ===== 整體評估 =====
@dataclass
class Assessment:
    car: CarProfile
    risk_score: int
    risk_level: str                  # LOW / MEDIUM / HIGH / CRITICAL
    signals: list[RiskSignal]
    summary: str


def assess(car: CarProfile) -> Assessment:
    """跑全部維度的純函式 inspection。"""
    checks = [
        check_mileage_vs_wear,
        check_year_vs_equipment,
        check_engine_bay_vs_accident,
        check_undercarriage_vs_flood,
        check_body_paint_consistency,
        check_tire_wear_vs_mileage,
        check_vin_plate,
    ]
    signals: list[RiskSignal] = []
    for fn in checks:
        sig = fn(car)
        if sig is not None:
            signals.append(sig)

    risk_score = min(100, sum(s.score for s in signals))
    has_critical_signal = any(s.severity == "critical" for s in signals)

    # 任何 critical signal(如 VIN 缺失 / 可疑、調表極端)→ 強制 CRITICAL
    if has_critical_signal:
        level = "CRITICAL"
        summary = (
            f"🔴 風險嚴重(score {risk_score})。**不建議購買**。已偵測到 CRITICAL 級別的訊號 — "
            f"風險組合表明可能是:事故重組車 / 泡水車 / 調表車 / 贓車。"
            f"即使議價也無法消除結構性風險(將來轉手 / 維修 / 保險都會出問題)。"
        )
    elif risk_score <= RISK_LOW:
        level = "LOW"
        summary = "車況風險低,賣方提供的資訊與觀察一致。"
    elif risk_score <= RISK_MEDIUM:
        level = "MEDIUM"
        summary = (
            f"風險中等(score {risk_score})。**建議**:① 帶車進原廠做完整檢查(NT$3-5K)"
            f"② 議價空間 NT$1-3 萬以反映風險 ③ 簽約時加註「事故 / 泡水 / 調表」保證條款 + 違約退款。"
        )
    elif risk_score <= RISK_HIGH:
        level = "HIGH"
        summary = (
            f"⚠️ 風險偏高(score {risk_score})。**強烈建議**:① 立即停止交易直到原廠完整鑑定"
            f"② 若仍想買,議價空間 NT$3-8 萬 + 限期 7 天退款條款 ③ 另尋同款車款比較。"
        )
    else:
        level = "CRITICAL"
        summary = (
            f"🔴 風險嚴重(score {risk_score})。**不建議購買**。風險組合表明可能是:"
            f"事故重組車 / 泡水車 / 調表車 / 贓車。即使議價也無法消除結構性風險(將來轉手 / 維修 / 保險都會出問題)。"
        )

    return Assessment(
        car=car,
        risk_score=risk_score,
        risk_level=level,
        signals=signals,
        summary=summary,
    )
