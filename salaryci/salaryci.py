"""salaryci CLI — 台灣求職者薪資 conformal prediction interval.

Usage:
    python salaryci.py --profile samples/jobseeker.json
    python salaryci.py --profile samples/jobseeker.json --no-ai
    python salaryci.py --profile samples/jobseeker.json --alpha 0.20  # 80% CI
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from conformal import (
    JobseekerProfile, predict_interval, negotiation_anchors, ConformalResult,
)


def load_profile(path: Path) -> JobseekerProfile:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    valid = set(JobseekerProfile.__dataclass_fields__.keys())
    return JobseekerProfile(**{k: v for k, v in data.items() if k in valid})


def confidence_warning(result: ConformalResult) -> str | None:
    """Return a warning string if calibration set is small / unreliable."""
    n = result.calibration_set_size
    if n < 6:
        return f"⚠️ **calibration set 僅 {n} 筆** — 信心區間信賴度低。建議僅作參考,實際請多查 PTT Salary / 104 / 詢問前輩。"
    if n < 10:
        return f"ℹ️ calibration set {n} 筆 — 樣本中等,90% CI 為合理估計但可能稍寬。"
    return None


def render_no_ai(result: ConformalResult) -> str:
    p = result.profile
    anchors = negotiation_anchors(result)
    lines = [
        f"# salaryci 薪資談判 conformal prediction 報告",
        "",
        f"**求職者**: {p.name}",
        f"**目標職位**: {p.industry} / {p.role_family} / {p.level} / {p.exp_years} 年經驗 / {p.location}",
        "",
        "## 🎯 90% 信心區間 (conformal prediction interval)",
        "",
        f"### NT$ **{result.lower_ci_ntd_k:.0f} K — {result.upper_ci_ntd_k:.0f} K** / 月",
        "",
        f"- **中位數估計**: NT${result.median_estimate_ntd_k:.0f}K / 月",
        f"- **nonconformity quantile q**: {result.nonconformity_quantile} (90% 殘差)",
        f"- **CI 寬度**: ±NT${result.nonconformity_quantile:.0f}K (相當於 ±{result.nonconformity_quantile / result.median_estimate_ntd_k * 100:.0f}%)",
        f"- **覆蓋率保證**: 在交換性 (exchangeability) 假設下,真實薪資落入此區間機率 ≥ {result.confidence_level:.0%}",
        "",
        "## Calibration Set (純函式 nearest-cluster 比對)",
        "",
        f"- **匹配筆數**: {result.calibration_set_size} 筆同質性記錄",
        f"- **過濾條件**: `{result.calibration_filter}`",
        f"- **corpus 分布**: P10={result.p10_corpus:.0f}K, P50={result.p50_corpus:.0f}K, P90={result.p90_corpus:.0f}K",
        f"- **排序的殘差**: {result.raw_residuals}",
        "",
    ]
    warning = confidence_warning(result)
    if warning:
        lines.append(warning)
        lines.append("")

    if p.current_offer_ntd_k is not None:
        lines.extend([
            "## 你的 offer 在 corpus 中的位置",
            "",
            f"- **目前 offer**: NT${p.current_offer_ntd_k}K / 月",
            f"- **vs 中位數**: {result.offer_vs_median_pct:+.1f}%",
            f"- **在 calibration set 中**: 第 {result.offer_position_pct:.0f} 百分位",
        ])
        # 判讀
        if result.offer_position_pct < 25:
            lines.append("- 🔴 **顯著低於行情** — 有強烈空間 push 上去")
        elif result.offer_position_pct < 45:
            lines.append("- 🟡 **偏行情下緣** — 可以爭取到 median 附近")
        elif result.offer_position_pct < 70:
            lines.append("- 🟢 **接近行情中段** — 可微調 5-10% 試 push")
        else:
            lines.append("- 🟦 **已在行情上緣** — 爭取空間有限,可改談非薪資 (RSU / 簽約金 / 年假 / WFH)")
        lines.append("")

    lines.extend([
        "## 純函式談判錨點",
        "",
        f"- **walk-away (90% CI 下限)**: NT${anchors['walk_away_ntd_k']:.0f}K — 低於此可直接 walk away",
        f"- **median anchor**: NT${anchors['median_anchor_ntd_k']:.0f}K — 對方第一次出價這個算合理",
        f"- **aim for (median 與上限之間)**: NT${anchors['aim_for_ntd_k']:.0f}K — 你的目標應該瞄這裡",
        f"- **stretch target (90% CI 上限)**: NT${anchors['stretch_target_ntd_k']:.0f}K — 對方真的喜歡你會給到這",
        "",
        "## ⚠️ 模型限制",
        "",
        "- **不含 bonus / RSU / 簽約金 / 加班費** — 只看月薪 base",
        "- **calibration set 是 prototype 樣本** — 真實 launch 版會用 1,000+ 筆 PTT Salary + 104 + Yourator 資料",
        "- **conformal coverage 是邊際 (marginal)**,個別案件可能落 CI 外 — 但長期 90% 群體會落內",
        "- **交換性假設**: 假設樣本與你 i.i.d.,如果你有特殊背景(海外名校 / 大廠出身 / 特定證照),CI 會偏低估",
        "",
        "---",
        "*salaryci = conformal prediction × 台灣薪資談判 = 信心區間 +談判錨點 而非單一中位數猜測。*",
    ])
    return "\n".join(lines)


def render_with_ai(result: ConformalResult) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(result)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(result)

    base = render_no_ai(result)
    p = result.profile
    anchors = negotiation_anchors(result)

    facts = f"""
