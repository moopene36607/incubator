"""fitlog 多堂聚合統計 — 純函式 (no I/O, no LLM).

跑完一週 6-8 節課後,PT 想看「整週的圖」:
- 總共做了幾噸
- 每位學員上了幾堂
- 哪幾個動作的訓練量最多 (重點分布)

aggregate_batch 純函式產出 BatchSummary;render_batch_summary 把它
渲染成 markdown,寫成 _batch_summary.md 放在批次目錄裡。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable

from exercise_db import lookup
from metrics import _format_kg, compute_total_tonnage, compute_training_density

if TYPE_CHECKING:
    from fitlog import SessionInput


@dataclass(frozen=True)
class SessionRanking:
    """單堂課的排行榜資料 (跨學員 leaderboard 用)。"""
    student_name: str
    session_no: int
    session_date: str
    tonnage_kg: float


@dataclass(frozen=True)
class StudentRanking:
    """學員累積訓練量排行 (高頻 + 高量學員脫穎而出)。"""
    student_name: str
    total_tonnage_kg: float
    n_sessions: int


@dataclass(frozen=True)
class BatchSummary:
    n_sessions: int
    total_tonnage_kg: float
    students: dict[str, int]                     # 姓名 → session 數
    top_exercises: list[tuple[str, float]]       # (exercise_code, tonnage) 由高到低
    leaderboard: list[SessionRanking] = field(default_factory=list)
    student_total_leaderboard: list[StudentRanking] = field(default_factory=list)


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


@dataclass(frozen=True)
class WeeklyTonnage:
    """單一 ISO 週的訓練量加總 (週起始為週一)。"""
    week_start: str            # ISO date of Monday
    total_tonnage_kg: float
    n_sessions: int


@dataclass(frozen=True)
class StudentFrequency:
    """學員訓練頻率 (avg sessions / week + adherence 判讀)。"""
    total_sessions: int
    span_days: int               # first → last session 日期差
    sessions_per_week: float     # span 0 時為 0


@dataclass(frozen=True)
class GoalAchievement:
    """單堂報告 banner 用:該堂第一次達成的目標 (exercise + target)。"""
    exercise_code: str
    target_kg: float


@dataclass(frozen=True)
class GoalProgress:
    """學員某動作的目標 vs 現況 (target_kg / current_kg / percent)。
    若達標,achieved_on_session_no / date 記錄第一次達成那一堂 (歷史時刻)。"""
    exercise_code: str
    current_kg: float
    target_kg: float
    percent: float
    achieved_on_session_no: int | None = None
    achieved_on_date: str | None = None


def compute_session_leaderboard(
    sessions: Iterable["SessionInput"],
    top_n: int = 5,
) -> list[SessionRanking]:
    """產出跨學員單堂訓練量排行榜 (Top N)。
    Tie-break: 同 tonnage → (date, session_no, student_name) 字典序小者前。"""
    rankings = [
        SessionRanking(
            student_name=s.student_name,
            session_no=s.session_no,
            session_date=s.session_date,
            tonnage_kg=compute_total_tonnage(s.sets),
        )
        for s in sessions
    ]
    rankings.sort(key=lambda r: (-r.tonnage_kg, r.session_date, r.session_no, r.student_name))
    return rankings[:top_n]


def compute_student_total_leaderboard(
    sessions: Iterable["SessionInput"],
    top_n: int = 5,
) -> list[StudentRanking]:
    """產出學員累積訓練量排行 (整批跨堂加總,Top N)。
    Tie-break: 同 tonnage → session 數 desc → 姓名字典序。"""
    by_student: dict[str, tuple[float, int]] = {}
    for sess in sessions:
        prev_total, prev_count = by_student.get(sess.student_name, (0.0, 0))
        by_student[sess.student_name] = (
            prev_total + compute_total_tonnage(sess.sets),
            prev_count + 1,
        )
    rankings = [
        StudentRanking(
            student_name=name,
            total_tonnage_kg=total,
            n_sessions=count,
        )
        for name, (total, count) in by_student.items()
    ]
    rankings.sort(key=lambda r: (-r.total_tonnage_kg, -r.n_sessions, r.student_name))
    return rankings[:top_n]


def aggregate_batch(sessions: Iterable["SessionInput"]) -> BatchSummary:
    """彙總多堂 session 的整體訓練量、學員出席、動作排行、單堂排行、學員累積排行。"""
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
        leaderboard=compute_session_leaderboard(sessions),
        student_total_leaderboard=compute_student_total_leaderboard(sessions),
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


def compute_exercise_progression(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> dict[str, list[tuple[str, float]]]:
    """For 該學員的每個 weighted exercise,逐堂取 max weight 為當天代表值,
    回傳 dict[exercise_code, list[(date, top_weight)]] 按日期排序。"""
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    result: dict[str, list[tuple[str, float]]] = {}
    for sess in student_sessions:
        per_ex_max: dict[str, float] = {}
        for s in sess.sets:
            if s.weight_kg is None:
                continue
            cur = per_ex_max.get(s.exercise_code)
            if cur is None or s.weight_kg > cur:
                per_ex_max[s.exercise_code] = s.weight_kg
        for code, max_w in per_ex_max.items():
            result.setdefault(code, []).append((sess.session_date, max_w))
    return result


def _render_progression_line(name: str, points: list[tuple[str, float]]) -> str:
    """單行 sparkline + delta% (e.g. '槓鈴臥推: ▁▄█  (45 → 50 kg, +11.1%)')。"""
    weights = [w for _, w in points]
    lo, hi = min(weights), max(weights)
    if hi == lo:
        bars = _SPARKLINE_BARS[4] * len(weights)
    else:
        last_idx = len(_SPARKLINE_BARS) - 1
        bars = "".join(
            _SPARKLINE_BARS[int((w - lo) / (hi - lo) * last_idx)]
            for w in weights
        )
    first, last = weights[0], weights[-1]
    if first == 0:
        delta_str = _format_kg(last - first)
    else:
        pct = (last - first) / first * 100
        sign = "+" if pct >= 0 else ""
        delta_str = f"{sign}{pct:.1f}%"
    return (f"- {name}: {bars}  "
            f"({_format_kg(first)} → {_format_kg(last)}, {delta_str})")


def compute_student_density_progression(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> list[tuple[str, float]]:
    """For 該學員,逐堂計算訓練密度 (tonnage / min),按日期排序。
    全 BW (tonnage 0) 或 0 時長的 session 跳過。"""
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    points: list[tuple[str, float]] = []
    for sess in student_sessions:
        density = compute_training_density(
            compute_total_tonnage(sess.sets), sess.duration_min,
        )
        if density is not None and density > 0:
            points.append((sess.session_date, density))
    return points


def render_density_progression(points: list[tuple[str, float]]) -> str:
    """單行 sparkline + delta% (e.g. '**訓練密度趨勢**: ▁▄█  (90 → 100 kg/min, +11.1%)')。
    < 2 點 → ""。"""
    if len(points) < 2:
        return ""
    densities = [d for _, d in points]
    lo, hi = min(densities), max(densities)
    if hi == lo:
        bars = _SPARKLINE_BARS[4] * len(densities)
    else:
        last_idx = len(_SPARKLINE_BARS) - 1
        bars = "".join(
            _SPARKLINE_BARS[int((d - lo) / (hi - lo) * last_idx)]
            for d in densities
        )
    first, last = densities[0], densities[-1]
    if first == 0:
        delta_str = f"{round(last - first)} kg/min"
    else:
        pct = (last - first) / first * 100
        sign = "+" if pct >= 0 else ""
        delta_str = f"{sign}{pct:.1f}%"
    return (f"**訓練密度趨勢**: {bars}  "
            f"({round(first)} → {round(last)} kg/min, {delta_str})")


def compute_student_rpe_progression(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> list[tuple[str, float]]:
    """For 該學員,逐堂計算 avg RPE (該堂所有有 RPE 的 set 平均),按日期排序。
    全 set 無 RPE 的 session → 跳過 (避免 0 誤導)。"""
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    points: list[tuple[str, float]] = []
    for sess in student_sessions:
        rpes = [s.rpe for s in sess.sets if s.rpe is not None]
        if not rpes:
            continue
        avg = sum(rpes) / len(rpes)
        points.append((sess.session_date, avg))
    return points


def render_rpe_progression(points: list[tuple[str, float]]) -> str:
    """單行 sparkline + delta (e.g. '**訓練強度趨勢 (avg RPE)**: ▁▄█  (7.0 → 9.0, +2.0)')。
    < 2 點 → ""。"""
    if len(points) < 2:
        return ""
    rpes = [r for _, r in points]
    lo, hi = min(rpes), max(rpes)
    if hi == lo:
        bars = _SPARKLINE_BARS[4] * len(rpes)
    else:
        last_idx = len(_SPARKLINE_BARS) - 1
        bars = "".join(
            _SPARKLINE_BARS[int((r - lo) / (hi - lo) * last_idx)]
            for r in rpes
        )
    first, last = rpes[0], rpes[-1]
    delta = last - first
    sign = "+" if delta >= 0 else ""
    return (f"**訓練強度趨勢 (avg RPE)**: {bars}  "
            f"({first:.1f} → {last:.1f}, {sign}{delta:.1f})")


def compute_student_1rm_progression(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> dict[str, list[tuple[str, float]]]:
    """For 該學員的每個 weighted exercise,逐堂取 max estimated 1RM 為當天
    代表值,回傳 dict[exercise_code, list[(date, top_1rm_estimate)]]
    按日期排序。reps 不在 epley 範圍 / BW / 非整數 reps 的 set 跳過。"""
    from coaching import estimate_1rm
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    result: dict[str, list[tuple[str, float]]] = {}
    for sess in student_sessions:
        per_ex_max: dict[str, float] = {}
        for s in sess.sets:
            if s.weight_kg is None:
                continue
            reps_str = s.reps_or_duration.strip()
            if not reps_str.isdigit():
                continue
            est = estimate_1rm(s.weight_kg, int(reps_str))
            if est is None:
                continue
            cur = per_ex_max.get(s.exercise_code)
            if cur is None or est > cur:
                per_ex_max[s.exercise_code] = est
        for code, max_e in per_ex_max.items():
            result.setdefault(code, []).append((sess.session_date, max_e))
    return result


def render_1rm_progressions(
    progressions: dict[str, list[tuple[str, float]]],
) -> str:
    """產出「## 估計 1RM 跨堂進步」section。少於 2 點的 exercise 跳過。
    全跳過 (或 dict 空) → ""。排序: 各 exercise 的 max 1RM desc。"""
    if not progressions:
        return ""
    items = sorted(
        progressions.items(),
        key=lambda kv: -max(e for _, e in kv[1]) if kv[1] else 0,
    )
    body: list[str] = []
    for code, points in items:
        if len(points) < 2:
            continue
        ex = lookup(code)
        name = ex.chinese if ex else code
        body.append(_render_progression_line(name + " 1RM", points))
    if not body:
        return ""
    return "\n".join(["## 估計 1RM 跨堂進步", "", *body, ""])


def render_exercise_progressions(
    progressions: dict[str, list[tuple[str, float]]],
) -> str:
    """產出「## 主要動作進度」section。少於 2 點的 exercise 跳過。
    全跳過 (或 dict 空) → ""。排序: 各 exercise 的 max weight desc。"""
    if not progressions:
        return ""
    items = sorted(
        progressions.items(),
        key=lambda kv: -max(w for _, w in kv[1]) if kv[1] else 0,
    )
    body: list[str] = []
    for code, points in items:
        if len(points) < 2:
            continue
        ex = lookup(code)
        name = ex.chinese if ex else code
        body.append(_render_progression_line(name, points))
    if not body:
        return ""
    return "\n".join(["## 主要動作進度", "", *body, ""])


def compute_bw_reps_progression(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> dict[str, list[tuple[str, int]]]:
    """For 該學員的每個 BW exercise (weight_kg is None + reps 是純整數),
    逐堂取 max reps 為當天代表值,回傳 dict[exercise_code, list[(date, top_reps)]]
    按日期排序。時間/距離型 (60 sec / 500 m) 不算 reps,跳過。"""
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    result: dict[str, list[tuple[str, int]]] = {}
    for sess in student_sessions:
        per_ex_max: dict[str, int] = {}
        for s in sess.sets:
            if s.weight_kg is not None:
                continue  # 加重動作走 weight_progression
            reps_str = s.reps_or_duration.strip()
            if not reps_str.isdigit():
                continue  # 時間/距離型跳過
            r = int(reps_str)
            cur = per_ex_max.get(s.exercise_code)
            if cur is None or r > cur:
                per_ex_max[s.exercise_code] = r
        for code, max_r in per_ex_max.items():
            result.setdefault(code, []).append((sess.session_date, max_r))
    return result


def _render_reps_progression_line(name: str, points: list[tuple[str, int]]) -> str:
    """單行 sparkline + delta% (e.g. '引體向上: ▁▄█  (5 → 10 reps, +100.0%)')。"""
    reps = [r for _, r in points]
    lo, hi = min(reps), max(reps)
    if hi == lo:
        bars = _SPARKLINE_BARS[4] * len(reps)
    else:
        last_idx = len(_SPARKLINE_BARS) - 1
        bars = "".join(
            _SPARKLINE_BARS[int((r - lo) / (hi - lo) * last_idx)]
            for r in reps
        )
    first, last = reps[0], reps[-1]
    if first == 0:
        delta_str = f"{last - first:+d} reps"
    else:
        pct = (last - first) / first * 100
        sign = "+" if pct >= 0 else ""
        delta_str = f"{sign}{pct:.1f}%"
    return f"- {name}: {bars}  ({first} → {last} reps, {delta_str})"


def render_bw_reps_progressions(
    progressions: dict[str, list[tuple[str, int]]],
) -> str:
    """產出「## BW reps 跨堂進步」section。少於 2 點的 exercise 跳過。
    全跳過 (或 dict 空) → ""。排序: 各 exercise 的 max reps desc。"""
    if not progressions:
        return ""
    items = sorted(
        progressions.items(),
        key=lambda kv: -max(r for _, r in kv[1]) if kv[1] else 0,
    )
    body: list[str] = []
    for code, points in items:
        if len(points) < 2:
            continue
        ex = lookup(code)
        name = ex.chinese if ex else code
        body.append(_render_reps_progression_line(name, points))
    if not body:
        return ""
    return "\n".join(["## BW reps 跨堂進步", "", *body, ""])


def compute_student_intensity_progression(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> list[tuple[str, float]]:
    """For 該學員,逐堂算 intensity_score (tonnage × avg_rpe/10),按 date 排序。
    score=None (全 BW / 無 RPE) 的堂跳過。"""
    from metrics import compute_session_intensity_score
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    points: list[tuple[str, float]] = []
    for sess in student_sessions:
        score = compute_session_intensity_score(sess)
        if score is not None and score > 0:
            points.append((sess.session_date, score))
    return points


def render_intensity_progression(points: list[tuple[str, float]]) -> str:
    """單行 sparkline + delta% (e.g. '**訓練強度分數趨勢**: ▁▄█  (252 → 360, +42.9%)')。
    < 2 點 → ""。"""
    if len(points) < 2:
        return ""
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        bars = _SPARKLINE_BARS[4] * len(vals)
    else:
        last_idx = len(_SPARKLINE_BARS) - 1
        bars = "".join(
            _SPARKLINE_BARS[int((v - lo) / (hi - lo) * last_idx)]
            for v in vals
        )
    first, last = vals[0], vals[-1]
    if first == 0:
        delta_str = f"{round(last - first):+d}"
    else:
        pct = (last - first) / first * 100
        sign = "+" if pct >= 0 else ""
        delta_str = f"{sign}{pct:.1f}%"
    return (
        f"**訓練強度分數趨勢**: {bars}  "
        f"({round(first)} → {round(last)}, {delta_str})"
    )


@dataclass(frozen=True)
class ExerciseVariety:
    """學員動作多樣性指標 (recent window vs all-time)。"""
    recent_unique: int       # 最近 N 堂的 unique exercise code 數
    all_time_unique: int     # 歷來 unique exercise code 數
    window_sessions: int     # 實際 recent window 內的堂數 (可能 < N)


DEFAULT_VARIETY_WINDOW = 4


def compute_exercise_variety(
    sessions: Iterable["SessionInput"],
    student_name: str,
    window: int = DEFAULT_VARIETY_WINDOW,
) -> ExerciseVariety | None:
    """該學員過去 N 堂 unique exercise code 數 + all-time unique 數。
    沒任何 session → None。少於 N 堂時,recent = all-time (用全部),
    window_sessions 反映實際數。"""
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    if not student_sessions:
        return None
    all_codes: set[str] = set()
    for sess in student_sessions:
        for s in sess.sets:
            all_codes.add(s.exercise_code)
    recent = student_sessions[-window:]
    recent_codes: set[str] = set()
    for sess in recent:
        for s in sess.sets:
            recent_codes.add(s.exercise_code)
    return ExerciseVariety(
        recent_unique=len(recent_codes),
        all_time_unique=len(all_codes),
        window_sessions=len(recent),
    )


def render_exercise_variety(v: ExerciseVariety | None) -> str | None:
    """🎨 **動作多樣性**:近 4 堂用了 8 種動作 (歷來 12 種)。None → None。"""
    if v is None:
        return None
    return (
        f"🎨 **動作多樣性**:近 {v.window_sessions} 堂用了 "
        f"{v.recent_unique} 種動作 (歷來 {v.all_time_unique} 種)"
    )


@dataclass(frozen=True)
class CoachWorkload:
    """單一教練在批次內的工作量 (堂數 / 不重複學員數 / 總訓練量)。"""
    coach_name: str
    n_sessions: int
    n_students: int
    total_tonnage_kg: float


def compute_coach_workload(
    sessions: Iterable["SessionInput"],
) -> list[CoachWorkload]:
    """按 coach_name 匯總工作量。sort: 堂數 desc → 教練名字典序。"""
    # coach → (n_sessions, set[student], total_tonnage)
    buckets: dict[str, tuple[int, set[str], float]] = {}
    for sess in sessions:
        n, students, total = buckets.get(sess.coach_name, (0, set(), 0.0))
        students.add(sess.student_name)
        buckets[sess.coach_name] = (
            n + 1,
            students,
            total + compute_total_tonnage(sess.sets),
        )
    rows = [
        CoachWorkload(
            coach_name=name,
            n_sessions=n,
            n_students=len(students),
            total_tonnage_kg=total,
        )
        for name, (n, students, total) in buckets.items()
    ]
    rows.sort(key=lambda w: (-w.n_sessions, w.coach_name))
    return rows


def render_coach_workload(rows: list[CoachWorkload]) -> str:
    """產出「## 教練工作量」section。空 / 只 1 位教練 → "" (無比較意義)。"""
    if len(rows) < 2:
        return ""
    lines: list[str] = ["## 教練工作量", ""]
    lines.append("| 教練 | 堂數 | 學員數 | 總訓練量 |")
    lines.append("|------|------|--------|----------|")
    for w in rows:
        lines.append(
            f"| {w.coach_name} | {w.n_sessions} | {w.n_students} "
            f"| {_format_kg(w.total_tonnage_kg)} |"
        )
    lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True)
