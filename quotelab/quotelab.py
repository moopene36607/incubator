"""quotelab — SOHO / 自由工作者報價策略 Multi-armed Bandit CLI.

純函式做 bandit 計算 (bandit.py)。LLM 負責:
  ① 對推薦 tier 的「為什麼」做人話解釋
  ② 給配套建議(報價文案 / 議價 / 額外服務)
  ③ 對 explorer 不足的 tier 提建議:該不該主動探索
  ④ 整體報價策略洞察(哪個 case_type 最賺 / 該不該換領域)

LLM 永不算 EV / 機率(那是 bandit 工作)。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from bandit import (
    ArmStats,
    PortfolioSummary,
    QuoteRecord,
    TIER_LABEL_ZH,
    TIER_PRICES_BY_CASE_TYPE,
    TierRecommendation,
    compute_arm_stats,
    compute_portfolio_summary,
    thompson_sample_recommendation,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣 SOHO / 自由工作者報價策略顧問。

    輸入:
      - freelancer 過去報價歷史(case_type / tier_quoted / accepted)
      - 純函式 Thompson Sampling 推薦結果(各 case_type 推薦的 tier)
      - 新 case 描述

    工作:
      1. 為新 case 寫 100-150 字「為什麼這 tier 是好選擇」:
         - 引用具體歷史接受率 + 期望收益
         - 提及客戶 size(小餐廳 vs 中型零售)如何影響
      2. 給「**報價策略**」(報價文案的暖開場 + 議價底線):
         - 報價單怎麼寫(包含什麼項目)
         - 預設議價空間 5-10%
         - 客戶若殺價多少要走人
      3. 給「**配套建議**」(增加成交率的非價格 lever):
         - Portfolio 案例 reference
         - 分期付款 / 訂金 35-50%
         - 提供 1-2 個 mockup 預覽
      4. **Exploration 建議**:對樣本不足的 tier(<5 筆)建議「該不該主動試」
      5. **長期策略**:看 portfolio 哪個 case_type 最賺 / 該不該深耕該領域

    硬規則:
      - 你**絕不**重算 EV / 接受率 — 直接引用 bandit 結果
      - 不勸 freelancer「永遠報最高 tier」(忽略長期 reputation)
      - 不鼓勵「故意報太低撈 client review」(短視)
      - 用台灣 SOHO / freelancer 在地用語(報價單 / 議價 / 接案平台)

    回覆 JSON:
    {
      "recommended_tier_explanation": "...",
      "quoting_strategy": {
        "opening_pitch": "...",
        "include_in_quote": ["...", "..."],
        "negotiation_floor": "...",
        "walk_away_price": ...
      },
      "non_price_levers": ["...", "..."],
      "exploration_suggestions": ["...", "..."],
      "long_term_strategy": "..."
    }
""").strip()


def ai_explain(history: list[QuoteRecord], rec: TierRecommendation,
                portfolio: PortfolioSummary, new_case: dict) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "new_case": new_case,
        "recommendation": {
            "tier": rec.recommended_tier,
            "tier_zh": TIER_LABEL_ZH.get(rec.recommended_tier, rec.recommended_tier),
            "price_ntd": rec.recommended_price,
            "expected_revenue_ntd": rec.expected_revenue,
            "expected_accept_prob": rec.expected_accept_prob,
            "confidence_score": rec.confidence_score,
            "rationale": rec.rationale,
            "runner_up_tier": rec.runner_up_tier,
            "runner_up_expected_revenue": rec.runner_up_expected_revenue,
        },
        "arm_stats": [
            {
                "tier": s.tier,
                "price": s.representative_price,
                "n_quoted": s.n_quoted,
                "accept_prob_mean": s.accept_prob_mean,
                "expected_revenue": s.expected_revenue,
            }
            for s in rec.arm_stats
        ],
        "portfolio": {
            "n_total_quotes": portfolio.n_total_quotes,
            "n_accepted": portfolio.n_accepted,
            "overall_acceptance_rate": portfolio.overall_acceptance_rate,
            "total_revenue_actual_ntd": portfolio.total_revenue_actual_ntd,
            "most_profitable_case_type": portfolio.most_profitable_case_type,
            "underutilized_warnings": portfolio.underutilized_tier_warning,
        },
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


