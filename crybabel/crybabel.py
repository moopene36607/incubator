"""crybabel CLI — 嬰幼兒哭聲 Random Forest 分類 + 安撫建議。

Usage:
    python crybabel.py --events samples/cry_events.json --no-ai
    python crybabel.py --events samples/cry_events.json --trees 100
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rf import (
    fit_forest, predict_one, RandomForest, Prediction,
    accuracy, feature_importance_simple, class_distribution,
)


def load_events(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


CLASS_LABELS_ZH = {
    "hungry": "🍼 餓了",
    "tired": "😴 累了 / 想睡",
    "discomfort": "😣 不舒服 (衣物 / 溫度)",
    "pain": "😖 疼痛",
    "colic": "💢 腸絞痛 (colic)",
    "overstimulation": "😵 過度刺激",
    "wet_diaper": "💧 尿布濕 / 髒",
}

CLASS_ACTIONS_ZH = {
    "hungry": "立刻準備餵奶 (上次餵奶已過 90 分以上). 若 < 60 分剛餵過,改試吸吮 / 安撫奶嘴 安全感需求.",
    "tired": "降低環境刺激 (拉窗簾 / 關電視 / 白噪音), 包巾 + 輕拍睡。哭睡前一短陣是正常.",
    "discomfort": "檢查衣服標籤刮 / 領口太緊 / 室溫 (26°C±2)。剝層衣物 30 秒看哭聲變化.",
    "pain": "**馬上身體掃描** — 手指 / 腳趾頭髮絲纏繞 / 紙尿布太緊 / 蚊子叮 / 跌倒徵兆. 若 5 分內無解 + 拒絕安撫,**就醫考慮**.",
    "colic": "**典型黃昏腸絞痛** (3-3-3 規則:每天 3 hr+, 每週 3 天+, 持續 3 週+)。試 5S (Swaddle / Side-stomach 位 / Shush / Swing / Suck).",
    "overstimulation": "**馬上把寶寶帶到安靜暗房**。30-60 秒包巾 + 輕拍, 不要再玩 / 講話 / 給玩具.",
    "wet_diaper": "立刻換尿布 + 屁屁霜薄塗。檢查是否紅屁屁 / 尿布疹徵兆.",
}

CLASS_MEDICAL_RED_FLAGS = {
    "pain": "若 + 發燒 38°C+ / 嘔吐 / 一直高頻尖叫 30+ 分鐘 → 急診",
    "colic": "若 + 血便 / 嘔吐墨綠色 / 體重停滯 → 看小兒科",
    "discomfort": "若 + 紅疹 / 腫脹 / 反覆抓癢 → 看小兒科",
}


def render_no_ai(data: dict, forest: RandomForest, training_accuracy: float,
                  feat_importance: dict[str, float],
                  test_features: dict, test_meta: dict,
                  prediction: Prediction) -> str:
    lines = [
        f"# crybabel — {test_meta.get('infant_name', '寶寶')} 哭聲 Random Forest 分類",
        "",
        f"**年齡**: {test_meta.get('infant_age_months', 'N/A')} 個月",
        f"**模型訓練**: {len(data['training_samples'])} samples × {len(data['classes'])} 類 × {forest.n_trees} 棵樹",
        f"**Training accuracy**: {training_accuracy:.1%} (in-sample)",
        f"**Max depth**: {forest.max_depth}, **Max features/split**: {forest.max_features}",
        "",
        "## 哭聲與情境特徵",
        "",
        "| 特徵 | 值 | 直覺意義 |",
        "|---|---|---|",
        f"| 主頻率 (Hz) | {test_features['pitch_mean_hz']:.0f} | {'高頻 (痛 / colic 嫌疑)' if test_features['pitch_mean_hz'] > 650 else '中頻 (常見)' if test_features['pitch_mean_hz'] > 450 else '低頻 (餓 / 尿布)'} |",
        f"| 持續時間 (秒) | {test_features['duration_s']:.0f} | {'長 (>90 秒)' if test_features['duration_s'] > 90 else '中 (30-90 秒)' if test_features['duration_s'] > 30 else '短 (<30 秒)'} |",
        f"| 規律性 0-1 | {test_features['rhythm_regularity']:.2f} | {'極不規律 (爆發型)' if test_features['rhythm_regularity'] < 0.3 else '中度' if test_features['rhythm_regularity'] < 0.6 else '規律 (節奏型)'} |",
        f"| 強度趨勢 -1~+1 | {test_features['intensity_slope']:+.2f} | {'快速升強 (急迫)' if test_features['intensity_slope'] > 0.3 else '平緩' if test_features['intensity_slope'] > -0.3 else '漸弱'} |",
        f"| 距上次餵奶 (分) | {test_features['time_since_feed_min']:.0f} | {'飢餓區 >90 分' if test_features['time_since_feed_min'] > 90 else '剛餵過 <60 分' if test_features['time_since_feed_min'] < 60 else '中段'} |",
        f"| 距上次尿布 (分) | {test_features['time_since_diaper_min']:.0f} | {'可能濕布 >90 分' if test_features['time_since_diaper_min'] > 90 else '剛換 <30 分' if test_features['time_since_diaper_min'] < 30 else '中段'} |",
        f"| 距上次小睡 (分) | {test_features['time_since_nap_min']:.0f} | {'累積疲憊 >120 分' if test_features['time_since_nap_min'] > 120 else '剛睡醒 <30 分' if test_features['time_since_nap_min'] < 30 else '中段'} |",
        "",
        "## 🎯 Random Forest 分類結果",
        "",
        f"### {CLASS_LABELS_ZH.get(prediction.predicted_class, prediction.predicted_class)}",
        "",
        f"- **預測類別**: `{prediction.predicted_class}`",
        f"- **信心度 (vote share)**: **{prediction.confidence:.1%}** ({int(prediction.confidence * forest.n_trees)}/{forest.n_trees} 棵樹投這類)",
        "",
        "## 各類別投票分布",
        "",
        "| 類別 | 投票機率 | 標籤 |",
        "|---|---|---|",
    ]
    sorted_probs = sorted(prediction.class_probabilities.items(), key=lambda kv: -kv[1])
    for cls, prob in sorted_probs:
        marker = "⭐" if cls == prediction.predicted_class else " "
        bar = "█" * int(prob * 30)
        lines.append(f"| {marker} {CLASS_LABELS_ZH.get(cls, cls)} | {prob:.1%} | `{bar}` |")

    lines.extend([
        "",
        "## 純函式判讀: 推薦動作",
        "",
        f"**對 `{prediction.predicted_class}` 的標準建議**:",
        "",
        f"- {CLASS_ACTIONS_ZH.get(prediction.predicted_class, '請諮詢專業育兒顧問.')}",
    ])

    red_flag = CLASS_MEDICAL_RED_FLAGS.get(prediction.predicted_class)
    if red_flag:
        lines.append("")
        lines.append(f"⚠️ **就醫紅旗**: {red_flag}")

    lines.extend([
        "",
        "## Feature importance (整 forest)",
        "",
        "| 特徵 | 重要度 (normalized) | 視覺 |",
        "|---|---|---|",
    ])
    for f, v in feat_importance.items():
        bar = "█" * int(v * 50)
        lines.append(f"| `{f}` | {v:.3f} | `{bar}` |")

    lines.extend([
        "",
        "## ⚠️ Random Forest 模型假設與限制",
        "",
        "- **訓練資料 simulated**: prototype 用合成 features 訓練, 真實 launch 需要兒科 / 月子中心 標註資料 ≥ 1000 件",
        "- **哭聲特徵需要 audio extract**: prototype 用數值輸入, 真實 app 需要錄音 → MFCC 特徵抽取 (用 librosa 或 Claude audio API)",
        "- **多類別不平衡**: colic 比 hungry 少見;Pro 版用 SMOTE / weighted classes",
        "- **個別寶寶差異**: 「我家寶寶哭聲」可能 baseline 偏離訓練集;Pro 版加 per-baby calibration",
        "- **不取代醫師判斷**: AI 給的是 likely 類別,**痛 / 異常哭聲**永遠優先看小兒科",
        "- **新手父母 anxiety**: 用工具可能 anchor 在某類別反而忽略其他可能;UI 上要強調「3 個動作試試 + 不見效就重新評估」",
        "",
        "---",
        "*crybabel = Breiman 2001 Random Forest × 台灣繁中嬰幼兒哭聲 niche = 把 ChatterBaby 帶進中文母嬰市場。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, forest, training_accuracy, feat_importance,
                    test_features, test_meta, prediction):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, forest, training_accuracy, feat_importance,
                              test_features, test_meta, prediction)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, forest, training_accuracy, feat_importance,
                              test_features, test_meta, prediction)

    base = render_no_ai(data, forest, training_accuracy, feat_importance,
                          test_features, test_meta, prediction)
    history = test_meta.get("baby_history", {})

    prompt = f"""你是一位有 20 年新生兒護理師經驗的育兒顧問。下面是用 Random Forest 純函式分類算出的結果(數字 100% 算好, 不能改):

