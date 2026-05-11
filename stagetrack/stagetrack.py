"""stagetrack — 台灣房地產 listing 銷售階段 HMM 自動追蹤 CLI.

純函式做 forward-backward + Viterbi(hmm.py)。LLM 只負責:
  ① 將 HMM 推測的 state 翻譯成「房仲易懂」的故事(這個 listing 的故事)
  ② 為當前 state 給 4-6 條具體行動建議(調價 / 重拍照 / 改 listing 文案 / 議價 / 撤回)
  ③ 預警:若 state 連續 X 週 Cold 應該採取什麼措施
  ④ 對房仲整體 portfolio 給結構性建議

LLM 永不算 HMM 機率。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from hmm import (
    ListingAnalysis,
    N_STATES,
    OBSERVATION_LABELS,
    STATES,
    analyze_listing,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣房仲業務員顧問,專長 listing 銷售階段管理。

    輸入:
      - listing 基本資料(地址 / 物件)+ 12 週活動觀察
      - HMM 推測的 hidden state sequence(Hot / Warm / Cold / Closed)+ posterior
      - 當前 state + 連續週數 + state distribution

    工作:
      1. 為每個 listing 寫 100-150 字「故事化解讀」:
         - 從 Viterbi state sequence 看這個 listing 經歷了什麼階段
         - 解釋活動數據與 state 的關聯
         - 用故事說明「為什麼從 Hot 變 Cold」「為什麼一直 Warm 沒進展」等
      2. 為當前 state 推薦 3-5 條「立即可執行的行動」:
         - Hot: 議價技巧 + 把握黃金 7 天 + 不要降價
         - Warm: 微調定價(-3-5%) / 重拍 1-2 張關鍵照片 / 改 listing 標題
         - Cold: 大幅調價(-10-15%) / 重拍照片 / 改 listing 文案重寫 / 考慮撤回重刊
         - Closed: 移除追蹤 / 學習(這個物件成交價作為類似物件參考)
      3. 早期警示信號:
         - 連續 2 週 Cold → 主動聯繫屋主討論調整
         - Hot 連續 3 週但沒議價 → 詢問詢價人為何沒進議價
         - Warm 持續 8 週以上 → 重新檢視定價是否高出市場 10%+
      4. 若有多個 listings,給 portfolio 級別建議

    硬規則:
      - 你**絕不**重算 state probability — 直接引用 HMM 結果
      - 不勸屋主「立刻降價」— 提供「**討論調整**」的建議
      - 不勸「撤回重刊」當主要建議 — 那是最後手段
      - 用台灣繁體房仲在地用語(物件 / 售屋 / 帶看 / 議價 / 委託)

    回覆 JSON:
    {
      "per_listing_analysis": [
        {
          "listing_id": "L001",
          "story_narrative": "100-150 字故事",
          "current_state_label_zh": "已成交",
          "action_recommendations": [
            {"priority": 1, "action": "...", "expected_impact": "..."},
            ...
          ],
          "warning_signals": ["..."]
        },
        ...
      ],
      "portfolio_insights": ["...", "..."]
    }
""").strip()


STATE_LABEL_ZH = {
    "Hot": "🔥 熱賣中",
    "Warm": "🟡 溫溫的",
    "Cold": "❄️ 冷掉了",
    "Closed": "🔒 已結案",
}

STATE_EMOJI = {
    "Hot": "🔥",
    "Warm": "🟡",
    "Cold": "❄️",
    "Closed": "🔒",
}


