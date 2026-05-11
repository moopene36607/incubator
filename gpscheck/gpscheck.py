"""gpscheck CLI — 外送員 / 計程車 GPS 路徑 DTW 異常偵測 + 司機自證工具。

Usage:
    python gpscheck.py --trip samples/trip.json --no-ai
    python gpscheck.py --trip samples/trip.json --threshold 300
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dtw import (
    GPSPoint, Route, compute_dtw, classify_route, identify_deviations,
    route_total_distance, route_duration_s, route_avg_speed_kmh,
    extra_distance_estimate, Verdict, DTWResult,
)


def load_trip(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_route(data: dict) -> Route:
    return Route(
        name=data["name"],
        points=[GPSPoint(**{k: v for k, v in p.items() if k in {"lat", "lon", "t"}})
                for p in data["points"]],
    )


VERDICT_LABEL = {
    Verdict.NORMAL: "🟢 路線正常 (NORMAL)",
    Verdict.MINOR_DEVIATION: "🟡 輕微偏離 (MINOR DEVIATION)",
    Verdict.SIGNIFICANT_DEVIATION: "🟠 顯著偏離 (SIGNIFICANT)",
    Verdict.MAJOR_DEVIATION: "🔴 嚴重偏離 (MAJOR)",
}


def render_no_ai(trip: dict, planned: Route, actual: Route, result: DTWResult,
                  deviations: list, verdict: Verdict, threshold_m: float) -> str:
    extra_m = extra_distance_estimate(actual, planned)
    planned_dist = route_total_distance(planned)
    actual_dist = route_total_distance(actual)
    planned_time = route_duration_s(planned) / 60
    actual_time = route_duration_s(actual) / 60
    planned_speed = route_avg_speed_kmh(planned)
    actual_speed = route_avg_speed_kmh(actual)

    lines = [
        f"# gpscheck — 訂單 #{trip.get('trip_id', '')} GPS DTW 路徑分析",
        "",
        f"**司機**: {trip.get('driver_name', '')}  ·  **平台**: {trip.get('platform', '')}",
        f"**取餐地**: {trip.get('pickup_address', '')} → **送達地**: {trip.get('dropoff_address', '')}",
        f"**訂單金額**: NT${trip.get('order_total_ntd', 0):,}",
        f"**平台估時**: {trip.get('estimated_minutes', 0)} 分  ·  **實際耗時**: {trip.get('actual_minutes', 0)} 分",
        f"**平台處置**: {trip.get('platform_penalty', '無')}",
        "",
        "## 🎯 DTW 路徑相似度分析",
        "",
        f"### {VERDICT_LABEL[verdict]}",
        "",
        f"- **DTW similarity score**: **{result.similarity_score:.1f} / 100**",
        f"- **DTW 總成本**: {result.distance_total_m:.0f} m (alignment path)",
        f"- **平均每點偏離**: {result.distance_normalized_m:.0f} m",
        f"- **Alignment path 長度**: {result.path_length}",
        "",
        "## 路線基本指標對照",
        "",
        "| 指標 | 平台建議 | 實際 | 差距 |",
        "|---|---|---|---|",
        f"| 路線總距離 | {planned_dist:.0f} m | {actual_dist:.0f} m | {extra_m:+.0f} m ({extra_m / planned_dist * 100:+.1f}%) |",
        f"| 持續時間 | {planned_time:.1f} 分 | {actual_time:.1f} 分 | {actual_time - planned_time:+.1f} 分 |",
        f"| 平均車速 | {planned_speed:.1f} km/h | {actual_speed:.1f} km/h | {actual_speed - planned_speed:+.1f} km/h |",
        f"| GPS 點數 | {len(planned.points)} | {len(actual.points)} | — |",
        "",
    ]

    lines.append(f"## 偏離點識別 (閾值 = {threshold_m:.0f} m)")
    lines.append("")
    if deviations:
        lines.append(f"在 DTW alignment 上有 **{len(deviations)} 個偏離點** > {threshold_m:.0f} m:")
        lines.append("")
        lines.append("| # | actual idx | planned idx | actual (lat, lon) | planned (lat, lon) | 偏離距離 |")
        lines.append("|---|---|---|---|---|---|")
        for i, d in enumerate(deviations[:10]):
            lines.append(
                f"| {i + 1} | {d.actual_idx} | {d.planned_idx} | "
                f"({d.actual_point.lat:.4f}, {d.actual_point.lon:.4f}) | "
                f"({d.planned_point.lat:.4f}, {d.planned_point.lon:.4f}) | "
                f"**{d.distance_m:.0f} m** |"
            )
    else:
        lines.append(f"在 DTW alignment 上沒有 > {threshold_m:.0f} m 的偏離點 — 路線基本貼合系統建議。")

    lines.append("")
    lines.append("## 純函式判讀")
    lines.append("")

    # Reasoning signals
    signals = []
    if extra_m < 200:
        signals.append(f"✅ 實際路線僅多 {extra_m:.0f} m,合理範圍 (一般 GPS 誤差 + 紅綠燈繞行)")
    elif extra_m < 500:
        signals.append(f"⚠️ 實際路線多 {extra_m:.0f} m,稍微繞遠但可能因為塞車 / 單行道")
    else:
        signals.append(f"🔴 實際路線多 {extra_m:.0f} m,**顯著繞路**,需要解釋")

    if (actual_time - planned_time) > 5:
        signals.append(f"⚠️ 耗時多 {actual_time - planned_time:.1f} 分,常見原因:塞車 / 等紅燈 / 短暫停車")

    if actual_speed < planned_speed * 0.7:
        signals.append(f"⚠️ 實際車速 {actual_speed:.1f} 比建議 {planned_speed:.1f} 慢 {(1 - actual_speed/planned_speed)*100:.0f}%,可能塞車")

    if verdict == Verdict.NORMAL:
        signals.append("✅ DTW 相似度 ≥ 85,路線基本貼合,**平台處置可申訴撤銷**")
    elif verdict == Verdict.MINOR_DEVIATION:
        signals.append("🟡 DTW 相似度 70-85, 輕微偏離,可能是 lane change / 短繞,可申訴但帶說明")
    elif verdict == Verdict.SIGNIFICANT_DEVIATION:
        signals.append("🟠 DTW 相似度 50-70, 明顯繞路,司機需準備理由 (塞車照片 / 施工 / 道路封閉)")
    else:
        signals.append("🔴 DTW 相似度 < 50, 嚴重繞路,司機申訴難度高,建議檢視自己路線判斷")

    for s in signals:
        lines.append(f"- {s}")

    lines.append("")
    lines.append("## ⚠️ DTW 模型假設與限制")
    lines.append("")
    lines.append("- **DTW 為點對點 alignment**,不理解「實際走的道路網路」— 兩條路偏 100m 但都在 main road 上也會被算成 100m 偏離")
    lines.append("- **無權重 monotonicity 約束** — Sakoe-Chiba 帶 (warp constraint) 沒實作;Pro 版加 max warping ratio 過濾誤判")
    lines.append("- **GPS 誤差** 城市區 5-20m 都正常,>200m 才確定有偏離意圖")
    lines.append("- **單一 metric** — DTW 不知道車速 / 暫停 / 紅綠燈;與時間 / 距離 metric 聯合看才完整")
    lines.append("- **平台演算法不一定承認此分析** — 可作為司機自證證據,但 Uber Eats / Foodpanda 申訴決定權仍在平台")
    lines.append("")
    lines.append("---")
    lines.append("*gpscheck = Sakoe & Chiba 1978 DTW × 台灣外送員 / 司機 niche = 用數學替司機申訴而不是平台 algorithm 說了算。*")
    return "\n".join(lines)


def render_with_ai(trip: dict, planned: Route, actual: Route, result: DTWResult,
                    deviations: list, verdict: Verdict, threshold_m: float) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(trip, planned, actual, result, deviations, verdict, threshold_m)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(trip, planned, actual, result, deviations, verdict, threshold_m)

    base = render_no_ai(trip, planned, actual, result, deviations, verdict, threshold_m)

    extra_m = extra_distance_estimate(actual, planned)
    extra_time = (route_duration_s(actual) - route_duration_s(planned)) / 60

    prompt = f"""你是一位資深台灣外送員 / 司機申訴顧問。下面是用 DTW (Dynamic Time Warping) 純函式分析的 GPS 路線比對結果(數字 100% 算好,不能改):