class StudioWeek:
    """工作室 (cross-student) 單一 ISO 週的訓練量加總。week_start 為週一 ISO date。"""
    week_start: str
    total_tonnage_kg: float
    n_sessions: int
    n_students: int


def compute_studio_weekly_tonnage(
    sessions: Iterable["SessionInput"],
) -> list[StudioWeek]:
    """跨所有學員按 ISO 週分組,回傳 list (按 week_start 排序)。"""
    from datetime import date
    # week_start_iso → (total_kg, set[student_name], n_sessions)
    buckets: dict[str, tuple[float, set[str], int]] = {}
    for sess in sessions:
        try:
            d = date.fromisoformat(sess.session_date)
        except ValueError:
            continue
        y, w, _ = d.isocalendar()
        week_start = date.fromisocalendar(y, w, 1).isoformat()
        t = compute_total_tonnage(sess.sets)
        prev_total, prev_students, prev_n = buckets.get(
            week_start, (0.0, set(), 0)
        )
        prev_students.add(sess.student_name)
        buckets[week_start] = (
            prev_total + t,
            prev_students,
            prev_n + 1,
        )
    return [
        StudioWeek(
            week_start=ws,
            total_tonnage_kg=total,
            n_sessions=n,
            n_students=len(students),
        )
        for ws, (total, students, n) in sorted(buckets.items())
    ]


