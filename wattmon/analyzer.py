"""wattmon — 台灣中小型用戶 AMI 30 分鐘讀值用電異常偵測(純函式 / no I/O / no LLM).

責任:
  - 讀取 (timestamp, kwh) 序列
  - 計算週期摘要(總用電 / peak / base load / 商業時段比例 / 估算電費)
  - 偵測四類異常:
      1. NIGHT_LEAK   店休時段(預設 22:00-07:00)耗電遠高於 base load(漏電 / 冷凍失溫 / 設備未關)
      2. HOUR_BURST   單時段(連續 30 分鐘以上)比同 (DOW, hour) 4 週中位數高 50%+
      3. DAILY_HIGH   單日總用電比同 DOW 4 週中位數高 30%+
      4. BASELINE_DRIFT 後半段(後 14-15 天)平均比前半段高 15%+(設備老化 / 季節變化)

LLM 的責任在另一個檔案(wattmon.py 的 ai_explain),為純函式偵測到的 anomaly
寫人性化解釋 + 節電建議。本檔案完全不碰 LLM,確保異常偵測可單元測試、可重現。

電費估算:採商業用電簡化價 NT$3.50/kWh(實際隨契約容量 / 時段 / 季節變動,
真實產品要接台電費率 API)。

設計守則:
  - 數字 100% 純函式;LLM 永不算電費
  - 偵測閾值在常數寫死;未來可改 config
  - 連續 anomaly 自動合併(避免 6 條「14:00 高 / 14:30 高 / 15:00 高...」噪音)
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ---- 商業電價(簡化)----
NTD_PER_KWH = 3.50  # 商業用電平均價(實際因契約容量分時段)

# ---- 異常偵測閾值 ----
NIGHT_HOURS = (23, 6)              # 23:00-翌日 06:00 = 店休 / 待機核心時段
                                   # (避開 22:00 收店清潔 / 06:00 早班開機 transition)
NIGHT_LEAK_MULTIPLIER = 2.5        # 夜間耗電 > base × 2.5 → 漏電嫌疑
NIGHT_LEAK_MIN_DURATION_30MIN = 3  # 至少連續 3 個 30 分鐘 (1.5 小時) 才算

HOUR_BURST_RATIO = 1.5             # 同 (DOW, hour) baseline 之 1.5 倍以上
HOUR_BURST_MIN_DURATION_30MIN = 3  # 連續 1.5 小時以上

DAILY_HIGH_THRESHOLD = 1.30        # 整天總 kWh 比同 DOW 4 週中位數高 30%+
BASELINE_DRIFT_THRESHOLD = 0.10    # 後半段平均比前半段高 10%+


@dataclass
class Reading:
    timestamp: datetime
    kwh: float


@dataclass
class PeriodSummary:
    start: datetime
    end: datetime
    total_kwh: float
    peak_kwh_30min: float
    peak_at: datetime
    base_load_kwh_per_30min: float   # 凌晨 2-5 點中位數
    business_hours_kwh: float        # 09:00-22:00
    night_kwh: float                 # 22:00-翌日 09:00
    night_pct: float
    weekday_avg_daily_kwh: float
    weekend_avg_daily_kwh: float
    cost_estimate_ntd: float


@dataclass
class Anomaly:
    code: str            # NIGHT_LEAK / HOUR_BURST / DAILY_HIGH / BASELINE_DRIFT
    severity: str        # low / medium / high
    summary: str         # 一句話描述(純函式產出,無自然語言修辭)
    timestamp_start: datetime
    timestamp_end: datetime
    observed_kwh: float
    expected_kwh: float
    deviation_pct: float
    context: dict = field(default_factory=dict)


def parse_csv(path: str) -> list[Reading]:
    readings: list[Reading] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.strptime(row["timestamp"].strip(), "%Y-%m-%d %H:%M")
            readings.append(Reading(timestamp=ts, kwh=float(row["kwh"])))
    readings.sort(key=lambda r: r.timestamp)
    return readings


def _is_night(ts: datetime) -> bool:
    start, end = NIGHT_HOURS  # (22, 7)
    h = ts.hour
    return h >= start or h < end


def _is_weekend(ts: datetime) -> bool:
    return ts.weekday() >= 5


def summarize(readings: list[Reading]) -> PeriodSummary:
    assert readings, "需要至少 1 筆讀值"
    total = sum(r.kwh for r in readings)
    peak_r = max(readings, key=lambda r: r.kwh)
    night = sum(r.kwh for r in readings if _is_night(r.timestamp))
    business = total - night
    base_candidates = [r.kwh for r in readings if 2 <= r.timestamp.hour < 5]
    base_load = statistics.median(base_candidates) if base_candidates else 0.0

    # 每日 totals
    daily: dict[str, float] = {}
    for r in readings:
        key = r.timestamp.strftime("%Y-%m-%d")
        daily[key] = daily.get(key, 0.0) + r.kwh
    weekday_totals = []
    weekend_totals = []
    for d_str, total_d in daily.items():
        d = datetime.strptime(d_str, "%Y-%m-%d")
        (weekend_totals if d.weekday() >= 5 else weekday_totals).append(total_d)

    return PeriodSummary(
        start=readings[0].timestamp,
        end=readings[-1].timestamp,
        total_kwh=round(total, 2),
        peak_kwh_30min=round(peak_r.kwh, 3),
        peak_at=peak_r.timestamp,
        base_load_kwh_per_30min=round(base_load, 3),
        business_hours_kwh=round(business, 2),
        night_kwh=round(night, 2),
        night_pct=round(night / total * 100, 1) if total else 0.0,
        weekday_avg_daily_kwh=round(statistics.mean(weekday_totals), 2) if weekday_totals else 0.0,
        weekend_avg_daily_kwh=round(statistics.mean(weekend_totals), 2) if weekend_totals else 0.0,
        cost_estimate_ntd=round(total * NTD_PER_KWH, 0),
    )


def _baseline_dow_hour(readings: list[Reading], target_dow: int, target_hour: int) -> float:
    """同 (weekday, hour-of-day) 所有讀值的中位數。"""
    matches = [r.kwh for r in readings
               if r.timestamp.weekday() == target_dow and r.timestamp.hour == target_hour]
    return statistics.median(matches) if matches else 0.0


def _group_consecutive(indices: list[int]) -> list[list[int]]:
    """[3,4,5,9,10] -> [[3,4,5],[9,10]]"""
    if not indices:
        return []
    groups = [[indices[0]]]
    for idx in indices[1:]:
        if idx == groups[-1][-1] + 1:
            groups[-1].append(idx)
        else:
            groups.append([idx])
    return groups


def detect_night_leak(readings: list[Reading]) -> list[Anomaly]:
    """夜間 (22:00-07:00) 耗電 > base_load × NIGHT_LEAK_MULTIPLIER,連續 >= 1.5 小時。"""
    base_candidates = [r.kwh for r in readings if 2 <= r.timestamp.hour < 5]
    if not base_candidates:
        return []
    base_load = statistics.median(base_candidates)
    threshold = base_load * NIGHT_LEAK_MULTIPLIER
    flagged_indices = [i for i, r in enumerate(readings)
                       if _is_night(r.timestamp) and r.kwh > threshold]
    out: list[Anomaly] = []
    for group in _group_consecutive(flagged_indices):
        if len(group) < NIGHT_LEAK_MIN_DURATION_30MIN:
            continue
        seg = [readings[i] for i in group]
        observed = sum(r.kwh for r in seg)
        expected = base_load * len(seg)
        deviation = (observed - expected) / expected * 100 if expected else 0.0
        severity = "high" if deviation > 200 else ("medium" if deviation > 100 else "low")
        out.append(Anomaly(
            code="NIGHT_LEAK",
            severity=severity,
            summary=(f"店休時段 {seg[0].timestamp.strftime('%m/%d %H:%M')}-"
                     f"{seg[-1].timestamp.strftime('%H:%M')} 耗電 {observed:.2f} kWh,"
                     f"是同時段 base_load 預期 {expected:.2f} kWh 的 {observed/expected:.1f} 倍"),
            timestamp_start=seg[0].timestamp,
            timestamp_end=seg[-1].timestamp,
            observed_kwh=round(observed, 3),
            expected_kwh=round(expected, 3),
            deviation_pct=round(deviation, 1),
            context={
                "base_load_per_30min": round(base_load, 3),
                "duration_30min_slots": len(seg),
                "extra_kwh": round(observed - expected, 3),
                "extra_cost_ntd": round((observed - expected) * NTD_PER_KWH, 0),
            },
        ))
    return out


def detect_hour_bursts(readings: list[Reading]) -> list[Anomaly]:
    """某時段比同 (DOW, hour) 4 週中位數高 HOUR_BURST_THRESHOLD+,連續 >= HOUR_BURST_MIN。"""
    flagged_indices: list[int] = []
    for i, r in enumerate(readings):
        baseline = _baseline_dow_hour(readings, r.timestamp.weekday(), r.timestamp.hour)
        if baseline <= 0:
            continue
        if r.kwh / baseline >= HOUR_BURST_RATIO:
            flagged_indices.append(i)
    out: list[Anomaly] = []
    for group in _group_consecutive(flagged_indices):
        if len(group) < HOUR_BURST_MIN_DURATION_30MIN:
            continue
        seg = [readings[i] for i in group]
        observed = sum(r.kwh for r in seg)
        # expected 用每筆對應 baseline 的總和
        expected = 0.0
        for r in seg:
            expected += _baseline_dow_hour(readings, r.timestamp.weekday(), r.timestamp.hour)
        if expected <= 0:
            continue
        deviation = (observed - expected) / expected * 100
        severity = "high" if deviation > 80 else ("medium" if deviation > 50 else "low")
        dow_zh = ["一", "二", "三", "四", "五", "六", "日"][seg[0].timestamp.weekday()]
        out.append(Anomaly(
            code="HOUR_BURST",
            severity=severity,
            summary=(f"{seg[0].timestamp.strftime('%m/%d')} (週{dow_zh}) "
                     f"{seg[0].timestamp.strftime('%H:%M')}-{seg[-1].timestamp.strftime('%H:%M')} "
                     f"耗電 {observed:.2f} kWh,比同 (週{dow_zh}, 該時段) 4 週中位數 "
                     f"{expected:.2f} kWh 高 {deviation:.0f}%"),
            timestamp_start=seg[0].timestamp,
            timestamp_end=seg[-1].timestamp,
            observed_kwh=round(observed, 3),
            expected_kwh=round(expected, 3),
            deviation_pct=round(deviation, 1),
            context={
                "duration_30min_slots": len(seg),
                "extra_kwh": round(observed - expected, 3),
                "extra_cost_ntd": round((observed - expected) * NTD_PER_KWH, 0),
            },
        ))
    return out


def detect_daily_high(readings: list[Reading]) -> list[Anomaly]:
    """單日總用電比同 DOW 中位數高 DAILY_HIGH_THRESHOLD+。"""
    daily: dict[str, float] = {}
    daily_dow: dict[str, int] = {}
    for r in readings:
        key = r.timestamp.strftime("%Y-%m-%d")
        daily[key] = daily.get(key, 0.0) + r.kwh
        daily_dow[key] = r.timestamp.weekday()
    by_dow: dict[int, list[float]] = {}
    for d_str, total in daily.items():
        by_dow.setdefault(daily_dow[d_str], []).append(total)
    out: list[Anomaly] = []
    for d_str in sorted(daily.keys()):
        total = daily[d_str]
        dow = daily_dow[d_str]
        peers = by_dow.get(dow, [])
        if len(peers) < 2:
            continue
        median_dow = statistics.median(peers)
        if median_dow <= 0:
            continue
        ratio = total / median_dow
        if ratio < DAILY_HIGH_THRESHOLD:
            continue
        deviation = (ratio - 1) * 100
        severity = "high" if deviation > 60 else ("medium" if deviation > 40 else "low")
        d = datetime.strptime(d_str, "%Y-%m-%d")
        out.append(Anomaly(
            code="DAILY_HIGH",
            severity=severity,
            summary=(f"{d_str} (週{['一','二','三','四','五','六','日'][dow]}) 全日 "
                     f"{total:.1f} kWh,比其他週{['一','二','三','四','五','六','日'][dow]}"
                     f"中位數 {median_dow:.1f} kWh 高 {deviation:.0f}%"),
            timestamp_start=datetime(d.year, d.month, d.day, 0, 0),
            timestamp_end=datetime(d.year, d.month, d.day, 23, 30),
            observed_kwh=round(total, 2),
            expected_kwh=round(median_dow, 2),
            deviation_pct=round(deviation, 1),
            context={
                "weekday": dow,
                "extra_kwh": round(total - median_dow, 2),
                "extra_cost_ntd": round((total - median_dow) * NTD_PER_KWH, 0),
            },
        ))
    return out


def detect_baseline_drift(readings: list[Reading]) -> list[Anomaly]:
    """前半段 vs 後半段日均比較。"""
    if len(readings) < 48 * 7 * 2:  # 至少要 14 天
        return []
    daily: dict[str, float] = {}
    for r in readings:
        key = r.timestamp.strftime("%Y-%m-%d")
        daily[key] = daily.get(key, 0.0) + r.kwh
    keys = sorted(daily.keys())
    half = len(keys) // 2
    early = [daily[k] for k in keys[:half]]
    late = [daily[k] for k in keys[half:]]
    early_avg = statistics.mean(early)
    late_avg = statistics.mean(late)
    if early_avg <= 0:
        return []
    delta = (late_avg - early_avg) / early_avg
    if abs(delta) < BASELINE_DRIFT_THRESHOLD:
        return []
    severity = "high" if abs(delta) > 0.30 else ("medium" if abs(delta) > 0.20 else "low")
    direction = "上升" if delta > 0 else "下降"
    code = "BASELINE_DRIFT"
    return [Anomaly(
        code=code,
        severity=severity,
        summary=(f"後半期 ({keys[half]} 起) 日均 {late_avg:.1f} kWh,"
                 f"比前半期 ({keys[0]}-{keys[half-1]}) 日均 {early_avg:.1f} kWh "
                 f"{direction} {abs(delta)*100:.0f}%"),
        timestamp_start=datetime.strptime(keys[half], "%Y-%m-%d"),
        timestamp_end=datetime.strptime(keys[-1], "%Y-%m-%d") + timedelta(hours=23, minutes=30),
        observed_kwh=round(late_avg * len(late), 2),
        expected_kwh=round(early_avg * len(late), 2),
        deviation_pct=round(delta * 100, 1),
        context={
            "early_avg_daily_kwh": round(early_avg, 2),
            "late_avg_daily_kwh": round(late_avg, 2),
            "monthly_extra_cost_ntd": round((late_avg - early_avg) * 30 * NTD_PER_KWH, 0),
        },
    )]


def detect_all(readings: list[Reading]) -> list[Anomaly]:
    out = []
    out.extend(detect_night_leak(readings))
    out.extend(detect_hour_bursts(readings))
    out.extend(detect_daily_high(readings))
    out.extend(detect_baseline_drift(readings))
    out.sort(key=lambda a: (a.timestamp_start, a.code))
    return out
