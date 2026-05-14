"""fitlog — 台灣健身教練 課後訓練報告產生器

Usage:
    python fitlog.py samples/sample_input.json
    python fitlog.py samples/sample_input.json --out report.md --out-line report_line.txt
    python fitlog.py samples/sample_input.json --no-ai  # 骨架版

每堂 1 對 1 PT 課後,教練輸入學員姓名 + 動作清單 (組數/重量/RPE) + 觀察 + 學員主訴,
30 秒產出一份學員拿了會看完的繁中課後報告 (markdown + LINE 純文字版)。

設計重點:
- 純函式組裝報告標頭、訓練量化表格、LINE 純文字版
- AI 只寫「文字段落」(今日摘要、進步觀察、身體反應、下次重點、恢復建議)
- 動作 grounding 用 exercise_db 維持台灣健身圈通用詞
- 不編造學員未提到的飲食 / 數據,不下醫療診斷

ANTHROPIC_API_KEY 在 AI 模式必要 (--no-ai 跳過,輸出骨架)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from exercise_db import EXERCISES, Exercise, lookup
from csv_export import write_session_csv
from metrics import render_category_breakdown, render_volume_summary
from progress import compute_bw_reps_deltas, compute_pr_deltas, render_pr_summary
from validation import validate_session


REPORT_SYSTEM = """你是台灣健身教練 (PT) 的課後報告助理,協助教練把訓練紀錄與觀察轉成
學員當天會看完的課後報告 (傳到 LINE 用)。

## 寫作原則

- 繁體中文,第二人稱對學員 (例:「你今天 squat 表現…」),語氣是「教練朋友」,
  不是「健身房 sales」。專業但有溫度,不油膩。
- 用台灣健身圈常見詞:RPE、組數、超負荷、TUT、deload、bodyweight、訓練量、力竭。
  不要過度使用簡體中文式術語 (避免:「卧推」「桑拿」「肌肥大」)。
- **絕不編造**教練沒提供的數據 — 不亂猜學員體重、體脂、卡路里、心率
- **絕不下醫療診斷** — 學員提到不適時用「建議下次回來告知狀況」「下次會視情況調整」,
  不要寫「你可能有 XX 症」
- 量化資料優先:寫「Bench Press 從 47.5 kg 進步到 50 kg」, 不要寫「你變強了」

## 結構

請輸出 5 段,markdown 格式。**只回這 5 段**,不要前後說明、不要重複學員資料:

### 一、今日訓練摘要
2-3 句說明今日課程主題 (e.g. 全身肌力 / 上半身推 / 下半身) + 整體完成度。

### 二、本次主要進步 / 突破
2-4 個 bullet point。具體寫進步細節:
- 「Squat 深度從上次 90° 提升到本次 110° 完整深蹲」
- 「Bench Press 突破 47.5 kg 瓶頸,本次完成 4×8×50 kg, RPE 8」

### 三、身體反應與觀察
2-4 個 bullet。可包含:
- 教練看到的動作品質改善 / 退步
- 學員主述的不適 (用「下次留意」措辭,不下診斷)
- 疲勞趨勢、握力、核心控制等 qualitative 評估

### 四、下次課程重點
1-2 段。寫:
- 下次課的訓練主題與重點動作 (依教練輸入的 next session plan)
- 為什麼這樣安排 (e.g. 連續 2 次推系後該休)

### 五、本週恢復 / 飲食提醒 (只寫教練輸入的內容,不要編)
1 段。如果教練沒提供恢復或飲食目標,只寫「保持充足睡眠」這種通用建議,
**絕不發明「每日喝 3L 水」「攝取 2,000 大卡」這種具體數字**。

## 嚴格規則

