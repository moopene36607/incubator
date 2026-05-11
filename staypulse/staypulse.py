"""staypulse CLI -- 民宿 / B&B 房價彈性 Metropolis-Hastings 動態定價.

Usage:
    python3 staypulse.py --data samples/inn.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from mcmc import (
    Booking, run_mh, sweep_prices, optimal_price,
    DEFAULT_PRIORS, MCMCResult, PricePoint,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bookings_from_data(data: dict) -> list[Booking]:
    out = []
    for row in data["nightly_history"]:
        out.append(Booking(
            price=float(row["price_ntd"]),
            is_weekend=int(row["is_weekend"]),
            is_holiday=int(row["is_holiday"]),
            booked=int(row["booked"]),
        ))
    return out


def render_no_ai(data: dict, result: MCMCResult,
                  baseline: float, history: list[Booking],
                  scenarios: list[dict]) -> str:
    n_book = sum(b.booked for b in history)
    occ_rate = n_book / len(history) if history else 0.0

    lines = [
        f"# staypulse -- {data['property_name']} 房價彈性 MCMC Bayesian 動態定價",
        "",
        f"**地點**: {data.get('location', '')}",
        f"**過去 {len(history)} 晚紀錄**: 訂房 {n_book} 晚 (入住率 {occ_rate:.0%})",
        f"**Baseline 房價 (平日平均)**: NT$ {baseline:.0f}",
        f"**MCMC samples**: {len(result.samples)} (burn-in {result.burn_in}, thin {result.thin}, "
        f"acceptance {result.acceptance_rate():.0%})",
        "",
        "## 📊 後驗 (Bayesian posterior) 估計",
        "",
        "| 參數 | 後驗均值 | 後驗 SD | 95% 可信區間 | 經濟意義 |",
        "|---|---|---|---|---|",
    ]
    interp = {
        "alpha":        "intercept (baseline 平日 logit)",
        "beta_price":   "**價格彈性** -- 應該為負",
        "beta_weekend": "週末加價效果 -- 應該為正",
        "beta_holiday": "連假加價效果 -- 應該為正",
    }
    for k in ("alpha", "beta_price", "beta_weekend", "beta_holiday"):
        mu = result.posterior_mean(k)
        sd = result.posterior_std(k)
        lo, hi = result.credible_interval(k, 0.95)
        lines.append(
            f"| `{k}` | {mu:+.3f} | ±{sd:.3f} | [{lo:+.3f}, {hi:+.3f}] | {interp[k]} |"
        )

    beta_price_mu = result.posterior_mean("beta_price")
    lines.extend([
        "",
        f"> **價格彈性解讀**: 房價提高 1% 訂房機率 odds 改變 {beta_price_mu:.2f}% (β_price = {beta_price_mu:+.2f}).",
        f"> 負值越大 = 客人對價格越敏感, 該天 / 該段時間漲價會掉很多訂房。",
        "",
        "## 🎯 各情境最佳定價建議",
        "",
    ])

    for sc in scenarios:
        scenario_name = sc["name"]
        is_weekend = sc["is_weekend"]
        is_holiday = sc["is_holiday"]
        prices = sc["price_grid"]
        points = sweep_prices(result, is_weekend, is_holiday, baseline, prices, credible_level=0.90)
        best = optimal_price(points)

        lines.append(f"### {scenario_name}")
        lines.append("")
        lines.append(
            f"**推薦定價**: **NT$ {best.price:.0f}** "
            f"(後驗 EV = NT$ {best.expected_revenue_mean:.0f}/晚, "
            f"90% 區間 [{best.expected_revenue_low:.0f}, {best.expected_revenue_high:.0f}])"
        )
        lines.append("")
        lines.append("| 試算房價 | 訂房機率 | 預期收入 (mean ± 90% CI) | 推薦 |")
        lines.append("|---|---|---|---|")
        for pt in points:
            marker = "⭐" if pt.price == best.price else ""
            lines.append(
                f"| NT$ {pt.price:.0f} | {pt.book_prob_mean:.0%} "
                f"({pt.book_prob_low:.0%} -- {pt.book_prob_high:.0%}) | "
                f"NT$ {pt.expected_revenue_mean:.0f} "
                f"([{pt.expected_revenue_low:.0f}, {pt.expected_revenue_high:.0f}]) | {marker} |"
            )
        lines.append("")

    lines.extend([
        "## ⚠️ MCMC / Bayesian 模型假設與限制",
        "",
        "- **Logit 線性假設**: P(book) 對 log(price), weekend, holiday 線性, 真實有非線性 (整數天感) + 交互, Pro 版加 spline / GP / NN",
        "- **Independent observations**: 假設每晚獨立, 真實連假頭尾相關 + 上週同人有可能回購, Pro 版加 group-level random effects",
        "- **No competitor signal**: 鄰近民宿同期定價也影響訂房, 此 prototype 未捕捉, Pro 版加 hierarchical model with 區域 prior",
        "- **MCMC convergence**: 接受率應在 20-50% 區間; 接受率 < 10% 或 > 80% 表示 proposal_sigma 該調; 建議跑多 chain + Gelman-Rubin 診斷",
        "- **訓練樣本不大**: prototype 60 晚, real launch 需 ≥ 180 晚 (1 年) 才能 capture 完整季節性",
        "- **不捕捉重大事件**: 颱風 / 連假取消 / 跨年特殊定價, Pro 版加 explicit dummy 變數 + event detector",
        "- **競爭者壓力**: 純 MCMC 給 *單店* 最佳化, 多店搶客時 game-theoretic 均衡需 RL / Nash 模型",
        "- **隱性人為干預**: 老闆心情 / 朋友打折 / 平台促銷 噪音未建模",
        "",
        "---",
        "*staypulse = Metropolis & Hastings 1953/1970 MCMC × Bayesian logistic demand × 台灣民宿 / B&B 房價 niche = "
        "從 60+ 晚歷史資料 sample 後驗 (alpha, beta_price, beta_weekend, beta_holiday), "
        "拆出明確的「平日 / 週末 / 連假 / 旺季」最佳定價 + EV 90% 區間, 民宿老闆從「憑感覺」變「Bayesian decision」。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, result, baseline, history, scenarios):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, result, baseline, history, scenarios)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, result, baseline, history, scenarios)

    base = render_no_ai(data, result, baseline, history, scenarios)

    summary_lines = []
    for sc in scenarios:
        pts = sweep_prices(result, sc["is_weekend"], sc["is_holiday"], baseline, sc["price_grid"])
        best = optimal_price(pts)
        summary_lines.append(
            f"{sc['name']}: 最佳 NT${int(best.price)} (EV NT${int(best.expected_revenue_mean)}/晚, "
            f"book_prob {best.book_prob_mean:.0%})"
        )
    summary = " | ".join(summary_lines)

    beta_price = result.posterior_mean("beta_price")
    beta_weekend = result.posterior_mean("beta_weekend")
    beta_holiday = result.posterior_mean("beta_holiday")

    prompt = f"""你是台灣民宿經營顧問 (15+ 年, 訓練過 200+ 間花蓮 / 台東 / 宜蘭 / 金門 民宿老闆動態定價). 下面是用 Metropolis-Hastings MCMC 純函式分析的結果:

