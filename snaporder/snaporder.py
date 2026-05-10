"""snaporder — 台灣 LINE 團媽訂購對話自動整單

Usage:
    # 結構化 JSON 輸入(免 API key)
    python snaporder.py samples/sample_structured.json

    # 自由文字 LINE 對話輸入(需 API key)
    python snaporder.py --chat samples/sample_chat.txt --products samples/products.json

    # 同時輸出 markdown 彙整 + LINE 對帳訊息
    python snaporder.py samples/sample_structured.json \\
        --out summary.md --out-line line_replies.md

設計重點:
- 訂單聚合與金額計算 100% 純函式 (aggregator.py),絕不交 LLM
- AI 只負責「自由文字 LINE 對話 → 結構化 OrderEvent 清單」(aggregator.py 的 input)
- 跳過閒聊訊息(問候 / 確認 / 感謝);只保留訂購相關事件

ANTHROPIC_API_KEY 在 --chat 模式必要(--no-ai 跳過,要結構化 JSON)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from aggregator import (
    AggregatedSummary,
    OrderEvent,
    Product,
    aggregate,
    render_buyer_replies,
    render_markdown_summary,
)


PARSE_SYSTEM = """你是台灣團購 LINE 群組訊息解析助理。賣家(團媽)會把整段團購群組對話貼給你,
你的任務是把每一條訂購相關訊息轉成結構化 JSON。

## 產品清單(只用以下品項代號)

{products_block}

## 輸出格式

只回 JSON,不要任何其他文字:

```json
{{
  "events": [
    {{
      "buyer": "<買家姓名>",
      "item": "<產品代號 — 必須是上方清單中之一>",
      "quantity": <整數,>= 0>,
      "action": "add | set | cancel",
      "line_no": <訊息行號,從 1 開始>,
      "raw_text": "<原始訊息文字節錄,不超過 60 字>"
    }},
    ...
  ]
}}
```

## 解析規則

- **add 動作**:正常訂購語句,例:
  - 「我要 5 包辛辣麵」→ add 5
  - 「+1」「+2 草莓」→ add 1 / 2
  - 「再 2 盒」→ add 2(在前一筆品項上累加,需從上下文判斷)
- **set 動作**:明確修正前一筆,例:
  - 「對不起 草莓改成 2 盒」→ set 2
  - 「總共 5 盒」「我訂的辛辣麵改成 8 包」→ set
- **cancel 動作**:明確取消,例:
  - 「取消我之前的辛辣麵訂單」→ cancel item=辛辣麵
  - 「不要了」「都取消吧」需從上下文推
- **跳過閒聊**:問候、感謝、確認收到、付款詢問、價格詢問 → 不產生 event
- **跳過模糊或不存在的訂單**:有人發「取消」但他從沒下單過 → 跳過
- **品項對應**:用戶可能寫品項俗名(草莓 / 大湖草莓 / 草莓季 都對應 STRAWBERRY)— 用最接近的產品代號
- **不在產品清單的品項**(如:「我要 1 杯珍奶」但產品沒珍奶)→ 仍輸出 event,item 設成原文(後段聚合會跳過)
- **多人對話**:[周大姐] 是團媽自己,通常不訂單;從訊息頭的 [姓名] 找買家
- **同一買家多次訊息**:每筆都產出獨立 event,聚合會合併

## 不要做的事

- 不要編造買家名字(沒提到就不產出 event)
- 不要解讀模糊語句(「之後再買」「下次團購」等不算當前訂單)
- 不要算錢(只輸出數量,純函式聚合會算金額)
"""


def build_parse_system(products: dict[str, Product]) -> str:
    products_block = "\n".join(
        f"- `{code}` → {p.name}({p.unit_label},單價 NT${p.unit_price})"
        for code, p in products.items()
    )
    return PARSE_SYSTEM.format(products_block=products_block)


def llm_parse_chat(chat_text: str, products: dict[str, Product]) -> list[OrderEvent]:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=[{"type": "text", "text": build_parse_system(products),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user",
                   "content": f"以下是 LINE 群組對話(每行一條訊息):\n\n{chat_text}"}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON:\n{raw}")
    parsed = json.loads(raw[start : end + 1])
    return [
        OrderEvent(
            buyer=e["buyer"],
            item=e["item"],
            quantity=int(e["quantity"]),
            action=e.get("action", "add"),
            line_no=int(e.get("line_no", 0)),
            raw_text=e.get("raw_text", ""),
        )
        for e in parsed.get("events", [])
    ]


def load_products(payload: dict[str, Any]) -> dict[str, Product]:
    return {
        code: Product(name=p["name"], unit_price=int(p["unit_price"]),
                      unit_label=p.get("unit_label", "份"))
        for code, p in payload["products"].items()
    }


def load_structured(path: Path) -> tuple[dict[str, Product], list[OrderEvent], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    products = load_products(payload)
    events = [
        OrderEvent(
            buyer=e["buyer"],
            item=e["item"],
            quantity=int(e["quantity"]),
            action=e.get("action", "add"),
            line_no=int(e.get("line_no", 0)),
            raw_text=e.get("raw_text", ""),
        )
        for e in payload.get("events", [])
    ]
    group_name = payload.get("group_name", "本團")
    return products, events, group_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", nargs="?", type=Path, help="結構化 JSON 輸入")
    parser.add_argument("--chat", type=Path, help="自由文字 LINE 對話檔(需 --products + API key)")
    parser.add_argument("--products", type=Path, help="產品清單 JSON(配合 --chat)")
    parser.add_argument("--out", type=Path, help="markdown 彙整輸出(賣家對帳用)")
    parser.add_argument("--out-line", type=Path, help="LINE 對帳訊息輸出(複製貼上用)")
    args = parser.parse_args()

    if args.chat:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("error: --chat 需要 ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        if not args.chat.exists() or not args.products or not args.products.exists():
            print("error: --chat 需配合 --products(產品清單 JSON)", file=sys.stderr)
            return 2
        chat_text = args.chat.read_text(encoding="utf-8")
        products_payload = json.loads(args.products.read_text(encoding="utf-8"))
        products = load_products(products_payload)
        group_name = products_payload.get("group_name", "本團")
        events = llm_parse_chat(chat_text, products)
        print(f"info: AI 解析出 {len(events)} 筆 events", file=sys.stderr)
    else:
        if not args.input or not args.input.exists():
            print("error: 請提供結構化 JSON 或 --chat + --products", file=sys.stderr)
            return 2
        products, events, group_name = load_structured(args.input)

    summary = aggregate(events, products)

    md_summary = render_markdown_summary(summary, products, group_name)
    line_replies = render_buyer_replies(summary, products)

    if args.out:
        args.out.write_text(md_summary, encoding="utf-8")
        print(f"已寫入 markdown 彙整: {args.out}", file=sys.stderr)
    if args.out_line:
        args.out_line.write_text(line_replies, encoding="utf-8")
        print(f"已寫入 LINE 對帳訊息: {args.out_line}", file=sys.stderr)
    if not args.out and not args.out_line:
        sys.stdout.write(md_summary)
        sys.stdout.write("\n")
        sys.stdout.write(line_replies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
