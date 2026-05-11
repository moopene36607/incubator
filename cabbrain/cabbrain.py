"""cabbrain CLI -- 計程車 / Uber 司機 接單策略 Q-learning with linear function approximation.

Usage:
    python3 cabbrain.py --data samples/shifts.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import fmean

from rl import (
    Order, train_q_learning, recommend, policy_summary, replay_policy_on_log,
    LinearQ, OrderRecommendation, TrainingDiagnostics,
    N_FEATURES, ACTIONS,
)


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def order_from_dict(d: dict) -> Order:
    return Order(
        fare_ntd=float(d["fare_ntd"]),
        distance_km=float(d["distance_km"]),
        duration_min=float(d["duration_min"]),
        surge=float(d.get("surge", 1.0)),
        pickup_zone_density=float(d.get("pickup_zone_density", 0.5)),
        traffic_level=int(d.get("traffic_level", 3)),
        hour=int(d["hour"]),
        is_weekend=bool(d.get("is_weekend", False)),
    )


def render_no_ai(data: dict, q: LinearQ, diag: TrainingDiagnostics,
                  history: list[Order], query: Order, rec: OrderRecommendation,
                  replay: dict) -> str:
    decision_emoji = "✅" if rec.action == 1 else "❌"
    decision_text = "接單" if rec.action == 1 else "拒接"

    avg_first_half = fmean(diag.episode_returns[: len(diag.episode_returns) // 2 or 1])
    avg_second_half = fmean(diag.episode_returns[len(diag.episode_returns) // 2 :])

    lines = [
        f"# cabbrain -- {data.get('driver_id', '匿名司機')} 接單策略 RL 訓練",
        "",
        f"**訓練 orders**: {len(history)} 筆歷史訂單",
        f"**Q-learning**: 線性函數逼近 Q(s, a) = w_a · φ(s), 9 維 features × 2 actions = 18 weights",
        f"**訓練 episodes**: {len(diag.episode_returns)} 次 (epsilon 從 0.5 線性降到 0.05)",
        f"**Episode return**: 前半平均 {avg_first_half:.0f} → 後半平均 {avg_second_half:.0f} (越大越好)",
        f"**訓練接 / 拒比**: {diag.n_accepts} / {diag.n_declines} (探索 + 學習中)",
        "",
        "## 📈 學習到的策略 vs 全部接單 (replay on log)",
        "",
        "| 指標 | 學習策略 | 全部接 (naive) | 差異 |",
        "|---|---|---|---|",
        f"| 總淨利 (NT$) | {replay['learned_return']:.0f} | {replay['naive_return']:.0f} | "
        f"**{replay['delta']:+.0f}** |",
        f"| 接單數 | {replay['learned_n_accept']} / {replay['n_orders']} | "
        f"{replay['n_orders']} / {replay['n_orders']} | -- |",
        "",
        f"> 學習策略{('學會挑單' if replay['delta'] > 0 else '尚未明顯勝過 naive 全接' if replay['delta'] > -100 else '需要更多訓練')}, "
        f"差異 NT$ {replay['delta']:+.0f} per shift.",
        "",
        "## 🎯 待決策訂單",
        "",
        f"_{data['query'].get('_meta', '')}_",
        "",
        "| 屬性 | 值 |",
        "|---|---|",
        f"| 估價 | NT$ {query.fare_ntd:.0f} |",
        f"| 距離 | {query.distance_km:.1f} km |",
        f"| 預估時間 | {query.duration_min:.0f} 分鐘 |",
        f"| Surge 倍率 | x{query.surge:.2f} |",
        f"| 上車區密度 | {query.pickup_zone_density:.2f} |",
        f"| 路況 | {query.traffic_level}/5 |",
        f"| 時段 | {query.hour:02d}:00 |",
        f"| 週末 | {'是' if query.is_weekend else '否'} |",
        "",
        f"## {decision_emoji} RL 策略建議: **{decision_text}**",
        "",
        f"### {rec.rationale}",
        "",
        "| 指標 | 值 |",
        "|---|---|",
        f"| Q(s, accept) | {rec.q_accept:.1f} |",
        f"| Q(s, decline) | {rec.q_decline:.1f} |",
        f"| Margin (accept - decline) | **{rec.margin:+.1f}** |",
        f"| 接受預估淨利 | NT$ {rec.expected_reward_if_accept:.0f} |",
        "",
        "## 🔬 學到的權重 (top 5 by |w| per action)",
        "",
    ]
    summary = policy_summary(q)
    for action in (1, 0):
        action_name = "接單 (a=1)" if action == 1 else "拒接 (a=0)"
        lines.append(f"### {action_name}")
        lines.append("")
        lines.append("| Feature | 權重 | 物理意義 |")
        lines.append("|---|---|---|")
        meanings = {
            "hour": "時段 (晚上 / 凌晨 一般較虧)",
            "is_weekend": "週末 = 1",
            "fare_norm": "估價 / NT$600 ratio",
            "distance_norm": "距離 / 30 km ratio",
            "duration_norm": "時長 / 60 min ratio",
            "surge_norm": "Surge 加成 (>1 → +)",
            "zone_density": "上車區商業密度",
            "traffic_norm": "路況差度 (1=順 5=塞)",
            "bias": "常數項",
        }
        for fname, w in summary[action][:5]:
            lines.append(f"| {fname} | {w:+.3f} | {meanings.get(fname, '')} |")
        lines.append("")

    lines.extend([
        "## ⚠️ RL with linear function approximation 模型假設與限制",
        "",
        "- **Linear approximation 假設**: Q(s,a) = w·φ(s) 假設 Q 是 features 的線性函數;真實有非線性 (e.g. 距離平方項 / 時段交互), Pro 版加多項式 features 或 neural network",
        "- **Off-policy 偏差**: 歷史訂單是司機過去策略下產生, 並非完全 IID 樣本;若舊策略偏向只接「短程訂單」, Q-learning 會 underestimate 長程訂單價值 (covariate shift), Pro 版加 importance sampling",
        "- **Reward 工程主觀**: fuel_cost / opportunity_cost 是預設值, 不同車型 / 油價 / 司機機會成本不同; 真實 launch 要讓司機自訂",
        "- **不含關鍵 features**: 客戶評分 / 取消歷史 / 訂單 metadata, prototype 簡化 8 維; Pro 版加 20-30 維",
        "- **不取代司機判斷**: RL 給「策略建議」, 安全 / 心情 / 直覺 / 同行情報 仍是司機決定; 工具僅輔助",
        "- **episode 假設**: 訓練用 shuffled 順序, 真實一天訂單有時序相關 (e.g. 通勤尖峰), Pro 版用 ordered episodes",
        "- **沒考慮競爭**: 多司機搶單 game-theoretic 均衡需 multi-agent RL",
        "- **隱私敏感**: 訂單資料涉司機個資 + 乘客上車地點, 本地版完全在司機手機;雲端版需匿名化",
        "",
        "---",
        "*cabbrain = Q-learning + linear function approximation × 台灣計程車 / Uber 司機 接單策略 niche = "
        "從歷史訂單 log 學 Q(s, a) ≈ w · φ(s), ε-greedy 平衡探索 / 利用, 學到的策略 vs naive 全接 比較淨利提升, "
        "司機從「靠經驗 / 看心情」變「客觀 Q 值」, 對抗平台 algorithm 推爛單。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, q, diag, history, query, rec, replay):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, q, diag, history, query, rec, replay)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, q, diag, history, query, rec, replay)

    base = render_no_ai(data, q, diag, history, query, rec, replay)

    prompt = f"""你是台灣資深計程車 / Uber 老司機 (15+ 年 + 帶過 50+ 新司機). 下面是用 Q-learning with linear function approximation 純函式分析的結果:

訂單: NT${int(query.fare_ntd)} / {query.distance_km:.1f} km / {int(query.duration_min)} min / surge x{query.surge:.2f} / 路況 {query.traffic_level}/5 / {query.hour:02d}:00
RL 策略決定: {'接單' if rec.action == 1 else '拒接'} (Q_accept={rec.q_accept:.0f}, Q_decline={rec.q_decline:.0f}, margin={rec.margin:+.0f})
預估接後淨利 NT$ {rec.expected_reward_if_accept:.0f}
替代策略對比: 學習策略 NT${replay['learned_return']:.0f} vs 全接 NT${replay['naive_return']:.0f} (差異 NT${replay['delta']:+.0f})

請寫 250-330 字「給司機接單前 5 秒的判斷 SOP」:
1. 一句解讀 (避免「Q-learning」「TD error」這種術語): 為什麼這單 RL 算建議這樣
2. **3 個現場 5 秒判斷信號** (避免被平台 algorithm 推爛單; e.g. 時段 / 距離 / surge / 路況)
3. **何時應該違反 RL 建議** (e.g. 安全因素 / 客戶取消歷史 / 不熟區域)
4. 1 個給新司機的長期策略提醒 (e.g. 不要 always 接 short trips, 不要 always 拒長程)

**嚴格規則**:
- 不要重算 NT$ / Q 值, 引用 facts
- 不要套話 ("辛苦了" / "祝您天天高收入")
- 不超過 330 字
- 不要 markdown 標題
- 強調「RL 是平均化策略, 安全永遠優先」

直接寫 SOP。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 老司機接單 SOP\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="cabbrain -- 計程車接單策略 Q-learning")
    p.add_argument("--data", default="samples/shifts.json")
    p.add_argument("--episodes", type=int, default=200)
    p.add_argument("--alpha", type=float, default=0.01)
    p.add_argument("--gamma", type=float, default=0.90)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    history = [order_from_dict(o) for o in data["historical_orders"]]
    query = order_from_dict(data["query"]["order"])

    q, diag = train_q_learning(history, n_episodes=args.episodes,
                                 alpha=args.alpha, gamma=args.gamma, seed=args.seed)
    rec = recommend(q, query)
    replay = replay_policy_on_log(q, history)

    if args.no_ai:
        print(render_no_ai(data, q, diag, history, query, rec, replay))
    else:
        print(render_with_ai(data, q, diag, history, query, rec, replay))


if __name__ == "__main__":
    main()
