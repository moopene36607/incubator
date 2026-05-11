"""petfeed CLI -- 台灣寵物飼料推薦 Hierarchical Bayesian shrinkage.

Usage:
    python petfeed.py --data samples/pet_reviews.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from hb_shrink import (
    Review, Query, fit_hb, recommend_for_query,
    naive_vs_shrunk_table, most_corrected_cells, model_summary,
    HBModel, Recommendation,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def reviews_from_data(data: dict) -> list[Review]:
    out = []
    for r in data["historical_reviews"]:
        out.append(Review(
            breed=r["breed"],
            brand=r["brand"],
            rating=float(r["rating"]),
            age_group=r.get("age_group", "成犬"),
            weight_kg=float(r.get("weight_kg", 0.0)),
            sensitive_stomach=bool(r.get("sensitive_stomach", False)),
            grain_free=bool(r.get("grain_free", False)),
            months_fed=int(r.get("months_fed", 1)),
        ))
    return out


def render_no_ai(data: dict, model: HBModel,
                 query: Query, recs: list[Recommendation],
                 corrected: list[dict]) -> str:
    summ = model_summary(model)
    lines = [
        f"# petfeed -- {data['store_name']} 飼料 Hierarchical Bayes 推薦",
        "",
        f"**歷史 reviews**: {summ['n_total_reviews']} 件 ({summ['n_cells']} 個 (品種, 品牌) cells)",
        f"**全國均值 μ_global**: {summ['mu_global']:.3f} / 5.0 (各 cell 均值的平均)",
        f"**Cell 內 SD σ_within**: {summ['sigma_within']:.3f} (一隻狗對同一飼料 review 之間的雜訊)",
        f"**Cell 間 SD τ_between**: {summ['tau_between']:.3f} (不同 cell 之間真實差距)",
        f"**ICC**: {summ['icc']:.1%} -- 「總變異有多少來自 cell 之間的真實差距」 (剩餘來自雜訊)",
        "",
        "## 🐾 查詢條件",
        "",
        f"_{data['query'].get('_meta', '')}_",
        "",
        "| 欄位 | 值 |",
        "|---|---|",
        f"| 品種 | {query.breed} |",
        f"| 年齡層 | {query.age_group} |",
        f"| 體重 | {query.weight_kg} kg |",
        f"| 腸胃敏感 | {'是' if query.sensitive_stomach else '否'} |",
        f"| 偏好無穀 | {'是' if query.grain_free_preference else '否'} |",
        "",
    ]

    if not recs:
        lines.append(f"⚠️ 找不到品種 `{query.breed}` 的歷史 reviews -- 後驗會強拉向 μ_global, 建議先收集 5+ 件再用此模型.")
        lines.append("")
    else:
        lines.append(f"## 💡 Top {len(recs)} 推薦飼料 (依後驗 shrunk mean 排序)")
        lines.append("")
        lines.append("| # | 品牌 | 後驗均值 | 95% CI | n | shrinkage | raw_mean | Δ(raw−shrunk) | 解讀 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in recs:
            lines.append(
                f"| {r.rank} | **{r.brand}** | {r.shrunk_mean:.2f} | "
                f"[{r.ci_low:.2f}, {r.ci_high:.2f}] | {r.n_samples} | "
                f"{r.shrinkage_weight:.0%} | {r.raw_mean:.2f} | "
                f"{r.naive_vs_shrunk_delta:+.2f} | {r.rationale} |"
            )
        lines.append("")
        lines.append("> **shrinkage 解讀**: 100% = 後驗 = 原始 cell 均值 (n 大時); 0% = 後驗 = μ_global (n 小時拉回全國均值)")
        lines.append("")
        lines.append("> **Δ 解讀**: 正值 = 原始評分樂觀, 已被 HB 模型拉低; 負值 = 原始評分悲觀, 已被拉高")
        lines.append("")

    lines.append("## 🔧 模型最積極修正的 cells (|Δ| 最大)")
    lines.append("")
    lines.append("| 品種 | 品牌 | n | raw | shrunk | Δ | shrinkage |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in corrected:
        lines.append(
            f"| {row['breed']} | {row['brand']} | {row['n']} | "
            f"{row['raw_mean']:.2f} | {row['shrunk_mean']:.2f} | "
            f"{row['delta']:+.2f} | {row['shrinkage_weight']:.0%} |"
        )

    lines.extend([
        "",
        "> 這些 cell 的 raw 評分被 HB 修正最多 -- 通常是 n 小 + 評分極端 (5.0 或 2.0) 的偽信號. ",
        "",
        "## 📊 子群體 raw 均值 (僅為診斷, 不參與排序)",
        "",
    ])
    for feat, group in model.feature_group_means.items():
        lines.append(f"**{feat}**:")
        for v, m in sorted(group.items(), key=lambda kv: -kv[1]):
            lines.append(f"- `{v}` → {m:.2f}")
        lines.append("")

    lines.extend([
        "## ⚠️ Hierarchical Bayes 模型假設與限制",
        "",
        "- **常態假設**: rating ~ Normal, 真實是 1-5 ordinal -- Pro 版用 ordinal probit 較精確",
        "- **僅 2-level shrinkage**: (cell ← global), 實務上 (品種 ← 屬科 ← 全國) 三層更穩;Pro 版加品種分群",
        "- **σ_within / τ_between 用 method-of-moments**: 不一定 MLE 最優;大樣本 OK, n_cells < 20 時改用 REML",
        "- **未考慮飼主主觀偏差**: 同一隻狗不同主人打分差 0.5-1.0 顆星, Pro 版加 reviewer-effect random intercept",
        "- **冷啟動弱**: 新品種 / 新品牌 0 review 時退回 μ_global, 仍鼓勵實地試吃 + 寵物醫師意見",
        "- **不取代獸醫專業**: 嚴重腸胃 / 過敏 / 慢性病請先諮詢獸醫, 飼料只是輔助",
        "",
        "---",
        "*petfeed = Empirical-Bayes Hierarchical Linear Model (James 1961 / Efron-Morris 1973) × "
        "台灣寵物飼料 niche = 把零碎 (品種, 品牌) 評分 shrink 成穩健後驗推薦, "
        "n=2 的 5.0 不會打敗 n=30 的 4.6, 飼主一次選到 sample-bias 小的飼料.*",
    ])
    return "\n".join(lines)


def render_with_ai(data, model, query, recs, corrected):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, query, recs, corrected)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, query, recs, corrected)

    base = render_no_ai(data, model, query, recs, corrected)
    if not recs:
        return base

    rec_str = "; ".join(
        f"{r.rank}. {r.brand} 後驗 {r.shrunk_mean:.2f} (n={r.n_samples}, raw={r.raw_mean:.2f}, "
        f"shrinkage={r.shrinkage_weight:.0%})" for r in recs
    )
    corrected_str = ", ".join(
        f"{c['brand']}@{c['breed']} raw {c['raw_mean']:.2f}→{c['shrunk_mean']:.2f}"
        for c in corrected[:3]
    )
    summ = model_summary(model)

    prompt = f"""你是台灣寵物店店長 + 寵物營養顧問。下面是用 Hierarchical Bayesian 純函式分析的結果:

飼主查詢: {data['query'].get('_meta', '')}
品種: {query.breed} / 年齡層 {query.age_group} / 體重 {query.weight_kg} kg
腸胃敏感: {query.sensitive_stomach} / 偏好無穀: {query.grain_free_preference}

模型統計: μ_global={summ['mu_global']:.2f}, σ_within={summ['sigma_within']:.2f}, τ_between={summ['tau_between']:.2f}, ICC={summ['icc']:.1%}
Top 推薦: {rec_str}
修正最大的 cells: {corrected_str}

請寫 250-330 字「給飼主的選擇與換糧建議 + 寵物店 SKU 採購邏輯」:
1. 一句解讀 (避免「Bayesian」「shrinkage」「posterior」這種詞): 為什麼這 3 個品牌是首選
2. **3 個換糧 SOP 細節** (7-10 天交替比例 / 觀察便便 / 嘔吐警示 / 過敏跡象)
3. **寵物店 SKU 採購邏輯** (高 n 高評 brand 主推 / 低 n 高評 brand 試點進貨 / 低評 brand 退場)
4. 1 個風險提醒 (e.g. 高過敏品種 / 慢性病 / 處方飼料先問獸醫)

**嚴格規則**:
- 不要重算評分 / shrinkage %, 引用 facts
- 不要套話 ("加油" / "祝您愛犬健康")
- 不超過 330 字
- 不要 markdown 標題
- 不要建議特定品牌外的 (例如別亂推「皇家」如果它不在 Top 推薦)

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 寵物營養顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="petfeed -- 寵物飼料 Hierarchical Bayes")
    p.add_argument("--data", default="samples/pet_reviews.json")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    reviews = reviews_from_data(data)
    model = fit_hb(reviews)

    q = data["query"]["features"]
    query = Query(
        breed=q["breed"],
        age_group=q.get("age_group", "成犬"),
        weight_kg=float(q.get("weight_kg", 0.0)),
        sensitive_stomach=bool(q.get("sensitive_stomach", False)),
        grain_free_preference=bool(q.get("grain_free_preference", False)),
    )
    recs = recommend_for_query(model, query, top_k=args.top_k)
    corrected = most_corrected_cells(model, top_n=5)

    if args.no_ai:
        print(render_no_ai(data, model, query, recs, corrected))
    else:
        print(render_with_ai(data, model, query, recs, corrected))


if __name__ == "__main__":
    main()
