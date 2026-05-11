"""petskin CLI -- 寵物皮膚問題飼主端 LDA 三 選一鑑別 + 紅旗警示.

Usage:
    python3 petskin.py --data samples/skin_cases.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from lda import (
    fit_lda, predict_one, accuracy, loo_evaluate, confusion_matrix,
    class_centroid_distance,
    LDAModel, LDAPrediction,
)


CLASS_EMOJI = {
    "跳蚤過敏": "🦟",
    "異位性皮膚炎": "🐾",
    "食物過敏": "🍖",
    "黴菌感染": "🍄",
    "細菌性皮膚炎": "🦠",
    "耳疥蟲": "👂",
}

# Mapping from class to: (urgency, owner-action, red flags requiring vet)
CLASS_ADVICE: dict[str, dict[str, str]] = {
    "跳蚤過敏": {
        "urgency": "中等",
        "owner_action": "立刻除蚤 (Frontline / Bravecto / Revolution); 環境清潔換床套; 觀察 7 天",
        "red_flags": "搔抓出血 / 二次細菌感染 / 全身性紅疹 → 就醫",
    },
    "異位性皮膚炎": {
        "urgency": "高 (慢性)",
        "owner_action": "需獸醫處方 (Apoquel / Cytopoint / 免疫療法); 不是短期可解決",
        "red_flags": "**請就醫**: 此症慢性需長期管理, 飼主自行處理通常無效",
    },
    "食物過敏": {
        "urgency": "中等",
        "owner_action": "8 週水解蛋白 / 新蛋白質 elimination diet; 嚴格不給零食點心",
        "red_flags": "腹瀉 / 嘔吐 / 體重下降 → 就醫排除 IBD",
    },
    "黴菌感染": {
        "urgency": "中-高 (人畜共通)",
        "owner_action": "**請就醫**: 需顯微鏡確診 + 抗黴菌口服 / 外用; 隔離其他寵物 + 家人",
        "red_flags": "病灶擴散 / 家人也出疹子 → 立刻就醫 (錢癬人會傳染)",
    },
    "細菌性皮膚炎": {
        "urgency": "高",
        "owner_action": "**請就醫**: 通常需抗生素 + 藥浴 14-28 天; 自行處理會反覆惡化",
        "red_flags": "膿皰 / 異味 / 發燒 / 食慾不振 → 24h 內就醫",
    },
    "耳疥蟲": {
        "urgency": "中等",
        "owner_action": "獸醫處方 Revolution / Advocate; 兩週後複診; 家中其他寵物一起治療",
        "red_flags": "搖頭嚴重 / 耳血腫 / 平衡感異常 → 就醫排除中耳炎",
    },
}


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, model: LDAModel,
                  query: dict, x_query: list[float],
                  pred: LDAPrediction, train_acc: float,
                  loo: dict, cm: dict, mahalanobis: dict) -> str:
    lines = [
        f"# petskin -- {data['clinic_name']} 寵物皮膚 LDA 三 選一鑑別",
        "",
        f"**訓練 case 數**: {model.n_training} 筆 ({model.n_classes} 類)",
        f"**Features**: {len(model.feature_names)} 個 (飼主可觀察)",
        f"**In-sample accuracy**: {train_acc:.1%}",
        f"**LOO cross-validation**: {loo['accuracy']:.1%} ({loo['n_folds']} folds, {loo['n_skipped']} skipped)",
        "",
        "## 🐶 查詢個案",
        "",
        f"_{data['query'].get('_meta', '')}_",
        "",
        "| 觀察項目 | 值 |",
        "|---|---|",
    ]
    for fname, val in zip(model.feature_names, x_query):
        lines.append(f"| {fname} | {val} |")

    sorted_probs = sorted(pred.class_probabilities.items(), key=lambda kv: -kv[1])
    winner = pred.predicted_class
    winner_p = pred.class_probabilities[winner]
    runner_up = sorted_probs[1][0] if len(sorted_probs) > 1 else None

    lines.extend([
        "",
        "## 💡 LDA 鑑別結果",
        "",
        f"### {CLASS_EMOJI.get(winner, '🩺')} **最可能: {winner}** (信心 {winner_p:.1%})",
        "",
    ])

    if winner_p < 0.5:
        lines.append("> ⚠️ **信心度 < 50%** -- 症狀不典型 / 多重併發可能, 強烈建議獸醫鑑別診斷")
    elif runner_up and pred.class_probabilities[runner_up] > 0.25:
        lines.append(f"> ⚠️ **次高 {runner_up} 仍有 {pred.class_probabilities[runner_up]:.1%}** -- 兩種症狀重疊, 建議獸醫二次確認")
    else:
        lines.append("> 信心度足夠, 但 LDA 屬統計分類 **不取代獸醫診斷**")

    lines.extend([
        "",
        "## 📊 各類機率分布",
        "",
        "| 類別 | 機率 | Mahalanobis 距離 | 視覺 |",
        "|---|---|---|---|",
    ])
    for cls, prob in sorted_probs:
        d = mahalanobis.get(cls, 0.0)
        bar = "█" * int(prob * 40)
        marker = "⭐" if cls == winner else "  "
        lines.append(f"| {marker} {CLASS_EMOJI.get(cls, '🩺')} {cls} | {prob:.1%} | {d:.2f} | `{bar}` |")

    advice = CLASS_ADVICE.get(winner, {})
    lines.extend([
        "",
        f"## 🎯 對應建議 ({winner})",
        "",
        f"- **緊急度**: {advice.get('urgency', '請洽獸醫')}",
        f"- **飼主可做**: {advice.get('owner_action', '建議直接就醫')}",
        f"- **必須就醫紅旗**: {advice.get('red_flags', '不確定先諮詢')}",
        "",
        "## 🔍 為什麼是這類 (top 5 features by |相對權重 × 值|)",
        "",
        "| 特徵 | 觀察值 | 相對權重 × 值 |",
        "|---|---|---|",
    ])
    for name, val, contrib in pred.feature_contributions[:5]:
        sign = "+" if contrib > 0 else ""
        lines.append(f"| {name} | {val:.1f} | {sign}{contrib:.3f} |")

    lines.extend([
        "",
        "> **解讀**: 「相對權重」= 該特徵對勝出類的判別力 - 其他類平均判別力. 正值 = 推向勝出類; 負值 = 反對勝出類.",
        "",
        "## 📋 訓練集 confusion matrix",
        "",
        "| true \\ pred | " + " | ".join(model.class_names) + " |",
        "|---|" + "---|" * len(model.class_names),
    ])
    for true_cls in model.class_names:
        row = f"| **{true_cls}** | "
        row += " | ".join(str(cm[true_cls].get(p, 0)) for p in model.class_names)
        row += " |"
        lines.append(row)

    lines.extend([
        "",
        "## ⚠️ LDA 模型假設與限制",
        "",
        "- **常態分布假設**: 每類 features 假設 multivariate Normal 分布;真實有 skewed (搔癢分布偏右), Pro 版用 QDA / Mixture Discriminant",
        "- **共同 covariance 假設**: LDA 假設所有類 covariance 相同;若不同則需 Quadratic Discriminant Analysis (QDA)",
        "- **訓練樣本不大**: prototype 樣本小, real launch 需 ≥ 1,000 件多獸醫師標注 cases",
        "- **特徵主觀**: 搔癢 / 紅腫 / 落毛 分數靠飼主肉眼判斷, 有 ±1-2 分主觀誤差, Pro 版加照片上傳 + vision 自動評估",
        "- **不取代獸醫**: LDA 給「初步分流」是飼主決策輔助 (今天就醫 vs 觀察 24h vs 自行處理), **絕對不是診斷**;任何不確定都建議就醫",
        "- **致命遺漏**: 不能分辨 **皮膚癌 / 自體免疫疾病 / 內分泌異常** (cushing / 甲狀腺低下) 引起的皮膚症狀, 這類嚴重病慢性病需獸醫鑑別",
        "- **緊急紅旗永遠優先**: 發燒 / 食慾不振 / 嗜睡 / 嘔吐 / 全身性紅疹 → 不管 LDA 信心多高, 24h 內就醫",
        "",
        "---",
        "*petskin = Fisher 1936 Linear Discriminant Analysis × 台灣寵物皮膚問題飼主端三 選一鑑別 niche = "
        "從 60+ 件獸醫標注 cases 學習 6 類皮膚病典型 feature pattern, 飼主深夜遇毛孩搔抓拿到「該不該衝急診」客觀建議 (信心 +紅旗), "
        "230 萬犬主 + 90 萬貓主每月 1-2 次焦慮 → AI 飼主端輔助。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, model, query, x_query, pred, train_acc, loo, cm, mahalanobis):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, query, x_query, pred, train_acc, loo, cm, mahalanobis)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, query, x_query, pred, train_acc, loo, cm, mahalanobis)

    base = render_no_ai(data, model, query, x_query, pred, train_acc, loo, cm, mahalanobis)
    sorted_probs = sorted(pred.class_probabilities.items(), key=lambda kv: -kv[1])
    top3 = sorted_probs[:3]
    top3_str = "; ".join(f"{c} {p:.1%}" for c, p in top3)
    top_feats = pred.feature_contributions[:3]
    feat_str = ", ".join(f"{n}={v}→{c:+.2f}" for n, v, c in top_feats)

    prompt = f"""你是台灣資深小動物獸醫師 + 飼主衛教顧問。下面是用 Linear Discriminant Analysis 純函式分析的飼主回報:

{data['query'].get('_meta', '')}
最可能類型: {pred.predicted_class} (信心 {pred.class_probabilities[pred.predicted_class]:.0%})
Top 3: {top3_str}
主要 features: {feat_str}

請寫 250-330 字「給飼主深夜讀的 triage 建議」:
1. 一句解讀 (避免「LDA」「discriminant」「Mahalanobis」這種詞): 為什麼最可能是這類
2. **3 個今晚 / 明天可做的具體 home-care 步驟** (洗澡 / 換床套 / 隔離 / 觀察什麼)
3. **就醫紅旗清單** (出現任一就 24h 內掛號)
4. 1 個不能漏的風險提醒 (e.g. 人畜共通 / 慢性病不能自醫 / 二次感染)

**嚴格規則**:
- 不要重算 % / 信心, 引用 facts
- 不要套話 ("祝您愛犬早日康復")
- 不超過 330 字
- 不要 markdown 標題
- 強調「LDA 不是診斷, 是分流參考」
- 若信心 < 50% 直接建議就醫

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 獸醫師 triage 建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="petskin -- 寵物皮膚 LDA")
    p.add_argument("--data", default="samples/skin_cases.json")
    p.add_argument("--jitter", type=float, default=1e-3)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    cases = data["training_cases"]
    feature_names = data["feature_names"]

    X = [[float(c["features"][f]) for f in feature_names] for c in cases]
    y = [c["label"] for c in cases]

    model = fit_lda(X, y, feature_names, jitter=args.jitter)
    x_query = [float(data["query"]["features"][f]) for f in feature_names]
    pred = predict_one(model, x_query)
    train_acc = accuracy(model, X, y)
    loo = loo_evaluate(X, y, feature_names, jitter=args.jitter)
    cm = confusion_matrix(model, X, y)
    mahalanobis = class_centroid_distance(model, x_query)

    if args.no_ai:
        print(render_no_ai(data, model, data["query"], x_query, pred, train_acc, loo, cm, mahalanobis))
    else:
        print(render_with_ai(data, model, data["query"], x_query, pred, train_acc, loo, cm, mahalanobis))


if __name__ == "__main__":
    main()
