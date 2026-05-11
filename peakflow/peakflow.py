"""peakflow CLI — 餐廳尖峰時段 agent-based simulation 比較不同人力配置。

Usage:
    python peakflow.py --restaurant samples/restaurant.json --runs 5
    python peakflow.py --restaurant samples/restaurant.json --no-ai
    python peakflow.py --restaurant samples/restaurant.json --runs 10 --duration 120
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sim import RestaurantConfig, SimulationConfig, run_scenarios, ScenarioComparison


def load_restaurant(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_scenarios(data: dict) -> list[tuple[str, RestaurantConfig]]:
    """Build RestaurantConfig list from sample JSON. Each scenario may override any field."""
    base = data["baseline_setup"]
    svc = data["service_parameters"]
    scenarios = []
    for s in data["scenarios"]:
        scenarios.append((
            s["label"],
            RestaurantConfig(
                name=s["label"],
                n_tables=s.get("n_tables", base["n_tables"]),
                table_capacities=s.get("table_capacities", base["table_capacities"]),
                n_servers=s.get("n_servers", base["n_servers"]),
                kitchen_capacity=s.get("kitchen_capacity", base["kitchen_capacity"]),
                server_order_time_min=s.get("server_order_time_min", svc["server_order_time_min"]),
                server_order_time_max=s.get("server_order_time_max", svc["server_order_time_max"]),
                server_deliver_time_min=s.get("server_deliver_time_min", svc["server_deliver_time_min"]),
                server_deliver_time_max=s.get("server_deliver_time_max", svc["server_deliver_time_max"]),
                kitchen_cook_time_min=s.get("kitchen_cook_time_min", svc["kitchen_cook_time_min"]),
                kitchen_cook_time_max=s.get("kitchen_cook_time_max", svc["kitchen_cook_time_max"]),
                avg_eat_time_min=s.get("avg_eat_time_min", svc["avg_eat_time_min"]),
                avg_eat_time_max=s.get("avg_eat_time_max", svc["avg_eat_time_max"]),
                avg_check_per_person_ntd=data["average_check_per_person_ntd"],
                avg_patience_min=svc["avg_patience_min"],
                patience_std=svc["patience_std"],
            )
        ))
    return scenarios


def render_no_ai(data: dict, comparison: ScenarioComparison) -> str:
    """Pure-function rendered report (no LLM)."""
    parts = [
        f"# peakflow 餐廳尖峰時段營運模擬報告",
        "",
        f"**餐廳**: {data['restaurant_name']}",
        f"**模擬時段**: {data['lunch_peak_window']}",
        f"**模擬次數**: {len(comparison.scenarios)} scenarios × {data.get('_runs', 5)} runs (平均)",
        f"**到達率**: 平均每分鐘 {data['arrival_pattern']['customer_arrival_rate_per_min']} 組客人 / 客單價 NT${data['average_check_per_person_ntd']}",
        "",
        "## 各情境 KPI 比較",
        "",
        "| 情境 | 進店 | 服務完 | 流失 | 流失率 | 平均等待 | P95 等待 | 營收 | 服務員忙 | 廚房忙 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    baseline_revenue = comparison.scenarios[comparison.baseline_idx][1].revenue_ntd
    for name, r in comparison.scenarios:
        parts.append(
            f"| {name} | {r.n_arrived} | {r.n_served} | {r.n_lost} | {r.loss_rate_pct}% | "
            f"{r.avg_wait_time_min} min | {r.p95_wait_time_min} min | "
            f"NT${r.revenue_ntd:,} | {r.server_utilization_pct}% | {r.kitchen_utilization_pct}% |"
        )

    parts.extend([
        "",
        "## 投資 ROI 分析",
        "",
        "| 情境 | 月增成本 | 單日尖峰增營收 | 月增營收 (×30) | 淨增益 | ROI |",
        "|---|---|---|---|---|---|",
    ])
    for i, (name, r) in enumerate(comparison.scenarios):
        if i == comparison.baseline_idx:
            parts.append(f"| {name} | 基準 | 基準 | 基準 | — | — |")
            continue
        s = data["scenarios"][i]
        extra_cost = s.get("monthly_extra_cost_ntd", 0)
        single_day_lift = r.revenue_ntd - baseline_revenue
        monthly_lift = single_day_lift * 30
        net_gain = monthly_lift - extra_cost
        roi_pct = (net_gain / extra_cost * 100) if extra_cost > 0 else 0
        roi_str = f"{roi_pct:+.0f}%" if extra_cost > 0 else "—"
        parts.append(
            f"| {name} | NT${extra_cost:,} | NT${single_day_lift:+,} | NT${monthly_lift:+,} | "
            f"NT${net_gain:+,} | {roi_str} |"
        )

    parts.append("")
    parts.append("## 瓶頸辨識(純函式判讀)")
    parts.append("")
    base = comparison.scenarios[comparison.baseline_idx][1]
    if base.kitchen_utilization_pct >= 80:
        parts.append(f"- ⚠️ **廚房負載 {base.kitchen_utilization_pct}%** — 廚房逼近滿載,是潛在瓶頸。出餐慢=桌子翻不動=客人等到走。優先擴廚 / 加 prep 人員 / 縮短菜單。")
    if base.server_utilization_pct > 75:
        parts.append(f"- ⚠️ **服務員忙 {base.server_utilization_pct}%** — 點餐 / 上菜可能延遲,影響客人感受。考慮加 1 名外場。")
    if base.loss_rate_pct > 30:
        parts.append(f"- 🔴 **流失率 {base.loss_rate_pct}%** — 每 3 組客人就有 1 組等不到桌離開。每天損失約 NT${base.n_lost * data['average_check_per_person_ntd'] * 2:,} 機會營收。")
    if base.avg_wait_time_min > 10:
        parts.append(f"- 🟡 **平均等待 {base.avg_wait_time_min} 分** 已超出客人耐心(平均 {data['service_parameters']['avg_patience_min']} 分)。")
    parts.append("")
    parts.append("## 推薦投資方向")
    parts.append("")
    # Find best ROI
    best_idx = comparison.baseline_idx
    best_net = 0
    for i, (name, r) in enumerate(comparison.scenarios):
        if i == comparison.baseline_idx:
            continue
        s = data["scenarios"][i]
        extra_cost = s.get("monthly_extra_cost_ntd", 0)
        single_day_lift = r.revenue_ntd - baseline_revenue
        net_gain = single_day_lift * 30 - extra_cost
        if net_gain > best_net:
            best_net = net_gain
            best_idx = i
    if best_idx != comparison.baseline_idx:
        best_name, best_r = comparison.scenarios[best_idx]
        parts.append(f"**最佳方案: {best_name}**")
        parts.append(f"- 月淨增益: NT${best_net:+,}")
        parts.append(f"- 流失率從 {base.loss_rate_pct}% 降到 {best_r.loss_rate_pct}%")
        parts.append(f"- 平均等待從 {base.avg_wait_time_min} 分降到 {best_r.avg_wait_time_min} 分")
    else:
        parts.append("各方案都無正向 ROI;建議檢查到達率參數或重新考慮投資。")

    parts.append("")
    parts.append("---")
    parts.append("*peakflow 為營運參考,實際營收受天氣 / 競爭 / 行銷影響,投資前請保留 2-3 週實測數據驗證。*")
    return "\n".join(parts)


def render_with_ai(data: dict, comparison: ScenarioComparison) -> str:
    """LLM-wrapped report with owner-readable recommendations."""
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝,退回 no-ai 模式", file=sys.stderr)
        return render_no_ai(data, comparison)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定,退回 no-ai 模式", file=sys.stderr)
        return render_no_ai(data, comparison)

    facts_lines = []
    for name, r in comparison.scenarios:
        facts_lines.append(
            f"- 「{name}」: 進店 {r.n_arrived} 組 / 服務完 {r.n_served} 組 / 流失 {r.n_lost} 組 ({r.loss_rate_pct}%) / "
            f"平均等 {r.avg_wait_time_min} 分 / P95 等 {r.p95_wait_time_min} 分 / "
            f"營收 NT${r.revenue_ntd:,} / 服務員忙 {r.server_utilization_pct}% / 廚房忙 {r.kitchen_utilization_pct}%"
        )

    roi_lines = []
    base_rev = comparison.scenarios[comparison.baseline_idx][1].revenue_ntd
    for i, (name, r) in enumerate(comparison.scenarios):
        if i == comparison.baseline_idx:
            continue
        s = data["scenarios"][i]
        extra_cost = s.get("monthly_extra_cost_ntd", 0)
        monthly_lift = (r.revenue_ntd - base_rev) * 30
        net = monthly_lift - extra_cost
        roi_lines.append(f"- {name}: 月增成本 NT${extra_cost:,}, 月增營收 NT${monthly_lift:+,}, 淨增益 NT${net:+,}")

    prompt = f"""你是一位餐飲業經營顧問。下面是「{data['restaurant_name']}」尖峰時段 (午餐 {data['lunch_peak_window']}) 4 種人力配置的 agent-based simulation 結果。

