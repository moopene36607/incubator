"""groupbuzz CLI — LINE 群組 / 社群成員 PageRank 影響力排行。

Usage:
    python groupbuzz.py --group samples/group_messages.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pagerank import (
    Message, GroupSnapshot, build_influence_graph, pagerank,
    compute_member_stats, compute_group_health,
    PageRankResult, MemberStats, GroupHealth,
)


def load_group(path: Path) -> GroupSnapshot:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    valid_msg_fields = set(Message.__dataclass_fields__.keys())
    messages = [
        Message(**{k: v for k, v in m.items() if k in valid_msg_fields})
        for m in data["messages"]
    ]
    return GroupSnapshot(
        group_name=data["group_name"],
        members=data["members"],
        messages=messages,
    )


ROLE_LABEL = {
    "core_influencer": "⭐ 核心影響者",
    "connector": "🔗 連接者 (帶動氣氛)",
    "active_contributor": "🟢 積極參與",
    "regular": "👤 一般成員",
    "silent": "🤐 沈默",
    "lurker": "👻 潛水",
}


def render_no_ai(snap: GroupSnapshot, stats: list[MemberStats],
                  health: GroupHealth, pr: PageRankResult) -> str:
    lines = [
        f"# groupbuzz — {snap.group_name} PageRank 影響力分析",
        "",
        f"**總成員**: {health.n_members}  ·  **總訊息**: {health.n_messages}",
        f"**活躍成員 (≥3 訊息)**: {health.n_active_members}",
        f"**沈默成員 (≤2 訊息)**: {health.n_silent_members}  ·  **潛水 (0 訊息)**: {health.n_lurkers}",
        f"**PageRank iterations**: {pr.n_iterations} ({'converged' if pr.converged else 'max iter hit'}) damping={pr.damping}",
        "",
        "## 🎯 群組健康度",
        "",
        "| 指標 | 值 | 解讀 |",
        "|---|---|---|",
        f"| Top 5 PR 集中度 | {health.pagerank_concentration:.1%} | {'過度集中' if health.pagerank_concentration > 0.5 else '健康分散' if health.pagerank_concentration < 0.35 else '中等'} |",
        f"| Top 20% 訊息佔比 | {health.activity_skew:.1%} | {'明顯 80/20 分布' if health.activity_skew > 0.6 else '較均勻' if health.activity_skew < 0.4 else '中等'} |",
        f"| 潛水率 | {health.n_lurkers / health.n_members:.1%} | {'警示' if health.n_lurkers / health.n_members > 0.3 else 'OK'} |",
        "",
        "## 🏆 Top 10 影響力排行 (PageRank)",
        "",
        "| # | 成員 | PageRank | 角色 | 訊息數 | in_weight (被 reply/mention) | out_weight (主動 reply) |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(stats[:10]):
        role = ROLE_LABEL.get(s.role, s.role)
        lines.append(
            f"| {i + 1} | {s.name} | **{s.pagerank:.4f}** | {role} | "
            f"{s.message_count} | {s.in_weight:.2f} | {s.out_weight:.2f} |"
        )

    # Bottom 5 lurkers
    lurkers_sorted = sorted([s for s in stats if s.role in ("lurker", "silent")],
                              key=lambda s: (s.message_count, s.in_weight))
    if lurkers_sorted:
        lines.append("")
        lines.append("## 🤐 Bottom: 沈默 / 潛水成員 (可能需要召回)")
        lines.append("")
        lines.append("| 成員 | 訊息數 | in_weight | 入群多久 |")
        lines.append("|---|---|---|---|")
        for s in lurkers_sorted[:8]:
            lines.append(f"| {s.name} | {s.message_count} | {s.in_weight:.2f} | (Pro 版顯示加入日) |")

    lines.append("")
    lines.append("## 角色分布")
    lines.append("")
    role_counter: dict[str, int] = {}
    for s in stats:
        role_counter[s.role] = role_counter.get(s.role, 0) + 1
    lines.append("| 角色 | 人數 | 百分比 |")
    lines.append("|---|---|---|")
    for role, cnt in sorted(role_counter.items(), key=lambda kv: -kv[1]):
        pct = cnt / len(stats) * 100
        lines.append(f"| {ROLE_LABEL.get(role, role)} | {cnt} | {pct:.0f}% |")

    lines.append("")
    lines.append("## 純函式判讀")
    lines.append("")
    top1 = stats[0] if stats else None
    if top1:
        lines.append(f"- **Top influencer**: {top1.name} (PageRank {top1.pagerank:.4f})")
        lines.append(f"  - 被 reply / mention {top1.in_weight:.1f} 次  ·  自己發 {top1.message_count} 則訊息")
        lines.append(f"  - **群組的命脈**;若 {top1.name} 離開, 群組活躍度立即崩跌")
    if health.pagerank_concentration > 0.5:
        lines.append(f"- 🔴 **影響力過度集中** (top 5 佔 {health.pagerank_concentration:.0%})  ·  風險: 主要 KOL 離開群組崩塌")
    if health.n_lurkers / health.n_members > 0.3:
        lines.append(f"- 🟡 **潛水率高 {health.n_lurkers / health.n_members:.0%}** ({health.n_lurkers}/{health.n_members})  ·  建議週末 ice-breaker 引子 (照片問答 / 投票 / 周年回顧)")

    lines.append("")
    lines.append("## ⚠️ PageRank 模型假設與限制")
    lines.append("")
    lines.append("- **PageRank 假設邊權重反映真實影響力**: 但 mention 可能是 spam, reply 可能是 sarcasm;Pro 版加 sentiment-aware weighting")
    lines.append("- **時間衰減未處理**: 半年前 reply 跟昨天 reply 等權,Pro 版加 exponential time decay")
    lines.append("- **群組規模**: 50 人 OK, 500+ 人需要 sparse matrix 優化;1000+ 需要 distributed power iteration")
    lines.append("- **LINE 沒提供 official 訊息 dump**: 真實 launch 版需要用戶手動截圖 / 第三方 export 工具,有 ToS 風險")
    lines.append("- **隱私敏感**: 群組訊息涉個資 + 用戶不知道被分析,UI 必須**透明告知 + 群主同意 + 訊息 anonymize**")
    lines.append("")
    lines.append("---")
    lines.append("*groupbuzz = Brin & Page 1998 PageRank × 台灣 LINE 群組管理 niche = 從 200 條訊息 5 秒找出 top 5 influencers + 潛水召回名單。*")
    return "\n".join(lines)


def render_with_ai(snap, stats, health, pr):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(snap, stats, health, pr)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(snap, stats, health, pr)

    base = render_no_ai(snap, stats, health, pr)
    top3 = stats[:3]
    lurker_count = sum(1 for s in stats if s.role in ("lurker", "silent"))

    prompt = f"""你是一位資深台灣社群經營顧問 (FB / LINE 團媽 / Discord 經營 KOL)。下面是用 PageRank 純函式算出的群組影響力分析:

