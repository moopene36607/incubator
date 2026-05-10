"""shiftsync — 台灣餐廳外場輪班 LINE Bot 助手

Usage:
    # 結構化請求(免 API key)
    python shiftsync.py --schedule samples/initial_schedule.json \\
        --request samples/structured_requests.json

    # 自由文字請求(需 API key)
    python shiftsync.py --schedule samples/initial_schedule.json \\
        --line-text samples/sample_requests.txt

設計重點:
- 所有規則檢查在 `schedule_rules.py` 純函式,LLM 永不負責「能不能換」這個判斷
- LLM 只解析自然語言「我跟小明換週五晚班好嗎?」→ 結構化請求
- LLM 在規則檢查後,把 ApprovalResult 翻成人性化 LINE 回覆訊息

ANTHROPIC_API_KEY 在 --line-text 模式必要(--no-ai 跳過,要結構化)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from schedule_rules import (
    ApprovalResult,
    Employee,
    Shift,
    check_extra_shift,
    check_leave,
    check_swap,
)


PARSE_SYSTEM = """你是台灣餐廳排班 LINE Bot 助手。員工 / 店長會用日常台灣口語跟你提排班請求,
你的任務是把每則訊息分類並抽出結構化欄位。

## 訊息類型(只能選其一)

1. **swap** — 換班:「我這週五晚班想跟小明換」「能不能我週六午班跟阿偉的週日午班互換」
2. **leave** — 請假:「我下週二想請假」「禮拜三晚班我有事去不了」
3. **extra** — 加班 / 自願加班:「我這週才上 25 小時,可以多排嗎?」「我可以幫忙週末晚班」
4. **chitchat** — 不關於排班的(問候 / 確認 / 感謝)→ 全部欄位 null,type 設為 chitchat

## 輸出格式 (只回 JSON,不要任何其他文字)

```json
{
  "type": "swap | leave | extra | chitchat",
  "requester": "<發訊員工姓名,可從訊息上下文推>",
  "swap_target": "<換班對象姓名,僅 swap 用>",
  "shift_id": "<請假 / 加班 班次代碼,從可選清單選>",
  "swap_my_shift_id": "<swap: 自己這邊的班次>",
  "swap_their_shift_id": "<swap: 對方那邊的班次>",
  "raw_text": "<原始訊息節錄,不超過 80 字>"
}
```

## 可用 shift_id 對照(請從以下清單選最接近的)

{shift_table}

## 規則

- **不要編造員工姓名** — 訊息沒提到對方時 swap_target 留 null
- **shift_id 推斷**:用「週五晚班」→ FRI_DINNER 邏輯對應到清單代碼
- **時間說明用語**:「下週二」「禮拜三」就指當週(本系統當前週)的星期
- **不確定就 chitchat**:超出排班相關訊息(問價格 / 抱怨客人等)直接 chitchat
"""


def build_parse_system(shifts: list[Shift]) -> str:
    rows = []
    for s in shifts:
        assignee = s.assigned_to or "(空班)"
        rows.append(f"- `{s.shift_id}` → {s.day} {s.start_time}-{s.end_time} "
                    f"({s.role_required}) 目前: {assignee}")
    return PARSE_SYSTEM.format(shift_table="\n".join(rows))


REPLY_SYSTEM = """你是台灣餐廳排班 LINE Bot,要把規則檢查結果翻成人性化的 LINE 回覆訊息。

## 寫作風格

- 繁體中文,口語但禮貌(店長 / 員工視角)
- 短訊息(2-4 行),適合 LINE 群組
- 帶 emoji 但克制(✅ / ⚠️ / ❌ 為主)
- 引用具體數字(時數 / 日期)以可信

## 結構

依 status 分:
- **approved** → ✅ 確認 + 一句說明 + 建議下一步行動
- **approved_with_warning** → ⚠️ 確認 + 警示理由(如加班費)
- **needs_replacement** → 📋 列出建議代班人選讓老闆決定
- **rejected** → ❌ 婉拒 + 原因 + 給出替代建議

## 規則

