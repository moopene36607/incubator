"""cramlead CLI — 補習班招生 lead conversion 預測 Logistic Regression。

Usage:
    python cramlead.py --data samples/cram_leads.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from logreg import (
    FeatureEncoder, fit_logreg, predict_proba, predict_all,
    accuracy_score, log_loss_score, auc_roc_approx,
    coefficient_summary, LogRegModel, LogRegPrediction,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


FEATURE_DESC_ZH = {
    "grade": "年級",
    "distance_km": "距離 (km)",
    "referral": "推薦來源",
    "tried_subject": "試聽科目",
    "parent_education": "家長教育",
    "prev_cram_experience": "前補習經驗",
    "contact_method": "接觸管道",
    "days_since_last_contact": "上次聯絡 (天)",
    "attended_trial": "已試聽",
}


def severity_action(p: float) -> tuple[str, str]:
    if p >= 0.70:
        return ("🟢 高機率", "今天就打 + 推方案 + 個別老師導覽")
    if p >= 0.50:
        return ("🟡 中高", "明天 LINE follow-up + 寄試聽優惠券")
    if p >= 0.30:
        return ("🟠 中", "一週內 SMS 提醒 + 一般 follow-up")
    return ("🔴 低", "標準 nurture 流程 (月 1 次)")


def render_no_ai(data: dict, model: LogRegModel,
                  historical: list[dict], upcoming: list[dict],
                  train_metrics: dict, predictions: list[LogRegPrediction]) -> str:
    coefs = coefficient_summary(model)
    enroll_rate = sum(h["enrolled"] for h in historical) / len(historical)

    lines = [
        f"# cramlead — {data['cram_school_name']} 招生 Lead Logistic Regression",
        "",
        f"**歷史 leads**: {len(historical)} 件 (報名率 {enroll_rate:.1%})",
        f"**Upcoming**: {len(upcoming)} 個 leads 待 score",
        f"**Model**: Logistic Regression L2 λ={model.l2_lambda}, lr={model.learning_rate}",
        f"**訓練收斂**: {model.n_iterations_used} iterations ({'converged' if model.converged else 'max iter reached'})",
        "",
        "## 🎯 模型表現",
        "",
        f"- **In-sample accuracy**: {train_metrics['accuracy']:.1%}",
        f"- **Log-loss**: {train_metrics['log_loss']:.4f}",
        f"- **AUC-ROC**: {train_metrics['auc']:.3f} ({'excellent' if train_metrics['auc'] > 0.85 else 'good' if train_metrics['auc'] > 0.75 else 'fair'})",
        f"- **Intercept (b)**: {model.intercept:.3f} (baseline logit)",
        "",
        "## 📊 係數解釋 (β + odds ratio + 方向)",
        "",
        "| 特徵 (one-hot) | β | odds_ratio | 方向 |",
        "|---|---|---|---|",
    ]
    for name, beta, odds, dir_ in coefs[:12]:
        lines.append(f"| {name} | {beta:+.3f} | ×{odds:.2f} | {dir_} |")

    lines.extend([
        "",
        "> **odds ratio 解讀**: > 1 = 該 feature 使報名 odds 增加,< 1 = 降低。例如 odds=2.0 = 該 feature 出現時報名 odds 提升 2 倍。",
        "",
        f"## 🔮 未來 {len(upcoming)} 個 lead 報名機率預測",
        "",
        "| Lead | 年級 | 試聽 | 推薦 | 距離 | 試聽過 | 上次聯絡 | P(報名) | 風險 | 建議動作 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    # Sort by P(enroll) descending for triage
    sorted_pairs = sorted(zip(upcoming, predictions), key=lambda kv: -kv[1].probability)
    for lead, pred in sorted_pairs:
        f = lead["features"]
        severity, action = severity_action(pred.probability)
        lines.append(
            f"| {lead['lead_id']} | {f['grade']} | {f['tried_subject']} | "
            f"{f['referral']} | {f['distance_km']}km | "
            f"{'✓' if f['attended_trial'] else '✗'} | "
            f"{f['days_since_last_contact']}d | **{pred.probability:.1%}** | "
            f"{severity} | {action} |"
        )

    high_count = sum(1 for p in predictions if p.probability >= 0.7)
    med_count = sum(1 for p in predictions if 0.5 <= p.probability < 0.7)
    expected = sum(p.probability for p in predictions)
    lines.extend([
        "",
        "## 📈 群體預測總覽",
        "",
        f"- **預期報名數**: {expected:.1f} / {len(upcoming)} ({expected / len(upcoming):.1%})",
        f"- **高機率 (≥ 70%)**: {high_count} 個 — 今天就要 outreach",
        f"- **中高 (50-70%)**: {med_count} 個 — 一週內 follow-up",
        "",
        "## 🔍 Top 例: 高機率 lead 為何被預測",
        "",
    ])

    # Pick top-3 high prob predictions for explanation
    top_preds = sorted_pairs[:3]
    for i, (lead, pred) in enumerate(top_preds):
        lines.append(f"### #{i + 1} {lead['lead_id']} (P = {pred.probability:.1%}, logit = {pred.logit:.2f})")
        lines.append("")
        lines.append("Top contributing features (β × value):")
        for name, val, contrib in pred.feature_contributions[:5]:
            sign = "+" if contrib > 0 else ""
            lines.append(f"  - `{name}` = {val} → {sign}{contrib:.3f}")
        lines.append("")

    lines.extend([
        "## ⚠️ Logistic Regression 模型假設與限制",
        "",
        "- **線性假設**: P(報名) 通過 logit 跟 features 線性,真實有 nonlinear 交互 (e.g. 年級 × 距離) — Pro 版加交互項",
        "- **180 件樣本不大**: 真實 launch 需 ≥ 500 件多季 / 多年資料訓練, 避免 overfit",
        "- **L2 正則化 λ=0.01 是 mild**: 過大 → underfit, 過小 → overfit;Pro 版用 cross-validation 自動選 λ",
        "- **In-sample accuracy 高 ≠ 真實預測力**: 需 train/test split + temporal validation (用 t-1 季訓練, 預測 t 季)",
        "- **季節性未捕捉**: 暑假前 vs 開學後 conversion 差異, Pro 版加 month/seasonality 特徵",
        "- **隱私敏感**: lead 資料涉個資, 雲端版需加密 + 客戶同意 + 資料留存政策",
        "",
        "---",
        "*cramlead = Logistic Regression with L2 regularization × 台灣補習班招生季 lead conversion niche = 從 180 件歷史學報名模式, 對未來 15 leads 標 P(報名), 老闆 / 櫃台優先 outreach 高機率 lead, conversion 從 30% → 50%。*",
    ])
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

    coefs = coefficient_summary(model)
    top_positive = [c for c in coefs if c[1] > 0][:3]
    top_negative = [c for c in coefs if c[1] < 0][:3]
    expected_enrollment = sum(p.probability for p in predictions)
    high_count = sum(1 for p in predictions if p.probability >= 0.7)

    prompt = f"""你是一位資深台灣補教業 招生主任。下面是用 Logistic Regression 純函式分析 180 件歷史 leads 結果:

補習班: {data['cram_school_name']}
歷史報名率: {sum(h['enrolled'] for h in historical) / 180 * 100:.0f}%
模型 AUC: {train_metrics['auc']:.3f}, accuracy {train_metrics['accuracy']:.1%}
Top 3 正向係數: {top_positive}
Top 3 負向係數: {top_negative}
未來 15 leads 預期報名: {expected_enrollment:.1f} 件, 高機率 (≥ 70%) {high_count} 個

請寫 250-330 字「給招生主任 / 櫃台的 outreach 策略」:
1. 一句解讀: Top features 給的關鍵 insight (避免「Logistic Regression」「odds ratio」這種詞)
2. **3 個 outreach 流程改造** (例如:推薦獎勵金 / 試聽日 SOP / 距離篩選)
3. **本週 15 個 lead 行動分配** (高 / 中 / 低 各幾個 + 怎麼處理)
4. 1 個風險: 過度針對 high-prob leads → 反而錯失偶發 low-prob 也會報的學生; 或樣本 bias

**嚴格規則**:
- 不要重算 % / probabilities, 引用 facts
- 不要套話 ("加油")
- 不超過 330 字
- 不要 markdown 標題

直接寫策略。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 招生主任建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="cramlead — 補習班招生 Logistic Regression")
    p.add_argument("--data", default="samples/cram_leads.json")
    p.add_argument("--lr", type=float, default=0.3)
    p.add_argument("--l2", type=float, default=0.01)
    p.add_argument("--max-iter", type=int, default=1000)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    historical = data["historical_leads"]
    upcoming = data["upcoming_leads"]

    encoder = FeatureEncoder(
        numeric_features=data["numeric_features"],
        categorical_features=data["categorical_features"],
    )
    encoder.fit([h["features"] for h in historical])
    X_train = [encoder.transform(h["features"]) for h in historical]
    y_train = [h["enrolled"] for h in historical]

    model = fit_logreg(X_train, y_train, encoder.expanded_names, encoder,
                        lr=args.lr, l2_lambda=args.l2, max_iter=args.max_iter)

    train_probs = [predict_proba(model, h["features"]).probability for h in historical]
    train_metrics = {
        "accuracy": accuracy_score(y_train, train_probs),
        "log_loss": log_loss_score(y_train, train_probs),
        "auc": auc_roc_approx(y_train, train_probs),
    }
    predictions = [predict_proba(model, u["features"]) for u in upcoming]

    if args.no_ai:
        print(render_no_ai(data, model, historical, upcoming, train_metrics, predictions))
    else:
        print(render_with_ai(data, model, historical, upcoming, train_metrics, predictions))


if __name__ == "__main__":
    main()
