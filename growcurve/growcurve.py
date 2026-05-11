"""growcurve CLI — 嬰幼兒每日體重 Kalman filter smoothing + WHO 百分位 + 異常警示。

Usage:
    python growcurve.py --log samples/baby_log.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from kalman import (
    Measurement, KalmanConfig, kalman_pipeline,
    who_percentile, interpolate_who, detect_anomalies,
    WHO_BOY_P50_KG, WHO_GIRL_P50_KG, WHO_SIGMA_KG_BY_MONTH,
    KalmanResult, GrowthFlag,
)


def load_log(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, measurements: list[Measurement],
                  result: KalmanResult, flags: list[GrowthFlag]) -> str:
    info = data["infant_info"]
    age_start = info["infant_age_months_at_start"]
    age_end = age_start + result.days[-1] / 30
    sex = info["sex"]

    initial_w = result.smoothed_weight[0]
    final_w = result.smoothed_weight[-1]
    delta = final_w - initial_w
    final_velocity_g_day = result.smoothed_velocity[-1] * 1000
    avg_velocity_g_day = delta / result.days[-1] * 1000 if result.days[-1] else 0

    final_pct, final_tier = who_percentile(final_w, age_end, sex)
    initial_pct, _ = who_percentile(initial_w, age_start, sex)

    raw_min = min(result.raw_measurements)
    raw_max = max(result.raw_measurements)

    lines = [
        f"# growcurve — {info['infant_name']} 體重 Kalman filter 分析",
        "",
        f"**起始日期**: {info.get('start_date', 'N/A')}  ·  **觀察天數**: {len(measurements)}",
        f"**起始月齡**: {age_start:.1f} 月  ·  **目前月齡**: {age_end:.1f} 月",
        f"**性別**: {'男嬰' if sex == 'boy' else '女嬰'}",
        "",
        "## 🎯 Kalman Filter 平滑結果",
        "",
        "| 指標 | 起始 | 目前 | 變化 |",
        "|---|---|---|---|",
        f"| Smoothed 體重 (kg) | {initial_w:.3f} | **{final_w:.3f}** | +{delta * 1000:.0f} g |",
        f"| WHO 百分位 | P{initial_pct:.0f} | **P{final_pct:.0f}** ({final_tier}) | — |",
        f"| Smoothed 增重速率 (g/day) | — | **{final_velocity_g_day:.1f}** | — |",
        f"| 平均增重 (g/day) | — | {avg_velocity_g_day:.1f} | — |",
        "",
        "## 📊 Raw vs Smoothed 體重 (最近 7 天)",
        "",
        "| 日 | Raw (kg) | Smoothed (kg) | Velocity (g/day) | 變動 |",
        "|---|---|---|---|---|",
    ]

    n_show = min(14, len(measurements))
    for i in range(len(measurements) - n_show, len(measurements)):
        raw = result.raw_measurements[i]
        smoothed = result.smoothed_weight[i]
        vel = result.smoothed_velocity[i] * 1000
        diff = (raw - smoothed) * 1000
        marker = "🔴" if abs(diff) > 200 else ("🟡" if abs(diff) > 100 else "🟢")
        lines.append(
            f"| Day {result.days[i]} | {raw:.3f} | **{smoothed:.3f}** | {vel:+.1f} | "
            f"{marker} {diff:+.0f} g vs smoothed |"
        )

    lines.extend([
        "",
        "## 🔍 Raw noise vs smoothed signal",
        "",
        f"- **Raw min/max**: {raw_min:.2f} - {raw_max:.2f} kg (range {(raw_max - raw_min) * 1000:.0f} g — 量秤誤差 + 排便 + 餵奶前後)",
        f"- **Smoothed range**: {min(result.smoothed_weight):.3f} - {max(result.smoothed_weight):.3f} kg",
        f"- **Kalman 過濾掉 ~{int((raw_max - raw_min - (max(result.smoothed_weight) - min(result.smoothed_weight))) * 1000)} g 的 noise**",
        "",
        "## ⚠️ 成長異常警示",
        "",
    ])
    if not flags:
        lines.append("✅ 沒有偵測到異常。體重 trend 在 WHO 範圍內、增重速率符合月齡標準。")
    else:
        for f in flags:
            sev_marker = {"urgent": "🔴", "moderate": "🟡", "mild": "🟢"}.get(f.severity, "⚪")
            lines.append(f"### {sev_marker} {f.severity.upper()}: {f.flag_type}")
            lines.append("")
            lines.append(f"- {f.description}")
            lines.append("")

    lines.append("## WHO 0-24 月生長標準對照")
    lines.append("")
    table = WHO_BOY_P50_KG if sex == "boy" else WHO_GIRL_P50_KG
    lines.append("| 月齡 | P50 體重 (kg) | 寶寶當時體重對照 |")
    lines.append("|---|---|---|")
    for age in [0, 1, 2, 3, 4, 6, 9, 12]:
        p50 = table.get(age, 0)
        if age_start <= age <= age_end:
            day_at_age = int((age - age_start) * 30)
            if 0 <= day_at_age < len(result.smoothed_weight):
                actual = result.smoothed_weight[day_at_age]
                diff_pct = (actual - p50) / p50 * 100
                lines.append(f"| {age} mo | {p50:.1f} | **{actual:.2f} ({diff_pct:+.1f}%)** |")
        else:
            lines.append(f"| {age} mo | {p50:.1f} | — |")

    lines.append("")
    lines.append("## ⚠️ Kalman 模型假設與限制")
    lines.append("")
    lines.append("- **Linear-Gaussian 假設**: state evolution + observation 都假設高斯,真實生長有 nonlinear 成分;Pro 版可用 EKF / UKF")
    lines.append("- **Process noise σ² 是 prior**: 設定 0.001 kg² / 0.00001 kg/day² 是 conservative,個別寶寶可調")
    lines.append("- **觀察 noise σ² = 0.04 kg² (0.2 kg std)**: 適合家用體重計, 醫院級電子秤可用 0.01")
    lines.append("- **WHO 標準是全球**: 台灣寶寶平均體型較亞洲基準, 100% WHO 比對偶有偏差;Pro 版用 CDC / 台灣兒科 NHI 標準")
    lines.append("- **不取代兒科醫師**: 工具用於監控進度 + 早期警示,確診 / 治療仍需專業評估")
    lines.append("- **同一天多次量會誤導**: 餵奶前 vs 餵奶後可差 200-500 g, 建議每天固定時段 (e.g., 晨起空腹 / 餵奶前)")
    lines.append("")
    lines.append("---")
    lines.append("*growcurve = Kalman 1960 filter + RTS smoother × 台灣 0-24 月嬰幼兒生長監控 niche = 把 daily ±200g 噪音過濾, 還原真實 weight trajectory + 即時 percentile + 異常警示。*")
    return "\n".join(lines)


def render_with_ai(data, measurements, result, flags):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, measurements, result, flags)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, measurements, result, flags)

    base = render_no_ai(data, measurements, result, flags)
    info = data["infant_info"]
    age_end = info["infant_age_months_at_start"] + result.days[-1] / 30
    final_w = result.smoothed_weight[-1]
    final_velocity_g_day = result.smoothed_velocity[-1] * 1000
    final_pct, final_tier = who_percentile(final_w, age_end, info["sex"])
    flag_summary = "; ".join(f"{f.severity} {f.flag_type}" for f in flags) or "無異常"

    prompt = f"""你是一位資深台灣兒科醫師 / 兒童發展顧問。下面是用 Kalman filter 純函式分析的嬰兒體重結果:

