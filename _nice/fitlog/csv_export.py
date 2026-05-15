"""fitlog CSV 匯出 — 純函式把 SessionInput 轉成 Excel-friendly 行 (no LLM).

PT 拿到課後報告後常常還要把訓練紀錄帶進 Excel / Google Sheets 做進階
分析 (學員進步 dashboard、整年總噸位曲線、開課後對外請款附明細)。

每筆 set 一行,每行都帶 session metadata (date / student / session_no)
方便多堂 concat 後還能用 pivot table 切。

數值欄位走 Excel-friendly 慣例:
- 整數值不顯示小數 (70.0 → "70",不是 "70.0")
- weight_kg=None → 空字串 (Excel 視為「無資料」,而不是 0)
- tonnage 永遠輸出 (BW / 時間型 = 0,讓 SUM() 公式不出錯)
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from exercise_db import lookup
from metrics import compute_total_tonnage

if TYPE_CHECKING:
    from fitlog import SessionInput


CSV_HEADER: list[str] = [
    "date",
    "student_name",
    "session_no",
    "set_index",
    "exercise_code",
    "exercise_zh",
    "exercise_en",
    "category",
    "sets",
    "reps_or_duration",
    "weight_kg",
    "rpe",
    "tonnage_kg",
    "note",
]


def _format_number(value: float) -> str:
    """整數值丟小數;非整數保留至多一位小數;Excel-friendly。"""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def format_session_csv_rows(session: "SessionInput") -> list[list[str]]:
    """純函式把 session 轉成 list[list[str]] (含 header)。"""
    rows: list[list[str]] = [list(CSV_HEADER)]
    for i, s in enumerate(session.sets, 1):
        ex = lookup(s.exercise_code)
        weight_str = _format_number(s.weight_kg) if s.weight_kg is not None else ""
        rpe_str = str(s.rpe) if s.rpe is not None else ""
        tonnage = compute_total_tonnage([s])
        rows.append([
            session.session_date,
            session.student_name,
            str(session.session_no),
            str(i),
            s.exercise_code,
            ex.chinese if ex else "",
            ex.english if ex else "",
            ex.category if ex else "",
            str(s.sets),
            s.reps_or_duration,
            weight_str,
            rpe_str,
            _format_number(tonnage),
            s.note,
        ])
    return rows


def write_session_csv(session: "SessionInput", path: Path) -> None:
    """把 session 寫成 UTF-8 CSV 檔。"""
    rows = format_session_csv_rows(session)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def format_batch_csv_rows(sessions: list["SessionInput"]) -> list[list[str]]:
    """多堂 sessions 串成單一 CSV (header 共用)。空 → 僅 header。
    sessions 順序保持原序;每個 session 內的 set_index 各自從 1 開始。"""
    rows: list[list[str]] = [list(CSV_HEADER)]
    for session in sessions:
        for data_row in format_session_csv_rows(session)[1:]:  # skip per-session header
            rows.append(data_row)
    return rows


def write_batch_csv(sessions: list["SessionInput"], path: Path) -> None:
    """把多堂 sessions 一次寫成 UTF-8 CSV 檔。"""
    rows = format_batch_csv_rows(sessions)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
