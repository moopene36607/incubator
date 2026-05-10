"""salonguard — 台灣美髮 / 美容沙龍 回頭客流失預測 + 個人化 LINE 挽回訊息

Usage:
    # 純函式預測(免 API key)
    python salonguard.py --history samples/customer_history.csv \\
        --today 2026-05-10 --no-ai

    # 加 AI 寫個人化 LINE 訊息
    python salonguard.py --history samples/customer_history.csv \\
        --today 2026-05-10 --out output.md --out-line line_messages.md

設計重點:
- RFM 計算 + 風險評分 100% 純函式
- LLM 只為高風險客戶寫個人化 LINE 挽回訊息(語氣親切但不打擾)
- 三層輸出:高風險名單(老闆看)+ LINE 訊息草稿(老闆確認後群發)+ 流失客 trend
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from rfm import (
    CustomerRFM,
    Visit,
    compute_all,
    filter_by_level,
    rank_by_risk,
)


MESSAGE_SYSTEM = """你是台灣美髮 / 美容沙龍的客戶關係助手,協助店家為「流失風險高」的客人
寫個人化 LINE 挽回訊息。

## 寫作規則

- 繁體中文,語氣親切但專業(像老朋友打招呼,不是 mass marketing)
- 第二人稱對客人(「您」/「妳」),自然不僵硬
- **80 字內**(LINE 訊息要短,客人看 5 秒就決定要不要回)
- 必須引用該客人「上次的具體服務」(從客戶資料中)
- 提到回訪建議時間時自然(例:「最近有空嗎」「下週有空檔」),不要硬塞折扣
- 訊息結尾留個 hook(問句 / 開放邀請),讓客人容易回覆

## 嚴格規則

- 不要寫「親愛的 VIP」「感謝您一直以來的支持」這種空泛 mass marketing
- 不要編造客人沒提供的服務史或個資
- 不要塞長串折扣 / 優惠 / 滿額活動 — 那是 marketing automation,不是「老朋友打招呼」
- 不要結尾署名(由純函式模板加店家名)

## 輸出格式

