"""daypart — 餐飲店一日銷售型態 EM 分群 CLI(Mixture Models / EM Algorithm).

純函式做所有分群與 BIC(mixture.py)。LLM 只負責:
  ① 為每個 cluster 起一個「客群名稱」(早班族 / 主婦學生 / 上班族下午茶)
  ② 推測該 cluster 可能買什麼產品 / 來消費什麼動機
  ③ 為每個 cluster 設計個人化促銷策略
  ④ 對店家整體經營給結構性建議

LLM 永不算 cluster 數量 / 機率 / NT$。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from mixture import (
    ClusterProfile,
    Transaction,
    assign_transactions,
    bayesian_info_criterion,
    find_best_k,
    fit_em,
    load_csv,
    profile_clusters,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣餐飲店 / 飲料店 / 早午餐店行銷顧問。

    輸入:
      - 一週 / 一月 transactions 跑 EM Gaussian Mixture 後的 cluster profiles
      - 每個 cluster 有:時段中心 (HH:MM) / 客單價中心 / 樣本數 / 佔比 / 營收貢獻 / time_range / spend_range

    工作:
      1. 為每個 cluster 起「客群名稱」(基於時段 + 客單價推測):
         - 06:00-09:30 低客單(NT$50-100):**早班族 / 通勤族**
         - 06:00-09:30 高客單(NT$120+):**家庭早午餐 / 退休族**
         - 10:30-13:00 中客單:**主婦 / 學生中餐**
         - 10:30-13:00 高客單:**商務午餐**
         - 14:00-17:00 低客單:**下午茶上班族**
         - 14:00-17:00 高客單:**下午茶聚會**
         - 17:30-21:00 中客單:**晚餐自用**
         - 17:30-21:00 高客單:**晚餐家庭 / 聚餐**
      2. 為每個 cluster 推測「他們最常點什麼」+「為什麼來這間店」
      3. 為每個 cluster 設計**1 個具體促銷策略**:
         - 時段限定優惠(時段配合該 cluster 出沒時間)
         - 客單價提升 / 加值組合
         - 留客動作(下次回訪誘因)
      4. 對店家整體建議 1-2 條結構性洞察(例「最大營收來源是 X cluster 佔 Y%,該強化」「Z cluster 客單低但量大,可試圖升級」)

    硬規則:
      - 你**絕不**重算 NT$ / 機率 — 直接引用 profile 數字
      - 不勸老闆「歧視客群」(e.g.「拒收低客單客」)
      - 建議促銷必須具體可執行(壞例:「行銷下午茶」;好例:「14:00-16:30 第 2 杯飲料 6 折 + LINE 群推播」)
      - 用台灣繁體中文 + 在地用語(早午餐 / 套餐 / 加購 / 集點)

    回覆 JSON:
    {
      "cluster_interpretations": [
        {
          "cluster_id": 0,
          "persona_name": "早班通勤族",
          "persona_description": "...",
          "likely_purchases": ["...", "..."],
          "promotion_strategy": {
            "title": "...",
            "details": "...",
            "expected_impact": "..."
          }
        },
        ...
      ],
      "overall_insights": ["...", "..."]
    }
""").strip()


def ai_explain(profiles: list[ClusterProfile], best_k: int, bic_results: dict, n_total: int) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "n_total_transactions": n_total,
        "best_k_via_bic": best_k,
        "bic_comparison": bic_results,
        "cluster_profiles": [
            {
                "cluster_id": p.cluster_id,
                "weight": p.weight,
                "n_transactions": p.n_transactions,
                "mu_time_label": p.mu_time_label,
                "mu_spend": p.mu_spend,
                "time_range_label": p.time_range_label,
                "spend_range_label": p.spend_range_label,
                "total_revenue_contribution_ntd": p.total_revenue_contribution_ntd,
            }
            for p in profiles
        ],
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def render_no_ai_report(records: list[Transaction], profiles: list[ClusterProfile],
                        bic_results: dict, best_k: int, n_iter: int) -> str:
    parts = ["# daypart 餐飲店一日銷售型態 EM 分群報告\n"]
    parts.append("**模式**: 純函式 2D Gaussian Mixture + EM 演算法(免 API key)\n")
    parts.append("## 資料概況\n")
    parts.append(f"- **transactions**: {len(records)} 筆")
    parts.append(f"- **BIC 最佳 k**: {best_k}({n_iter} 次 EM 迭代收斂)")
    parts.append("")

    parts.append("## BIC 模型選擇\n")
    parts.append("| k | Log-Likelihood | BIC | iter |")
    parts.append("|---|---|---|---|")
    for r in bic_results['all_results']:
        marker = " ⭐" if r['k'] == best_k else ""
        parts.append(f"| {r['k']}{marker} | {r['log_likelihood']:.1f} | {r['bic']:.1f} | {r['n_iter']} |")
    parts.append("")

    parts.append(f"## Cluster Profiles (k={best_k})\n")
    parts.append("| Cluster | 時段中心 | 主要時段 | 客單價中心 | 客單範圍 | n | 佔比 | 營收貢獻 |")
    parts.append("|---|---|---|---|---|---|---|---|")
    for p in profiles:
        parts.append(
            f"| #{p.cluster_id} | {p.mu_time_label} | {p.time_range_label} | NT$ {p.mu_spend:.0f} | "
            f"{p.spend_range_label} | {p.n_transactions} | {p.weight*100:.1f}% | NT$ {p.total_revenue_contribution_ntd:,} |"
        )
    parts.append("")

    parts.append("## 各 Cluster 詳細\n")
    for p in profiles:
        parts.append(f"### Cluster {p.cluster_id}: 時段中心 {p.mu_time_label}, 客單 NT$ {p.mu_spend:.0f}")
        parts.append(f"- **樣本數**: {p.n_transactions}({p.weight*100:.1f}% of total)")
        parts.append(f"- **時段範圍**: {p.time_range_label} (±1σ)")
        parts.append(f"- **客單範圍**: {p.spend_range_label} (±1σ)")
        parts.append(f"- **時段標準差**: {p.std_time_minutes:.1f} 分鐘")
        parts.append(f"- **客單標準差**: NT$ {p.std_spend:.1f}")
        parts.append(f"- **營收貢獻**: NT$ {p.total_revenue_contribution_ntd:,}")
        parts.append("")

    parts.append("---")
    parts.append("*純函式模式無 AI 客群命名與促銷策略。AI 模式會為每個 cluster 起客群名稱 + 推測購買行為 + 設計促銷策略。*")
    parts.append("*daypart 是分析工具,**不取代實際客戶訪談**。Cluster 假設只是統計分布,實際客群行為需現場觀察。*")
    return "\n".join(parts)


