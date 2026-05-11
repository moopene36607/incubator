"""constsim CLI — 裝潢 / 建築工程 估價 k-NN 案例比對。

Usage:
    python constsim.py --data samples/construction_quotes.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from knn import (
    FeatureSpec, TrainingCase, knn_predict, auto_scale, loo_evaluate,
    numeric_feature_correlations, categorical_feature_mean_diff,
    KNNPrediction,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


DEFAULT_SPECS = [
    FeatureSpec("project_type", "categorical", weight=8.0),
    FeatureSpec("region", "categorical", weight=1.5),
    FeatureSpec("grade", "categorical", weight=4.0),
    FeatureSpec("ping", "numeric", weight=3.0),
    FeatureSpec("building_age_years", "numeric", weight=0.5),
    FeatureSpec("duration_weeks", "numeric", weight=0.7),
    FeatureSpec("has_plumbing_rewire", "numeric", weight=1.5),
    FeatureSpec("has_demolition", "numeric", weight=1.0),
]


FEATURE_DESC_ZH = {
    "project_type": "工程類型",
    "region": "地區",
    "grade": "材料等級",
    "ping": "坪數",
    "building_age_years": "屋齡 (年)",
    "duration_weeks": "工期 (週)",
    "has_plumbing_rewire": "水電遷移",
    "has_demolition": "需拆除",
}


def render_no_ai(data: dict, prediction: KNNPrediction, query: dict,
                  loo_metrics: dict, correlations: dict,
                  cat_means: dict) -> str:
    case_count = len(data["training_cases"])
    lines = [
        f"# constsim — 裝潢 / 建築工程 k-NN 估價",
        "",
        f"**訓練案例**: {case_count} 件歷史工程",
        f"**LOO cross-validation**: MAE NT${loo_metrics['mae']:.0f}K, MAPE {loo_metrics['mape']:.1f}%, RMSE NT${loo_metrics['rmse']:.0f}K",
        "",
        "## 🎯 新案需求",
        "",
        f"_{data['new_query'].get('_meta', '')}_",
        "",
        "| 特徵 | 值 |",
        "|---|---|",
    ]
    for fname, val in query.items():
        lines.append(f"| {FEATURE_DESC_ZH.get(fname, fname)} | {val} |")

    lines.extend([
        "",
        "## 💰 k-NN 估價結果",
        "",
        f"### NT$ **{prediction.predicted_value:.0f}** 千 (千元 = NT$1,000)",
        "",
        f"- **不確定性 (1 std)**: ±NT${prediction.predicted_std:.0f}K",
        f"- **合理區間**: NT${prediction.confidence_band[0]:.0f}K — NT${prediction.confidence_band[1]:.0f}K",
        f"- **k = {prediction.n_neighbors_used} 近鄰平均** (inverse distance weighted)",
        "",
        "## 🔍 k 個最相似歷史案例",
        "",
        "| Case | 距離 | 工程類型 | 坪數 | 等級 | 工期 | 水電 | 總價 (K NTD) |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for n in prediction.neighbors:
        f = n.features
        lines.append(
            f"| {n.case_id} | {n.distance:.2f} | {f['project_type']} | {f['ping']} 坪 | "
            f"{f['grade']} | {f['duration_weeks']}w | {'✓' if f.get('has_plumbing_rewire') else '✗'} | "
            f"**{n.target:.0f}** |"
        )

    lines.extend([
        "",
        "## 📊 Feature distance contribution",
        "",
        "| 特徵 | 累計距離貢獻 |",
        "|---|---|",
    ])
    sorted_contrib = sorted(prediction.feature_distance_breakdown.items(),
                              key=lambda kv: -kv[1])
    for fname, val in sorted_contrib:
        lines.append(f"| {FEATURE_DESC_ZH.get(fname, fname)} | {val:.3f} |")

    if correlations:
        lines.append("")
        lines.append("## 📈 數值特徵 vs 目標相關性 (Pearson)")
        lines.append("")
        lines.append("| 特徵 | r | 解讀 |")
        lines.append("|---|---|---|")
        for f, r in sorted(correlations.items(), key=lambda kv: -abs(kv[1])):
            interp = "強正" if r > 0.5 else ("中正" if r > 0.2 else ("弱" if r > -0.2 else ("中負" if r > -0.5 else "強負")))
            lines.append(f"| {FEATURE_DESC_ZH.get(f, f)} | {r:.3f} | {interp} |")

    if cat_means:
        lines.append("")
        lines.append("## 📋 各類別目標均值")
        lines.append("")
        for feat, groups in cat_means.items():
            lines.append(f"**{FEATURE_DESC_ZH.get(feat, feat)}**:")
            for cat, mean in sorted(groups.items(), key=lambda kv: kv[1]):
                lines.append(f"  - {cat}: NT${mean:.0f}K")
            lines.append("")

    lines.extend([
        "",
        "## 純函式判讀",
        "",
        f"- **報價合理區間**: NT${prediction.confidence_band[0]:.0f}-{prediction.confidence_band[1]:.0f}K",
        f"- 中位估價 NT${prediction.predicted_value:.0f}K, 業主可以此為談判錨點",
        f"- 多家報價超出 NT${prediction.confidence_band[1] * 1.2:.0f}K = 可疑偏高 (≥ 1.2× CI 上限)",
        f"- 多家報價低於 NT${prediction.confidence_band[0] * 0.7:.0f}K = 可能偷工 (< 0.7× CI 下限)",
        "",
        "## ⚠️ k-NN 模型假設與限制",
        "",
        "- **40 件 prototype 太小**: 真實 launch 需 ≥ 300 件多區域 / 多年份 / 多風格;Pro 版用 weighted recency",
        "- **Feature weights hand-tuned**: project_type 8.0 / grade 4.0 / ping 3.0 是 prototype 設定,Pro 版用 cross-validated grid search",
        "- **不考慮季節 / 物料漲跌**: 2024 vs 2026 報價需通膨調整,真實 launch 加 year-month feature + adjusted target",
        "- **業主隱性需求未納入**: 風格 / 偏好特定品牌 / 趕工 / 老人小孩在家等都未量化",
        "- **不取代專業估價**: 工具給合理區間, 詳細報價需要實地丈量 + 設計圖 + 材料清單",
        "- **k-NN 容易被 outlier 拖累**: 1 件特殊高 / 低價案會偏移預測;Pro 版加 outlier rejection",
        "",
        "---",
        "*constsim = k-NN regression (Cover & Hart 1967) × 台灣中小型裝潢 / 建築工程估價 niche = 從 40 件歷史案找最相似 k 件, 給業主 / 業者 合理區間 + 議價錨點。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, prediction, query, loo_metrics, correlations, cat_means):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, prediction, query, loo_metrics, correlations, cat_means)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, prediction, query, loo_metrics, correlations, cat_means)

    base = render_no_ai(data, prediction, query, loo_metrics, correlations, cat_means)
    similar_summary = "\n".join(
        f"- {n.case_id}: {n.features['project_type']} {n.features['ping']}坪 {n.features['grade']} → NT${n.target:.0f}K (dist {n.distance:.2f})"
        for n in prediction.neighbors[:3]
    )

    prompt = f"""你是一位資深台灣裝潢 / 建築顧問。下面是用 k-NN 純函式分析 40 件歷史案例的結果:

新案: {data['new_query'].get('_meta', '')}
特徵: {query}
k-NN 預測: NT${prediction.predicted_value:.0f}K ± {prediction.predicted_std:.0f}K
合理區間: NT${prediction.confidence_band[0]:.0f}-{prediction.confidence_band[1]:.0f}K
Top 3 相似案例:
{similar_summary}
LOO MAPE: {loo_metrics['mape']:.1f}%

請寫 250-330 字「給業主讀的估價解讀 + 議價腳本 + 防偷工風險」:
1. 一句解讀: NT${prediction.predicted_value:.0f}K 是怎麼來的 (基於相似案例,而不是 abstract 公式)
2. **3 個議價時必問的問題** (例如:水電是用什麼牌子的管 / 防水做幾層 / 拆除清運費另計嗎)
3. **2 個價格 outlier 解讀** (報價 < 區間 = 可能偷什麼工 / 報價 > 區間 = 多收什麼錢)
4. 1 個風險提醒 (例如:口頭報價 vs 書面 / 工期延誤違約金 / 完工驗收清單)

**嚴格規則**:
- 不要重算 NT$ / 區間,引用 facts
- 不要套話 ("加油", "祝順利")
- 不超過 330 字
- 不要 markdown 標題

直接寫業主腳本。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 裝潢顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="constsim — 裝潢 / 建築 k-NN 估價")
    p.add_argument("--data", default="samples/construction_quotes.json")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    cases = [
        TrainingCase(case_id=c["case_id"], features=c["features"], target=c["target_NTD_K"])
        for c in data["training_cases"]
    ]
    specs = auto_scale(cases, DEFAULT_SPECS)
    query = data["new_query"]["features"]

    prediction = knn_predict(query, cases, specs, k=args.k)
    loo_metrics = loo_evaluate(cases, specs, k=args.k)
    correlations = numeric_feature_correlations(cases, specs)
    cat_means = categorical_feature_mean_diff(cases, specs)

    if args.no_ai:
        print(render_no_ai(data, prediction, query, loo_metrics, correlations, cat_means))
    else:
        print(render_with_ai(data, prediction, query, loo_metrics, correlations, cat_means))


if __name__ == "__main__":
    main()