寶寶: {test_meta.get('infant_name')} {test_meta.get('infant_age_months')} 月
哭聲特徵: 主頻 {test_features['pitch_mean_hz']:.0f} Hz / 持續 {test_features['duration_s']:.0f} 秒 / 規律性 {test_features['rhythm_regularity']:.2f} / 強度 {test_features['intensity_slope']:+.2f}
情境: 距上次餵奶 {test_features['time_since_feed_min']:.0f} 分 / 尿布 {test_features['time_since_diaper_min']:.0f} 分 / 小睡 {test_features['time_since_nap_min']:.0f} 分
媽媽補充: {history.get('fed_well_today')} 今天吃得好 / {history.get('no_fever_no_vomit')} 無發燒嘔吐

RF 預測: {prediction.predicted_class} (信心 {prediction.confidence:.1%})
Top 3 機率: {sorted(prediction.class_probabilities.items(), key=lambda x: -x[1])[:3]}

請寫 220-300 字「給新手父母讀的具體安撫腳本」:
1. 一句翻譯結果 (不要用「Random Forest」「probability」這種詞)
2. **3 個立即可做的動作** (順序: 30 秒內試 → 2 分內試 → 5 分內試)
3. **就醫紅旗**: 出現什麼 signs 就要送醫 (具體 — 體溫 / 顏色 / 行為)
4. 1 個情緒安撫: 給焦慮新手父母的一句話 (不要套話「加油」)

