"""liftlab — 行銷投放真實因果 ROI CLI (Pearl backdoor adjustment).

純函式做所有因果計算(causal.py)。LLM 只負責:
  ① 用老闆易懂的話解釋「naive 跟 adjusted 的差別」
  ② 把 confounder bias decomposition 翻成「為什麼你之前以為廣告很有效」的故事
  ③ 給「下一步該怎麼做」具體建議(增加 ad budget?保持?減少?換 channel?)

LLM 永不算 ATE / 機率 / 任何 NT$ 數字。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from causal import (
    CONFOUNDER_NAMES,
    CausalAnalysis,
    ConfounderBias,
    HIGH_AD_THRESHOLD,
    MonthlyRecord,
    analyze,
    load_csv,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣 SME 行銷顧問,專長因果推斷(Pearl backdoor adjustment)。

    輸入:
      - 24 個月行銷 + 營收資料的純函式因果分析(naive ATE / adjusted ATE /
        confounder bias decomposition / inflation factor / verdict)

    工作:
      1. 用老闆易懂的話解釋(< 200 字):
         - 為什麼 naive 估計 NT$X/月跟真實因果 NT$Y/月差這麼多
         - 用故事 framing:「您過去以為廣告月多賺 NT$X,實際只有 NT$Y;
           另外 NT$(X-Y) 是季節 / 節慶 / 新品這些『會自己發生』的事貢獻的」
      2. Confounder 拆解:用 1-2 句把每個 confounder 的 bias 翻成人話
      3. 4-5 條「下一步該怎麼做」具體建議:
         - 是否該繼續維持當前 ad budget(看真實 ATE 是否合理 ROI)
         - 是否該在 ad budget 之外**加碼 confounder 月份**的策略
         - 是否該做「淡季時更激進測試」收集更多 control 資料
         - 是否該轉換廣告 channel(IG / FB / Google 比較)
      4. 警示:純函式只用 3 個 confounders,真實還有(對手活動 / 經濟景氣 /
         天氣 / 媒體報導 / 口碑)沒抓進來

    硬規則:
      - 你**絕不**重算 ATE / NT$ — 全部從 analysis 結果直接引用
      - 不勸老闆「立刻停止廣告」 — adjusted ATE 雖低但仍可能正
      - 不勸「無條件加倍 budget」 — 邊際 ROI 不一定線性
      - 用台灣繁體中文 + 在地用語(投放 / 旺季 / 雙 11 / 母親節 / 新品)

    回覆 JSON:
    {
      "executive_summary": "200 字以內故事化解釋",
      "confounder_interpretations": [
        {"name": "is_peak_season", "human_label": "旺季", "explanation": "...", "magnitude_ntd": ...},
        ...
      ],
      "true_causal_roi": {
        "real_ate_per_month": ...,
        "avg_monthly_ad_spend_when_high": ...,
        "estimated_roi_multiplier": ...,
        "reasoning": "..."
      },
      "action_recommendations": [
        {"priority": 1, "category": "budget", "action": "...", "expected_impact": "..."},
        ...
      ],
      "important_caveats": ["..."]
    }
""").strip()


def ai_explain(records: list[MonthlyRecord], analysis: CausalAnalysis) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "n_months": len(records),
        "high_ad_threshold_ntd": HIGH_AD_THRESHOLD,
        "naive": {
            "ate": analysis.naive.naive_ate,
            "n_treated": analysis.naive.n_treated,
            "n_control": analysis.naive.n_control,
            "mean_revenue_treated": analysis.naive.mean_revenue_treated,
            "mean_revenue_control": analysis.naive.mean_revenue_control,
        },
        "adjusted": {
            "ate": analysis.adjusted.adjusted_ate,
            "n_valid_strata": analysis.adjusted.n_valid_strata,
            "valid_strata": [
                {
                    "key": [
                        f"{name}={val}" for name, val in zip(CONFOUNDER_NAMES, s.stratum_key)
                    ],
                    "n_treated": s.n_treated,
                    "n_control": s.n_control,
                    "stratum_ate": s.stratum_ate,
                    "weight": s.weight,
                }
                for s in analysis.adjusted.strata if s.stratum_ate is not None
            ],
        },
        "inflation_factor": analysis.inflation_factor,
        "confounder_bias": [
            {
                "name": c.confounder,
                "prevalence_diff": c.prevalence_diff,
                "estimated_bias_ntd": c.estimated_bias_ntd,
                "interpretation": c.interpretation,
            }
            for c in analysis.bias_decomp
        ],
        "verdict": analysis.verdict,
        "avg_monthly_ad_spend_when_high": int(sum(r.ad_spend_ntd for r in records if r.ad_spend_ntd >= HIGH_AD_THRESHOLD)
                                              / max(1, sum(1 for r in records if r.ad_spend_ntd >= HIGH_AD_THRESHOLD))),
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


