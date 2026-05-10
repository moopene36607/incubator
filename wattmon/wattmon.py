"""wattmon — 台灣中小企業 / 餐廳 AMI 智慧電表用電異常偵測 CLI.

純函式做所有偵測 + 數字計算(analyzer.py),LLM 只負責為純函式偵測到的
anomaly 寫人性化解釋 + 節電建議。**LLM 永遠不算電費**。

模式:
  --no-ai  : 只跑純函式偵測 + 列出 anomaly 摘要(免 API key)
  full     : 加上 Claude 為每個 anomaly 寫 100 字解釋 + 3 條行動建議
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from analyzer import (
    Anomaly,
    PeriodSummary,
    Reading,
    detect_all,
    parse_csv,
    summarize,
    NTD_PER_KWH,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣中小企業節電顧問。輸入是純函式偵測到的用電異常 (anomalies),你的工作:

    對每筆 anomaly,寫:
      1. **possible_causes**: 2-3 條最可能成因(基於台灣餐飲 / 工廠 / 美業常見情境)
      2. **action_items**: 3 條具體行動建議(可立即執行)
      3. **estimated_savings_ntd**: 改善後預估月省金額(從 anomaly.context.extra_cost_ntd 推估,絕不憑空產生)

    硬規則:
      - 你**絕不**重新計算 anomaly 的 kWh 或費用 — 那些都是純函式算出的。直接引用 context 數字。
      - 不要猜 anomaly 沒有的數字。沒提到的設備 / 客流 / 員工資訊不要編造。
      - 行動建議必須**具體可執行**(壞例:「節能」、「檢查設備」;好例:「請維修廠商檢查冷凍櫃 R134a 冷媒壓力」)
      - 用台灣繁體中文 + 在地用語(冷氣壓縮機 / 冷凍櫃 / 變頻 / 起停 / 待機)
      - 嚴禁推銷「換新設備」當主建議 — 老闆要的是先排除問題。

    回覆 JSON:
    {
      "explanations": [
        {
          "anomaly_index": 0,
          "possible_causes": ["...", "..."],
          "action_items": ["...", "...", "..."],
          "estimated_savings_ntd": 850,
          "estimated_savings_note": "假設成因是冷凍櫃失溫;每月夜間多耗 200 度 × NT$3.5"
        },
        ...
      ],
      "overall_summary": "本月用電量 XXX 度 / NT$XXX。偵測到 N 筆異常,主要集中在...",
      "top_3_priority_actions": ["1. ...", "2. ...", "3. ..."]
    }
""").strip()


def _fmt_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M")


def render_summary_block(s: PeriodSummary) -> str:
    days = (s.end - s.start).days + 1
    return textwrap.dedent(f"""
        ## 期間摘要 ({_fmt_ts(s.start)} → {_fmt_ts(s.end)},共 {days} 天)

        - **總用電**: {s.total_kwh:,.1f} kWh
        - **估算電費**: NT$ {s.cost_estimate_ntd:,.0f}(以商業電價 NT$ {NTD_PER_KWH}/kWh 簡化估算)
        - **Peak 30 分鐘**: {s.peak_kwh_30min} kWh @ {_fmt_ts(s.peak_at)}
        - **凌晨 base load (2-5 點中位數)**: {s.base_load_kwh_per_30min} kWh / 30min
        - **店休時段比例 (23:00-06:00)**: {s.night_pct}% of total
        - **平日日均**: {s.weekday_avg_daily_kwh} kWh / **週末日均**: {s.weekend_avg_daily_kwh} kWh
    """).strip()


def render_anomaly_block_no_ai(a: Anomaly, idx: int) -> str:
    extra_cost = a.context.get("extra_cost_ntd", a.context.get("monthly_extra_cost_ntd", 0))
    return textwrap.dedent(f"""
        ### 異常 #{idx + 1}: [{a.severity.upper()}] {a.code}

        - **時段**: {_fmt_ts(a.timestamp_start)} → {_fmt_ts(a.timestamp_end)}
        - **觀察**: {a.summary}
        - **預期 kWh**: {a.expected_kwh} / **實際 kWh**: {a.observed_kwh} / **偏差**: {a.deviation_pct:+.0f}%
        - **多耗 (估算)**: NT$ {extra_cost:,.0f}
    """).strip()


