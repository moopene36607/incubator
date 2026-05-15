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


@dataclass(frozen=True)
class AllTimeBest:
    """單一學員某動作的歷來最佳 (max weight + 達成日)。"""
    exercise_code: str
    max_weight_kg: float
    on_session_no: int
    on_session_date: str


@dataclass(frozen=True)
class AllTimeBwBest:
    """單一學員某 BW 動作的歷來最佳 reps (Pull-up 8 reps 之類)。"""
    exercise_code: str
    max_reps: int
    on_session_no: int
    on_session_date: str


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


def compute_student_prs(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> dict[str, AllTimeBest]:
    """單一學員每個 weighted exercise 的歷來最重 set。
    Tie-break: 同重量 → 取最早達成的日子 (歷史意義)。"""
    student_sessions = [s for s in sessions if s.student_name == student_name]
    by_exercise: dict[str, list[tuple[float, str, int]]] = {}
    for sess in student_sessions:
        for s in sess.sets:
            if s.weight_kg is None:
                continue
            by_exercise.setdefault(s.exercise_code, []).append(
                (s.weight_kg, sess.session_date, sess.session_no)
            )
    result: dict[str, AllTimeBest] = {}
    for code, items in by_exercise.items():
        # max weight 優先;同重量取最早 date 與最小 session_no
        items.sort(key=lambda t: (-t[0], t[1], t[2]))
        max_w, date, sno = items[0]
        result[code] = AllTimeBest(
            exercise_code=code,
            max_weight_kg=max_w,
            on_session_no=sno,
            on_session_date=date,
        )
    return result


def compute_student_bw_prs(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> dict[str, AllTimeBwBest]:
    """單一學員每個 BW exercise (weight_kg=None + 整數 reps) 的歷來最高 reps。
    Tie-break: 同 reps → 取最早達成的日子。"""
    student_sessions = [s for s in sessions if s.student_name == student_name]
    by_exercise: dict[str, list[tuple[int, str, int]]] = {}
    for sess in student_sessions:
        for s in sess.sets:
            if s.weight_kg is not None:
                continue
            reps_str = s.reps_or_duration.strip()
            if not reps_str.isdigit():
                continue
            by_exercise.setdefault(s.exercise_code, []).append(
                (int(reps_str), sess.session_date, sess.session_no)
            )
    result: dict[str, AllTimeBwBest] = {}
    for code, items in by_exercise.items():
        items.sort(key=lambda t: (-t[0], t[1], t[2]))
        max_r, date, sno = items[0]
        result[code] = AllTimeBwBest(
            exercise_code=code,
            max_reps=max_r,
            on_session_no=sno,
            on_session_date=date,
        )
    return result


def render_all_time_prs(
    prs: dict[str, AllTimeBest],
    bw_prs: dict[str, AllTimeBwBest] | None = None,
) -> str:
    """產出「## 歷來最佳」section markdown。
    weighted (按重量 desc) 後接 BW (按 reps desc)。兩邊空 → "".
    bw_prs 可省略 (向後相容上輪的單參數呼叫)。"""
    bw_prs = bw_prs or {}
    if not prs and not bw_prs:
        return ""
    lines: list[str] = ["## 歷來最佳", ""]
    for b in sorted(prs.values(), key=lambda b: -b.max_weight_kg):
        ex = lookup(b.exercise_code)
        name = f"{ex.chinese} ({ex.english})" if ex else b.exercise_code
        lines.append(
            f"- {name}: **{_format_kg(b.max_weight_kg)}** "
            f"(第 {b.on_session_no} 堂, {b.on_session_date})"
        )
    for b in sorted(bw_prs.values(), key=lambda b: -b.max_reps):
        ex = lookup(b.exercise_code)
        name = f"{ex.chinese} ({ex.english})" if ex else b.exercise_code
        lines.append(
            f"- {name} (BW): **{b.max_reps} reps** "
            f"(第 {b.on_session_no} 堂, {b.on_session_date})"
        )
    lines.append("")
    return "\n".join(lines)


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


_SPARKLINE_BARS = "▁▂▃▄▅▆▇█"


def render_tonnage_sparkline(points: list[StudentTrendPoint]) -> str:
    """用 8-level Unicode 方塊把 tonnage 序列畫成單行 sparkline。

    格式: '**訓練量趨勢**: ▆▇▇█  (5,640 → 6,200 kg, +9.9%)'
    空 → '';單點 → '... (X kg)';第一筆 0 不會 div-by-zero。
    """
    if not points:
        return ""
    values = [p.tonnage_kg for p in points]
    if len(points) == 1:
        return f"**訓練量趨勢**: {_SPARKLINE_BARS[4]}  ({_format_kg(values[0])})"

    lo, hi = min(values), max(values)
    if hi == lo:
        bars = _SPARKLINE_BARS[4] * len(points)
    else:
        last_idx = len(_SPARKLINE_BARS) - 1
        bars = "".join(
            _SPARKLINE_BARS[int((v - lo) / (hi - lo) * last_idx)]
            for v in values
        )

    first, last = values[0], values[-1]
    if first == 0:
        delta_str = f"{'+' if last >= 0 else ''}{_format_kg(last - first)}"
    else:
        pct = (last - first) / first * 100
        sign = "+" if pct >= 0 else ""
        delta_str = f"{sign}{pct:.1f}%"
    return (f"**訓練量趨勢**: {bars}  "
            f"({_format_kg(first)} → {_format_kg(last)}, {delta_str})")


def render_student_trend(
    trend: StudentTrend,
    all_time_prs: dict[str, AllTimeBest] | None = None,
    all_time_bw_prs: dict[str, AllTimeBwBest] | None = None,
) -> str:
    """產出單一學員的多堂進步趨勢 markdown。
    傳入 all_time_prs 時加「## 歷來最佳」section (default 不加,向後相容)。"""
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
    sparkline = render_tonnage_sparkline(trend.points)
    if sparkline:
        lines.append(sparkline)
        lines.append("")
    if all_time_prs or all_time_bw_prs:
        lines.append(render_all_time_prs(all_time_prs or {}, all_time_bw_prs))
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
