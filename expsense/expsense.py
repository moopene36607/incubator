"""expsense CLI — SME 員工費用報銷異常偵測 Isolation Forest。

Usage:
    python expsense.py --records samples/reimbursements.json --no-ai
    python expsense.py --records samples/reimbursements.json --top 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from iforest import (
    fit_iforest, score_all, top_k_anomalies, feature_contribution,
    IsolationForest,
)


def load_records(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Categorical feature encoding (one-hot or scalar)
CATEGORY_ORDER = ["餐費", "交通", "住宿", "文具", "通訊", "客戶招待", "差旅雜支"]
ROLE_ORDER = ["sales", "engineer", "hr_admin"]


def featurize(records: list[dict]) -> list[dict[str, float]]:
    """Convert reimbursement records to numeric feature dicts for IF."""
    # Per-employee category baselines for "amount vs personal avg" feature
    employee_cat_amounts: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in records:
        employee_cat_amounts[(r["employee_id"], r["category"])].append(r["amount_ntd"])

    # Personal-category mean amounts
    personal_means = {key: sum(vals) / len(vals) for key, vals in employee_cat_amounts.items()}

    out = []
    for r in records:
        emp_cat_mean = personal_means.get((r["employee_id"], r["category"]), r["amount_ntd"])
        amt_vs_personal = r["amount_ntd"] / max(emp_cat_mean, 1)

        # Distance from work hour 9-18 (closer to weekday + business hours = lower)
        # Distance from "typical workday hour" 9-18 midpoint = 13.5
        hour_atypical = abs(r["hour"] - 13.5)

        out.append({
            "amount_log": __import__("math").log(r["amount_ntd"] + 1),  # log scale
            "amount_ntd": float(r["amount_ntd"]),
            "category_idx": float(CATEGORY_ORDER.index(r["category"])),
            "hour": float(r["hour"]),
            "hour_atypical": hour_atypical,
            "weekday": float(r["weekday"]),
            "is_weekend": 1.0 if r["weekday"] >= 6 else 0.0,
            "amount_vs_personal_cat": amt_vs_personal,
        })
    return out


VERDICT_THRESHOLD_HIGH = 0.65
VERDICT_THRESHOLD_LOW = 0.55


def render_no_ai(data: dict, records: list[dict], scores: list[float],
                  forest: IsolationForest, top_n: int) -> str:
    top = top_k_anomalies(records, scores, k=top_n)

    lines = [
        f"# expsense — {data['company_name']} 報銷異常偵測",
        "",
        f"**月份**: {data.get('fiscal_month', 'N/A')}  ·  **提交人**: {data.get('submitted_by', 'N/A')}",
        f"**總筆數**: {len(records)}  ·  **員工數**: {len(data.get('employees', []))}",
        f"**Isolation Forest 設定**: {forest.n_trees} 棵樹 × subsample {forest.sample_size}",
        f"**Features 使用**: {', '.join(forest.features)}",
        "",
        "## 🎯 Top {} 可疑報銷筆".format(top_n),
        "",
        "| # | ID | 員工 | 日期 | 類別 | 金額 | 時間 | weekday | 異常分 | 嚴重 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, (idx, score, x) in enumerate(top):
        severity = "🔴" if score >= VERDICT_THRESHOLD_HIGH else ("🟡" if score >= VERDICT_THRESHOLD_LOW else "🟢")
        amount_str = f"NT${x['amount_ntd']:,}"
        lines.append(
            f"| {i + 1} | {x['id']} | {x['employee_name']} | {x['date']} | "
            f"{x['category']} | **{amount_str}** | {x['hour']:.0f}時 | W{x['weekday']} | "
            f"**{score:.3f}** | {severity} |"
        )

    lines.append("")
    lines.append("## 各筆 anomaly 原因(feature contribution)")
    lines.append("")
    featurized = featurize(records)
    for i, (idx, score, x) in enumerate(top[:5]):
        contribs = feature_contribution(featurized[idx], forest)
        sorted_contribs = sorted(contribs.items(), key=lambda kv: -kv[1])
        top_feats = ", ".join(f"`{f}` ({v:.2f})" for f, v in sorted_contribs[:3])
        lines.append(f"### 🔴 #{i+1} {x['id']} ({x['employee_name']} / {x['category']} / NT${x['amount_ntd']:,})")
        lines.append("")
        lines.append(f"- **異常分數**: {score:.3f}  ·  **隔離深度貢獻最大的特徵**: {top_feats}")
        # Specific reason
        reasons = []
        if x['amount_ntd'] > 5000:
            reasons.append(f"金額 NT${x['amount_ntd']:,} 顯著偏高 ({x['category']} 類別正常 < NT$3K)")
        if x['hour'] < 7 or x['hour'] > 22:
            reasons.append(f"時段異常 ({x['hour']:.0f} 時非辦公時間)")
        if x['weekday'] >= 6:
            reasons.append(f"週末發生 (W{x['weekday']})")
        # Description hint
        if x.get('description'):
            reasons.append(f"自填說明: 「{x['description']}」")
        for r in reasons:
            lines.append(f"  - {r}")
        lines.append("")

    lines.append("## 員工 anomaly 排行 (累積 anomaly score)")
    lines.append("")
    employee_score: dict[str, list[float]] = defaultdict(list)
    employee_name: dict[str, str] = {}
    for r, s in zip(records, scores):
        employee_score[r["employee_id"]].append(s)
        employee_name[r["employee_id"]] = r["employee_name"]
    emp_summary = []
    for eid, sc_list in employee_score.items():
        emp_summary.append({
            "id": eid, "name": employee_name[eid],
            "max_score": max(sc_list),
            "avg_score": sum(sc_list) / len(sc_list),
            "n_records": len(sc_list),
            "n_anomalies": sum(1 for s in sc_list if s >= VERDICT_THRESHOLD_HIGH),
        })
    emp_summary.sort(key=lambda e: -e["max_score"])
    lines.append("| 員工 | 筆數 | 平均分 | 最高分 | 高風險筆數 |")
    lines.append("|---|---|---|---|---|")
    for e in emp_summary:
        marker = "🔴" if e["n_anomalies"] >= 2 else ("🟡" if e["n_anomalies"] >= 1 else "🟢")
        lines.append(f"| {marker} {e['name']} ({e['id']}) | {e['n_records']} | {e['avg_score']:.3f} | {e['max_score']:.3f} | {e['n_anomalies']} |")

    lines.append("")
    lines.append("## ⚠️ Isolation Forest 模型假設與限制")
    lines.append("")
    lines.append("- **無監督方法**: 沒有 labeled 訓練資料,只找「跟其他人不一樣」的點,**不等於詐騙**")
    lines.append("- **小樣本 risk**: < 30 筆 IF 不穩定 (subsample 變小);Pro 版要求 ≥ 100 筆")
    lines.append("- **特徵工程依賴**: 加更多 features (供應商 / 報銷時段 / 同筆多人會審) 可提高準確度")
    lines.append("- **anomaly ≠ fraud**: 異常筆**只是值得問**,不是直接定罪;需要老闆 / HR 人工 follow-up")
    lines.append("- **季節性 / 月底特例**: 業務員月底衝業績可能合理高消費,模型不知道 context")
    lines.append("")
    lines.append("---")
    lines.append("*expsense = Liu, Ting & Zhou 2008 Isolation Forest × 台灣 SME niche = 老闆每月 1-2 小時對帳壓到 30 秒。*")
    return "\n".join(lines)


def render_with_ai(data: dict, records: list[dict], scores: list[float],
                    forest: IsolationForest, top_n: int) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, records, scores, forest, top_n)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, records, scores, forest, top_n)

    base = render_no_ai(data, records, scores, forest, top_n)
    top = top_k_anomalies(records, scores, k=min(5, top_n))
    summary_lines = []
    for i, (idx, score, x) in enumerate(top):
        summary_lines.append(
            f"#{i+1} {x['id']} 員工 {x['employee_name']} {x['category']} "
            f"NT${x['amount_ntd']:,} {x['date']} {x['hour']}時 score={score:.3f}"
        )

    prompt = f"""你是一位資深台灣中小企業會計顧問。下面是用 Isolation Forest 純函式偵測的可疑報銷筆:

公司: {data['company_name']}, 月份 {data.get('fiscal_month')}
總筆數 {len(records)}, 員工 {len(data.get('employees', []))} 人

Top {len(top)} 可疑筆:
{chr(10).join(summary_lines)}

請寫 250-320 字「給老闆讀的對帳建議」:
1. **每筆寫 1-2 句**: 這筆為什麼可疑 + 老闆該怎麼跟員工確認(具體開場句, 例如「小華,我看 5/12 那筆客戶招待 NT$18,800, 能幫我看看是哪家客戶 + 收據嗎?」)
2. **整體 1-2 句**: 跨員工有沒有模式 (sales 偏高 / engineer 異常 / 月底集中)
3. **1 個風險提醒**: anomaly ≠ fraud / 員工解釋優先 / 不要當員工面 confront

**嚴格規則**:
- 不要重新算分數, 引用上面數字
- 不要套話 ("加油")
- 不超過 320 字
- 不要 markdown 標題

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 會計顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="expsense — SME 報銷異常偵測 IF")
    p.add_argument("--records", default="samples/reimbursements.json")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--trees", type=int, default=120)
    p.add_argument("--sample-size", type=int, default=64)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_records(Path(args.records))
    records = data["records"]
    featurized = featurize(records)
    features_to_use = ["amount_log", "amount_vs_personal_cat", "hour_atypical",
                       "is_weekend", "category_idx"]
    forest = fit_iforest(featurized, features=features_to_use,
                          n_trees=args.trees, sample_size=args.sample_size,
                          seed=args.seed)
    scores = score_all(featurized, forest)

    if args.no_ai:
        print(render_no_ai(data, records, scores, forest, args.top))
    else:
        print(render_with_ai(data, records, scores, forest, args.top))


if __name__ == "__main__":
    main()