def render_anomaly_block_with_ai(a: Anomaly, idx: int, ai: dict) -> str:
    extra_cost = a.context.get("extra_cost_ntd", a.context.get("monthly_extra_cost_ntd", 0))
    causes = "\n".join(f"  - {c}" for c in ai.get("possible_causes", []))
    actions = "\n".join(f"  {i+1}. {a_}" for i, a_ in enumerate(ai.get("action_items", [])))
    savings = ai.get("estimated_savings_ntd", 0)
    savings_note = ai.get("estimated_savings_note", "")
    return textwrap.dedent(f"""
        ### 異常 #{idx + 1}: [{a.severity.upper()}] {a.code}

        - **時段**: {_fmt_ts(a.timestamp_start)} → {_fmt_ts(a.timestamp_end)}
        - **觀察**: {a.summary}
        - **預期 kWh**: {a.expected_kwh} / **實際 kWh**: {a.observed_kwh} / **偏差**: {a.deviation_pct:+.0f}%
        - **多耗 (估算)**: NT$ {extra_cost:,.0f}

        **可能成因**:
        {causes}

        **建議行動**:
        {actions}

        **改善後預估月省**: NT$ {savings:,} ({savings_note})
    """).strip()


def ai_explain(summary: PeriodSummary, anomalies: list[Anomaly]) -> dict:
    """呼叫 Claude 為純函式偵測到的 anomaly 寫解釋 + 建議。"""
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")

    client = Anthropic()
    payload = {
        "summary": {
            "total_kwh": summary.total_kwh,
            "cost_estimate_ntd": summary.cost_estimate_ntd,
            "base_load_per_30min": summary.base_load_kwh_per_30min,
            "night_pct": summary.night_pct,
            "weekday_avg_daily_kwh": summary.weekday_avg_daily_kwh,
            "weekend_avg_daily_kwh": summary.weekend_avg_daily_kwh,
        },
        "anomalies": [
            {
                "index": i,
                "code": a.code,
                "severity": a.severity,
                "summary": a.summary,
                "observed_kwh": a.observed_kwh,
                "expected_kwh": a.expected_kwh,
                "deviation_pct": a.deviation_pct,
                "context": a.context,
            }
            for i, a in enumerate(anomalies)
        ],
    }
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}],
    )
    text = resp.content[0].text
    # 提取 JSON
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def render_report(
    site_name: str,
    summary: PeriodSummary,
    anomalies: list[Anomaly],
    ai: dict | None = None,
) -> str:
    parts: list[str] = []
    parts.append(f"# wattmon 用電異常偵測報告 — {site_name}\n")
    parts.append(render_summary_block(summary))
    parts.append("")
    if not anomalies:
        parts.append("## 異常偵測\n\n本期未偵測到顯著異常 ✓")
    else:
        parts.append(f"## 異常偵測 (共 {len(anomalies)} 筆)\n")
        for i, a in enumerate(anomalies):
            if ai and i < len(ai.get("explanations", [])):
                parts.append(render_anomaly_block_with_ai(a, i, ai["explanations"][i]))
            else:
                parts.append(render_anomaly_block_no_ai(a, i))
            parts.append("")
    if ai:
        parts.append("## 整體分析\n")
        parts.append(ai.get("overall_summary", ""))
        parts.append("")
        actions = ai.get("top_3_priority_actions", [])
        if actions:
            parts.append("### 本月 Top 3 優先行動\n")
            for line in actions:
                parts.append(f"- {line}")
        parts.append("")
    parts.append("---")
    parts.append(f"*由 wattmon 自動產生於 {datetime.now().strftime('%Y-%m-%d')}。"
                 f"電費為以 NT${NTD_PER_KWH}/kWh 簡化估算,實際請對照台電帳單。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="wattmon — AMI 智慧電表異常偵測")
    p.add_argument("csv", help="AMI 30 分鐘讀值 CSV (timestamp,kwh)")
    p.add_argument("--site-name", default="未命名店家", help="店家名稱")
    p.add_argument("--out", help="輸出 markdown 檔案路徑")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    readings = parse_csv(args.csv)
    s = summarize(readings)
    anomalies = detect_all(readings)

    ai = None
    if not args.no_ai:
        ai = ai_explain(s, anomalies) if anomalies else None

    report = render_report(args.site_name, s, anomalies, ai)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