直接輸出訊息本文,不要任何前後解說、不要 markdown 格式、不要 emoji 開頭
(emoji 適量在訊息中可用,如 ☺️ 🌸 ✨,但不要堆)。
"""


def load_visits(csv_path: Path) -> list[Visit]:
    visits: list[Visit] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            visits.append(Visit(
                customer_name=row["customer_name"].strip(),
                visit_date=date.fromisoformat(row["visit_date"].strip()),
                service=row["service"].strip(),
                price_twd=int(row["price_twd"]),
            ))
    return visits


def llm_write_message(salon_name: str, customer: CustomerRFM) -> str:
    import anthropic

    payload = {
        "salon_name": salon_name,
        "customer_name": customer.name,
        "last_visit_date": customer.last_visit_date.isoformat(),
        "last_service": customer.last_service,
        "last_price_twd": customer.last_price_twd,
        "recency_days": customer.recency_days,
        "avg_interval_days": customer.avg_interval_days,
        "total_visits_past_year": customer.frequency,
        "risk_level": customer.risk_level,
    }
    user_msg = (
        f"請為這位客人寫一段 LINE 挽回訊息:\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=[{"type": "text", "text": MESSAGE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def template_message(salon_name: str, customer: CustomerRFM) -> str:
    """無 AI 時的純函式 LINE 訊息模板。"""
    return (
        f"哈囉 {customer.name},好久不見!上次來做 {customer.last_service} "
        f"已經 {customer.recency_days} 天了,最近有空嗎?想幫您留個適合的時段。☺️"
    )


def render_main_report(salon_name: str, today: date, all_rfm: list[CustomerRFM],
                       high_risk: list[CustomerRFM]) -> str:
    out: list[str] = []
    out.append(f"# {salon_name} — 客戶流失風險警示")
    out.append("")
    out.append(f"**監控日期**: {today.isoformat()}    "
               f"**客戶總數**: {len(all_rfm)}")
    out.append("")

    level_counts = Counter(c.risk_level for c in all_rfm)
    out.append("## 風險分佈總覽")
    out.append("")
    out.append("| 等級 | 人數 | 說明 |")
    out.append("|------|------|------|")
    labels = {
        "active":  ("🟢 活躍",     "回訪間隔正常,在預期範圍內"),
        "watch":   ("🟡 觀察",     "略超預期間隔,但尚未明顯流失"),
        "warning": ("🟠 警示",     "明顯超預期,需主動聯繫"),
        "high":    ("🔴 高風險",   "推算高機率流失中,需立刻挽回"),
        "lost":    ("⚫ 已流失",   "極長時間未回,挽回機率較低"),
    }
    for lvl_key in ("active", "watch", "warning", "high", "lost"):
        zh, desc = labels[lvl_key]
        out.append(f"| {zh} | {level_counts.get(lvl_key, 0)} | {desc} |")
    out.append("")

    out.append(f"## 🎯 本週優先挽回對象 ({len(high_risk)} 位)")
    out.append("")
    if not high_risk:
        out.append("(目前沒有警示 / 高風險客戶,辛苦了 ☺️)")
        out.append("")
    else:
        out.append("| 排名 | 客戶 | 風險分 | 等級 | 距上次 | 平均間隔 | 上次服務 | 客單價 |")
        out.append("|------|------|------:|------|------:|--------:|----------|--------:|")
        for i, c in enumerate(high_risk, 1):
            lvl_zh, _ = labels.get(c.risk_level, (c.risk_level, ""))
            out.append(
                f"| {i} | **{c.name}** | {c.risk_score} | {lvl_zh} | "
                f"{c.recency_days} 天 | {int(c.avg_interval_days)} 天 | "
                f"{c.last_service} | NT${c.last_price_twd:,} |"
            )
        out.append("")
    return "\n".join(out) + "\n"


def render_messages(salon_name: str, high_risk: list[CustomerRFM],
                    use_ai: bool) -> str:
    out: list[str] = []
    out.append(f"# {salon_name} — LINE 挽回訊息草稿")
    out.append("")
    out.append(f"以下訊息由 AI 為每位高風險客戶個人化生成。建議**老闆審閱後**手動傳送,")
    out.append("不要批量自動發送(避免被 LINE 標記為騷擾)。")
    out.append("")

    for i, c in enumerate(high_risk, 1):
        msg = llm_write_message(salon_name, c) if use_ai else template_message(salon_name, c)
        out.append(f"## {i}. {c.name}(風險 {c.risk_score} / {c.recency_days} 天未到)")
        out.append("")
        out.append("```")
        out.append(msg)
        out.append("```")
        out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history", type=Path, required=True, help="客戶預約歷史 CSV")
    parser.add_argument("--salon-name", default="本沙龍", help="沙龍名稱")
    parser.add_argument("--today", help="模擬日期 YYYY-MM-DD(default 系統日期)")
    parser.add_argument("--lookback-months", type=int, default=12, help="回顧月份 (default 12)")
    parser.add_argument("--levels", nargs="+", default=["warning", "high"],
                        help="高風險等級篩選(default warning + high)")
    parser.add_argument("--out", type=Path, help="主報告 markdown 輸出")
    parser.add_argument("--out-line", type=Path, help="LINE 挽回訊息草稿輸出")
    parser.add_argument("--no-ai", action="store_true", help="不呼叫 AI,用模板訊息")
    args = parser.parse_args()

    if not args.history.exists():
        print(f"error: 找不到 {args.history}", file=sys.stderr)
        return 2

    visits = load_visits(args.history)
    today = date.fromisoformat(args.today) if args.today else date.today()

    all_rfm = compute_all(visits, today, lookback_months=args.lookback_months)
    ranked = rank_by_risk(all_rfm)
    high_risk = filter_by_level(ranked, levels=args.levels)

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,改用模板訊息", file=sys.stderr)

    main_report = render_main_report(args.salon_name, today, all_rfm, high_risk)
    msg_report = render_messages(args.salon_name, high_risk, use_ai)

    if args.out:
        args.out.write_text(main_report, encoding="utf-8")
        print(f"已寫入主報告: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(main_report)

    if args.out_line:
        args.out_line.write_text(msg_report, encoding="utf-8")
        print(f"已寫入 LINE 訊息: {args.out_line}", file=sys.stderr)
    elif not args.out:
        sys.stdout.write("\n")
        sys.stdout.write(msg_report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