各情境 KPI:
{chr(10).join(facts_lines)}

ROI 數字 (已純函式算好,你**絕不能改數字**):
{chr(10).join(roi_lines)}

請只寫一份「給老闆讀的 5-7 行建議」,口語化、不超過 300 字。重點:
1. 指出瓶頸(廚房 or 服務員)
2. 推薦最佳投資方案 + 理由
3. 1-2 個 risk 要老闆注意(例如 ROI 算法假設 / 平日 vs 假日 / 客單價變動)

**嚴格規則**:
- 引用任何數字必須來自上面 KPI / ROI 區塊,不能編造
- 不要重複 markdown 表格,只寫文字建議
- 不要套話「請考慮」「祝您生意興隆」等

直接寫建議內容,不要有開場白。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    ai_text = resp.content[0].text

    base = render_no_ai(data, comparison)
    return base + "\n\n## 🤖 AI 顧問建議\n\n" + ai_text + "\n"


def main():
    parser = argparse.ArgumentParser(description="peakflow — 餐廳尖峰時段營運模擬器")
    parser.add_argument("--restaurant", default="samples/restaurant.json",
                        help="餐廳設定 JSON 路徑")
    parser.add_argument("--runs", type=int, default=5,
                        help="每情境跑幾次取平均(預設 5)")
    parser.add_argument("--duration", type=float, default=120,
                        help="模擬尖峰持續分鐘數(預設 120 = 2 小時)")
    parser.add_argument("--no-ai", action="store_true",
                        help="不呼叫 LLM,只跑純函式 simulation")
    parser.add_argument("--seed", type=int, default=42,
                        help="隨機種子")
    args = parser.parse_args()

    data = load_restaurant(Path(args.restaurant))
    data["_runs"] = args.runs
    scenarios = build_scenarios(data)
    sim_cfg = SimulationConfig(
        simulation_duration_min=args.duration,
        customer_arrival_rate=data["arrival_pattern"]["customer_arrival_rate_per_min"],
        seed=args.seed,
    )

    comparison = run_scenarios(scenarios, sim_cfg, n_runs=args.runs)

    if args.no_ai:
        print(render_no_ai(data, comparison))
    else:
        print(render_with_ai(data, comparison))


if __name__ == "__main__":
    main()
