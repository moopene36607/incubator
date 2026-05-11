"""storehunt CLI — 台灣店面承租 optimal stopping 決策助手。

Usage:
    python storehunt.py --search samples/store_search.json
    python storehunt.py --search samples/store_search.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from optstop import (
    StoreAttributes, SearchState, decide, Decision, Verdict,
    composite_score, all_scores_breakdown, observation_phase_size,
    DEFAULT_WEIGHTS,
)


def load_search(path: Path) -> SearchState:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    valid_fields = set(StoreAttributes.__dataclass_fields__.keys())

    def make_store(d: dict) -> StoreAttributes:
        return StoreAttributes(**{k: v for k, v in d.items() if k in valid_fields})

    seen = [make_store(d) for d in data.get("seen_stores", [])]
    current = make_store(data["current_store"])
    return SearchState(
        seen_stores=seen,
        estimated_total_stores=data["estimated_total_stores"],
        current_store=current,
        search_weeks_elapsed=data.get("search_weeks_elapsed", 0),
        expected_search_weeks=data.get("expected_search_weeks", 8),
        user_must_decide=data.get("user_must_decide", False),
        weights=data.get("weights", DEFAULT_WEIGHTS.copy()),
    )


VERDICT_LABEL = {
    Verdict.STRONG_ACCEPT: "🟢 強烈建議簽 (STRONG ACCEPT)",
    Verdict.ACCEPT: "🟩 建議簽 (ACCEPT)",
    Verdict.CONTINUE_OBSERVATION: "🟡 觀察期未結束,先看不下訂 (OBSERVE)",
    Verdict.WAIT_FOR_BETTER: "🟦 等更好的 (WAIT)",
    Verdict.RELUCTANT_ACCEPT: "🟧 勉強可簽 (RELUCTANT ACCEPT)",
    Verdict.RECONSIDER: "🔴 強烈不建議 (RECONSIDER)",
}


def render_no_ai(state: SearchState, decision: Decision) -> str:
    lines = [
        "# storehunt 店面承租 Optimal Stopping 報告",
        "",
        f"**搜尋週數**: 已 {state.search_weeks_elapsed} 週 / 預計 {state.expected_search_weeks} 週",
        f"**已看店數**: {decision.n_seen}  ·  **預估總共看**: {state.estimated_total_stores} 間",
        f"**Secretary observation phase (N/e)**: {decision.n_observation_phase} 間",
        f"**剩餘估計**: ~{decision.n_remaining_estimated} 間",
        f"**房東要求 24-48h 決定**: {'是' if state.user_must_decide else '否'}",
        "",
        "## 🎯 決策",
        "",
        f"### {VERDICT_LABEL[decision.verdict]}",
        "",
        f"- **當前店面**: {state.current_store.name}",
        f"- **當前綜合分數**: {decision.current_score:.1f} / 100",
        f"- **觀察期 threshold (原始)**: {decision.threshold:.1f}",
        f"- **時間壓力調整後 threshold**: {decision.threshold_adjusted:.1f}",
        f"- **目前已看過 best**: {decision.best_seen_so_far[0]} 分數 {decision.best_seen_so_far[1]:.1f}",
        f"- **secretary 規則理論成功率** (在 i.i.d. 假設下選到最佳): ~{decision.theoretical_p_best:.1%}",
        "",
        "## 推理訊號 (純函式)",
        "",
    ]
    for sig in decision.reasoning_signals:
        lines.append(f"- {sig}")

    lines.extend([
        "",
        "## 當前店面屬性分解",
        "",
        f"| 屬性 | 分數 | 權重 | 加權分 |",
        "|---|---|---|---|",
    ])
    breakdown = [
        ("人流 / 位置", state.current_store.location_score, state.weights["location"]),
        ("租金合理性", state.current_store.rent_score, state.weights["rent"]),
        ("坪數實用", state.current_store.size_score, state.weights["size"]),
        ("押金合理", state.current_store.deposit_score, state.weights["deposit"]),
        ("合約彈性", state.current_store.contract_score, state.weights["contract"]),
    ]
    for name, score, weight in breakdown:
        lines.append(f"| {name} | {score:.0f} | ×{weight:.2f} | {score * weight:.2f} |")

    lines.extend([
        "",
        "## 已看店面排序 (按綜合分數)",
        "",
        "| 排序 | 店面 | 綜合分 | 階段 |",
        "|---|---|---|---|",
    ])
    scored = []
    for i, store in enumerate(state.seen_stores):
        score = composite_score(store, state.weights)
        phase = "觀察期" if i < decision.n_observation_phase else "決策期"
        scored.append((i + 1, store.name, score, phase))
    # Sort by score desc
    scored.sort(key=lambda x: -x[2])
    for rank, (orig_idx, name, score, phase) in enumerate(scored[:10]):
        lines.append(f"| {rank + 1} | {name} (第 {orig_idx} 看) | {score:.1f} | {phase} |")
    lines.append(f"| → | **{state.current_store.name} (當前考慮)** | **{decision.current_score:.1f}** | **決策中** |")

    lines.extend([
        "",
        "## ⚠️ Optimal Stopping 模型假設與限制",
        "",
        "- **secretary 規則假設 N 已知**: 你估的「總共看 30 間」若實際只有 20 間,門檻會設過高",
        "- **i.i.d. 假設**: 假設店面到達順序隨機;若仲介**先帶你看爛的**,實際是 adversarial 偏離理論",
        "- **不可回頭規則**: 若你「想回去看上一間」現實中**多數情況房東已給別人**",
        "- **多屬性權重主觀**: 權重 (人流 30% / 租金 25%) 是預設值,個別產業 (餐飲 vs 服飾 vs 烘焙) 應自訂",
        "- **理論 1/e 成功率僅供參考**: 是「選到 absolute best」的機率,選到「top 5%」機率更高 ~80%+",
        "",
        "---",
        "*storehunt = secretary problem × 台灣店面承租 = 序列決策不可回頭 + 1/e 法則。",
    ])
    return "\n".join(lines)


def render_with_ai(state: SearchState, decision: Decision) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(state, decision)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(state, decision)

    base = render_no_ai(state, decision)

    signal_text = "\n".join(f"- {s}" for s in decision.reasoning_signals)
    must_decide = "房東要求 24h 內回覆" if state.user_must_decide else "無立即 deadline"

    prompt = f"""你是一位資深台灣商業地產顧問。下面是「{state.current_store.name}」這個店面的 optimal stopping 計算結果(純函式算好,你絕不能改數字):