寶寶: {info['infant_name']} {age_end:.1f} 月齡 ({info['sex']})
觀察 {len(measurements)} 天
Smoothed 體重: {result.smoothed_weight[0]:.3f} → {final_w:.3f} kg (+{(final_w - result.smoothed_weight[0]) * 1000:.0f} g)
WHO 百分位: P{final_pct:.0f} ({final_tier})
近 5 天 smoothed 增重速率: {final_velocity_g_day:.1f} g/day
警示: {flag_summary}

請寫 220-300 字「給父母讀的解讀 + 餵食建議 + 何時就醫紅旗」:
1. 一句話翻譯 (避免「Kalman」「smoother」這種詞)
2. **3 個具體餵食 / 照顧建議** (奶量增加 / 副食品種類 / 配方奶 vs 母乳)
3. **就醫紅旗** (體溫 / 餵食 / 大小便 紅旗 3-4 個)
4. 1 個情緒安撫 (不要套話)

**嚴格規則**:
- 不要重算 g/day / percentile, 引用 facts
- 不要套話 ("加油")
- 不超過 300 字
- 不要 markdown 標題

直接寫解讀。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 兒科醫師解讀\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="growcurve — 嬰幼兒體重 Kalman filter")
    p.add_argument("--log", default="samples/baby_log.json")
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_log(Path(args.log))
    measurements = [Measurement(**m) for m in data["measurements"]]
    config = KalmanConfig()
    result = kalman_pipeline(measurements, config)
    flags = detect_anomalies(
        result,
        age_months_at_start=data["infant_info"]["infant_age_months_at_start"],
        sex=data["infant_info"]["sex"],
    )

    if args.no_ai:
        print(render_no_ai(data, measurements, result, flags))
    else:
        print(render_with_ai(data, measurements, result, flags))


if __name__ == "__main__":
    main()
