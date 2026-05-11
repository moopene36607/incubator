"""clinicqueue CLI — 自費診所預約 no-show 預測 GBDT。

Usage:
    python clinicqueue.py --data samples/clinic_appointments.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from gbdt import (
    fit_gbdt, predict_proba, predict_all, accuracy, log_loss,
    auc_roc_approx, feature_importance_gain, GBDTModel,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


FEATURE_DESC_ZH = {
    "patient_age": "年齡",
    "days_since_last_visit": "上次來訪距今 (天)",
    "booking_lead_time_days": "預約提前天數",
    "prev_no_show_count": "歷史失約次數",
    "prev_visit_count": "歷史就診次數",
    "appointment_hour": "預約時段 (時)",
    "weekday": "預約週幾",
    "is_winter": "冬季 (1=是)",
    "is_aesthetic": "服務類型 (1=醫美 / 0=其他)",
    "is_self_pay": "自費 (1=是)",
    "weather_rain_prob": "預約日降雨機率",
}


def severity_label(p: float) -> str:
    if p >= 0.60:
        return "🔴 高風險"
    if p >= 0.40:
        return "🟠 中高"
    if p >= 0.25:
        return "🟡 中"
    return "🟢 低"


def action_label(p: float) -> str:
    if p >= 0.60:
        return "雙重預約 + LINE 提前 24h 確認 + 預收訂金"
    if p >= 0.40:
        return "前一天 LINE 提醒 + 候補名單備用"
    if p >= 0.25:
        return "前一天簡訊提醒"
    return "標準流程"


def render_no_ai(data: dict, model: GBDTModel,
                  historical: list[dict], upcoming: list[dict],
                  train_metrics: dict, predictions: list) -> str:
    feature_names = data["feature_names"]
    n_hist = len(historical)
    historical_no_show_rate = sum(h["no_show"] for h in historical) / n_hist

    fi = feature_importance_gain(model)

    lines = [
        f"# clinicqueue — {data['clinic_name']} 預約 No-Show 預測 (GBDT)",
        "",
        f"**歷史 appointments**: {n_hist} (no-show rate {historical_no_show_rate:.1%})",
        f"**Upcoming**: {len(upcoming)} 個待預測",
        f"**Model**: GBDT {model.n_trees} trees × max_depth {model.max_depth} × lr {model.learning_rate}",
        "",
        "## 🎯 模型表現 (in-sample, train 200 件)",
        "",
        f"- **Accuracy**: {train_metrics['accuracy']:.1%}",
        f"- **Log-loss**: {train_metrics['log_loss']:.4f}",
        f"- **AUC**: {train_metrics['auc']:.3f} ({'excellent' if train_metrics['auc'] > 0.85 else 'good' if train_metrics['auc'] > 0.75 else 'fair'})",
        "",
        "## 📊 Feature importance (按 gain 加權貢獻)",
        "",
        "| 特徵 | 貢獻度 | 視覺 |",
        "|---|---|---|",
    ]
    for f, v in fi.items():
        bar = "█" * int(v * 60)
        lines.append(f"| {FEATURE_DESC_ZH.get(f, f)} | {v:.3f} | `{bar}` |")

    lines.extend([
        "",
        f"## 🔮 未來 {len(upcoming)} 個 appointment no-show 機率預測",
        "",
        "| Appt ID | 年齡 | 失約史 | 預約提前 (天) | 時段 | 雨機率 | P(no-show) | 風險 | 建議動作 |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    # Sort upcoming by P(no-show) desc for prioritization
    sorted_pairs = sorted(zip(upcoming, predictions), key=lambda kv: -kv[1].probability)
    for app, pred in sorted_pairs:
        f = app["features"]
        lines.append(
            f"| {app['appointment_id']} | {f['patient_age']} | {f['prev_no_show_count']}x "
            f"| {f['booking_lead_time_days']}d | {f['appointment_hour']}:00 "
            f"| {f['weather_rain_prob']:.0%} | **{pred.probability:.1%}** | "
            f"{severity_label(pred.probability)} | {action_label(pred.probability)} |"
        )

    high_risk = [p for p in predictions if p.probability >= 0.4]
    expected_no_shows = sum(p.probability for p in predictions)
    lines.extend([
        "",
        "## 📈 群體預測總覽",
        "",
        f"- **預期 no-show 數**: {expected_no_shows:.1f} / {len(upcoming)} ({expected_no_shows / len(upcoming):.1%})",
        f"- **高 / 中高風險 (P ≥ 40%)**: {len(high_risk)} 個",
        f"- **低風險 (P < 25%)**: {sum(1 for p in predictions if p.probability < 0.25)} 個",
        "",
        "## 純函式判讀",
        "",
    ])
    top_feat = list(fi.keys())[0] if fi else ""
    lines.append(f"- **最關鍵 driver**: `{FEATURE_DESC_ZH.get(top_feat, top_feat)}` (貢獻 {fi.get(top_feat, 0):.0%})")
    lines.append(f"  - 這診所的 no-show 主要決定於這個特徵, 改善這方面可以最有效降低 no-show")
    lines.append("")
    lines.append("- **行動建議優先順序**:")
    lines.append("  - 🔴 高風險 (P ≥ 60%): 雙重預約 + 預收訂金 + 24h 前 LINE 個人化確認")
    lines.append("  - 🟠 中高 (P 40-60%): 前一天 LINE 提醒 + 預備候補名單 1-2 人")
    lines.append("  - 🟡 中 (P 25-40%): 前一天 SMS 提醒")
    lines.append("  - 🟢 低 (P < 25%): 標準流程")
    lines.append("")
    lines.append("## ⚠️ GBDT 模型假設與限制")
    lines.append("")
    lines.append("- **In-sample accuracy 高 = overfit 風險**: 真實 launch 必須 train/test split + cross-validation")
    lines.append("- **歷史只 200 件不足**: 鼓勵診所累積 ≥ 500 件才正式上線預測;Pro 版加 transfer learning")
    lines.append("- **季節 / 節日 / 特殊事件未納入**: 連假前後 / 颱風天 / 流感季節等 systematic 因素需另外處理")
    lines.append("- **GBDT 容易 overfit on noise**: max_depth=3 + learning_rate=0.1 + 50 trees 是 conservative, 可降低過擬合")
    lines.append("- **GBDT 不解釋為何**: feature_importance 給總體 driver, 個別 case 為何高需要 SHAP / TreeSHAP (Pro 版)")
    lines.append("- **隱私敏感**: 病患就診紀錄涉個資 + 醫療性質, 雲端版需加密 + 院方同意 + 資料去識別化")
    lines.append("")
    lines.append("---")
    lines.append("*clinicqueue = Friedman 2001 Gradient Boosting Decision Trees × 台灣自費診所預約 no-show niche = 從 200 件歷史學會 no-show 模式, 對未來 20 個 appt 標出高風險, 雙重預約策略 + 個人化提醒。*")
    return "\n".join(lines)


def render_with_ai(data, model, historical, upcoming, train_metrics, predictions):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, historical, upcoming, train_metrics, predictions)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, historical, upcoming, train_metrics, predictions)

    base = render_no_ai(data, model, historical, upcoming, train_metrics, predictions)
    fi = feature_importance_gain(model)
    expected_no_shows = sum(p.probability for p in predictions)
    high_risk = sum(1 for p in predictions if p.probability >= 0.4)

    prompt = f"""你是一位資深醫療管理顧問,專精台灣自費診所運營 (醫美 / 牙科 / 中醫)。下面是用 Gradient Boosting Decision Trees 純函式分析的預測結果:

診所: {data['clinic_name']}
歷史 200 件 no-show rate: {sum(h['no_show'] for h in historical) / 200:.1%}
模型: 50 trees, max_depth 3, AUC {train_metrics['auc']:.3f}, accuracy {train_metrics['accuracy']:.1%}
Top 3 features: {list(fi.items())[:3]}
未來 20 個 appt 預期 no-show: {expected_no_shows:.1f} 件, 高/中高風險 (P ≥ 40%): {high_risk} 件

請寫 250-330 字「給診所經理 / 醫師讀的運營建議」:
1. 一句解讀: top feature driver 給的關鍵 insight (避免「GBDT」「gain」這種詞)
2. **3 個立即可做的流程改造** (例如:預約系統加問句 / LINE 機器人腳本 / 候補名單 SOP)
3. **本週 20 個 appt 具體行動分配** (高 / 中 / 低 風險各幾個, 各該怎麼處理)
4. 1 個風險: 訂金政策 / 過度提醒 / 法律 / 隱私 (具體一個)

**嚴格規則**:
- 不要重算 P / %, 引用 facts
- 不要套話 ("加油")
- 不超過 330 字
- 不要 markdown 標題

直接寫運營建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 醫療管理顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="clinicqueue — 預約 no-show 預測 GBDT")
    p.add_argument("--data", default="samples/clinic_appointments.json")
    p.add_argument("--trees", type=int, default=50)
    p.add_argument("--max-depth", type=int, default=3)
    p.add_argument("--lr", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    feature_names = data["feature_names"]
    historical = data["historical_appointments"]
    upcoming = data["upcoming_appointments"]

    X_train = [h["features"] for h in historical]
    y_train = [h["no_show"] for h in historical]

    model = fit_gbdt(X_train, y_train, features=feature_names,
                      n_trees=args.trees, max_depth=args.max_depth,
                      learning_rate=args.lr, seed=args.seed)

    # In-sample metrics
    train_probs = [predict_proba(model, x).probability for x in X_train]
    train_metrics = {
        "accuracy": accuracy(y_train, train_probs),
        "log_loss": log_loss(y_train, train_probs),
        "auc": auc_roc_approx(y_train, train_probs),
    }

    X_upcoming = [a["features"] for a in upcoming]
    predictions = predict_all(model, X_upcoming)

    if args.no_ai:
        print(render_no_ai(data, model, historical, upcoming, train_metrics, predictions))
    else:
        print(render_with_ai(data, model, historical, upcoming, train_metrics, predictions))


if __name__ == "__main__":
    main()
