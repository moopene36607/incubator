"""fitlog 多堂聚合統計 — 純函式 (no I/O, no LLM).

跑完一週 6-8 節課後,PT 想看「整週的圖」:
- 總共做了幾噸
- 每位學員上了幾堂
- 哪幾個動作的訓練量最多 (重點分布)

aggregate_batch 純函式產出 BatchSummary;render_batch_summary 把它
渲染成 markdown,寫成 _batch_summary.md 放在批次目錄裡。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from exercise_db import lookup
from metrics import _format_kg, compute_total_tonnage

if TYPE_CHECKING:
    from fitlog import SessionInput


@dataclass(frozen=True)
class BatchSummary:
    n_sessions: int
    total_tonnage_kg: float
    students: dict[str, int]                     # 姓名 → session 數
    top_exercises: list[tuple[str, float]]       # (exercise_code, tonnage) 由高到低


@dataclass(frozen=True)
class StudentTrendPoint:
    """單一學員某堂課的訓練量摘要。"""
    date: str
    session_no: int
    tonnage_kg: float


@dataclass(frozen=True)
class StudentTrend:
    """單一學員跨多堂的訓練趨勢。"""
    student_name: str
    points: list[StudentTrendPoint]
    total_tonnage: float


def aggregate_batch(sessions: Iterable["SessionInput"]) -> BatchSummary:
    """彙總多堂 session 的整體訓練量、學員出席、動作排行。"""
    sessions = list(sessions)
    students: dict[str, int] = {}
    exercise_tonnage: dict[str, float] = {}
    total = 0.0
    for sess in sessions:
        students[sess.student_name] = students.get(sess.student_name, 0) + 1
        total += compute_total_tonnage(sess.sets)
        for s in sess.sets:
            t = compute_total_tonnage([s])
            if t > 0:
                exercise_tonnage[s.exercise_code] = (
                    exercise_tonnage.get(s.exercise_code, 0.0) + t
                )
    top = sorted(exercise_tonnage.items(), key=lambda kv: -kv[1])
    return BatchSummary(
        n_sessions=len(sessions),
        total_tonnage_kg=total,
        students=students,
        top_exercises=top,
    )


def find_prev_session(
    target: "SessionInput",
    all_sessions: Iterable["SessionInput"],
) -> "SessionInput | None":
    """從 all_sessions 找出與 target 同學員、(date, session_no) 字典序較早
    的最近一筆 (用於批次模式自動 PR 比對)。沒有 → None。"""
    candidates = [
        s for s in all_sessions
        if s.student_name == target.student_name
        and (s.session_date, s.session_no) < (target.session_date, target.session_no)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.session_date, s.session_no))


def compute_student_trend(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> StudentTrend:
    """過濾出該學員的所有 session,按 (date, session_no) 排序後算 trend。"""
    student_sessions = [s for s in sessions if s.student_name == student_name]
    student_sessions.sort(key=lambda s: (s.session_date, s.session_no))
    points = [
        StudentTrendPoint(
            date=s.session_date,
            session_no=s.session_no,
            tonnage_kg=compute_total_tonnage(s.sets),
        )
        for s in student_sessions
    ]
    return StudentTrend(
        student_name=student_name,
        points=points,
        total_tonnage=sum(p.tonnage_kg for p in points),
    )


def render_student_trend(trend: StudentTrend) -> str:
    """產出單一學員的多堂進步趨勢 markdown。"""
    lines: list[str] = []
    lines.append(f"# {trend.student_name} 個人訓練趨勢")
    lines.append("")
    lines.append(f"- **總堂數**: {len(trend.points)}")
    lines.append(f"- **總訓練量**: {_format_kg(trend.total_tonnage)}")
    lines.append("")
    lines.append("## 各堂訓練量")
    lines.append("")
    if trend.points:
        lines.append("| 日期 | 第 N 堂 | 訓練量 |")
        lines.append("|------|---------|--------|")
        for p in trend.points:
            lines.append(f"| {p.date} | {p.session_no} | {_format_kg(p.tonnage_kg)} |")
    else:
        lines.append("- (沒有此學員的 session)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*由 fitlog --batch 自動產出*")
    return "\n".join(lines) + "\n"


def render_batch_summary(summary: BatchSummary) -> str:
    """產出 markdown 批次彙總報告。"""
    lines: list[str] = []
    lines.append("# 批次彙總報告")
    lines.append("")
    lines.append(f"- **堂數**: {summary.n_sessions}")
    lines.append(f"- **總訓練量**: {_format_kg(summary.total_tonnage_kg)}")
    lines.append("")

    lines.append("## 學員出席")
    lines.append("")
    if summary.students:
        for name, n in sorted(summary.students.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {name}: {n} 堂")
    else:
        lines.append("- (本批次沒有任何 session)")
    lines.append("")

    lines.append("## 動作訓練量排行 (Top 10)")
    lines.append("")
    if summary.top_exercises:
        for code, tonnage in summary.top_exercises[:10]:
            ex = lookup(code)
            name = f"{ex.chinese} ({ex.english})" if ex else code
            lines.append(f"- {name}: {_format_kg(tonnage)}")
    else:
        lines.append("- (沒有加權動作可統計)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*由 fitlog --batch 自動彙總*")
    return "\n".join(lines) + "\n"