CONFOUNDER_LABEL_ZH = {
    "is_peak_season": "旺季",
    "is_holiday_promo": "節慶 / 大檔促銷",
    "launched_new_product": "新品上市",
}


def _stratum_label(key: tuple[bool, bool, bool]) -> str:
    peak, hol, nprod = key
    parts = []
    parts.append("旺季" if peak else "淡季")
    parts.append("有檔期" if hol else "無檔期")
    parts.append("有新品" if nprod else "無新品")
    return " / ".join(parts)


def render_no_ai_report(records: list[MonthlyRecord], a: CausalAnalysis) -> str:
    parts = ["# liftlab 行銷 ROI 因果分析報告\n"]
    parts.append("**模式**: 純函式 Pearl backdoor adjustment(免 API key)\n")
    parts.append(f"## 資料概況\n")
    parts.append(f"- **月度資料**: {len(records)} 個月")
    parts.append(f"- **Treatment 定義**: ad_spend ≥ NT$ {HIGH_AD_THRESHOLD:,}(以下稱「高 ads 月」)")
    parts.append(f"- **Confounders(共因)**: 旺季、節慶 / 大檔促銷、新品上市")
    parts.append("")

    parts.append("## 1. Naive 估計(老闆通常會這樣想)\n")
    parts.append(f"- 高 ads 月平均營收: **NT$ {a.naive.mean_revenue_treated:,}** ({a.naive.n_treated} 個月)")
    parts.append(f"- 低 ads 月平均營收: **NT$ {a.naive.mean_revenue_control:,}** ({a.naive.n_control} 個月)")
    parts.append(f"- **Naive ATE**: NT$ {a.naive.naive_ate:,} / 月")
    parts.append(f"- 看起來廣告每月多賺 NT$ {a.naive.naive_ate:,},但這**包含 confounders 偏差**。")
    parts.append("")

    parts.append("## 2. Backdoor-adjusted 估計(真實因果)\n")
    parts.append(f"- **Adjusted ATE**: **NT$ {a.adjusted.adjusted_ate:,} / 月**")
    parts.append(f"- **Inflation factor**(naïve / adjusted): **{a.inflation_factor}x**")
    parts.append(f"- **可用 strata**: {a.adjusted.n_valid_strata} / 8")
    parts.append("")
    parts.append("### 各 stratum 細節\n")
    parts.append("| 情境 | n (T+C) | T mean | C mean | Stratum ATE | weight |")
    parts.append("|---|---|---|---|---|---|")
    for s in a.adjusted.strata:
        if s.stratum_ate is None:
            continue
        label = _stratum_label(s.stratum_key)
        parts.append(f"| {label} | {s.n_treated}+{s.n_control} | NT$ {s.mean_revenue_treated:,} | NT$ {s.mean_revenue_control:,} | NT$ {s.stratum_ate:,} | {s.weight} |")
    parts.append("")

    parts.append("## 3. Confounder Bias 拆解\n")
    parts.append("Naive ATE 比 Adjusted ATE 多出 NT$ {} 的偏差,由以下 confounders 貢獻:".format(a.naive.naive_ate - a.adjusted.adjusted_ate))
    parts.append("")
    parts.append("| Confounder | 偏差 NT$ | 解釋 |")
    parts.append("|---|---|---|")
    for c in a.bias_decomp:
        zh = CONFOUNDER_LABEL_ZH.get(c.confounder, c.confounder)
        parts.append(f"| {zh} | {c.estimated_bias_ntd:+,} | {c.interpretation[:80]}... |")
    parts.append("")
    parts.append("> ⚠️ 因為 confounders 彼此相關(旺季常含節慶),個別 bias 加總**不等於**總 inflation。")
    parts.append("")

    parts.append("## 4. 純函式結論\n")
    parts.append(a.verdict)
    parts.append("")
    parts.append("---")
    parts.append("*純函式模式無 AI 行銷建議。AI 模式會給故事化解釋 + 4-5 條具體 action items。*")
    parts.append("*liftlab 提供因果推斷指引,不取代行銷顧問。實際決策請結合產業經驗。*")
    return "\n".join(parts)