def render_studio_weekly_tonnage(rows: list[StudioWeek]) -> str:
    """產出「## 工作室週訓練量」section。空 list → "" 。
    2+ 列時加 sparkline。"""
    if not rows:
        return ""
    lines: list[str] = ["## 工作室週訓練量", ""]
    lines.append("| 週起 (週一) | 噸位 | 堂數 | 學員數 |")
    lines.append("|------------|------|------|--------|")
    for r in rows:
        lines.append(
            f"| {r.week_start} | {_format_kg(r.total_tonnage_kg)} "
            f"| {r.n_sessions} | {r.n_students} |"
        )
    lines.append("")
    if len(rows) >= 2:
        tons = [r.total_tonnage_kg for r in rows]
        lo, hi = min(tons), max(tons)
        if hi == lo:
            bars = _SPARKLINE_BARS[4] * len(tons)
        else:
            last_idx = len(_SPARKLINE_BARS) - 1
            bars = "".join(
                _SPARKLINE_BARS[int((t - lo) / (hi - lo) * last_idx)]
                for t in tons
            )
        first, last = tons[0], tons[-1]
        delta_str = (
            f"{(last - first) / first * 100:+.1f}%"
            if first > 0 else f"{last - first:+.0f}"
        )
        lines.append(
            f"**工作室週訓練量趨勢**: {bars}  "
            f"({_format_kg(first)} → {_format_kg(last)}, {delta_str})"
        )
        lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True)
