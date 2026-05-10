"""motoval — 台灣二手機車 AI 估價助手

Usage:
    # 結構化 JSON 輸入(免 API key)
    python motoval.py samples/sample_input.json

    # 自由文字描述輸入(需 API key)
    python motoval.py --freetext samples/sample_input_freetext.txt

    # 寫入檔案
    python motoval.py samples/sample_input.json --out report.md

設計重點:
- 純函式估價 (pricing.py) 全程無 LLM,絕不亂算錢
- AI 只負責:① 解析自由文字車況描述 → 結構化 input
            ② 產生「為什麼這個價」的中文說明文字
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from motorcycle_db import (
    ADJUSTMENT_FACTORS,
    CONDITION_MULTIPLIERS,
    MotorcycleModel,
    all_models,
    lookup,
)
from pricing import (
    ADJUSTMENT_LABELS,
    ValuationInput,
    ValuationResult,
    calc_valuation,
)


PARSE_SYSTEM = """你是台灣二手機車估價助理。使用者會給你自由文字的車況描述,你的任務
是把它轉成結構化 JSON,**只回 JSON,不要其他文字**。

## 可選車款代碼

{models_block}

## 可選車況等級

- "excellent" — 顯著高於平均(記錄齊全、外觀近全新、無事故、單一車主)
- "good"      — 略高於平均(一般保養、外觀無大刮傷)
- "fair"      — 平均水準(一般使用磨耗)
- "poor"      — 顯著低於平均(重大事故 / 泡水 / 漆面嚴重 / 引擎異音)

## 可選加分減分項目

{adjustments_block}

## 輸出 JSON 格式

```json
{{
  "model_code": "<上方代碼>",
  "year": <西元年份,4 位數>,
  "mileage_km": <整數>,
  "condition_rating": "excellent | good | fair | poor",
  "adjustments": ["<key1>", "<key2>", ...]
}}
```

## 規則

- 只用上方提供的車款代碼。如果使用者描述的車款不在清單中,回傳最接近的代碼
  並在 JSON 加 `"_warning": "原始描述車款 XX 不在清單中,改用最接近的 YY"`