def render_full_report(records: list[MonthlyRecord], a: CausalAnalysis, ai: dict) -> str:
    parts = ["# liftlab 行銷 ROI 因果分析報告\n"]
    parts.append("**模式**: 純函式 Pearl backdoor adjustment + AI 行銷顧問\n")

    parts.append("## Executive Summary\n")
    parts.append(ai.get("executive_summary", ""))
    parts.append("")

    parts.append("## 數字 at a glance\n")
    parts.append(f"- **Naïve ATE(老闆通常的看法)**: NT$ {a.naive.naive_ate:,} / 月")
    parts.append(f"- **真實因果 ATE(backdoor-adjusted)**: NT$ {a.adjusted.adjusted_ate:,} / 月")
    parts.append(f"- **Inflation factor**: {a.inflation_factor}x(naive 高估 {a.inflation_factor:.1f} 倍)")
    parts.append(f"- **可用 strata**: {a.adjusted.n_valid_strata} / 8")
    parts.append("")

    parts.append("## 各 stratum 細節(純函式)\n")
    parts.append("| 情境 | n (T+C) | T mean | C mean | Stratum ATE | weight |")
    parts.append("|---|---|---|---|---|---|")
    for s in a.adjusted.strata:
        if s.stratum_ate is None:
            continue
        label = _stratum_label(s.stratum_key)
        parts.append(f"| {label} | {s.n_treated}+{s.n_control} | NT$ {s.mean_revenue_treated:,} | NT$ {s.mean_revenue_control:,} | NT$ {s.stratum_ate:,} | {s.weight} |")
    parts.append("")

    parts.append("## Confounder 影響(AI 翻譯)\n")
    for c in ai.get("confounder_interpretations", []):
        parts.append(f"### {c.get('human_label', c.get('name'))}")
        parts.append(f"- **估計 bias**: NT$ {c.get('magnitude_ntd', 0):+,}")
        parts.append(f"- {c.get('explanation', '')}")
        parts.append("")

    if ai.get("true_causal_roi"):
        roi = ai["true_causal_roi"]
        parts.append("## 真實 ROI 計算\n")
        parts.append(f"- **真實 ATE**: NT$ {roi.get('real_ate_per_month', 0):,} / 月")
        parts.append(f"- **平均高 ads 月支出**: NT$ {roi.get('avg_monthly_ad_spend_when_high', 0):,} / 月")
        parts.append(f"- **真實 ROI 倍數**: {roi.get('estimated_roi_multiplier', 0)}x")
        parts.append(f"- {roi.get('reasoning', '')}")
        parts.append("")

    parts.append("## 具體行動建議\n")
    for item in ai.get("action_recommendations", []):
        parts.append(f"### #{item.get('priority', '?')} [{item.get('category', '')}] {item.get('action', '')}")
        parts.append(f"- **預期影響**: {item.get('expected_impact', '')}")
        parts.append("")

    if ai.get("important_caveats"):
        parts.append("## ⚠️ 重要 caveats\n")
        for c in ai["important_caveats"]:
            parts.append(f"- {c}")
        parts.append("")

    parts.append("---")
    parts.append("*liftlab 提供因果推斷指引,不取代行銷顧問。本分析僅控制 3 個 confounders(旺季 / 節慶 / 新品);真實還有對手活動 / 經濟景氣 / 天氣 / 媒體報導 / 口碑等未抓進來。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="liftlab — 行銷投放真實因果 ROI 分析")
    p.add_argument("csv", help="月度資料 CSV (month, ad_spend_ntd, revenue_ntd, is_peak_season, is_holiday_promo, launched_new_product)")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    records = load_csv(args.csv)
    if len(records) < 12:
        print(f"⚠️ 警告:資料 {len(records)} 個月太短,backdoor adjustment 可能不穩定 (建議 ≥ 24 個月)")

    a = analyze(records)

    if args.no_ai:
        report = render_no_ai_report(records, a)
    else:
        ai = ai_explain(records, a)
        report = render_full_report(records, a, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
