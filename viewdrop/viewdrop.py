"""viewdrop CLI — 自媒體創作者每日 metric BOCPD 流量斷點偵測。

Usage:
    python viewdrop.py --creator samples/youtuber.json --no-ai
    python viewdrop.py --creator samples/youtuber.json --metric subscriptions
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from bocpd import run_bocpd, estimate_obs_sigma, BOCPDResult


def load_creator(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_date(creator: dict, idx: int) -> str:
    """Map index → ISO date."""
    dates = creator.get("dates")
    if dates and idx < len(dates):
        return dates[idx]
    return f"day {idx}"


METRIC_LABEL_ZH = {
    "views": "每日觀看數",
    "subscriptions": "每日訂閱數變化",
    "engagement_rate": "每日互動率",
    "watch_time": "每日觀看時間 (秒)",
    "ctr": "點擊率 (CTR)",
}


def render_no_ai(creator: dict, metric: str, result: BOCPDResult, sigma: float) -> str:
    timeseries = creator["metrics"][metric]
    label = METRIC_LABEL_ZH.get(metric, metric)
    lines = [
        f"# viewdrop — {creator['creator_name']} {label} BOCPD 斷點偵測報告",
        "",
        f"**頻道**: {creator['channel_url']}  ·  **平台**: {creator['platform']}",
        f"**追蹤指標**: `{metric}` ({label})",
        f"**時間範圍**: {fmt_date(creator, 0)} → {fmt_date(creator, len(timeseries) - 1)} ({len(timeseries)} 天)",
        f"**估計噪音 σ**: {sigma}",
        f"**hazard λ** (預期段長): {creator.get('hazard_lambda', 30)}",
        "",
        "## 🎯 BOCPD 偵測結果",
        "",
    ]
    if not result.changepoints:
        lines.append("### ✅ 沒有顯著斷點 — 數據在觀察期內可視為單一 stable segment")
        lines.append("")
        lines.append(f"- 全期 mean: {result.segment_summaries[0]['mean']}, std: {result.segment_summaries[0]['std']}")
    else:
        lines.append(f"### 🔴 偵測到 {len(result.changepoints)} 個斷點")
        lines.append("")
        lines.append("| 斷點 | 日期 | 之前 mean | 之後 mean | 變化 |")
        lines.append("|---|---|---|---|---|")
        for cp_idx in result.changepoints:
            cp_date = fmt_date(creator, cp_idx)
            before = next((s for s in result.segment_summaries if s["end_idx"] + 1 == cp_idx), None)
            after = next((s for s in result.segment_summaries if s["start_idx"] == cp_idx), None)
            if before and after:
                delta = after["mean"] - before["mean"]
                delta_pct = (delta / before["mean"] * 100) if before["mean"] != 0 else 0
                arrow = "📉" if delta < 0 else "📈"
                lines.append(f"| `t={cp_idx}` | {cp_date} | {before['mean']:.0f} | {after['mean']:.0f} | {arrow} {delta:+.0f} ({delta_pct:+.1f}%) |")

        if result.most_likely_changepoint is not None:
            lines.append("")
            lines.append(f"### ⭐ **最可能的關鍵斷點**: t={result.most_likely_changepoint} ({fmt_date(creator, result.most_likely_changepoint)})")
            lines.append("")
            lines.append(f"- **confidence**: {result.most_likely_cp_confidence}")
            lines.append(f"- BOCPD posterior 在這天明顯指向 run-length reset")

    lines.append("")
    lines.append("## 各 segment 摘要")
    lines.append("")
    lines.append("| Segment | 起始 | 結束 | 天數 | mean | std | min-max |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, s in enumerate(result.segment_summaries):
        lines.append(
            f"| #{i + 1} | {fmt_date(creator, s['start_idx'])} | {fmt_date(creator, s['end_idx'])} | "
            f"{s['n']} | {s['mean']:.0f} | {s['std']:.0f} | {s['min']:.0f}-{s['max']:.0f} |"
        )

    lines.append("")
    lines.append("## MAP run-length 軌跡 (每 5 天取樣)")
    lines.append("")
    lines.append("```")
    for t in range(0, len(timeseries), 5):
        bar = "█" * min(40, result.map_run_lengths[t] // 2)
        lines.append(f"t={t:2d} ({fmt_date(creator, t)}): r={result.map_run_lengths[t]:3d} {bar}")
    lines.append("```")

    lines.append("")
    lines.append("## ⚠️ BOCPD 模型假設與限制")
    lines.append("")
    lines.append("- **Gaussian likelihood 假設**: 假設 segment 內觀測 ~ N(μ_segment, σ²),極端值會稀釋偵測力")
    lines.append("- **hazard λ 是先驗**: λ=30 代表「平均每 30 天有 1 個斷點」;若實際更頻繁或更稀疏需手動調整")
    lines.append("- **單變數模型**: 只看一個 metric;views vs subs vs CTR 同時看會增強信號 (Pro 版多變數 BOCPD)")
    lines.append("- **演算法不告訴你為什麼**: BOCPD 只說「哪天斷的」,**原因要靠你 trace back** (演算法改 / 標題改 / 競品開頻道 / 季節)")
    lines.append("")
    lines.append("---")
    lines.append("*viewdrop = Adams & MacKay 2007 BOCPD × 自媒體 daily metric niche = 從感覺『流量好像怪怪』升級到「精準到天的斷點 + 原因 trace」。*")
    return "\n".join(lines)


def render_with_ai(creator: dict, metric: str, result: BOCPDResult, sigma: float) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(creator, metric, result, sigma)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(creator, metric, result, sigma)

    base = render_no_ai(creator, metric, result, sigma)

    cp_info = ""
    if result.most_likely_changepoint is not None:
        cp_idx = result.most_likely_changepoint
        before = next((s for s in result.segment_summaries if s["end_idx"] + 1 == cp_idx), None)
        after = next((s for s in result.segment_summaries if s["start_idx"] == cp_idx), None)
        if before and after:
            cp_info = f"changepoint t={cp_idx} ({fmt_date(creator, cp_idx)}): before mean {before['mean']} → after mean {after['mean']} (Δ {after['mean'] - before['mean']:+.0f})"

    prompt = f"""你是一位資深台灣自媒體 / 創作者顧問。下面是用 BOCPD (Bayesian Online Changepoint Detection) 純函式偵測的結果(數字 100% 算好,你不能改):