**嚴格規則**:
- 不要重算 confidence / probabilities
- 不要套話 ("祝順利", "辛苦了")
- 不超過 300 字
- 不要 markdown 標題

直接寫安撫腳本。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 育兒顧問安撫腳本\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="crybabel — 嬰幼兒哭聲 RF 分類")
    p.add_argument("--events", default="samples/cry_events.json")
    p.add_argument("--trees", type=int, default=80)
    p.add_argument("--max-depth", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_events(Path(args.events))
    X_train = [s["features"] for s in data["training_samples"]]
    y_train = [s["label"] for s in data["training_samples"]]

    feature_names = list(X_train[0].keys())

    forest = fit_forest(
        X_train, y_train, features=feature_names,
        n_trees=args.trees, max_depth=args.max_depth,
        max_features=int(len(feature_names) ** 0.5),
        seed=args.seed,
    )
    # In-sample accuracy
    from rf import predict
    train_preds = predict(forest, X_train)
    acc = accuracy(train_preds, y_train)
    feat_imp = feature_importance_simple(forest, X_train, y_train)

    test_event = data["test_event"]
    pred = predict_one(forest, test_event["cry_features"])

    if args.no_ai:
        print(render_no_ai(data, forest, acc, feat_imp,
                             test_event["cry_features"], test_event, pred))
    else:
        print(render_with_ai(data, forest, acc, feat_imp,
                               test_event["cry_features"], test_event, pred))


if __name__ == "__main__":
    main()