def render_no_ai_report(history: list[QuoteRecord], rec: TierRecommendation,
                         portfolio: PortfolioSummary, new_case: dict, freelancer_info: dict) -> str:
    parts = ["# quotelab 報價策略 Multi-armed Bandit 報告\n"]
    parts.append("**模式**: 純函式 Thompson Sampling(免 API key)\n")
    parts.append("## 自由工作者 Portfolio\n")
    parts.append(f"- **Freelancer**: {freelancer_info.get('name', '匿名')}")
    parts.append(f"- **專長**: {' / '.join(freelancer_info.get('specialty', []))}")
    parts.append(f"- **接案年資**: {freelancer_info.get('years_freelancing', 0)} 年")
    parts.append(f"- **目標月收**: NT$ {freelancer_info.get('monthly_income_target_ntd', 0):,}")
    parts.append(f"- **歷史報價**: {portfolio.n_total_quotes} 筆 / 成交: {portfolio.n_accepted}({portfolio.overall_acceptance_rate*100:.1f}%)")
    parts.append(f"- **歷史實收**: NT$ {portfolio.total_revenue_actual_ntd:,}")
    parts.append(f"- **最賺領域**: {portfolio.most_profitable_case_type} (NT$ {portfolio.most_profitable_revenue:,})")
    parts.append("")

    parts.append("## 新 case\n")
    parts.append(f"- **Case ID**: {new_case.get('case_id', '')}")
    parts.append(f"- **類型**: {new_case.get('case_type', '')}")
    parts.append(f"- **描述**: {new_case.get('description', '')}")
    parts.append(f"- **客戶 size**: {new_case.get('client_size_hint', '')}")
    parts.append(f"- **截止**: {new_case.get('deadline_days', 0)} 天")
    parts.append("")

    parts.append(f"## Thompson Sampling 推薦 tier\n")
    parts.append(f"- **推薦 tier**: **{rec.recommended_tier}** ({TIER_LABEL_ZH.get(rec.recommended_tier, '')})")
    parts.append(f"- **建議報價**: **NT$ {rec.recommended_price:,}**")
    parts.append(f"- **期望接受率**: {rec.expected_accept_prob*100:.1f}%")
    parts.append(f"- **期望收益(EV)**: NT$ {rec.expected_revenue:,.0f}")
    parts.append(f"- **信心度**: {rec.confidence_score*100:.1f}%(在 1000 次 Thompson sampling 中該 tier 勝出比例)")
    parts.append(f"- **第 2 名 tier**: {rec.runner_up_tier} (EV NT$ {rec.runner_up_expected_revenue:,.0f})")
    parts.append("")
    parts.append(f"**推薦理由**: {rec.rationale}\n")

    parts.append(f"## {new_case.get('case_type', '')} 各 tier 表現\n")
    parts.append("| Tier | 報價 | n_quoted | 接受率(均) | 95% CI | 期望收益 |")
    parts.append("|---|---|---|---|---|---|")
    for s in rec.arm_stats:
        ci = f"[{s.accept_prob_lower95*100:.0f}-{s.accept_prob_upper95*100:.0f}%]"
        marker = " ⭐" if s.tier == rec.recommended_tier else ""
        parts.append(
            f"| {TIER_LABEL_ZH.get(s.tier, s.tier)}{marker} | NT$ {s.representative_price:,} | {s.n_quoted} | "
            f"{s.accept_prob_mean*100:.1f}% | {ci} | NT$ {s.expected_revenue:,.0f} |"
        )
    parts.append("")

    if portfolio.underutilized_tier_warning:
        parts.append("## ⚠️ Exploration warnings(樣本不足的 tier)\n")
        for w in portfolio.underutilized_tier_warning[:8]:
            parts.append(f"- {w}")
        parts.append("")

    parts.append("---")
    parts.append("*純函式模式無 AI 配套策略。AI 模式會給報價文案開場 + 議價底線 + 配套建議 + 長期策略。*")
    parts.append("*quotelab 是輔助工具,最終報價決策由 freelancer 自行判斷;市場價格隨時變動需定期 calibrate。*")
    return "\n".join(parts)