class FavoriteExercise:
    """學員累積 tonnage 最大的 weighted exercise + 占該學員總 tonnage 比例。"""
    exercise_code: str
    total_tonnage_kg: float
    pct: float  # 0-100


def compute_favorite_exercise(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> FavoriteExercise | None:
    """找該學員累積 tonnage 最大的 exercise。全 BW (tonnage 0) → None。
    Tie-break: 同 tonnage → exercise_code 字典序小者。"""
    per_ex: dict[str, float] = {}
    total = 0.0
    for sess in sessions:
        if sess.student_name != student_name:
            continue
        for s in sess.sets:
            t = compute_total_tonnage([s])
            if t <= 0:
                continue
            per_ex[s.exercise_code] = per_ex.get(s.exercise_code, 0.0) + t
            total += t
    if not per_ex or total <= 0:
        return None
    code, ton = max(per_ex.items(), key=lambda kv: (kv[1], -ord(kv[0][0])))
    # 上面 tie-break 用 -ord(first_char) 不完美;改用穩定排序
    code, ton = sorted(per_ex.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return FavoriteExercise(
        exercise_code=code,
        total_tonnage_kg=ton,
        pct=ton / total * 100,
    )


def render_favorite_exercise(fav: FavoriteExercise | None) -> str | None:
    """🌟 **最常練**:槓鈴臥推 1,600 kg (52% 累積訓練量)。None → None。"""
    if fav is None:
        return None
    ex = lookup(fav.exercise_code)
    name = ex.chinese if ex else fav.exercise_code
    return (
        f"🌟 **最常練**:{name} {_format_kg(fav.total_tonnage_kg)} "
        f"({round(fav.pct)}% 累積訓練量)"
    )


# 開課日分布;0=Monday ... 6=Sunday (符合 Python date.weekday())
_WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
# 8 級方塊 bar 字元 (1/8 to 8/8)
_BAR_CHARS = "▏▎▍▌▋▊▉█"


def compute_day_of_week_distribution(
    sessions: Iterable["SessionInput"],
) -> dict[int, int]:
    """數每堂課落在週幾 (0=Mon ... 6=Sun)。永遠回傳 7 個 keys (含 0 count)
    讓 render 端格式穩定。"""
    from datetime import date
    dist: dict[int, int] = {d: 0 for d in range(7)}
    for s in sessions:
        try:
            wd = date.fromisoformat(s.session_date).weekday()
        except ValueError:
            continue
        dist[wd] += 1
    return dist


def render_day_of_week_distribution(dist: dict[int, int]) -> str:
    """產出「## 開課日分布」section,每行一個週幾 + bar + count。
    全 0 → "" (沒東西可講)。bar 長度按 max count 等比例縮放,最大 12 字元。"""
    total = sum(dist.values())
    if total == 0:
        return ""
    max_count = max(dist.values())
    max_bar_width = 12  # 字元寬度上限,避免報表太寬
    lines: list[str] = ["## 開課日分布", ""]
    for d in range(7):
        count = dist[d]
        if max_count == 0:
            bar = ""
        else:
            # 用 8 級方塊把比例切細;count=0 → 空字串
            eighths = round(count / max_count * max_bar_width * 8)
            full = eighths // 8
            partial = eighths % 8
            bar = "█" * full
            if partial > 0:
                bar += _BAR_CHARS[partial - 1]
        lines.append(f"- {_WEEKDAY_ZH[d]} `{bar}` {count}")
    lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True)
class AbsentStudent:
    """超過門檻天數沒進場的學員。"""
    student_name: str
    last_session_date: str
    days_since: int


# 從沒一堂課就上不到名單 (沒「上次」可比);> 此天數才算缺席
DEFAULT_ABSENT_THRESHOLD_DAYS = 14


def compute_absent_students(
    sessions: Iterable["SessionInput"],
    as_of_iso: str,
    threshold_days: int = DEFAULT_ABSENT_THRESHOLD_DAYS,
) -> list[AbsentStudent]:
    """as_of_iso 為準,列出 days_since > threshold 的學員。
    sort: days desc, ties by name asc。從沒上過課的人不入名單。"""
    from datetime import date
    as_of = date.fromisoformat(as_of_iso)
    latest_per_student: dict[str, str] = {}
    for s in sessions:
        cur = latest_per_student.get(s.student_name)
        if cur is None or s.session_date > cur:
            latest_per_student[s.student_name] = s.session_date
    absents: list[AbsentStudent] = []
    for name, last_date in latest_per_student.items():
        days = (as_of - date.fromisoformat(last_date)).days
        if days > threshold_days:
            absents.append(AbsentStudent(
                student_name=name, last_session_date=last_date,
                days_since=days,
            ))
    absents.sort(key=lambda a: (-a.days_since, a.student_name))
    return absents


def render_absent_students(absents: list[AbsentStudent]) -> str:
    """產出「## 長期缺席學員」section。空 list → ""(不渲染)。"""
    if not absents:
        return ""
    lines = ["## 長期缺席學員 (>2 週)", ""]
    for a in absents:
        lines.append(
            f"- {a.student_name}: 最後一堂 {a.last_session_date} "
            f"({a.days_since} 天前)"
        )
    lines.append("")
    return "\n".join(lines)


def compute_training_streak(
    sessions: Iterable["SessionInput"],
    student_name: str,
    today_iso: str,
) -> int:
    """該學員到 today_iso 為止,往回連續多少 ISO 週都有 session。
    當週若沒 session → 直接 0 (避免假慶祝)。沒任何 session → 0。
    today_iso 格式 YYYY-MM-DD。"""
    from datetime import date, timedelta
    today = date.fromisoformat(today_iso)
    today_year, today_week, _ = today.isocalendar()
    weeks = {
        date.fromisoformat(s.session_date).isocalendar()[:2]
        for s in sessions
        if s.student_name == student_name
    }
    if (today_year, today_week) not in weeks:
        return 0
    # 從當週往回算連續週
    streak = 0
    y, w = today_year, today_week
    while (y, w) in weeks:
        streak += 1
        # 退一週 (跨年: ISO 第 1 週前是上一年的 52 或 53)
        # 用 date 去走 7 天前再取 isocalendar 最安全
        prev = date.fromisocalendar(y, w, 1) - timedelta(days=1)
        y, w, _ = prev.isocalendar()
    return streak


def render_training_streak(streak: int) -> str | None:
    """🔥 **連續訓練 {N} 週**。0 → None (避免每個剛中斷的學員被打臉)。"""
    if streak <= 0:
        return None
    return f"🔥 **連續訓練 {streak} 週**"


@dataclass(frozen=True)
class NewPrRecord:
    """當堂打破歷來最佳的 PR 紀錄。
    kind: "weight" (top weight kg) | "bw_reps" (BW 動作 top reps)。
    prev_best=0 → 從沒做過這個動作 (首次嘗試也算 PR)。"""
    exercise_code: str
    kind: str  # "weight" | "bw_reps"
    curr_value: float        # 重量 kg 或 reps int (用 float 包通用)
    prev_best: float


def _curr_max_weight(sets: Iterable["SetRecord"], code: str) -> float | None:
    weights = [s.weight_kg for s in sets
               if s.exercise_code == code and s.weight_kg is not None]
    return max(weights) if weights else None


def _curr_max_bw_reps(sets: Iterable["SetRecord"], code: str) -> int | None:
    candidates: list[int] = []
    for s in sets:
        if s.exercise_code != code or s.weight_kg is not None:
            continue
        reps_str = s.reps_or_duration.strip()
        if not reps_str.isdigit():
            continue
        candidates.append(int(reps_str))
    return max(candidates) if candidates else None


def detect_new_prs(
    sessions: Iterable["SessionInput"],
    student_name: str,
    current_session: "SessionInput",
) -> list[NewPrRecord]:
    """偵測 current_session 中,有哪個 exercise 的 max weight (或 BW max reps)
    嚴格大於該學員所有「嚴格早於當堂」的 sessions 的 max。回傳 list,排序:
    weight (delta desc) → bw_reps (delta desc)。"""
    cur_key = (current_session.session_date, current_session.session_no)
    prior = [
        s for s in sessions
        if s.student_name == student_name
        and (s.session_date, s.session_no) < cur_key
    ]
    if not prior:
        # 第一堂沒歷史可比,不算 PR (避免每位學員的處女堂都被狂歡)
        return []
    # 歷來 weight max per exercise
    prior_weight_max: dict[str, float] = {}
    prior_bw_max: dict[str, int] = {}
    for sess in prior:
        for s in sess.sets:
            if s.weight_kg is not None:
                cur = prior_weight_max.get(s.exercise_code, 0.0)
                if s.weight_kg > cur:
                    prior_weight_max[s.exercise_code] = s.weight_kg
            else:
                reps_str = s.reps_or_duration.strip()
                if not reps_str.isdigit():
                    continue
                r = int(reps_str)
                cur_r = prior_bw_max.get(s.exercise_code, 0)
                if r > cur_r:
                    prior_bw_max[s.exercise_code] = r

    weight_prs: list[NewPrRecord] = []
    bw_prs: list[NewPrRecord] = []
    seen_codes: set[str] = set()
    for s in current_session.sets:
        if s.exercise_code in seen_codes:
            continue
        seen_codes.add(s.exercise_code)
        # weight track
        curr_w = _curr_max_weight(current_session.sets, s.exercise_code)
        if curr_w is not None:
            prev = prior_weight_max.get(s.exercise_code, 0.0)
            if curr_w > prev:
                weight_prs.append(NewPrRecord(
                    exercise_code=s.exercise_code, kind="weight",
                    curr_value=curr_w, prev_best=prev,
                ))
            continue
        # BW reps track
        curr_r = _curr_max_bw_reps(current_session.sets, s.exercise_code)
        if curr_r is not None:
            prev_r = prior_bw_max.get(s.exercise_code, 0)
            if curr_r > prev_r:
                bw_prs.append(NewPrRecord(
                    exercise_code=s.exercise_code, kind="bw_reps",
                    curr_value=float(curr_r), prev_best=float(prev_r),
                ))
    weight_prs.sort(key=lambda r: -(r.curr_value - r.prev_best))
    bw_prs.sort(key=lambda r: -(r.curr_value - r.prev_best))
    return weight_prs + bw_prs


def _format_pr_value(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


def render_new_pr_banner(prs: list[NewPrRecord]) -> str | None:
    """「🏆 **PR 突破**!: 槓鈴臥推 50 kg (打破歷來最高 45 kg) · 引體向上 8 reps ...」。
    空 → None。prev_best 0 → 「首次」標記。"""
    if not prs:
        return None
    parts: list[str] = []
    for pr in prs:
        ex = lookup(pr.exercise_code)
        name = ex.chinese if ex else pr.exercise_code
        unit = "kg" if pr.kind == "weight" else "reps"
        curr_str = _format_pr_value(pr.curr_value)
        if pr.prev_best <= 0:
            parts.append(f"{name} {curr_str} {unit} (首次)")
        else:
            prev_str = _format_pr_value(pr.prev_best)
            parts.append(
                f"{name} {curr_str} {unit} "
                f"(打破歷來最高 {prev_str} {unit})"
            )
    return "🏆 **PR 突破**!: " + " · ".join(parts)


def compute_duration_progression(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> dict[str, tuple[str, list[tuple[str, int]]]]:
    """For 該學員的每個 duration 型 exercise (reps_or_duration = "N <unit>",
    unit ∈ sec/min/m/km),逐堂取 max value 為當天代表值。
    回傳 dict[code, (unit, [(date, value), ...])] 按 date 排序。

    跨堂單位變了 → 整個 exercise 跳過 (避免 60 sec vs 1 min 混淆)。
    """
    from progress import _parse_duration  # 共用解析,避免重複
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    per_ex: dict[str, tuple[str, list[tuple[str, int]]]] = {}
    mixed_codes: set[str] = set()
    for sess in student_sessions:
        per_ex_top: dict[str, tuple[int, str]] = {}
        for s in sess.sets:
            parsed = _parse_duration(s.reps_or_duration)
            if parsed is None:
                continue
            val, unit = parsed
            cur = per_ex_top.get(s.exercise_code)
            if cur is None or val > cur[0]:
                per_ex_top[s.exercise_code] = (val, unit)
        for code, (val, unit) in per_ex_top.items():
            if code in mixed_codes:
                continue
            existing = per_ex.get(code)
            if existing is None:
                per_ex[code] = (unit, [(sess.session_date, val)])
            else:
                seen_unit, points = existing
                if seen_unit != unit:
                    mixed_codes.add(code)
                    per_ex.pop(code, None)
                else:
                    points.append((sess.session_date, val))
    return per_ex


def _render_duration_progression_line(
    name: str, unit: str, points: list[tuple[str, int]],
) -> str:
    """單行 sparkline + delta% (e.g. '棒式: ▁▄█  (45 → 90 sec, +100.0%)')。"""
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        bars = _SPARKLINE_BARS[4] * len(vals)
    else:
        last_idx = len(_SPARKLINE_BARS) - 1
        bars = "".join(
            _SPARKLINE_BARS[int((v - lo) / (hi - lo) * last_idx)]
            for v in vals
        )
    first, last = vals[0], vals[-1]
    if first == 0:
        delta_str = f"{last - first:+d} {unit}"
    else:
        pct = (last - first) / first * 100
        sign = "+" if pct >= 0 else ""
        delta_str = f"{sign}{pct:.1f}%"
    return f"- {name}: {bars}  ({first} → {last} {unit}, {delta_str})"


def render_duration_progressions(
    progressions: dict[str, tuple[str, list[tuple[str, int]]]],
) -> str:
    """產出「## 時間/距離跨堂進步」section。少於 2 點的 exercise 跳過。
    全跳過 (或 dict 空) → ""。排序: 各 exercise 的 max value desc。"""
    if not progressions:
        return ""
    items = sorted(
        progressions.items(),
        key=lambda kv: -max(v for _, v in kv[1][1]) if kv[1][1] else 0,
    )
    body: list[str] = []
    for code, (unit, points) in items:
        if len(points) < 2:
            continue
        ex = lookup(code)
        name = ex.chinese if ex else code
        body.append(_render_duration_progression_line(name, unit, points))
    if not body:
        return ""
    return "\n".join(["## 時間/距離跨堂進步", "", *body, ""])


def compute_weekly_tonnage(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> list[WeeklyTonnage]:
    """按 ISO 週分組學員 sessions,加總每週 tonnage 與堂數。
    回傳按 week_start (週一日) 升序排列的 list。"""
    from datetime import date as _date
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    weeks: dict[tuple[int, int], list[float]] = {}
    for sess in student_sessions:
        d = _date.fromisoformat(sess.session_date)
        iso = d.isocalendar()
        key = (iso[0], iso[1])
        if key not in weeks:
            weeks[key] = [0.0, 0]
        weeks[key][0] += compute_total_tonnage(sess.sets)
        weeks[key][1] += 1
    result: list[WeeklyTonnage] = []
    for (year, week), (total, count) in sorted(weeks.items()):
        monday = _date.fromisocalendar(year, week, 1).isoformat()
        result.append(WeeklyTonnage(
            week_start=monday,
            total_tonnage_kg=total,
            n_sessions=int(count),
        ))
    return result


def render_weekly_tonnage(weekly: list[WeeklyTonnage]) -> str:
    """產出「## 週訓練量分布」table。< 2 週 → "" (沒分布可講)。"""
    if len(weekly) < 2:
        return ""
    lines = ["## 週訓練量分布", "", "| 週起始 | 堂數 | 訓練量 |", "|---------|------|---------|"]
    for w in weekly:
        lines.append(f"| {w.week_start} | {w.n_sessions} | {_format_kg(w.total_tonnage_kg)} |")
    lines.append("")
    return "\n".join(lines)


def compute_student_session_frequency(
    sessions: Iterable["SessionInput"],
    student_name: str,
) -> StudentFrequency | None:
    """計算該學員的 first→last 期間平均週訓練次數 (adherence 指標)。
    無 session → None;單堂或同日多堂 (span 0) → freq 0 (不能 div0)。"""
    from datetime import date as _date
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    if not student_sessions:
        return None
    first = _date.fromisoformat(student_sessions[0].session_date)
    last = _date.fromisoformat(student_sessions[-1].session_date)
    span_days = (last - first).days
    sessions_per_week = (
        len(student_sessions) / (span_days / 7.0) if span_days > 0 else 0.0
    )
    return StudentFrequency(
        total_sessions=len(student_sessions),
        span_days=span_days,
        sessions_per_week=sessions_per_week,
    )


def render_session_frequency(freq: StudentFrequency | None) -> str:
    """**訓練頻率**: 平均 X 次/週 (N 堂 / D 天)。
    None / 單堂 / span 0 → "" (沒進步可講)。"""
    if freq is None or freq.total_sessions < 2 or freq.span_days == 0:
        return ""
    return (f"**訓練頻率**: 平均 {freq.sessions_per_week:.1f} 次/週 "
            f"({freq.total_sessions} 堂 / {freq.span_days} 天)")


def find_newly_achieved_goals(
    session: "SessionInput",
    all_sessions: Iterable["SessionInput"],
    targets: list[dict],
) -> list[GoalAchievement]:
    """偵測 `session` 是否首次達成 `targets` 中任何目標 (本堂達標 + 歷史所有
    prior session 該動作都未達)。同學員的較早 sessions 才算 prior。"""
    sessions_list = list(all_sessions)
    achievements: list[GoalAchievement] = []
    for t in targets:
        code = t.get("exercise_code")
        target = t.get("target_weight_kg")
        if not code or target is None:
            continue
        try:
            target_f = float(target)
        except (TypeError, ValueError):
            continue
        if target_f <= 0:
            continue
        # 本堂該動作的 max weight
        max_w = max(
            (s.weight_kg for s in session.sets
             if s.exercise_code == code and s.weight_kg is not None),
            default=None,
        )
        if max_w is None or max_w < target_f:
            continue
        # 看歷史 prior 是否也達過
        prior_sessions = [
            s for s in sessions_list
            if s.student_name == session.student_name
            and (s.session_date, s.session_no) < (session.session_date, session.session_no)
        ]
        prior_hit = any(
            (sr.weight_kg is not None and sr.weight_kg >= target_f
             and sr.exercise_code == code)
            for sess in prior_sessions for sr in sess.sets
        )
        if not prior_hit:
            achievements.append(GoalAchievement(
                exercise_code=code,
                target_kg=target_f,
            ))
    return achievements


def render_session_goal_banner(achievements: list[GoalAchievement]) -> str:
    """產出「🎉 目標達成」banner;空 list → ""。"""
    if not achievements:
        return ""
    lines: list[str] = ["🎉 **目標達成!**", ""]
    for a in achievements:
        ex = lookup(a.exercise_code)
        name = ex.chinese if ex else a.exercise_code
        lines.append(f"- {name}: 突破 {_format_kg(a.target_kg)} 目標!")
    lines.append("")
    return "\n".join(lines)


def _find_goal_achievement(
    exercise_code: str,
    target_kg: float,
    sessions: list["SessionInput"],
    student_name: str,
) -> tuple[int, str] | None:
    """掃該學員的 sessions (按日期+session_no 排序),找第一個 max(weight) >= target
    的 session,回傳 (session_no, date)。沒達標 → None。"""
    student_sessions = sorted(
        (s for s in sessions if s.student_name == student_name),
        key=lambda s: (s.session_date, s.session_no),
    )
    for sess in student_sessions:
        max_w = max(
            (s.weight_kg for s in sess.sets
             if s.exercise_code == exercise_code and s.weight_kg is not None),
            default=None,
        )
        if max_w is not None and max_w >= target_kg:
            return (sess.session_no, sess.session_date)
    return None


def compute_goal_progress(
    targets: list[dict],
    prs: dict[str, AllTimeBest],
    sessions: Iterable["SessionInput"] | None = None,
    student_name: str | None = None,
) -> list[GoalProgress]:
    """對每個 target 算 (現況 / 目標) %。target=0 跳過 (避免 div0)。
    若有 sessions + student_name,額外找第一次達標那一堂的 session_no/date。"""
    sessions_list = list(sessions) if sessions else []
    result: list[GoalProgress] = []
    for t in targets:
        code = t.get("exercise_code")
        target = t.get("target_weight_kg")
        if not code or target is None:
            continue
        try:
            target_f = float(target)
        except (TypeError, ValueError):
            continue
        if target_f <= 0:
            continue
        current = prs[code].max_weight_kg if code in prs else 0.0
        achieved_no, achieved_date = None, None
        if sessions_list and student_name is not None:
            ach = _find_goal_achievement(code, target_f, sessions_list, student_name)
            if ach is not None:
                achieved_no, achieved_date = ach
        result.append(GoalProgress(
            exercise_code=code,
            current_kg=current,
            target_kg=target_f,
            percent=current / target_f * 100,
            achieved_on_session_no=achieved_no,
            achieved_on_date=achieved_date,
        ))
    return result


def render_goal_progress(
    progress: list[GoalProgress],
    etas: dict[str, str] | None = None,
) -> str:
    """產出「## 目標達成進度」section,每行 progress bar (10 字寬)。
    達 100% 加 ✅;空 list → ""。
    傳 etas={code: iso_date} 時,未達標的目標附加「(預估達成 DATE)」。"""
    if not progress:
        return ""
    etas = etas or {}
    lines: list[str] = ["## 目標達成進度", ""]
    for p in sorted(progress, key=lambda x: -x.percent):
        ex = lookup(p.exercise_code)
        name = ex.chinese if ex else p.exercise_code
        bar_pct = min(p.percent, 100.0)
        filled = int(bar_pct / 10)
        bar = "█" * filled + "░" * (10 - filled)
        check = " ✅" if p.percent >= 100 else ""
        achievement = ""
        if p.achieved_on_session_no is not None:
            achievement = f" 達成於第 {p.achieved_on_session_no} 堂 ({p.achieved_on_date})"
        eta_str = ""
        if p.percent < 100 and p.exercise_code in etas:
            eta_str = f" (預估達成 {etas[p.exercise_code]})"
        lines.append(
            f"- {name}: {_format_kg(p.current_kg)} / {_format_kg(p.target_kg)} "
            f"({p.percent:.0f}%) {bar}{check}{achievement}{eta_str}"
        )
    lines.append("")
    return "\n".join(lines)


# 目標預估的最遠外推距離 (超過視為不切實際,不顯示;避免「2 年後達標」這種無意義 ETA)
DEFAULT_ETA_HORIZON_DAYS = 365


def project_goal_eta(
    points: list[tuple[str, float]],
    target_kg: float,
    today_iso: str,
    max_horizon_days: int = DEFAULT_ETA_HORIZON_DAYS,
) -> str | None:
    """linear regression on (days_since_first, weight),外推到 target_kg。
    回傳預估達成日 (ISO date) 或 None。
    None 觸發條件:點少於 2、slope ≤ 0、已達標、預估超過 horizon。"""
    from datetime import date
    if len(points) < 2:
        return None
    base = date.fromisoformat(points[0][0])
    xs = [(date.fromisoformat(d) - base).days for d, _ in points]
    ys = [w for _, w in points]
    n = len(points)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return None
    slope = num / den  # kg per day
    if slope <= 0:
        return None
    current = ys[-1]
    if current >= target_kg:
        return None
    days_needed = (target_kg - current) / slope
    if days_needed > max_horizon_days:
        return None
    today = date.fromisoformat(today_iso)
    from datetime import timedelta
    eta = today + timedelta(days=int(round(days_needed)))
    return eta.isoformat()


def compute_goal_etas(
    targets: list[dict],
    progressions: dict[str, list[tuple[str, float]]],
    today_iso: str,
    max_horizon_days: int = DEFAULT_ETA_HORIZON_DAYS,
) -> dict[str, str]:
    """對每個 target 找對應的 progression 跑 projection。空 / 已達標 / 無進步
    都跳過。回傳 dict[code, eta_iso_date]。"""
    result: dict[str, str] = {}
    for t in targets:
        code = t.get("exercise_code")
        target = t.get("target_weight_kg")
        if not code or target is None:
            continue
        try:
            target_f = float(target)
        except (TypeError, ValueError):
            continue
        if target_f <= 0:
            continue
        points = progressions.get(code)
        if not points:
            continue
        eta = project_goal_eta(points, target_f, today_iso, max_horizon_days)
        if eta is not None:
            result[code] = eta
    return result


def _insert_toc(text: str) -> str:
    """掃 markdown text 中的 ## headers,2+ 個時插「## 目錄」section
    在 # title 後 / 第一個 ## 前。已有的 ## 目錄 不會被列入避免遞迴。"""
    lines = text.split("\n")
    headers = [l[3:].strip() for l in lines
               if l.startswith("## ") and l[3:].strip() != "目錄"]
    if len(headers) < 2:
        return text
    toc_lines = ["## 目錄", ""]
    for h in headers:
        toc_lines.append(f"- {h}")
    toc_lines.append("")
    # 插在 # title (line 0) + 空行 (line 1) 後
    return "\n".join(lines[:2] + toc_lines + lines[2:])


def render_student_trend(
    trend: StudentTrend,
    all_time_prs: dict[str, AllTimeBest] | None = None,
    all_time_bw_prs: dict[str, AllTimeBwBest] | None = None,
    progressions: dict[str, list[tuple[str, float]]] | None = None,
    goals: list[GoalProgress] | None = None,
    one_rm_progressions: dict[str, list[tuple[str, float]]] | None = None,
    density_progression: list[tuple[str, float]] | None = None,
    frequency: StudentFrequency | None = None,
    weekly_tonnage: list[WeeklyTonnage] | None = None,
    rpe_progression: list[tuple[str, float]] | None = None,
    bw_reps_progressions: dict[str, list[tuple[str, int]]] | None = None,
    duration_progressions: dict[str, tuple[str, list[tuple[str, int]]]] | None = None,
    training_streak: int | None = None,
    goal_etas: dict[str, str] | None = None,
    favorite_exercise: FavoriteExercise | None = None,
    exercise_variety: ExerciseVariety | None = None,
    intensity_progression: list[tuple[str, float]] | None = None,
) -> str:
    """產出單一學員的多堂進步趨勢 markdown。
    傳入 all_time_prs 時加「## 歷來最佳」section (default 不加,向後相容)。"""
    lines: list[str] = []
    lines.append(f"# {trend.student_name} 個人訓練趨勢")
    lines.append("")
    lines.append(f"- **總堂數**: {len(trend.points)}")
    lines.append(f"- **總訓練量**: {_format_kg(trend.total_tonnage)}")
    if training_streak:
        streak_line = render_training_streak(training_streak)
        if streak_line:
            lines.append(f"- {streak_line}")
    if favorite_exercise is not None:
        fav_line = render_favorite_exercise(favorite_exercise)
        if fav_line:
            lines.append(f"- {fav_line}")
    if exercise_variety is not None:
        variety_line = render_exercise_variety(exercise_variety)
        if variety_line:
            lines.append(f"- {variety_line}")
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
    if density_progression:
        density_line = render_density_progression(density_progression)
        if density_line:
            lines.append(density_line)
            lines.append("")
    if rpe_progression:
        rpe_line = render_rpe_progression(rpe_progression)
        if rpe_line:
            lines.append(rpe_line)
            lines.append("")
    if intensity_progression:
        intensity_line = render_intensity_progression(intensity_progression)
        if intensity_line:
            lines.append(intensity_line)
            lines.append("")
    if frequency:
        freq_line = render_session_frequency(frequency)
        if freq_line:
            lines.append(freq_line)
            lines.append("")
    if weekly_tonnage:
        weekly_str = render_weekly_tonnage(weekly_tonnage)
        if weekly_str:
            lines.append(weekly_str)
    if progressions:
        prog_str = render_exercise_progressions(progressions)
        if prog_str:
            lines.append(prog_str)
    if one_rm_progressions:
        one_rm_str = render_1rm_progressions(one_rm_progressions)
        if one_rm_str:
            lines.append(one_rm_str)
    if bw_reps_progressions:
        bw_reps_str = render_bw_reps_progressions(bw_reps_progressions)
        if bw_reps_str:
            lines.append(bw_reps_str)
    if duration_progressions:
        dur_str = render_duration_progressions(duration_progressions)
        if dur_str:
            lines.append(dur_str)
    if goals:
        lines.append(render_goal_progress(goals, etas=goal_etas))
    if all_time_prs or all_time_bw_prs:
        lines.append(render_all_time_prs(all_time_prs or {}, all_time_bw_prs))
    lines.append("---")
    lines.append("")
    lines.append("*由 fitlog --batch 自動產出*")
    return _insert_toc("\n".join(lines) + "\n")


def render_session_one_liner(
    session: "SessionInput",
    pr_count: int = 0,
) -> str:
    """單堂 1-liner 給該學員 LINE 推播。
    格式: '💪 NAME 第 N 堂 · X kg · M min · 主題:T [· P PR]'。
    全 BW (tonnage 0) → 'BW only';0 PR / 無 theme → 不顯示對應段。"""
    tonnage = compute_total_tonnage(session.sets)
    parts: list[str] = [f"💪 {session.student_name} 第 {session.session_no} 堂"]
    parts.append(_format_kg(tonnage) if tonnage > 0 else "BW only")
    parts.append(f"{session.duration_min} min")
    if session.theme.strip():
        parts.append(f"主題:{session.theme}")
    if pr_count > 0:
        parts.append(f"{pr_count} PR")
    return parts[0] + " · " + " · ".join(parts[1:])


def render_batch_one_liner(summary: BatchSummary) -> str:
    """產出一行 emoji 摘要適合 LINE/手機分享。
    格式: '💪 今日 N 堂 / X kg · M 位學員 · 領先 NAME Y kg'。
    0 sessions → "" (沒東西可講)。"""
    if summary.n_sessions == 0:
        return ""
    parts = [
        f"💪 今日 {summary.n_sessions} 堂",
        f"{_format_kg(summary.total_tonnage_kg)}",
        f"{len(summary.students)} 位學員",
    ]
    if summary.leaderboard:
        top = summary.leaderboard[0]
        parts.append(f"領先 {top.student_name} {_format_kg(top.tonnage_kg)}")
    return parts[0] + " / " + " · ".join(parts[1:])


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

    lines.append("## 單堂訓練量排行 (Top 5)")
    lines.append("")
    if summary.leaderboard:
        for i, r in enumerate(summary.leaderboard, 1):
            lines.append(
                f"{i}. {r.student_name} 第 {r.session_no} 堂 ({r.session_date}): "
                f"{_format_kg(r.tonnage_kg)}"
            )
    else:
        lines.append("- (沒有 sessions 可排)")
    lines.append("")

    lines.append("## 學員累積訓練量排行 (Top 5)")
    lines.append("")
    if summary.student_total_leaderboard:
        for i, r in enumerate(summary.student_total_leaderboard, 1):
            lines.append(
                f"{i}. {r.student_name}: {_format_kg(r.total_tonnage_kg)} "
                f"({r.n_sessions} 堂)"
            )
    else:
        lines.append("- (沒有學員資料)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*由 fitlog --batch 自動彙總*")
    return "\n".join(lines) + "\n"