訂單: {trip.get('trip_id')}  ·  司機 {trip.get('driver_name')}
平台處置: {trip.get('platform_penalty', '無')}
verdict: {verdict.value}
DTW similarity: {result.similarity_score} / 100
實際路線多 {extra_m:+.0f} m, 多耗 {extra_time:+.1f} 分鐘
偏離點 (>{threshold_m}m): {len(deviations)} 個
平台估時 {trip.get('estimated_minutes')} 分 vs 實際 {trip.get('actual_minutes')} 分

請寫 200-280 字「司機申訴建議」:
1. 一句話翻譯 verdict (是 normal / minor / significant / major)
2. **3 個具體申訴步驟** (Uber Eats / Foodpanda 申訴管道, 該附什麼證據, 怎麼寫申訴內容)
3. **3 個可能的合理解釋** (司機應該優先用哪個解釋 — 塞車 / 施工 / 客戶改地址 / 單行道 / 取餐延誤)
4. 1 個風險提醒 (申訴成功率 / 申訴後可能反效果 / 平台政策)

**嚴格規則**:
- 不要重新算 m / 百分比, 引用上面數字
- 不要套話 ("加油", "祝順利")
- 不超過 280 字
- 不要 markdown 標題

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 申訴顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="gpscheck — GPS 路徑 DTW 異常偵測")
    p.add_argument("--trip", default="samples/trip.json")
    p.add_argument("--threshold", type=float, default=200, help="deviation threshold in meters")
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    trip = load_trip(Path(args.trip))
    planned = make_route(trip["planned_route"])
    actual = make_route(trip["actual_route"])
    result = compute_dtw(actual, planned)
    verdict = classify_route(result)
    deviations = identify_deviations(actual, planned, result.alignment_path, threshold_m=args.threshold)

    if args.no_ai:
        print(render_no_ai(trip, planned, actual, result, deviations, verdict, args.threshold))
    else:
        print(render_with_ai(trip, planned, actual, result, deviations, verdict, args.threshold))


if __name__ == "__main__":
    main()
