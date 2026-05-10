"""weddingmatch — 台灣準新人婚攝風格 AI 配對

Usage:
    # 結構化 JSON(免 API key)
    python weddingmatch.py samples/sample_query.json

    # 自由文字風格描述(需 API key)
    python weddingmatch.py --freetext samples/sample_query_freetext.txt

    # 寫入檔案
    python weddingmatch.py samples/sample_query.json --out report.md

設計重點:
- 配對演算法 (matching.py) 100% 純函式 cosine similarity
- AI 只在兩個地方介入:
    1. 解析自由文字風格描述 → 12 維 style_vector
    2. 為配對結果撰寫人性化推薦理由

ANTHROPIC_API_KEY 在 --freetext 與 AI 推薦理由模式才需要。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from matching import MatchResult, UserQuery, match
from photographers_db import (
    PHOTOGRAPHERS,
    Photographer,
    STYLE_DIMENSIONS,
    STYLE_LABELS_ZH,
)


PARSE_SYSTEM = """你是台灣婚禮籌備助手。準新人會用自由文字描述他們喜歡的婚攝風格,
你的任務是把描述轉成 12 維 0/1 風格向量。

## 12 維風格(順序固定)

{dim_table}

## 輸出格式 (只回 JSON,不要其他文字)

```json
{{
  "style_vector": [<12 個 0 或 1, 順序對應上方>],
  "matched_dimensions": ["<開啟的 tag 中文名,供查核>"],
  "budget_min_twd": <整數或 null>,
  "budget_max_twd": <整數或 null>,
  "region_preference": "北部 | 中部 | 南部 | 全台 | null"
}}
```

## 規則

- **典型情境**:大多數新人會勾選 3-6 個 tag = 1。如果用戶描述很模糊只給 1-2 個明確線索,只開那幾個。
- **互斥性**:`film_emulation` 與 `digital_clean` 通常不會同時 = 1(底片感 vs 數位乾淨是衝突取向)。但若用戶兩種都喜歡,可以都開。
- **隱含對應**:
  - 「自然」「不擺拍」「抓拍」→ candid
  - 「有故事感」「像紀錄片」→ journalistic
  - 「網美風」「IG 感」→ pastel_soft + outdoor (常見組合)
  - 「電影感」「大片感」→ cinematic
  - 「老長輩會喜歡的傳統」→ posed + indoor_ceremony
  - 「飯店宴客為主」→ indoor_ceremony
  - 「在森林 / 海邊拍」→ outdoor
- **預算解析**:「6 萬」=> 60000;「8-10 萬」=> min 80000 max 100000;「不超過 12 萬」=> max 120000
- **地區**:「台北 / 新北 / 桃園 / 基隆」→ 北部;「台中 / 苗栗 / 彰化 / 南投」→ 中部;「高雄 / 台南 / 屏東」→ 南部
- **不要編造**:用戶沒提的維度設 0、沒提的預算 / 地區設 null
"""


REASONING_SYSTEM = """你是台灣婚禮籌備助手,根據純函式配對演算法的結果,為準新人寫一段人性化的婚攝推薦理由。

## 寫作規則

- 繁體中文,口語但專業(像懂婚禮的朋友推薦)
- 每位婚攝寫 2-3 句:① 為什麼風格匹配(引用具體 overlap tags)② 一個記憶點(從 short_bio 抽出)③ 預算 / 地區提醒(若有 stretches_budget 或全台)
- 不要寫「太棒了」「絕佳選擇」這種空泛 hype
- 不要編造婚攝沒提供的資訊

## 輸出格式

直接輸出 markdown,Top N 排名 + 每位介紹 + 結尾 1 句「給準新人的下一步建議」(例:先看 IG 作品集、約見面聊風格)。

