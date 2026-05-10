"""propvision — 台灣房屋室內照片 Vision AI 估價

Usage:
    # 結構化 JSON 輸入(免 API key,renovation_score 已給)
    python propvision.py samples/sample_input.json --no-ai

    # 自然文字房況描述 + AI 解析(需 API key)
    python propvision.py samples/sample_input.json --out report.md

設計重點:
- 所有金額計算 100% 純函式(pricing_model.py)
- AI 只在兩件事:
    1. 從照片狀況描述抽取結構化裝修評分 1-10
    2. 為估值結果寫人性化「為什麼這個價」說明
- 不下定論(估值報告僅供參考,實價仍以雙方議價為主)

ANTHROPIC_API_KEY 在 AI 解析 / AI 報告模式才必要。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pricing_model import (
    HouseInput,
    PricingBreakdown,
    calc_valuation,
)


VISION_PARSE_SYSTEM = """你是台灣房屋室內裝修評估專家。準新人 / 房仲會給你 3-5 張室內
照片或文字描述,你的任務是給出客觀的裝修評分。

## 輸出格式(只回 JSON,不要其他文字)

```json
{
  "renovation_score": <整數 1-10>,
  "renovation_notes": [
    "<具體觀察點 1>",
    "<具體觀察點 2>",
    "<...>"
  ],
  "concerns": [
    "<明顯瑕疵或顧慮,例如:廁所有發霉跡象>"
  ]
}
```

## 評分 rubric (1-10)

- **9-10 全新豪裝**: 名牌廚具 / 進口建材 / 設計師裝修 / 屋齡 5 年內
- **7-8 良好裝修**: 5-10 年內裝修過 / 廚具浴室更新 / 牆面塗料新 / 採光良好
- **5-6 標準屋況**: 一般使用痕跡 / 廚具浴室仍堪用但非新 / 牆面有部分泛黃
- **3-4 老舊但可住**: 廚具浴室 15+ 年 / 磁磚老式 / 油煙累積 / 需大規模翻新
- **1-2 嚴重待整修**: 漏水 / 壁癌嚴重 / 廚具浴室不堪用 / 結構性問題

## 評分原則

- 不要過度樂觀(房仲會自吹)
- 不要看單張照片就下定論 — 用 3-5 張綜合判斷
- 嚴重瑕疵(漏水 / 壁癌 / 結構)直接給 1-2,不論其他細節再美
- 「採光不足」「通風不佳」是非裝修問題,不影響 score,但記入 concerns

## 規則

- 只看 user 提供的照片 / 描述,不要編造未提到的細節
- renovation_notes 引用具體觀察(如「廚具是 IKEA 約 3 年內款式」),不要寫「裝修不錯」
"""


REASONING_SYSTEM = """你是台灣房屋估價師助理,為估值結果寫人性化說明。

## 寫作風格

- 繁體中文,中性客觀口吻
- 引用具體數字(NT$ 金額、坪、屋齡、樓層、裝修分數)
- 不誇大、不貶低、不下定論(避免「絕對買!」「不要買!」)
- 風險點(漏水、壁癌、嫌惡設施)要明確指出
- 對議價空間給「自售合理價 / 急售價 / 房仲收購價」三種參考

## 輸出格式

直接輸出 markdown,4-6 段(不要前後解說、不要重複報告其他資料)。

## 嚴格規則