群組: {snap.group_name} ({health.n_members} 成員, {health.n_messages} 訊息)
Top 3 PageRank:
{chr(10).join(f"- #{i+1} {s.name}: PR {s.pagerank:.4f}, 角色 {s.role}, msgs {s.message_count}, in_w {s.in_weight}, out_w {s.out_weight}" for i, s in enumerate(top3))}
沈默 / 潛水: {lurker_count} 人
PR 集中度 (top 5): {health.pagerank_concentration:.1%}
訊息分布 (top 20% 佔): {health.activity_skew:.1%}

請寫 250-320 字「給群組擁有者 / 團媽的行動建議」:
1. 1 句翻譯 (避免「PageRank」「damping」等技術詞)
2. **3 個利用 top 3 influencers 的具體動作** (推薦 / 內部公告 / 帶風向, 每個帶具體腳本)
3. **2 個救活沈默成員的策略** (ice-breaker / 私訊問候 / 投票)
4. 1 個風險: 群組過度依賴 top 1 的 fragility / 隱私 / 不要當面 confront

**嚴格規則**:
- 不要重算 PR / 百分比, 引用 facts
- 不要套話 ("加油")
- 不超過 320 字
- 不要 markdown 標題

直接寫建議。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 社群經營顧問建議\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="groupbuzz — LINE 群組 PageRank 影響力分析")
    p.add_argument("--group", default="samples/group_messages.json")
    p.add_argument("--damping", type=float, default=0.85)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    snap = load_group(Path(args.group))
    graph = build_influence_graph(snap)
    pr = pagerank(graph, list(snap.members.keys()), damping=args.damping)
    stats = compute_member_stats(snap, graph, pr)
    health = compute_group_health(snap, stats)

    if args.no_ai:
        print(render_no_ai(snap, stats, health, pr))
    else:
        print(render_with_ai(snap, stats, health, pr))


if __name__ == "__main__":
    main()
