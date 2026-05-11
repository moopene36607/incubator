"""cleanmate CLI — 家政服務客戶需求 Naive Bayes 阿姨類型推薦。

Usage:
    python cleanmate.py --data samples/cleaner_marketplace.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from naive_bayes import (
    TrainingExample, fit_naive_bayes, predict_one, accuracy,
    loo_evaluate, confusion_matrix, class_distinctive_features,
    NaiveBayesModel, PredictionResult,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


FEATURE_DESC_ZH = {
    "household": "家庭規模",
    "pet": "寵物",
    "elderly": "老人狀況",
    "kids": "幼童狀況",
    "focus": "清潔重點",
    "time": "服務時段",
    "budget": "預算範圍",
    "season": "季節需求",
}


def render_no_ai(data: dict, model: NaiveBayesModel,
                  request: dict, prediction: PredictionResult,
                  train_acc: float, loo_metrics: dict,
                  distinctive_per_class: dict) -> str:
    lines = [
        f"# cleanmate — 家政服務 Naive Bayes 阿姨類型推薦",
        "",
        f"**訓練 pairings**: {model.n_training} 件歷史成功配對",
        f"**Specialty 類別**: {len(model.classes)} 類",
        f"**In-sample accuracy**: {train_acc:.1%}",
        f"**LOO cross-validation**: {loo_metrics['accuracy']:.1%} ({loo_metrics['n_folds']} folds)",
        f"**Laplace smoothing α**: {model.smoothing_alpha}",
        "",
        "## 🎯 客戶需求",
        "",
        f"_{data['new_request'].get('_meta', '')}_",
        "",
        "| 特徵 | 值 |",
        "|---|---|",
    ]
    for fname in model.feature_names:
        val = request.get(fname, "未填")
        lines.append(f"| {FEATURE_DESC_ZH.get(fname, fname)} | {val} |")

    lines.extend([
        "",
        "## 💡 推薦 阿姨 Specialty",
        "",
        f"### {prediction.predicted_class}",
        "",
        "## 各 specialty 機率分布",
        "",
        "| Specialty | 機率 | 視覺 |",
        "|---|---|---|",
    ])
    sorted_probs = sorted(prediction.class_probabilities.items(), key=lambda kv: -kv[1])
    for cls, prob in sorted_probs:
        bar = "█" * int(prob * 40)
        marker = "⭐" if cls == prediction.predicted_class else "  "
        lines.append(f"| {marker} {cls} | {prob:.1%} | `{bar}` |")

    lines.append("")
    lines.append("## 🔍 為什麼推薦這類 (Top 5 contributing features)")
    lines.append("")
    lines.append("| 特徵 | 值 | log P(feature\\|class) |")
    lines.append("|---|---|---|")
    for f, v, ll in prediction.top_contributing_features:
        lines.append(f"| {FEATURE_DESC_ZH.get(f, f)} | {v} | {ll:.3f} |")

    lines.append("")
    lines.append(f"## 📊 各 specialty 區別性特徵 (top 3)")
    lines.append("")
    for cls in sorted(model.classes):
        lines.append(f"### {cls}")
        lines.append("")
        feats = distinctive_per_class.get(cls, [])
        for f, v, d in feats[:3]:
            lines.append(f"- `{FEATURE_DESC_ZH.get(f, f)} = {v}`: 區別力 +{d:.2f}")
        lines.append("")

    lines.append("## ⚠️ Naive Bayes 模型假設與限制")
    lines.append("")
    lines.append("- **獨立性假設**: P(features | class) = Π P(feature_i | class) — 假設各特徵獨立, 真實有相關 (e.g., 老人 + 嬰兒共存); Pro 版用 TAN (Tree-Augmented NB)")
    lines.append("- **Laplace 平滑 α = 1.0**: 對 unseen feature value 給最小概率, 但仍可能 over-smooth")
    lines.append("- **訓練樣本 100 件不足**: 真實 launch 需 ≥ 500 件多樣 pairing")
    lines.append("- **類別不平衡**: 老人照顧 friendly 只 4 件 → 信心區間寬, 容易誤判;Pro 版加 class weight 補正")
    lines.append("- **不取代實地評估**: 推薦 specialty 是初步分類, 具體阿姨還需老闆 / 平台二次媒合")
    lines.append("- **隱私敏感**: 客戶家庭資料 (老人 / 嬰兒 / 寵物) 涉個資, 雲端版需加密 + 客戶同意 + 資料留存政策")
    lines.append("")
    lines.append("---")
    lines.append("*cleanmate = Multinomial Naive Bayes (Bayes 1763) × 台灣家政服務 客戶需求分類 niche = 100 件歷史 pairing → 客戶需求自動推薦 specialty type, 平台分派更精準, 退服率 30% → 10%。*")
    return "\n".join(lines)


def render_with_ai(data, model, request, prediction, train_acc, loo_metrics, distinctive_per_class):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, request, prediction, train_acc, loo_metrics, distinctive_per_class)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, request, prediction, train_acc, loo_metrics, distinctive_per_class)

    base = render_no_ai(data, model, request, prediction, train_acc, loo_metrics, distinctive_per_class)

    top_probs = sorted(prediction.class_probabilities.items(), key=lambda kv: -kv[1])[:3]
    top_str = ", ".join(f"{c} {p:.0%}" for c, p in top_probs)
    top_feats_str = ", ".join(f"{FEATURE_DESC_ZH.get(f, f)}={v}" for f, v, _ in prediction.top_contributing_features[:3])

    prompt = f"""你是一位資深台灣家政平台運營顧問 (Hello 阿姨 / 居家清潔 / 蘭舍規模)。下面是用 Naive Bayes 純函式分析的結果:

客戶: {data['new_request'].get('_meta', '')}
推薦 specialty: {prediction.predicted_class}
Top 3 機率: {top_str}
主要 features 影響: {top_feats_str}
LOO accuracy: {loo_metrics['accuracy']:.1%}

請寫 250-330 字「給家政平台運營 / 阿姨派遣窗口讀的指派建議 + 客戶溝通腳本」:
1. 一句解讀 (避免「Naive Bayes」「log-likelihood」這種詞): 為什麼推這 specialty
2. **3 個分派 SOP 細節** (找哪種阿姨 / 約面試前該問什麼 / 服務當天必確認)
3. **客戶溝通腳本** (LINE 一段話告訴客戶為什麼派這位 + 期待管理)
4. 1 個風險提醒 (e.g., 阿姨可能臨時請假需 backup / 安全 / 過敏 / 客戶期望管理)

**嚴格規則**:
- 不要重算 % / 機率, 引用 facts
- 不要套話 ("加油")
- 不超過 330 字
- 不要 markdown 標題

直接寫指派建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 家政平台運營建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="cleanmate — 家政服務 Naive Bayes")
    p.add_argument("--data", default="samples/cleaner_marketplace.json")
    p.add_argument("--alpha", type=float, default=1.0)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    feature_names = data["feature_names"]

    examples = [
        TrainingExample(features=p["features"], label=p["label"])
        for p in data["training_pairings"]
    ]

    model = fit_naive_bayes(examples, feature_names, smoothing_alpha=args.alpha)
    request = data["new_request"]["features"]
    prediction = predict_one(model, request)
    train_acc = accuracy(model, examples)
    loo_metrics = loo_evaluate(examples, feature_names, args.alpha)
    distinctive_per_class = {
        c: class_distinctive_features(model, c, top_n=5) for c in model.classes
    }

    if args.no_ai:
        print(render_no_ai(data, model, request, prediction, train_acc, loo_metrics, distinctive_per_class))
    else:
        print(render_with_ai(data, model, request, prediction, train_acc, loo_metrics, distinctive_per_class))


if __name__ == "__main__":
    main()