- 「7 萬公里」=> 70000;「3 萬 5」=> 35000
- 若使用者沒提到年份,請從上下文推估或填 null
- adjustments 只填使用者描述明確的項目;沒提到不要猜
- 不要編造任何使用者沒說的資訊
"""


def build_parse_system() -> str:
    models = "\n".join(
        f"- `{m.code}` {m.brand} {m.name} ({m.displacement_cc}cc, MSRP ~NT${m.msrp_twd:,})"
        for m in all_models()
    )
    adjustments = "\n".join(
        f"- `{key}` ({delta:+.0%}) — {ADJUSTMENT_LABELS.get(key, key)}"
        for key, delta in ADJUSTMENT_FACTORS.items()
    )
    return PARSE_SYSTEM.format(models_block=models, adjustments_block=adjustments)


def llm_parse_freetext(text: str) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": build_parse_system(), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"請從以下文字描述抽出結構化資料:\n\n{text}"}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON: {raw}")
    return json.loads(raw[start : end + 1])


def fmt_twd(amount: int) -> str:
    return f"NT$ {amount:,}"


def render_report(inp: ValuationInput, result: ValuationResult,
                  raw_description: str | None = None) -> str:
    today = date.today().isoformat()
    out: list[str] = []

    out.append(f"# 二手機車估價報告 — {inp.model.brand} {inp.model.name}")
    out.append("")
    out.append(f"**估值日期**: {today}    **估值年份**: {inp.valuation_year}")
    out.append("")

    out.append("## 車輛基本資料")
    out.append("")
    out.append(f"- **車款**: {inp.model.brand} {inp.model.name} ({inp.model.displacement_cc} cc"
               + (", 電動" if inp.model.is_electric else "") + ")")
    out.append(f"- **出廠年份**: {inp.year} 年(車齡 {inp.valuation_year - inp.year} 年)")
    out.append(f"- **里程**: {inp.mileage_km:,} km")
    out.append(f"- **車況等級**: **{inp.condition_rating}** ({CONDITION_MULTIPLIERS[inp.condition_rating]:.0%})")
    out.append("")

    out.append("## 估值結果")
    out.append("")
    out.append(f"### 自售合理價(FB / Yahoo / 露天)")
    out.append("")
    out.append(f"建議區間 **{fmt_twd(result.range_low_twd)} ~ {fmt_twd(result.range_high_twd)}**,"
               f"中位 **{fmt_twd(result.midpoint_twd)}**")
    out.append("")
    out.append(f"### 二手車行收購價(扣 20-25% 利潤)")
    out.append("")
    out.append(f"預期 **{fmt_twd(result.dealer_acquisition_twd)} ~ "
               f"{fmt_twd(result.dealer_acquisition_high_twd)}**")
    out.append("")
    out.append(f"### 急售底價(1 週內成交)")
    out.append("")
    out.append(f"參考 **{fmt_twd(int(result.midpoint_twd * 0.85))}**(自售合理價下緣)")
    out.append("")

    out.append("## 折舊明細")
    out.append("")
    b = result.breakdown
    out.append("| 步驟 | 金額 / 倍率 |")
    out.append("|------|-------------:|")
    out.append(f"| 1. 出廠新車 MSRP | {fmt_twd(int(b['msrp']))} |")
    out.append(f"| 2. 年份折舊 ({inp.model.annual_depreciation_rate:.0%}/年 × {int(b['age_years'])} 年) "
               f"| {fmt_twd(int(b['after_age_depreciation']))} |")
    out.append(f"| 3. 里程修正 (預期 {int(b['expected_total_km']):,} km / 實際 {inp.mileage_km:,} km) "
               f"× **{b['mileage_factor']}** | {fmt_twd(int(b['after_mileage']))} |")
    out.append(f"| 4. 車況等級 × **{b['condition_multiplier']}** | {fmt_twd(int(b['after_condition']))} |")
    out.append(f"| 5. 細項加減分 (累計 **{b['total_adjustment_pct']:+.1f}%**) "
               f"| **{fmt_twd(int(b['final']))}** |")
    out.append("")

    if result.adjustment_explanations:
        out.append("## 細項加分 / 減分")
        out.append("")
        for key, delta, label in result.adjustment_explanations:
            sign = "✓" if delta > 0 else "−"
            out.append(f"- {sign} **{label}** ({delta:+.0%})")
        out.append("")

    out.append("## 議價建議")
    out.append("")
    out.append("- **自售買家**:從區間中位 + 5% 開價,預留下殺空間到區間下緣 + 10%")
    out.append("- **賣給車行**:車行收購價已含其利潤,不太能再殺;若車行報太低,直接走自售")
    out.append("- **急售處分**:1 週內要成交,定價落在「自售下緣」最快")
    out.append("")
    out.append("**參考此報告時注意**:")
    out.append("- 估值不含車主過戶費 (約 NT$200-450)、強制險月剩餘額")
    out.append("- 真實成交價會受該車款季節性供需、地區、買賣雙方議價能力影響")
    out.append("- 大改車 / 海外水貨 / 競品稀缺性等情境本工具未涵蓋")
    out.append("")

    if raw_description:
        out.append("---")
        out.append("")
        out.append("### 原始車況描述(供查核)")
        out.append("")
        out.append("> " + raw_description.replace("\n", "\n> "))
        out.append("")

    out.append("---")
    out.append("")
    out.append(f"*motoval prototype 自動產生於 {today}。"
               f"估值僅供參考,實際成交價以雙方議價結果為準。*")

    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", nargs="?", type=Path, help="結構化 JSON 輸入")
    parser.add_argument("--freetext", type=Path, help="自由文字描述檔(需 API key)")
    parser.add_argument("--out", type=Path, help="輸出 markdown 路徑")
    args = parser.parse_args()

    raw_description: str | None = None
    if args.freetext:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: --freetext 需要 ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        if not args.freetext.exists():
            print(f"error: 找不到 {args.freetext}", file=sys.stderr)
            return 2
        raw_description = args.freetext.read_text(encoding="utf-8").strip()
        payload = llm_parse_freetext(raw_description)
        print(f"info: AI 解析結果 — {json.dumps(payload, ensure_ascii=False)}", file=sys.stderr)
    else:
        if not args.input or not args.input.exists():
            print("error: 請提供 input JSON 或 --freetext", file=sys.stderr)
            return 2
        payload = json.loads(args.input.read_text(encoding="utf-8"))

    model = lookup(payload["model_code"])
    if model is None:
        print(f"error: 未知車款代碼 {payload['model_code']!r}", file=sys.stderr)
        return 2

    inp = ValuationInput(
        model=model,
        year=int(payload["year"]),
        mileage_km=int(payload["mileage_km"]),
        condition_rating=payload["condition_rating"],
        adjustments=list(payload.get("adjustments", [])),
        valuation_year=int(payload.get("valuation_year", 2026)),
    )
    result = calc_valuation(inp)
    report = render_report(inp, result, raw_description=raw_description)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
