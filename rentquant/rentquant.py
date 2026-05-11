"""rentquant CLI -- 台灣租屋月租 Quantile Regression P10/P25/P50/P75/P90.

Usage:
    python rentquant.py --data samples/taipei_rentals.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from qreg import (
    FeatureEncoder, fit_quantile, predict_quantiles, coverage_report,
    negotiation_anchors, classify_offer,
    QuantileModel, QuantilePrediction,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_no_ai(data: dict, model: QuantileModel, encoder: FeatureEncoder,
                  listings: list[dict], y: list[float],
                  query_row: dict, pred: QuantilePrediction,
                  coverage: dict[float, float]) -> str:
    anchors = negotiation_anchors(pred)
    actual = query_row.get("actual_offer_ntd")
    classification = None
    if actual is not None:
        classification = classify_offer(float(actual), anchors)

    lines = [
        f"# rentquant -- {data['market_name']} 租屋月租 Quantile Regression",
        "",
        f"**訓練 listings**: {len(listings)} 筆 (台北市 + 新北 7 區)",
        f"**Quantile levels**: {', '.join(f'P{int(t * 100)}' for t in model.tau_levels)}",
        f"**Features**: {len(model.feature_names)} 個 ({len(encoder.numeric_features)} 數值 + {len(encoder.categorical_features)} 類別 one-hot)",
        "",
        "## 🎯 模型訓練統計",
        "",
        "| τ | iter 收斂 | pinball loss | 樣本覆蓋率 (應 ≈ τ) |",
        "|---|---|---|---|",
    ]
    for tau in model.tau_levels:
        lines.append(
            f"| P{int(tau * 100)} | {model.n_iter_used[tau]} | "
            f"{model.final_loss[tau]:.0f} | {coverage[tau]:.1%} |"
        )

    lines.extend([
        "",
        "> **覆蓋率解讀**: 訓練資料中, 實際月租 ≤ 預測 Q_τ 的比例. 收斂良好時應接近 τ.",
        "",
        "## 🏠 查詢物件",
        "",
        f"_{data['query'].get('_meta', '')}_",
        "",
        "| 欄位 | 值 |",
        "|---|---|",
    ])
    for f in encoder.numeric_features:
        lines.append(f"| {f} | {query_row[f]} |")
    for f in encoder.categorical_features:
        lines.append(f"| {f} | {query_row[f]} |")

    if actual is not None:
        lines.append(f"| **房東開價** | **NT$ {int(actual):,} / 月** |")

    lines.extend([
        "",
        "## 💡 月租 Quantile 預測 (P10 / P50 / P90 band)",
        "",
        "| 分位數 | 月租 (NT$) | 解讀 |",
        "|---|---|---|",
    ])
    for tau in model.tau_levels:
        q = pred.quantiles[tau]
        if tau == 0.1:
            interp = "P10 = 撿到便宜 (房東若低於這 = 賠錢; 房客若拿到 = 立刻簽)"
        elif tau == 0.25:
            interp = "P25 = 合理偏低 / 議價底線"
        elif tau == 0.5:
            interp = "P50 = 行情中位"
        elif tau == 0.75:
            interp = "P75 = 合理偏高 / 議價空間"
        elif tau == 0.9:
            interp = "P90 = 超出行情 (房東若超這 = 議價或拒簽)"
        else:
            interp = ""
        lines.append(f"| **P{int(tau * 100)}** | NT$ {int(q):,} | {interp} |")

    lines.extend([
        "",
        f"**90% 行情區間**: NT$ {int(anchors.walk_away):,} -- NT$ {int(anchors.ceiling):,}",
        f"**50% 行情區間**: NT$ {int(anchors.fair_low):,} -- NT$ {int(anchors.fair_high):,}",
        f"**中位 (P50)**: NT$ {int(anchors.median):,}",
        "",
    ])

    if classification is not None:
        label, action = classification
        gap_to_median = float(actual) - anchors.median
        sign = "+" if gap_to_median > 0 else ""
        pct = gap_to_median / anchors.median * 100 if anchors.median > 0 else 0
        lines.extend([
            "## 🎯 房東開價評估",
            "",
            f"**開價 NT$ {int(float(actual)):,} vs 中位 NT$ {int(anchors.median):,}**: {sign}{int(gap_to_median):,} ({sign}{pct:.1f}%)",
            "",
            f"### {label}",
            "",
            f"**建議動作**: {action}",
            "",
        ])

    # Feature contributions for P50 (most stable quantile)
    lines.extend([
        "## 🔍 P50 預測係數解構 (top 6 features by |β × value|)",
        "",
        "| 特徵 | 編碼後值 | β × value (NT$/月) |",
        "|---|---|---|",
    ])
    for name, val, contrib in pred.feature_contributions[0.5][:6]:
        sign = "+" if contrib > 0 else ""
        lines.append(f"| `{name}` | {val:.2f} | {sign}{contrib:.0f} |")

    lines.extend([
        "",
        "> **解讀**: β > 0 = 該特徵推高月租; β < 0 = 壓低月租. 編碼後值 = z-score (數值) 或 0/1 (one-hot).",
        "",
        "## ⚠️ Quantile Regression 模型假設與限制",
        "",
        "- **線性假設**: Q_τ(Y | X) 假設為 X 的線性函數;真實有非線性 (坪數 × 區域 交互), Pro 版用 quantile GBM / quantile forest",
        "- **獨立 τ 模型可能交叉**: 已用排序後處理保證 P10 ≤ P25 ≤ P50 ≤ P75 ≤ P90 monotone 非減",
        "- **訓練樣本不大**: real launch 需 ≥ 1000 筆且每區 ≥ 30 筆才能對細區域穩定預測",
        "- **季節 / 通膨未捕捉**: 暑假 vs 平日 + 物價漲跌, Pro 版加 month / year feature",
        "- **不含實地特徵**: 採光 / 噪音 / 鄰居 / 房東個性等價格決定因素無法量化, 工具給統計區間, 個人感受仍需實地看",
        "- **隱私敏感**: rental data 含地址 + 房東聯絡, 雲端版需匿名化 + 房東 / 房客同意 + 資料留存政策",
        "- **不取代律師審約**: 月租公允性歸 rentquant, 但條款 (押金 / 修繕 / 違約金) 違法性需 leasecheck (Round 24) 配合",
        "",
        "---",
        "*rentquant = Koenker & Bassett 1978 Quantile Regression × 台灣租屋市場 niche = 給每個物件 P10-P90 月租 band 而非單一估價, 房東知道天花板, 房客知道議價底線, 雙方都拿到客觀第三方錨點。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, model, encoder, listings, y, query_row, pred, coverage):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, encoder, listings, y, query_row, pred, coverage)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, model, encoder, listings, y, query_row, pred, coverage)

    base = render_no_ai(data, model, encoder, listings, y, query_row, pred, coverage)
    anchors = negotiation_anchors(pred)
    actual = query_row.get("actual_offer_ntd")
    classification_str = ""
    if actual is not None:
        label, action = classify_offer(float(actual), anchors)
        classification_str = f"房東開價 NT${int(float(actual)):,} → {label} ({action})"

    role = data["query"].get("role", "tenant")  # "tenant" or "landlord"

    top_feats = pred.feature_contributions[0.5][:3]
    feat_str = ", ".join(f"{n}={v:.2f}→{c:+.0f}" for n, v, c in top_feats)

    prompt = f"""你是台灣租屋市場資深房仲顧問 (15+ 年, 中山 / 信義 / 大安在地). 下面是用 Quantile Regression 純函式分析的結果:

{data['query'].get('_meta', '')}
詢問人角色: {'房客 tenant' if role == 'tenant' else '房東 landlord'}
查詢物件: {query_row.get('district', '')} {query_row.get('property_type', '')} {query_row.get('floor_area_ping', '')} 坪 屋齡 {query_row.get('building_age_years', '')} 年

P10 = NT${int(anchors.walk_away):,} / P25 = NT${int(anchors.fair_low):,} / P50 = NT${int(anchors.median):,} / P75 = NT${int(anchors.fair_high):,} / P90 = NT${int(anchors.ceiling):,}
{classification_str}
P50 top 影響: {feat_str}

請寫 250-330 字 ({'給房客的議價腳本' if role == 'tenant' else '給房東的訂價 + 招租建議'}):
1. 一句解讀 (避免「Quantile Regression」「pinball」這種詞): 為什麼這 band 合理
2. **{'3 個議價開場 + 推進步驟' if role == 'tenant' else '3 個訂價 + 招租策略'}** (具體話術 + 對方回應預判)
3. **{'1 個 walk-away 條件 / 簽約前必做' if role == 'tenant' else '1 個房客篩選紅旗'}**
4. 1 個風險提醒 (e.g. 採光 / 鄰居 / 樓層噪音 / 鄰避設施 / 短租 / 法規)

**嚴格規則**:
- 不要重算 NT$ / quantile, 引用 facts
- 不要套話 ("祝您")
- 不超過 330 字
- 不要 markdown 標題
- 不要拒絕回答或加 disclaimer

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    section_title = "AI 議價腳本 (給房客)" if role == "tenant" else "AI 訂價建議 (給房東)"
    return base + f"\n\n## 🤖 {section_title}\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="rentquant -- 租屋月租 Quantile Regression")
    p.add_argument("--data", default="samples/taipei_rentals.json")
    p.add_argument("--lr", type=float, default=0.05)
    p.add_argument("--max-iter", type=int, default=3000)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    listings = data["listings"]

    encoder = FeatureEncoder(
        numeric_features=data["numeric_features"],
        categorical_features=data["categorical_features"],
    )
    encoder.fit(listings)
    X_train = [encoder.transform(r) for r in listings]
    y_train = [float(r["monthly_rent_ntd"]) for r in listings]

    model = fit_quantile(X_train, y_train, encoder.expanded_names,
                          lr=args.lr, max_iter=args.max_iter)
    coverage = coverage_report(model, X_train, y_train)

    query_row = dict(data["query"]["features"])
    if "actual_offer_ntd" in data["query"]:
        query_row["actual_offer_ntd"] = data["query"]["actual_offer_ntd"]
    x_q = encoder.transform({k: v for k, v in query_row.items() if k != "actual_offer_ntd"})
    pred = predict_quantiles(model, x_q)

    if args.no_ai:
        print(render_no_ai(data, model, encoder, listings, y_train, query_row, pred, coverage))
    else:
        print(render_with_ai(data, model, encoder, listings, y_train, query_row, pred, coverage))


if __name__ == "__main__":
    main()