def render_full_report(records: list[Transaction], profiles: list[ClusterProfile],
                       bic_results: dict, best_k: int, n_iter: int, ai: dict) -> str:
    parts = ["# daypart 餐飲店一日銷售型態 EM 分群報告\n"]
    parts.append("**模式**: 純函式 EM + AI 行銷顧問\n")
    parts.append("## 資料概況\n")
    parts.append(f"- **transactions**: {len(records)} 筆 / **BIC 最佳 k**: {best_k}")
    parts.append("")

    parts.append("## BIC 模型選擇\n")
    parts.append("| k | Log-Likelihood | BIC |")
    parts.append("|---|---|---|")
    for r in bic_results['all_results']:
        marker = " ⭐" if r['k'] == best_k else ""
        parts.append(f"| {r['k']}{marker} | {r['log_likelihood']:.1f} | {r['bic']:.1f} |")
    parts.append("")

    ci_map = {ci['cluster_id']: ci for ci in ai.get("cluster_interpretations", [])}

    parts.append(f"## Customer Personas (k={best_k} clusters)\n")
    for p in profiles:
        ci = ci_map.get(p.cluster_id, {})
        persona_name = ci.get("persona_name", f"Cluster {p.cluster_id}")
        parts.append(f"### 🧍 {persona_name} — Cluster {p.cluster_id}")
        parts.append(f"- **時段中心**: {p.mu_time_label}({p.time_range_label})")
        parts.append(f"- **客單價**: NT$ {p.mu_spend:.0f}({p.spend_range_label})")
        parts.append(f"- **n**: {p.n_transactions}({p.weight*100:.1f}% of total)")
        parts.append(f"- **營收貢獻**: NT$ {p.total_revenue_contribution_ntd:,}")
        parts.append("")
        if ci.get("persona_description"):
            parts.append(f"**客群描述**: {ci['persona_description']}")
            parts.append("")
        if ci.get("likely_purchases"):
            parts.append("**可能購買**:")
            for item in ci["likely_purchases"]:
                parts.append(f"- {item}")
            parts.append("")
        promo = ci.get("promotion_strategy")
        if promo:
            parts.append(f"**促銷策略:{promo.get('title', '')}**")
            parts.append(f"- 細節: {promo.get('details', '')}")
            parts.append(f"- 預期效果: {promo.get('expected_impact', '')}")
            parts.append("")

    parts.append("## 整體經營洞察\n")
    for insight in ai.get("overall_insights", []):
        parts.append(f"- {insight}")
    parts.append("")
    parts.append("---")
    parts.append("*daypart 是分析工具,**不取代實際客戶訪談**。Cluster 假設只是統計分布,實際客群行為需現場觀察。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="daypart — 餐飲店一日銷售型態 EM 分群")
    p.add_argument("csv", help="transactions CSV (time, spend_ntd, weekday)")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--k", type=int, default=0, help="指定 cluster 數量(0 = BIC 自動選擇)")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    records = load_csv(args.csv)
    if len(records) < 20:
        print(f"⚠️ {len(records)} 筆 transactions 太少,EM 分群可能不穩定(建議 ≥ 100)")

    if args.k > 0:
        best_k = args.k
        clusters, n_iter, ll = fit_em(records, k=best_k)
        bic = bayesian_info_criterion(ll, len(records), best_k)
        bic_results = {"all_results": [{"k": best_k, "log_likelihood": round(ll, 2), "bic": round(bic, 2), "n_iter": n_iter}], "best_k": best_k, "best_bic": round(bic, 2)}
    else:
        bic_results = find_best_k(records)
        best_k = bic_results["best_k"]
        clusters, n_iter, ll = fit_em(records, k=best_k)

    assignments = assign_transactions(records, clusters)
    profiles = profile_clusters(records, clusters, assignments)

    if args.no_ai:
        report = render_no_ai_report(records, profiles, bic_results, best_k, n_iter)
    else:
        ai = ai_explain(profiles, best_k, bic_results, len(records))
        report = render_full_report(records, profiles, bic_results, best_k, n_iter, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