def ai_explain(listings_data: list[dict], analyses: list[ListingAnalysis]) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()
    payload = {
        "listings": [
            {
                "listing_id": L["listing_id"],
                "address": L.get("address", ""),
                "weekly_activity": L["weekly_activity"],
                "viterbi_states": a.viterbi_states,
                "current_state": a.current_state,
                "current_state_prob": a.current_state_prob,
                "current_state_distribution": a.current_state_distribution,
                "state_transitions": a.state_transitions,
                "weeks_in_current_state": a.weeks_in_current_state,
            }
            for L, a in zip(listings_data, analyses)
        ]
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def render_no_ai_report(listings_data: list[dict], analyses: list[ListingAnalysis]) -> str:
    parts = ["# stagetrack 房地產 listing HMM 銷售階段追蹤報告\n"]
    parts.append("**模式**: 純函式 Hidden Markov Model + Viterbi(免 API key)\n")
    parts.append(f"## Portfolio 概況 — {len(listings_data)} 個 listings\n")

    # Summary table
    parts.append("| Listing | 地址 | 當前 state | 信賴度 | 連續週數 | State 演變 |")
    parts.append("|---|---|---|---|---|---|")
    for L, a in zip(listings_data, analyses):
        addr_short = L.get("address", "")[:25]
        parts.append(
            f"| {a.listing_id} | {addr_short} | {STATE_LABEL_ZH[a.current_state]} | "
            f"{a.current_state_prob*100:.0f}% | {a.weeks_in_current_state} 週 | "
            f"{' → '.join(a.state_transitions)} |"
        )
    parts.append("")

    # Per-listing detail
    for L, a in zip(listings_data, analyses):
        parts.append(f"## {a.listing_id} — {L.get('address', '')}\n")
        parts.append(f"**筆記**: {L.get('notes', '-')}\n")
        parts.append(f"### 12 週活動觀察 vs HMM 推測 state\n")
        parts.append("| 週 | 觀察 (0-4) | 觀察描述 | Viterbi state |")
        parts.append("|---|---|---|---|")
        for week, (obs, state, obs_label) in enumerate(zip(a.observations, a.viterbi_states, a.observation_labels), 1):
            parts.append(f"| W{week} | {obs} | {obs_label} | {STATE_EMOJI[state]} {state} |")
        parts.append("")
        parts.append(f"### 當前 state 分布(W12 posterior)\n")
        for state, prob in a.current_state_distribution.items():
            bar = "█" * int(prob * 30)
            parts.append(f"- {STATE_EMOJI[state]} **{state}**: {prob*100:.1f}% {bar}")
        parts.append("")
        parts.append(f"### State 演變\n")
        parts.append("**" + " → ".join(a.state_transitions) + "**")
        parts.append("")
        parts.append(f"連續 **{a.weeks_in_current_state} 週**在 {a.current_state}")
        parts.append("")

    parts.append("---")
    parts.append("*純函式模式無 AI 故事化解讀與行動建議。AI 模式會為每個 listing 寫故事 + 3-5 條立即行動 + 預警信號 + portfolio 建議。*")
    parts.append("*stagetrack 是分析工具,**最終決策**(調價 / 撤回)請依房仲經驗 + 屋主溝通。HMM 推測有不確定性。*")
    return "\n".join(parts)


def render_full_report(listings_data: list[dict], analyses: list[ListingAnalysis], ai: dict) -> str:
    parts = ["# stagetrack 房地產 listing HMM 銷售階段追蹤報告\n"]
    parts.append("**模式**: 純函式 HMM + AI 房仲顧問解讀\n")
    parts.append(f"## Portfolio 概況 — {len(listings_data)} 個 listings\n")

    # Summary table
    parts.append("| Listing | 地址 | 當前 state | 信賴度 | 連續週數 |")
    parts.append("|---|---|---|---|---|")
    for L, a in zip(listings_data, analyses):
        addr_short = L.get("address", "")[:25]
        parts.append(
            f"| {a.listing_id} | {addr_short} | {STATE_LABEL_ZH[a.current_state]} | "
            f"{a.current_state_prob*100:.0f}% | {a.weeks_in_current_state} 週 |"
        )
    parts.append("")

    ai_map = {x["listing_id"]: x for x in ai.get("per_listing_analysis", [])}

    # Per-listing detail
    for L, a in zip(listings_data, analyses):
        ai_entry = ai_map.get(a.listing_id, {})
        parts.append(f"## {a.listing_id} — {L.get('address', '')}\n")
        parts.append(f"**當前狀態**: {STATE_LABEL_ZH[a.current_state]} ({a.current_state_prob*100:.0f}% 信賴度, 連續 {a.weeks_in_current_state} 週)\n")

        parts.append("### 故事化解讀\n")
        parts.append(ai_entry.get("story_narrative", ""))
        parts.append("")

        parts.append("### State 演變\n")
        parts.append("**" + " → ".join(a.state_transitions) + "**\n")

        parts.append("### 12 週活動觀察 vs HMM state\n")
        parts.append("| 週 | 觀察 | Viterbi state |")
        parts.append("|---|---|---|")
        for week, (obs, state, obs_label) in enumerate(zip(a.observations, a.viterbi_states, a.observation_labels), 1):
            parts.append(f"| W{week} | {obs} ({obs_label}) | {STATE_EMOJI[state]} {state} |")
        parts.append("")

        parts.append("### 當前 state 分布\n")
        for state, prob in a.current_state_distribution.items():
            bar = "█" * int(prob * 30)
            parts.append(f"- {STATE_EMOJI[state]} **{state}**: {prob*100:.1f}% {bar}")
        parts.append("")

        if ai_entry.get("action_recommendations"):
            parts.append("### 🎯 立即行動建議\n")
            for action in ai_entry["action_recommendations"]:
                parts.append(f"#### #{action.get('priority', '?')} {action.get('action', '')}")
                parts.append(f"- **預期影響**: {action.get('expected_impact', '')}")
                parts.append("")

        if ai_entry.get("warning_signals"):
            parts.append("### ⚠️ 早期警示信號\n")
            for s in ai_entry["warning_signals"]:
                parts.append(f"- {s}")
            parts.append("")

    # Portfolio insights
    parts.append("## 📊 Portfolio 整體建議\n")
    for insight in ai.get("portfolio_insights", []):
        parts.append(f"- {insight}")
    parts.append("")

    parts.append("---")
    parts.append("*stagetrack 是分析工具,**最終決策**(調價 / 撤回)請依房仲經驗 + 屋主溝通。HMM 推測有不確定性。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="stagetrack — 房地產 listing HMM 銷售階段追蹤")
    p.add_argument("json_path", help="listings.json")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    listings_data = data["listings"]

    analyses = [analyze_listing(L["listing_id"], L["weekly_activity"]) for L in listings_data]

    if args.no_ai:
        report = render_no_ai_report(listings_data, analyses)
    else:
        ai = ai_explain(listings_data, analyses)
        report = render_full_report(listings_data, analyses, ai)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