不要包含使用者的查詢內容或 photographer code,只用婚攝姓名 + IG handle。
"""


def build_parse_system() -> str:
    rows = "\n".join(
        f"- `{dim}` ({STYLE_LABELS_ZH[dim]})"
        for dim in STYLE_DIMENSIONS
    )
    return PARSE_SYSTEM.format(dim_table=rows)


def llm_parse_query(text: str) -> UserQuery:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": build_parse_system(),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"準新人描述: {text}"}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON: {raw}")
    parsed = json.loads(raw[start : end + 1])
    vec = tuple(int(v) for v in parsed["style_vector"])
    if len(vec) != 12:
        raise ValueError(f"style_vector 必須 12 維,得到 {len(vec)}")
    return UserQuery(
        style_vector=vec,
        budget_min_twd=parsed.get("budget_min_twd"),
        budget_max_twd=parsed.get("budget_max_twd"),
        region_preference=parsed.get("region_preference"),
        free_text=text,
    )


def llm_format_recommendation(query: UserQuery, matches: list[MatchResult]) -> str:
    import anthropic

    payload: list[dict[str, Any]] = []
    for r in matches:
        p = r.photographer
        payload.append({
            "rank": len(payload) + 1,
            "name": p.name,
            "ig_handle": p.ig_handle,
            "region": p.region,
            "price_range": f"NT${p.price_range_min_twd:,}-{p.price_range_max_twd:,}",
            "short_bio": p.short_bio,
            "similarity": round(r.similarity, 3),
            "overlap_tags": r.overlap_tags,
            "price_fit": r.price_fit,
            "region_fit": r.region_fit,
        })
    user_msg = (
        "## 配對結果(已依純函式演算法排序好)\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n\n"
        "請寫推薦段落。"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=[{"type": "text", "text": REASONING_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def render_skeleton_recommendation(matches: list[MatchResult]) -> str:
    """無 AI 時的簡潔推薦清單。"""
    out: list[str] = []
    for i, r in enumerate(matches, 1):
        p = r.photographer
        out.append(f"### {i}. {p.name}({p.ig_handle})")
        out.append("")
        out.append(f"- 風格匹配度: **{r.similarity:.0%}**")
        out.append(f"- 區域: {p.region}({r.region_fit})")
        out.append(f"- 價格: NT${p.price_range_min_twd:,}-{p.price_range_max_twd:,}({r.price_fit})")
        if r.overlap_tags:
            out.append(f"- 共同風格: {', '.join(r.overlap_tags)}")
        out.append(f"- 簡介: {p.short_bio}")
        out.append("")
    return "\n".join(out)


def render_full_report(query: UserQuery, matches: list[MatchResult],
                       reasoning_md: str) -> str:
    today = date.today().isoformat()
    user_tags_zh = [
        STYLE_LABELS_ZH[dim]
        for dim, v in zip(STYLE_DIMENSIONS, query.style_vector)
        if v == 1
    ]

    out: list[str] = []
    out.append(f"# 婚攝配對結果")
    out.append("")
    out.append(f"**配對日期**: {today}")
    out.append("")

    out.append("## 你的需求摘要")
    out.append("")
    out.append(f"- **偏好風格**: {', '.join(user_tags_zh) if user_tags_zh else '(未明確指定)'}")
    if query.budget_min_twd or query.budget_max_twd:
        bmin = query.budget_min_twd or 0
        bmax = query.budget_max_twd or 0
        if bmin and bmax:
            out.append(f"- **預算**: NT${bmin:,} ~ NT${bmax:,}")
        elif bmax:
            out.append(f"- **預算上限**: NT${bmax:,}")
        elif bmin:
            out.append(f"- **預算下限**: NT${bmin:,}")
    if query.region_preference:
        out.append(f"- **地區偏好**: {query.region_preference}")
    out.append("")
    if query.free_text:
        out.append(f"_原始描述_:「{query.free_text.strip()}」")
        out.append("")

    out.append(f"## Top {len(matches)} 配對結果")
    out.append("")

    if reasoning_md:
        out.append(reasoning_md)
    else:
        out.append(render_skeleton_recommendation(matches))

    out.append("")
    out.append("---")
    out.append("")
    out.append(f"*由 weddingmatch 自動產生於 {today}。配對演算法使用 cosine similarity over 12 維風格向量,純函式可重現。*")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", nargs="?", type=Path, help="結構化 JSON")
    parser.add_argument("--freetext", type=Path, help="自由文字描述檔(需 API key)")
    parser.add_argument("--out", type=Path, help="輸出 markdown 路徑")
    parser.add_argument("--top-n", type=int, default=5, help="推薦人數 (default 5)")
    parser.add_argument("--no-ai", action="store_true", help="不呼叫 AI 寫推薦理由")
    args = parser.parse_args()

    raw_text = ""
    if args.freetext:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: --freetext 需要 ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        if not args.freetext.exists():
            print(f"error: 找不到 {args.freetext}", file=sys.stderr)
            return 2
        raw_text = args.freetext.read_text(encoding="utf-8")
        query = llm_parse_query(raw_text)
    else:
        if not args.input or not args.input.exists():
            print("error: 請提供結構化 JSON 或 --freetext", file=sys.stderr)
            return 2
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        query = UserQuery(
            style_vector=tuple(int(v) for v in payload["style_vector"]),
            budget_min_twd=payload.get("budget_min_twd"),
            budget_max_twd=payload.get("budget_max_twd"),
            region_preference=payload.get("region_preference"),
            free_text=payload.get("free_text", ""),
        )

    matches = match(query, top_n=args.top_n)
    if not matches:
        print("warn: 找不到任何符合的婚攝", file=sys.stderr)

    use_ai_reasoning = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_ai_reasoning and matches:
        reasoning = llm_format_recommendation(query, matches)
    else:
        reasoning = render_skeleton_recommendation(matches)

    report = render_full_report(query, matches, reasoning)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
