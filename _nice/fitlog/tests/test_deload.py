"""紅色測試 — 自動偵測 deload 週 (avg RPE-based recovery suggestion).

Coaching 學:學員連續 3 堂平均 RPE 過高 (>= 8.5) 是過度訓練前兆,該安排
deload (降量週) 讓身體恢復。本輪在當堂報告插「📉 建議下次 deload」banner,
讓 PT 看數據而非憑感覺決定。

定義:
- 看「該學員到當堂為止的最近 N 堂」(包含當堂)
- N = DELOAD_MIN_SESSIONS (預設 3)
- 平均所有 sets 的 RPE (跳過無 RPE 的 set)
- 若 avg >= DELOAD_RPE_THRESHOLD (預設 8.5) → signal
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coaching import (  # noqa: E402
    DELOAD_MIN_SESSIONS,
    DELOAD_RPE_THRESHOLD,
    DeloadSignal,
    detect_deload_signal,
    render_deload_banner,
)
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, session_no: int, date: str,
          sets: list[SetRecord]) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=session_no, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t", sets=sets,
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


def _high_rpe_session(student, sno, date) -> SessionInput:
    return _make(student, sno, date, [
        _set("BENCH_PRESS", 4, "8", 50.0, 9),
        _set("BB_BACK_SQUAT", 4, "10", 70.0, 9),
    ])


def _low_rpe_session(student, sno, date) -> SessionInput:
    return _make(student, sno, date, [
        _set("BENCH_PRESS", 4, "8", 50.0, 7),
    ])


class TestDetectDeloadSignal(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        cur = _high_rpe_session("林阿明", 1, "2026-05-10")
        self.assertIsNone(detect_deload_signal([], "林阿明", cur))

    def test_too_few_prior_sessions_returns_none(self) -> None:
        # 只有當堂,不足 N=3
        cur = _high_rpe_session("林阿明", 1, "2026-05-10")
        self.assertIsNone(detect_deload_signal([cur], "林阿明", cur))

    def test_low_avg_rpe_returns_none(self) -> None:
        sessions = [
            _low_rpe_session("林阿明", 1, "2026-05-01"),
            _low_rpe_session("林阿明", 2, "2026-05-08"),
            _low_rpe_session("林阿明", 3, "2026-05-15"),
        ]
        result = detect_deload_signal(sessions, "林阿明", sessions[-1])
        self.assertIsNone(result)

    def test_high_avg_rpe_returns_signal(self) -> None:
        sessions = [
            _high_rpe_session("林阿明", 1, "2026-05-01"),
            _high_rpe_session("林阿明", 2, "2026-05-08"),
            _high_rpe_session("林阿明", 3, "2026-05-15"),
        ]
        result = detect_deload_signal(sessions, "林阿明", sessions[-1])
        self.assertIsNotNone(result)
        self.assertEqual(result.avg_rpe, 9.0)
        self.assertEqual(result.n_recent_sessions, 3)

    def test_uses_only_last_n_sessions(self) -> None:
        # 早 2 堂高 RPE,但近 3 堂低 → 不該觸發 deload
        sessions = [
            _high_rpe_session("林阿明", 1, "2026-04-01"),
            _high_rpe_session("林阿明", 2, "2026-04-08"),
            _low_rpe_session("林阿明", 3, "2026-05-01"),
            _low_rpe_session("林阿明", 4, "2026-05-08"),
            _low_rpe_session("林阿明", 5, "2026-05-15"),
        ]
        result = detect_deload_signal(sessions, "林阿明", sessions[-1])
        self.assertIsNone(result)

    def test_only_counts_target_student(self) -> None:
        # 王小華 高 RPE,林阿明 低 RPE → 林阿明 不該觸發
        sessions = [
            _high_rpe_session("王小華", 1, "2026-05-01"),
            _high_rpe_session("王小華", 2, "2026-05-08"),
            _high_rpe_session("王小華", 3, "2026-05-15"),
            _low_rpe_session("林阿明", 1, "2026-05-15"),
        ]
        cur = _low_rpe_session("林阿明", 1, "2026-05-15")
        result = detect_deload_signal(sessions, "林阿明", cur)
        self.assertIsNone(result)

    def test_threshold_constant_exposed(self) -> None:
        self.assertGreater(DELOAD_RPE_THRESHOLD, 7.0)
        self.assertLess(DELOAD_RPE_THRESHOLD, 10.0)
        self.assertGreaterEqual(DELOAD_MIN_SESSIONS, 2)

    def test_returns_deload_signal_dataclass(self) -> None:
        sessions = [
            _high_rpe_session("林阿明", i, f"2026-05-0{i}")
            for i in range(1, 4)
        ]
        result = detect_deload_signal(sessions, "林阿明", sessions[-1])
        self.assertIsInstance(result, DeloadSignal)


class TestRenderDeloadBanner(unittest.TestCase):
    def test_none_returns_empty(self) -> None:
        self.assertEqual(render_deload_banner(None), "")

    def test_signal_renders_banner(self) -> None:
        signal = DeloadSignal(avg_rpe=9.0, n_recent_sessions=3)
        result = render_deload_banner(signal)
        self.assertIn("📉", result)
        self.assertIn("deload", result.lower())
        self.assertIn("9.0", result)
        self.assertIn("3", result)


class TestCliBatchProducesDeloadBanner(unittest.TestCase):
    def test_high_rpe_history_triggers_banner(self) -> None:
        # 3 堂全 RPE 9 → 該堂 .md 含「deload」banner
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            for i in range(1, 4):
                p = json.loads(json.dumps(SAMPLE_PAYLOAD))
                p["student"]["name"] = "林阿明"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                # 全部 RPE 9
                for s in p["session"]["sets"]:
                    if s.get("rpe") is not None:
                        s["rpe"] = 9
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            s3_md = (Path(out_td) / "s3.md").read_text(encoding="utf-8")
            self.assertIn("📉", s3_md)
            self.assertIn("deload", s3_md.lower())


if __name__ == "__main__":
    unittest.main()