profile: {p.industry} {p.role_family} {p.level} {p.exp_years}y {p.location}
90% CI: NT${result.lower_ci_ntd_k:.0f}K - NT${result.upper_ci_ntd_k:.0f}K
median: NT${result.median_estimate_ntd_k:.0f}K
calibration set: {result.calibration_set_size} 筆 ({result.calibration_filter})
offer: {'NT$' + str(p.current_offer_ntd_k) + 'K' if p.current_offer_ntd_k else '尚未收到'}
offer position: {str(result.offer_position_pct) + 'th percentile' if result.offer_position_pct is not None else 'N/A'}
walk-away: NT${anchors['walk_away_ntd_k']:.0f}K
aim-for: NT${anchors['aim_for_ntd_k']:.0f}K
stretch: NT${anchors['stretch_target_ntd_k']:.0f}K
"""

    prompt = f"""你是一位資深台灣 HR / 獵頭顧問。下面是基於 conformal prediction 算出的薪資談判數字 (純函式算出, 不能改):

{facts.strip()}

請寫一段 150-220 字的「談判腳本」, 內容包括:
1. 解讀 offer 在區間的相對位置 (告訴求職者「行情上」是好還是不好)
2. **具體的對話開場**(寫出 1-2 句該怎麼跟 HR 講, 引用具體數字)
3. 非薪資談判槓桿提醒 (RSU / 簽約金 / 年假 / 試用期 / WFH 政策)
4. 1 個風險提醒 (例如 不要一接就 push / 公司現金流 / 撤回 offer 機率)

**規則**:
- 不要重新算數字, 直接引用 facts
- 不要套話 ("加油", "祝順利")
- 不要寫超過 220 字
- 不要 markdown 標題

直接寫談判腳本。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 獵頭談判腳本\n\n" + resp.content[0].text + "\n"


def main():
    parser = argparse.ArgumentParser(description="salaryci — 薪資談判 conformal CI")
    parser.add_argument("--profile", default="samples/jobseeker.json")
    parser.add_argument("--alpha", type=float, default=0.10,
                        help="顯著性 (預設 0.10 = 90% CI)")
    parser.add_argument("--no-ai", action="store_true")
    args = parser.parse_args()

    profile = load_profile(Path(args.profile))
    result = predict_interval(profile, alpha=args.alpha)

    if args.no_ai:
        print(render_no_ai(result))
    else:
        print(render_with_ai(result))


if __name__ == "__main__":
    main()