- 不寫具體藥物 / 補充劑品牌 (避免廣告嫌疑與責任)
- 不寫具體飲食卡路里數字,除非教練明確提供
- 報告結尾不署名 (教練資料由純函式模板帶入)
"""


@dataclass
class SetRecord:
    exercise_code: str
    sets: int
    reps_or_duration: str   # "10" or "60 sec" or "500 m"
    weight_kg: float | None
    rpe: int | None
    note: str = ""


@dataclass
class SessionInput:
    student_name: str
    student_age: int | None
    student_goal: str
    session_no: int
    session_date: str
    duration_min: int
    coach_name: str
    studio_name: str
    contact: str
    theme: str               # 今日主題: e.g. "全身肌力 / Day A"
    sets: list[SetRecord]
    coach_observations: list[str]
    student_subjective: list[str]      # 學員主述 (如「下背稍緊」)
    next_session: dict[str, Any]       # {"date": "...", "theme": "...", "focus": [...]}
    recovery_diet: dict[str, Any] = field(default_factory=dict)


def parse_payload(payload: dict[str, Any]) -> SessionInput:
    s = payload["student"]
    c = payload["coach"]
    se = payload["session"]
    return SessionInput(
        student_name=s["name"],
        student_age=s.get("age"),
        student_goal=s.get("goal", ""),
        session_no=int(se["session_no"]),
        session_date=se["date"],
        duration_min=int(se["duration_min"]),
        coach_name=c["name"],
        studio_name=c["studio_name"],
        contact=c.get("contact", ""),
        theme=se["theme"],
        sets=[
            SetRecord(
                exercise_code=s["exercise_code"],
                sets=int(s["sets"]),
                reps_or_duration=str(s["reps_or_duration"]),
                weight_kg=(float(s["weight_kg"]) if s.get("weight_kg") not in (None, "") else None),
                rpe=(int(s["rpe"]) if s.get("rpe") is not None else None),
                note=s.get("note", ""),
            )
            for s in se["sets"]
        ],
        coach_observations=list(payload.get("coach_observations", [])),
        student_subjective=list(payload.get("student_subjective", [])),
        next_session=payload.get("next_session", {}),
        recovery_diet=payload.get("recovery_diet", {}),
    )


def render_session_table(session: SessionInput) -> list[str]:
    out: list[str] = []
    out.append("| # | 動作 | 組數 × 次/秒/m | 重量 | RPE | 備註 |")
    out.append("|---|------|---------------|------|------|------|")
    for i, s in enumerate(session.sets, 1):
        ex = lookup(s.exercise_code)
        name = f"{ex.chinese} ({ex.english})" if ex else f"{s.exercise_code}(代碼未知)"
        weight = f"{s.weight_kg} kg" if s.weight_kg is not None else "BW"
        rpe_str = f"{s.rpe}" if s.rpe is not None else "—"
        out.append(f"| {i} | {name} | {s.sets} × {s.reps_or_duration} | {weight} | {rpe_str} | {s.note} |")
    return out


def render_skeleton_body() -> str:
    return (
        "### 一、今日訓練摘要\n(待 AI 填:今日主題 + 整體完成度)\n\n"
        "### 二、本次主要進步 / 突破\n- (待 AI 填)\n- (待 AI 填)\n\n"
        "### 三、身體反應與觀察\n- (待 AI 填)\n- (待 AI 填)\n\n"
        "### 四、下次課程重點\n(待 AI 填)\n\n"
        "### 五、本週恢復 / 飲食提醒\n(待 AI 填,不要編造學員未提到的具體數字)\n"
    )


def ai_write_body(session: SessionInput) -> str:
    import anthropic

    detail = {
        "學員": {"姓名": session.student_name, "年齡": session.student_age, "目標": session.student_goal},
        "課程": {"次數": session.session_no, "日期": session.session_date,
                "時長分鐘": session.duration_min, "主題": session.theme},
        "訓練動作": [
            {
                "動作": (lookup(s.exercise_code).chinese if lookup(s.exercise_code) else s.exercise_code),
                "代碼": s.exercise_code,
                "組數": s.sets,
                "次或秒": s.reps_or_duration,
                "重量公斤": s.weight_kg,
                "RPE": s.rpe,
                "備註": s.note,
            }
            for s in session.sets
        ],
        "教練觀察": session.coach_observations,
        "學員主述": session.student_subjective,
        "下次課程計畫": session.next_session,
        "恢復飲食目標 (學員或教練輸入)": session.recovery_diet,
    }
    user = (
        "以下為這堂課的完整資料,請寫一份學員會看完的課後報告 (5 段 markdown):\n\n"
        f"```json\n{json.dumps(detail, ensure_ascii=False, indent=2)}\n```"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2200,
        system=[{"type": "text", "text": REPORT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def render_full_report(session: SessionInput, body: str, pr_summary: str | None = None) -> str:
    out: list[str] = []
    out.append(f"# {session.student_name} 課後訓練報告 (第 {session.session_no} 堂)")
    out.append("")
    out.append(f"**日期**: {session.session_date}    "
               f"**時長**: {session.duration_min} 分鐘    "
               f"**今日主題**: {session.theme}")
    out.append("")
    out.append("## 學員資料")
    out.append("")
    out.append(f"- 姓名: {session.student_name}"
               + (f"   /  年齡: {session.student_age}" if session.student_age else ""))
    if session.student_goal:
        out.append(f"- 訓練目標: {session.student_goal}")
    out.append("")
    out.append("## 訓練量化紀錄")
    out.append("")
    out.extend(render_session_table(session))
    summary = render_volume_summary(session.sets)
    breakdown = render_category_breakdown(session.sets)
    if summary or breakdown or pr_summary:
        out.append("")
    if summary:
        out.append(summary)
    if breakdown:
        out.append(breakdown)
    if pr_summary:
        out.append(pr_summary)
    out.append("")
    out.append("---")
    out.append("")
    out.append(body)
    out.append("")
    out.append("---")
    out.append("")
    out.append(f"**教練**: {session.coach_name}  /  **工作室**: {session.studio_name}")
    if session.contact:
        out.append(f"**聯絡**: {session.contact}")
    out.append("")
    out.append(f"*由 fitlog 自動產生於 {date.today().isoformat()} — 教練確認後傳給學員*")
    return "\n".join(out) + "\n"


def render_line_friendly(session: SessionInput, body: str, pr_summary: str | None = None) -> str:
    """LINE 純文字版,去 markdown 符號,加 emoji 分段。"""
    plain = body.replace("### ", "\n").replace("## ", "\n").replace("**", "")
    quick_table_rows = []
    for i, s in enumerate(session.sets, 1):
        ex = lookup(s.exercise_code)
        name = ex.chinese if ex else s.exercise_code
        weight = f"{s.weight_kg}kg" if s.weight_kg is not None else "BW"
        rpe = f" RPE{s.rpe}" if s.rpe is not None else ""
        quick_table_rows.append(f"  {i}. {name} {s.sets}×{s.reps_or_duration} @{weight}{rpe}")
    summary = render_volume_summary(session.sets)
    breakdown = render_category_breakdown(session.sets)
    summary_parts: list[str] = []
    if summary:
        summary_parts.append(f"🏋️ 總噸位:{summary.split(': ', 1)[1]}")
    if breakdown:
        summary_parts.append(f"📦 分解:{breakdown.split(': ', 1)[1]}")
    if pr_summary:
        summary_parts.append(f"🏆 進步:{pr_summary.split(': ', 1)[1]}")
    summary_line = "\n" + "\n".join(summary_parts) + "\n" if summary_parts else "\n"
    return (
        f"💪 {session.student_name} 第 {session.session_no} 堂課後報告\n"
        f"📅 {session.session_date}  ⏱ {session.duration_min} min\n"
        f"📌 主題:{session.theme}\n"
        f"━━━━━━━━━━━━━━\n"
        "📊 訓練紀錄:\n"
        + "\n".join(quick_table_rows)
        + summary_line
        + "━━━━━━━━━━━━━━\n"
        + plain.strip()
        + f"\n━━━━━━━━━━━━━━\n"
        f"教練 {session.coach_name} | {session.studio_name}\n"
        f"有任何不適請隨時告知 ☺️"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="本堂課訓練紀錄 JSON")
    parser.add_argument("--out", type=Path, help="markdown 輸出路徑 (省略 stdout)")
    parser.add_argument("--out-line", type=Path, help="LINE 純文字版輸出路徑")
    parser.add_argument("--csv", type=Path, help="把單堂訓練紀錄匯出成 CSV (Excel-friendly)")
    parser.add_argument("--prev", type=Path, help="上次課程 JSON,用來算 PR / 噸位 delta")
    parser.add_argument("--no-ai", action="store_true", help="不呼叫 AI,輸出骨架")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    session = parse_payload(payload)

    for w in validate_session(session):
        print(f"warning: {w}", file=sys.stderr)

    pr_summary: str | None = None
    if args.prev:
        if not args.prev.exists():
            print(f"warning: --prev 檔案找不到: {args.prev}", file=sys.stderr)
        else:
            prev_payload = json.loads(args.prev.read_text(encoding="utf-8"))
            prev_session = parse_payload(prev_payload)
            pr_summary = render_pr_summary(
                compute_pr_deltas(prev_session.sets, session.sets),
                compute_bw_reps_deltas(prev_session.sets, session.sets),
            )

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,輸出骨架版", file=sys.stderr)

    body = ai_write_body(session) if use_ai else render_skeleton_body()
    full = render_full_report(session, body, pr_summary)

    if args.out:
        args.out.write_text(full, encoding="utf-8")
        print(f"已寫入 markdown: {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(full)

    if args.out_line:
        args.out_line.write_text(render_line_friendly(session, body, pr_summary), encoding="utf-8")
        print(f"已寫入 LINE 版: {args.out_line}", file=sys.stderr)

    if args.csv:
        write_session_csv(session, args.csv)
        print(f"已寫入 CSV: {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
