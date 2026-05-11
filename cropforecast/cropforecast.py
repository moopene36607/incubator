"""cropforecast CLI -- 台灣蔬果批發價 Gaussian Process 14-day 預測.

Usage:
    python3 cropforecast.py --data samples/wholesale_prices.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import fmean, pstdev

from gp import (
    fit_gp, predict_gp, log_marginal_likelihood, rmse,
    empirical_coverage, mean_band_width,
    GPModel, GPPrediction,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, model: GPModel,
                  X_train: list[float], y_train: list[float],
                  X_test: list[float], pred: GPPrediction,
                  train_rmse: float, lml: float) -> str:
    forecast_horizon = data.get("forecast_horizon_days", 14)
    commodity = data["commodity"]
    unit = data.get("unit", "NT$/kg")
    history_len = len(y_train)

    last_actual = y_train[-1]
    next_pred = pred.mean[0]
    horizon_pred = pred.mean[forecast_horizon - 1] if forecast_horizon <= len(pred.mean) else pred.mean[-1]
    horizon_band = (pred.ci_low_95[forecast_horizon - 1] if forecast_horizon <= len(pred.ci_low_95) else pred.ci_low_95[-1],
                    pred.ci_high_95[forecast_horizon - 1] if forecast_horizon <= len(pred.ci_high_95) else pred.ci_high_95[-1])

    change_pct = (horizon_pred - last_actual) / last_actual * 100 if last_actual > 0 else 0
    direction = "📈 預估上漲" if change_pct > 3 else ("📉 預估下跌" if change_pct < -3 else "➡️ 預估持平")

    lines = [
        f"# cropforecast -- {commodity} 批發價 Gaussian Process {forecast_horizon} 天預測",
        "",
        f"**訓練資料**: 過去 {history_len} 天每日批發價",
        f"**Kernel**: Squared-Exponential (RBF)",
        f"**Hyperparameters**: σ_f = {model.sigma_f:.2f} ({unit}), ℓ = {model.ell:.1f} 天, σ_n = {model.sigma_n:.2f} ({unit})",
        f"**Training RMSE**: {train_rmse:.2f} {unit}",
        f"**Log marginal likelihood**: {lml:.1f} (越大越好,用於 hyperparameter 調校診斷)",
        "",
        "## 📊 過去 7 天回顧",
        "",
        "| 天序 | 日期 (rel) | 實際價 |",
        "|---|---|---|",
    ]
    n_recent = min(7, history_len)
    for i in range(history_len - n_recent, history_len):
        lines.append(f"| D{i - history_len + 1} | T-{history_len - 1 - i} | {y_train[i]:.2f} |")

    lines.extend([
        "",
        f"## 🔮 未來 {forecast_horizon} 天 GP 預測",
        "",
        f"### {direction}: 從 {unit} {last_actual:.2f} (今天) → {horizon_pred:.2f} (D+{forecast_horizon}) = {change_pct:+.1f}%",
        "",
        f"**95% 信心區間 (D+{forecast_horizon})**: {horizon_band[0]:.2f} -- {horizon_band[1]:.2f} {unit}",
        "",
        "| 預測天 | 後驗均值 | 80% CI | 95% CI | 不確定性 σ |",
        "|---|---|---|---|---|",
    ])
    for i, x_pred in enumerate(X_test[:forecast_horizon]):
        lines.append(
            f"| D+{i + 1} | **{pred.mean[i]:.2f}** | "
            f"[{pred.ci_low_80[i]:.2f}, {pred.ci_high_80[i]:.2f}] | "
            f"[{pred.ci_low_95[i]:.2f}, {pred.ci_high_95[i]:.2f}] | "
            f"±{pred.std[i]:.2f} |"
        )

    band_width_95 = mean_band_width(pred, 0.95)
    avg_actual = fmean(y_train)
    relative_uncertainty = band_width_95 / avg_actual * 100 if avg_actual > 0 else 0

    lines.extend([
        "",
        f"**平均 95% 區間寬度**: {band_width_95:.2f} {unit} ({relative_uncertainty:.1f}% of 過去 {history_len} 天均價)",
        "",
        "## 🎯 對 3 類使用者的建議區間",
        "",
        "| 角色 | 該關注的數字 | 應對方向 |",
        "|---|---|---|",
        f"| **農民** (供貨決策) | D+{forecast_horizon} 中位 {horizon_pred:.2f} | "
        f"{'多送貨' if change_pct > 5 else '保守送貨' if change_pct < -5 else '依平日量送'}, "
        f"95% lower {horizon_band[0]:.2f} 作為「最壞情境」 |",
        f"| **量販 / 餐廳採購** | 95% upper {horizon_band[1]:.2f} | "
        f"{'盡早囤貨' if change_pct > 5 else '可等待降價' if change_pct < -5 else '正常採購'}, "
        f"95% upper 是「議價封頂」 |",
        f"| **加工業者** (庫存) | 80% CI 中位 {pred.mean[forecast_horizon // 2]:.2f} | "
        f"中期週期決策,用 80% 較窄區間穩 |",
        "",
        "## ⚠️ Gaussian Process 模型假設與限制",
        "",
        "- **核函數選擇**: RBF kernel 假設價格隨日期 *smoothly* 變動;真實有跳變 (颱風 / 政策),Pro 版加 white-noise kernel + 突變 detector",
        "- **獨立同分布噪音**: σ_n 假設 homoscedastic;真實 weekend / 颱風日 noise 大很多, Pro 版用 heteroscedastic GP",
        "- **單變數時序**: 此 prototype 只用 day-of-history 作 input;真實需加 weather / 颱風 / 季節 / DOW 多 features (multi-dim GP)",
        "- **預測越遠不確定性越大**: D+14 比 D+1 寬 2-3x,這是 GP **數學保證的正確行為**,不是 bug",
        "- **訓練樣本不大**: prototype 60 天, real launch 需 ≥ 2-3 年資料才能 capture 季節性 + 異常",
        "- **不適合突變後立即預測**: 颱風剛過 / 政策剛改, GP 仍按平滑歷史推, 需 explicit 變點重訓",
        "- **隱性人為干預未捕捉**: 拍賣市場進場量被預期心理影響,GP 假設 stationarity 在這層失效",
        "",
        "---",
        "*cropforecast = Rasmussen & Williams 2006 Gaussian Process Regression × RBF kernel × 台灣蔬果批發價 niche = "
        "對 D+1 ~ D+14 給後驗均值 + 95% 信心區間, 農民 / 餐廳採購 / 加工業者三方都拿到客觀數據而非「老農經驗 / 大盤喊價」, "
        "終結批發市場資訊不對稱。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, model, X_train, y_train, X_test, pred,
                    train_rmse, lml):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, X_train, y_train, X_test, pred, train_rmse, lml)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, X_train, y_train, X_test, pred, train_rmse, lml)

    base = render_no_ai(data, model, X_train, y_train, X_test, pred, train_rmse, lml)
    forecast_horizon = data.get("forecast_horizon_days", 14)
    last_actual = y_train[-1]
    horizon_idx = min(forecast_horizon - 1, len(pred.mean) - 1)
    horizon_pred = pred.mean[horizon_idx]
    horizon_band = (pred.ci_low_95[horizon_idx], pred.ci_high_95[horizon_idx])
    change_pct = (horizon_pred - last_actual) / last_actual * 100 if last_actual > 0 else 0

    prompt = f"""你是台灣果菜批發市場資深行情顧問 + 農民團體秘書。下面是用 Gaussian Process Regression 純函式分析的結果:

商品: {data['commodity']}
過去 {len(y_train)} 天每日批發價區間: {min(y_train):.1f} - {max(y_train):.1f} {data.get('unit', 'NT$/kg')}
今日價格: {last_actual:.2f}
D+{forecast_horizon} 預測中位: {horizon_pred:.2f} ({change_pct:+.1f}%)
D+{forecast_horizon} 95% 區間: {horizon_band[0]:.2f} -- {horizon_band[1]:.2f}
{data.get('market_context', '')}

請寫 250-330 字「給 3 類使用者的兩週行動建議」:
1. 一句解讀 (避免「Gaussian Process」「kernel」「posterior」這種詞): 兩週走向 + 信心度
2. **農民 (出貨方)** 兩週具體行動 (集中出貨 vs 保留 vs 觀望; 應準備哪個情境)
3. **量販 / 餐廳採購方** 兩週具體行動 (現在搶貨 vs 等便宜 vs 簽預購)
4. 1 個風險提醒 (e.g. 颱風 / 政策補貼 / 進口量 / 寒流 / 連假效應)

**嚴格規則**:
- 不要重算 NT$ / %, 引用 facts
- 不要套話 ("辛苦了" / "祝豐收")
- 不超過 330 字
- 不要 markdown 標題
- 強調「GP 是統計預測, 突發事件 (颱風) 一過即失效」

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 行情顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="cropforecast -- 蔬果批發價 Gaussian Process 預測")
    p.add_argument("--data", default="samples/wholesale_prices.json")
    p.add_argument("--sigma-f", type=float, default=None)
    p.add_argument("--ell", type=float, default=None)
    p.add_argument("--sigma-n", type=float, default=None)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))

    history = data["historical_prices"]
    X_train = [float(i) for i in range(len(history))]   # day index
    y_train = [float(p) for p in history]

    forecast_horizon = data.get("forecast_horizon_days", 14)
    X_test = [float(len(history) + i) for i in range(forecast_horizon)]

    model = fit_gp(X_train, y_train,
                    sigma_f=args.sigma_f, ell=args.ell, sigma_n=args.sigma_n)
    pred = predict_gp(model, X_test)
    train_rmse = rmse(model, X_train, y_train)
    lml = log_marginal_likelihood(model)

    if args.no_ai:
        print(render_no_ai(data, model, X_train, y_train, X_test, pred, train_rmse, lml))
    else:
        print(render_with_ai(data, model, X_train, y_train, X_test, pred, train_rmse, lml))


if __name__ == "__main__":
    main()