- 不要編造規則沒提到的細節
- 不要堆 emoji
- 直接輸出 LINE 回覆內容,不要前後解說
"""


def serialize_shifts(shifts: list[Shift]) -> list[dict[str, Any]]:
    return [
        {
            "shift_id": s.shift_id, "day": s.day,
            "start_time": s.start_time, "end_time": s.end_time,
            "duration_hours": s.duration_hours, "role_required": s.role_required,
            "assigned_to": s.assigned_to,
        }
        for s in shifts
    ]


def llm_parse_request(text: str, shifts: list[Shift]) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": build_parse_system(shifts),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"員工訊息: {text}"}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON: {raw}")
    return json.loads(raw[start : end + 1])


def llm_format_reply(approval: ApprovalResult, request_type: str) -> str:
    import anthropic

    payload = {
        "request_type": request_type,
        "status": approval.status,
        "summary": approval.summary,
        "reasons": approval.reasons,
        "suggested_replacements": approval.suggested_replacements,
        "rule_violations": approval.rule_violations,
    }
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=[{"type": "text", "text": REPLY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user",
                   "content": f"規則檢查結果:\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n\n請寫 LINE 回覆訊息。"}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def template_reply(approval: ApprovalResult, request_type: str) -> str:
    """無 AI 時的純函式回覆模板。"""
    icon = {"approved": "✅", "approved_with_warning": "⚠️",
            "needs_replacement": "📋", "rejected": "❌"}.get(approval.status, "🤖")
    lines = [f"{icon} {approval.summary}"]
    if approval.reasons:
        lines.append("")
        for r in approval.reasons:
            lines.append(f"  - {r}")
    if approval.suggested_replacements:
        lines.append("")
        lines.append(f"建議代班人選:{', '.join(approval.suggested_replacements)}")
    if approval.rule_violations:
        lines.append("")
        for v in approval.rule_violations:
            lines.append(f"  ✗ {v}")
    return "\n".join(lines)


def load_schedule(path: Path) -> tuple[dict[str, Employee], list[Shift], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    employees = {
        e["name"]: Employee(
            name=e["name"], role=e["role"],
            is_full_time=bool(e.get("is_full_time", False)),
            target_weekly_hours=float(e.get("target_weekly_hours", 24)),
            can_substitute_for=tuple(e.get("can_substitute_for", [])),
        )
        for e in payload["employees"]
    }
    shifts = [
        Shift(
            shift_id=s["shift_id"], day=s["day"],
            start_time=s["start_time"], end_time=s["end_time"],
            duration_hours=float(s["duration_hours"]),
            role_required=s["role_required"],
            assigned_to=s.get("assigned_to"),
        )
        for s in payload["shifts"]
    ]
    store_name = payload.get("store_name", "餐廳")
    return employees, shifts, store_name


def dispatch(request: dict[str, Any], shifts: list[Shift],
             employees: dict[str, Employee]) -> ApprovalResult:
    rt = request.get("type")
    if rt == "swap":
        return check_swap(
            shifts, employees,
            request["requester"], request["swap_my_shift_id"],
            request["swap_target"], request["swap_their_shift_id"],
        )
    if rt == "leave":
        return check_leave(shifts, employees, request["requester"], request["shift_id"])
    if rt == "extra":
        return check_extra_shift(shifts, employees, request["requester"], request["shift_id"])
    if rt == "chitchat":
        return ApprovalResult(status="approved", summary="(非排班訊息,略過)")
    return ApprovalResult(status="rejected", summary="未知請求類型",
                          rule_violations=[f"type {rt!r} 無效"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--schedule", type=Path, required=True, help="本週班表 JSON")
    parser.add_argument("--request", type=Path, help="結構化請求 JSON 陣列")
    parser.add_argument("--line-text", type=Path,
                        help="自由文字請求(每行一則,需 ANTHROPIC_API_KEY)")
    parser.add_argument("--out", type=Path, help="輸出 markdown 路徑")
    args = parser.parse_args()

    if not args.schedule.exists():
        print(f"error: 找不到班表 {args.schedule}", file=sys.stderr)
        return 2

    employees, shifts, store_name = load_schedule(args.schedule)

    use_ai = args.line_text and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if args.line_text and not use_ai:
        print("error: --line-text 需要 ANTHROPIC_API_KEY", file=sys.stderr)
        return 2

    requests: list[dict[str, Any]] = []
    raw_messages: list[str] = []
    if args.request:
        requests = json.loads(args.request.read_text(encoding="utf-8"))
        raw_messages = [r.get("raw_text", "") for r in requests]
    elif args.line_text:
        for line in args.line_text.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            raw_messages.append(line)
            requests.append(llm_parse_request(line, shifts))

    out: list[str] = []
    out.append(f"# {store_name} 排班助手 — 本週請求處理")
    out.append("")
    for i, (msg, req) in enumerate(zip(raw_messages, requests), 1):
        out.append(f"## 請求 {i}")
        out.append("")
        out.append(f"**員工訊息**: {msg}")
        out.append("")
        out.append(f"**AI 解析類型**: `{req.get('type')}`")
        out.append("")
        approval = dispatch(req, shifts, employees)
        if use_ai:
            reply = llm_format_reply(approval, req.get("type", "unknown"))
        else:
            reply = template_reply(approval, req.get("type", "unknown"))
        out.append("**Bot 回覆**:")
        out.append("")
        out.append("```")
        out.append(reply)
        out.append("```")
        out.append("")
        out.append("---")
        out.append("")

    output = "\n".join(out) + "\n"

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