def render_full_report(history: list[QuoteRecord], rec: TierRecommendation,
                       portfolio: PortfolioSummary, new_case: dict,
                       freelancer_info: dict, ai: dict) -> str:
    parts = ["# quotelab 報價策略 Multi-armed Bandit 報告\n"]
    parts.append("**模式**: 純函式 Thompson Sampling + AI 報價顧問\n")
    parts.append("## Freelancer Portfolio\n")
    parts.append(f"- {freelancer_info.get('name', '匿名')} / 專長: {' / '.join(freelancer_info.get('specialty', []))}")
    parts.append(f"- 歷史 {portfolio.n_total_quotes} 報價 / 成交 {portfolio.n_accepted}({portfolio.overall_acceptance_rate*100:.1f}%)")
    parts.append(f"- 實收 NT$ {portfolio.total_revenue_actual_ntd:,}")
    parts.append("")

    parts.append("## 新 case\n")
    parts.append(f"> **{new_case.get('case_type', '')}** — {new_case.get('description', '')}")
    parts.append(f"> 客戶 size: {new_case.get('client_size_hint', '')} / 截止: {new_case.get('deadline_days', 0)} 天")
    parts.append("")

    parts.append("## 🎯 Bandit 推薦\n")
    parts.append(f"- **建議報價 tier**: **{rec.recommended_tier}** ({TIER_LABEL_ZH.get(rec.recommended_tier, '')})")
    parts.append(f"- **建議金額**: **NT$ {rec.recommended_price:,}**")
    parts.append(f"- **期望接受率**: {rec.expected_accept_prob*100:.1f}% / **期望收益**: NT$ {rec.expected_revenue:,.0f}")
    parts.append(f"- **信心度**: {rec.confidence_score*100:.1f}%")
    parts.append("")

    if ai.get("recommended_tier_explanation"):
        parts.append("### 為什麼這 tier 是好選擇\n")
        parts.append(ai["recommended_tier_explanation"])
        parts.append("")

    parts.append("## 報價策略\n")
    qs = ai.get("quoting_strategy", {})
    if qs.get("opening_pitch"):
        parts.append(f"### 開場 pitch\n")
        parts.append(qs["opening_pitch"])
        parts.append("")
    if qs.get("include_in_quote"):
        parts.append("### 報價單應包含\n")
        for item in qs["include_in_quote"]:
            parts.append(f"- {item}")
        parts.append("")
    if qs.get("negotiation_floor"):
        parts.append(f"### 議價底線\n{qs['negotiation_floor']}\n")
    if qs.get("walk_away_price") is not None:
        parts.append(f"**Walk-away 價**: NT$ {qs['walk_away_price']:,}")
        parts.append("")

    if ai.get("non_price_levers"):
        parts.append("## 非價格 levers(提升成交率)\n")
        for lever in ai["non_price_levers"]:
            parts.append(f"- {lever}")
        parts.append("")

    parts.append(f"## {new_case.get('case_type', '')} 各 tier bandit 表現\n")
    parts.append("| Tier | 報價 | n | 接受率 | EV |")
    parts.append("|---|---|---|---|---|")
    for s in rec.arm_stats:
        marker = " ⭐" if s.tier == rec.recommended_tier else ""
        parts.append(
            f"| {TIER_LABEL_ZH.get(s.tier, s.tier)}{marker} | NT$ {s.representative_price:,} | {s.n_quoted} | "
            f"{s.accept_prob_mean*100:.1f}% | NT$ {s.expected_revenue:,.0f} |"
        )
    parts.append("")

    if ai.get("exploration_suggestions"):
        parts.append("## 🧪 Exploration 建議\n")
        for s in ai["exploration_suggestions"]:
            parts.append(f"- {s}")
        parts.append("")

    if ai.get("long_term_strategy"):
        parts.append("## 📈 長期策略\n")
        parts.append(ai["long_term_strategy"])
        parts.append("")

    parts.append("---")
    parts.append("*quotelab 是輔助工具,最終報價決策由 freelancer 自行判斷;市場價格隨時變動需定期 calibrate。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="quotelab — SOHO 報價策略 Multi-armed Bandit")
    p.add_argument("json_path", help="quote_history.json")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    history = [QuoteRecord(**r) for r in data["history"]]
    new_case = data.get("new_case_query", {})
    freelancer_info = data.get("freelancer_info", {})

    case_type = new_case.get("case_type", "LOGO_DESIGN")
    rec = thompson_sample_recommendation(history, case_type, n_samples=1000, seed=42)
    portfolio = compute_portfolio_summary(history)

    if args.no_ai:
        report = render_no_ai_report(history, rec, portfolio, new_case, freelancer_info)
    else:
        ai = ai_explain(history, rec, portfolio, new_case)
        report = render_full_report(history, rec, portfolio, new_case, freelancer_info, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