- 估值僅供「議價起點」參考,不是鑑定
- 不要寫「保證會漲」「投資穩賺」這種推銷話術
- 用「建議」「可考慮」「值得注意」這類審慎措辭
"""


def parse_payload_to_input(payload: dict[str, Any]) -> HouseInput:
    h = payload["house"]
    return HouseInput(
        region=h["region"],
        region_avg_price_per_ping=int(h["region_avg_price_per_ping"]),
        size_ping=float(h["size_ping"]),
        age_years=int(h["age_years"]),
        floor=int(h["floor"]),
        total_floors=int(h["total_floors"]),
        orientation=h.get("orientation", "未知"),
        has_elevator=bool(h.get("has_elevator", True)),
        has_parking=bool(h.get("has_parking", False)),
        near_mrt_meters=h.get("near_mrt_meters"),
        nearby_school_district=h.get("nearby_school_district", ""),
        nearby_dislike_facilities=tuple(h.get("nearby_dislike_facilities", [])),
        renovation_score=int(h.get("renovation_score", 5)),
        renovation_notes=tuple(h.get("renovation_notes", [])),
    )


def ai_parse_photos(photo_descriptions: list[str]) -> dict[str, Any]:
    import anthropic

    user_msg = "照片狀況描述(每行一張):\n\n" + "\n".join(
        f"- {d}" for d in photo_descriptions
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": VISION_PARSE_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON: {raw}")
    return json.loads(raw[start : end + 1])


def ai_write_reasoning(inp: HouseInput, br: PricingBreakdown) -> str:
    import anthropic

    summary = {
        "區域": inp.region,
        "坪數": inp.size_ping,
        "屋齡": inp.age_years,
        "樓層": f"{inp.floor}/{inp.total_floors}",
        "朝向": inp.orientation,
        "電梯": inp.has_elevator,
        "車位": inp.has_parking,
        "近捷運m": inp.near_mrt_meters,
        "嫌惡設施": list(inp.nearby_dislike_facilities),
        "學區": inp.nearby_school_district,
        "裝修評分": inp.renovation_score,
        "裝修觀察": list(inp.renovation_notes),
        "估值中位": br.final_midpoint,
        "估值區間": [br.range_low, br.range_high],
        "折舊明細": {
            "base": br.base_price,
            "after_age": br.after_age,
            "after_floor": br.after_floor,
            "after_orientation": br.after_orientation,
            "after_renovation": br.after_renovation,
            "total_adjustment_pct": br.total_adjustment_pct,
        },
        "加減分": [{"key": k, "delta": d, "label": l} for k, d, l in br.adjustment_explanations],
    }
    user_msg = f"```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n\n請為這份估值寫人性化說明。"
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=[{"type": "text", "text": REASONING_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def fmt_twd(amount: int) -> str:
    if amount >= 10000:
        return f"NT$ {amount:,}({amount / 10000:.0f} 萬)"
    return f"NT$ {amount:,}"


def render_report(inp: HouseInput, br: PricingBreakdown, reasoning_md: str | None) -> str:
    today = date.today().isoformat()
    out: list[str] = []
    out.append(f"# 房屋估價報告 — {inp.region}")
    out.append("")
    out.append(f"**估值日期**: {today}")
    out.append("")

    out.append("## 物件基本資料")
    out.append("")
    out.append(f"- **區域**: {inp.region}")
    out.append(f"- **坪數**: {inp.size_ping} 坪")
    out.append(f"- **屋齡**: {inp.age_years} 年")
    out.append(f"- **樓層**: {inp.floor}F / 共 {inp.total_floors}F")
    out.append(f"- **朝向**: {inp.orientation}")
    out.append(f"- **電梯**: {'有' if inp.has_elevator else '無'}")
    out.append(f"- **車位**: {'有' if inp.has_parking else '無'}")
    if inp.near_mrt_meters is not None:
        out.append(f"- **距捷運**: {inp.near_mrt_meters} 公尺")
    if inp.nearby_school_district:
        out.append(f"- **學區**: {inp.nearby_school_district}")
    if inp.nearby_dislike_facilities:
        out.append(f"- **嫌惡設施**: {', '.join(inp.nearby_dislike_facilities)}")
    out.append(f"- **裝修評分(AI 推估)**: {inp.renovation_score} / 10")
    if inp.renovation_notes:
        out.append("- **裝修觀察**:")
        for n in inp.renovation_notes:
            out.append(f"  - {n}")
    out.append("")

    out.append("## 估值結果")
    out.append("")
    out.append(f"### 自售合理價區間")
    out.append("")
    out.append(f"**{fmt_twd(br.range_low)} ~ {fmt_twd(br.range_high)}**,中位 **{fmt_twd(br.final_midpoint)}**")
    out.append("")
    out.append(f"### 議價參考")
    out.append("")
    out.append(f"- **自售開價建議**:{fmt_twd(int(br.final_midpoint * 1.05))}(中位 +5% 預留下殺空間)")
    out.append(f"- **急售底價**:{fmt_twd(br.range_low)}(區間下緣)")
    out.append(f"- **房仲收購估**:{fmt_twd(int(br.final_midpoint * 0.85))}(扣 15% 利潤)")
    out.append("")

    out.append("## 估值明細(純函式可重現)")
    out.append("")
    out.append("| 步驟 | 金額 | factor |")
    out.append("|------|-------:|--------:|")
    out.append(f"| 1. 區域均價 × 坪數 | {fmt_twd(br.base_price)} | NT${inp.region_avg_price_per_ping:,}/坪 × {inp.size_ping} 坪 |")
    out.append(f"| 2. 屋齡折舊({inp.age_years} 年) | {fmt_twd(br.after_age)} | × **{br.age_factor}** |")
    out.append(f"| 3. 樓層調整({inp.floor}F / {inp.total_floors}F) | {fmt_twd(br.after_floor)} | × **{br.floor_factor}** |")
    out.append(f"| 4. 朝向({inp.orientation}) | {fmt_twd(br.after_orientation)} | × **{br.orientation_factor}** |")
    out.append(f"| 5. 裝修評分({inp.renovation_score}/10) | {fmt_twd(br.after_renovation)} | × **{br.renovation_factor}** |")
    out.append(f"| 6. 加減分(累計 {br.total_adjustment_pct:+.1f}%) | **{fmt_twd(br.final_midpoint)}** | |")
    out.append("")

    if br.adjustment_explanations:
        out.append("## 加減分明細")
        out.append("")
        for key, delta, label in br.adjustment_explanations:
            sign = "✓" if delta > 0 else "−"
            out.append(f"- {sign} **{label}** ({delta:+.0%})")
        out.append("")

    if reasoning_md:
        out.append("## 估值說明")
        out.append("")
        out.append(reasoning_md)
        out.append("")

    out.append("---")
    out.append("")
    out.append(f"*propvision 自動產生於 {today}。估值僅供議價起點參考,不作為正式不動產鑑價依據。實際成交價以雙方議價結果為準。*")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="物件 JSON 路徑")
    parser.add_argument("--out", type=Path, help="輸出 markdown 路徑")
    parser.add_argument("--no-ai", action="store_true",
                        help="不呼叫 AI;renovation_score 從 JSON 帶")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,改用 --no-ai 模式", file=sys.stderr)

    # AI vision 解析(若有照片描述 + 有 API key)
    photo_desc = payload.get("photo_descriptions")
    if use_ai and photo_desc:
        ai_result = ai_parse_photos(list(photo_desc))
        payload["house"]["renovation_score"] = int(ai_result["renovation_score"])
        payload["house"]["renovation_notes"] = list(ai_result.get("renovation_notes", []))

    inp = parse_payload_to_input(payload)
    breakdown = calc_valuation(inp)

    reasoning = ai_write_reasoning(inp, breakdown) if use_ai else None
    report = render_report(inp, breakdown, reasoning)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