民宿: {data['property_name']} ({data.get('location', '')})
歷史: {len(history)} 晚, 入住率 {sum(b.booked for b in history)/len(history):.0%}
Baseline (平日均價): NT$ {baseline:.0f}
價格彈性 β_price 後驗均值: {beta_price:+.2f} (應為負)
週末效果 β_weekend: {beta_weekend:+.2f}
連假效果 β_holiday: {beta_holiday:+.2f}
情境最佳定價: {summary}

請寫 250-330 字「給民宿老闆的動態定價週工作流」:
1. 一句解讀 (避免「MCMC」「posterior」「彈性」這種詞): 你客人對價格的敏感度有多大
2. **3 個本週可立刻調整的具體 SOP** (平日 / 週末 / 連假定價; 何時放在 Booking / Airbnb / 自家網; LINE 預訂的特別優惠)
3. **1 個避免賠錢的 walk-away rule** (e.g. 颱風前還沒訂滿要降幾 % / 連假隔週要怎麼救)
4. 1 個風險提醒 (e.g. 鄰居打價格戰 / 平台政策改變 / 颱風事件)

**嚴格規則**:
- 不要重算 NT$ / 機率, 引用 facts
- 不要套話 ("祝您生意興隆")
- 不超過 330 字
- 不要 markdown 標題
- 強調「MCMC 是 60 晚樣本估計, 真實還要看當季 / 競爭」

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 民宿經營顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="staypulse -- 民宿動態定價 MCMC")
    p.add_argument("--data", default="samples/inn.json")
    p.add_argument("--n-iter", type=int, default=5000)
    p.add_argument("--burn-in", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    history = bookings_from_data(data)
    baseline = float(data["baseline_price"])
    scenarios = data["scenarios"]

    result = run_mh(history, baseline,
                     n_iter=args.n_iter, burn_in=args.burn_in, seed=args.seed)

    if args.no_ai:
        print(render_no_ai(data, result, baseline, history, scenarios))
    else:
        print(render_with_ai(data, result, baseline, history, scenarios))


if __name__ == "__main__":
    main()