verdict: {decision.verdict.value}
current_score: {decision.current_score}
threshold: {decision.threshold} (時間壓力調整後 {decision.threshold_adjusted})
n_seen / n_total: {decision.n_seen} / {state.estimated_total_stores}
n_observation_phase: {decision.n_observation_phase}
n_remaining: {decision.n_remaining_estimated}
best_seen: {decision.best_seen_so_far[0]} 分數 {decision.best_seen_so_far[1]}
landlord_pressure: {must_decide}
search progress: 已 {state.search_weeks_elapsed} 週 / 預計 {state.expected_search_weeks} 週

純函式 signals:
{signal_text}

請寫一段 180-250 字「給創業老闆讀的決策建議」:
1. 用一句話下 verdict 翻譯(避免 jargon「secretary 規則」「i.i.d.」)
2. **2-3 個具體可做的下一步**(例如:現在打給房東談押金 / 24 小時內找會計師看合約 / 再拖 1 週看 X 間)
3. 1 個明確風險(例如:房東話術「今天不簽就讓給別人」其實是 universal 銷售話術 / 押金條款常見坑)

**嚴格規則**:
- 不要重新算分數,不要算 threshold
- 不要套話 (「祝順利」「相信自己」)
- 不超過 250 字
- 不要用 markdown 標題或表格

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 商業地產顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="storehunt — 店面承租 optimal stopping")
    p.add_argument("--search", default="samples/store_search.json")
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    state = load_search(Path(args.search))
    decision = decide(state)

    if args.no_ai:
        print(render_no_ai(state, decision))
    else:
        print(render_with_ai(state, decision))


if __name__ == "__main__":
    main()
