"""snaporder — 訂單聚合與統計 (純函式,no I/O, no LLM).

責任:
  - 合併同一買家的多筆同品項訂單
  - 處理「修正訂單」(把先前訂單某品項改成新數量)與「取消訂單」
  - 計算每買家小計、品項總數、總金額
  - 渲染 markdown 彙整表(賣家對帳用)+ 買家訊息回覆(LINE 截圖用)

LLM 的責任在另一個檔案(snaporder.py 中的 ai_parse_chat),
從非結構化 LINE 對話 → 結構化 OrderEvent 清單。
本檔案完全不碰 LLM,確保金額計算永遠可重現、可單元測試。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrderEvent:
    """單一訂購事件 — LLM 從對話解析後產生這個結構。"""
    buyer: str            # 買家姓名 / 識別
    item: str             # 品項名稱 (要對應到產品清單)
    quantity: int         # 數量(可為 0 表示取消後)
    action: str = "add"   # "add" | "set" | "cancel"
    line_no: int = 0      # 來源訊息序號(供查核)
    raw_text: str = ""    # 原始訊息文字(供查核)


@dataclass
class Product:
    name: str
    unit_price: int       # NT$ 整數,純函式不處理小數
    unit_label: str = "份" # "包" / "盒" / "罐" 等


@dataclass
class BuyerOrder:
    buyer: str
    items: dict[str, int] = field(default_factory=dict)  # {item: quantity}


@dataclass
class AggregatedSummary:
    buyer_orders: list[BuyerOrder]   # 每位買家明細
    item_totals: dict[str, int]       # 全團每品項總數
    item_revenue: dict[str, int]      # 全團每品項小計 NT$
    grand_total: int                  # 全團總金額 NT$
    skipped_events: list[OrderEvent]  # 因品項不在產品清單而被跳過的事件


def aggregate(events: list[OrderEvent], products: dict[str, Product]) -> AggregatedSummary:
    """把 OrderEvent 清單合併成每買家彙整 + 全團統計。

    處理規則:
      - "add" 事件:在該買家的該品項上累加
      - "set" 事件:把該買家的該品項覆寫為指定數量(處理「改成 N 個」)
      - "cancel" 事件:把該買家的該品項設為 0
      - 品項若不在 products 清單 → 加入 skipped_events,不參與計算
      - quantity < 0 → 視為 0(無 negative)
    """
    # 收集每位買家在出現順序中的索引,維持結果有序
    buyer_index: dict[str, int] = {}
    buyer_orders: list[BuyerOrder] = []
    skipped: list[OrderEvent] = []

    for event in events:
        if event.item not in products:
            skipped.append(event)
            continue
        if event.buyer not in buyer_index:
            buyer_index[event.buyer] = len(buyer_orders)
            buyer_orders.append(BuyerOrder(buyer=event.buyer))
        order = buyer_orders[buyer_index[event.buyer]]
        qty = max(0, event.quantity)

        if event.action == "set":
            order.items[event.item] = qty
        elif event.action == "cancel":
            order.items[event.item] = 0
        else:  # "add"
            order.items[event.item] = order.items.get(event.item, 0) + qty

    # 過濾掉所有品項皆 0 的買家(可能整單取消)
    buyer_orders = [b for b in buyer_orders if any(q > 0 for q in b.items.values())]

    # 全團每品項統計
    item_totals: dict[str, int] = {name: 0 for name in products}
    for order in buyer_orders:
        for item, qty in order.items.items():
            item_totals[item] = item_totals.get(item, 0) + qty

    item_revenue = {
        item: qty * products[item].unit_price for item, qty in item_totals.items()
    }
    grand_total = sum(item_revenue.values())

    return AggregatedSummary(
        buyer_orders=buyer_orders,
        item_totals=item_totals,
        item_revenue=item_revenue,
        grand_total=grand_total,
        skipped_events=skipped,
    )


def render_markdown_summary(summary: AggregatedSummary, products: dict[str, Product],
                            group_name: str = "本團") -> str:
    out: list[str] = []
    out.append(f"# {group_name} 訂單彙整")
    out.append("")

    # 1. 全團統計
    out.append("## 全團統計")
    out.append("")
    out.append("| 品項 | 單價 | 總數 | 小計 |")
    out.append("|------|----:|-----:|-----:|")
    for name, p in products.items():
        qty = summary.item_totals.get(name, 0)
        revenue = summary.item_revenue.get(name, 0)
        out.append(f"| {p.name} | NT${p.unit_price} | {qty} {p.unit_label} | NT${revenue:,} |")
    out.append(f"| **合計** |  |  | **NT${summary.grand_total:,}** |")
    out.append("")

    # 2. 每買家明細
    out.append("## 個人訂單明細")
    out.append("")
    out.append(f"共 **{len(summary.buyer_orders)}** 位買家。")
    out.append("")
    for order in summary.buyer_orders:
        active_items = {k: v for k, v in order.items.items() if v > 0}
        if not active_items:
            continue
        line_total = sum(
            v * products[k].unit_price for k, v in active_items.items() if k in products
        )
        out.append(f"### 🧑 {order.buyer} — 小計 **NT${line_total:,}**")
        out.append("")
        for item, qty in active_items.items():
            p = products.get(item)
            if not p:
                continue
            out.append(f"- {p.name} × {qty} {p.unit_label} (NT${qty * p.unit_price:,})")
        out.append("")

    # 3. 跳過的訊息(供賣家檢查)
    if summary.skipped_events:
        out.append("## ⚠️ 未匹配到產品的訊息")
        out.append("")
        out.append("以下訊息提到了不在產品清單中的品項,請賣家手動確認:")
        out.append("")
        for ev in summary.skipped_events:
            ref = f"(行 {ev.line_no})" if ev.line_no else ""
            out.append(f"- **{ev.buyer}**: 「{ev.raw_text}」 {ref}")
        out.append("")

    out.append("---")
    out.append("")
    out.append("*由 snaporder 自動產生 — 請賣家核對後再向買家收款*")
    return "\n".join(out) + "\n"


def render_buyer_replies(summary: AggregatedSummary, products: dict[str, Product]) -> str:
    """產生可直接複製貼到 LINE 群組的對帳訊息(每位買家一段)。"""
    out: list[str] = []
    out.append("# LINE 群組對帳訊息(可複製貼上)")
    out.append("")
    for order in summary.buyer_orders:
        active_items = {k: v for k, v in order.items.items() if v > 0}
        if not active_items:
            continue
        line_total = sum(
            v * products[k].unit_price for k, v in active_items.items() if k in products
        )
        items_str = "、".join(
            f"{products[k].name}×{v}" for k, v in active_items.items() if k in products
        )
        out.append("```")
        out.append(f"@{order.buyer} 你的訂單:{items_str},合計 NT${line_total:,} 🙏")
        out.append("```")
        out.append("")
    return "\n".join(out) + "\n"