頻道: {creator['creator_name']} ({creator['platform']})
追蹤指標: {METRIC_LABEL_ZH.get(metric, metric)}
觀察期: {len(creator['metrics'][metric])} 天
偵測到的斷點: {result.changepoints}
最可能斷點: {cp_info}
confidence: {result.most_likely_cp_confidence}

請寫 200-280 字「給創作者讀的解讀 + 推測原因 + 下一步」:
1. 把 BOCPD 結果翻成創作者聽得懂的話 (避免「posterior」「run-length」)
2. 推測 3 個常見原因 (演算法 / 內容 / 競品 / 外部事件 / 季節),要具體不要泛泛
3. **3 個今天就能做的診斷動作** (查 Studio analytics 哪個維度先掉 / 比對標題 thumbnail / 對標同類創作者)
4. 1 個風險提醒 (例如:不要為了救流量盲目改題材 / 季節性波動可能誤判)

**規則**: 不要重算數字, 引用上面 facts。不要套話。不要 markdown 標題。

直接寫解讀。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 創作者顧問解讀\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="viewdrop — 自媒體 daily metric BOCPD")
    p.add_argument("--creator", default="samples/youtuber.json")
    p.add_argument("--metric", default=None, help="metric key in metrics dict (default: first)")
    p.add_argument("--hazard-lambda", type=float, default=None)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    creator = load_creator(Path(args.creator))
    metric_keys = list(creator["metrics"].keys())
    metric = args.metric or metric_keys[0]
    if metric not in creator["metrics"]:
        print(f"unknown metric '{metric}'. available: {metric_keys}", file=sys.stderr)
        sys.exit(1)

    data = creator["metrics"][metric]
    sigma = estimate_obs_sigma(data)
    haz = args.hazard_lambda or creator.get("hazard_lambda", 30)
    prior_mu = sum(data) / len(data)
    prior_sigma = max(sigma * 3, 1.0)

    result = run_bocpd(
        data, hazard_lambda=haz, obs_sigma=sigma,
        prior_mu=prior_mu, prior_sigma=prior_sigma,
    )

    if args.no_ai:
        print(render_no_ai(creator, metric, result, sigma))
    else:
        print(render_with_ai(creator, metric, result, sigma))


if __name__ == "__main__":
    main()
