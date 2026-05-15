"""紅色測試 — 動作分類失衡警示 (近 N 堂某分類占比過高).

PT 處方時可能不小心連續幾堂只練 push (推系) 或只練 legs (腿系)。本輪
跨堂偵測「近 3 堂某分類 tonnage 占 >= 70%」→ 渲染 ⚠️ banner 提醒下次
補對應動作。

跟 round 34 deload 警示 (RPE-based) 互補:一個看「強度過大」、一個看
「結構失衡」。
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
    ImbalanceWarning,
    detect_imbalance_warning,
    render_imbalance_warning,
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


def _set(code: str, sets: int, reps: str, weight: float | None) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=None)


def _push_only_session(student, sno, date) -> SessionInput:
    # BENCH_PRESS / OHP / DIPS 都是 push (per exercise_db)
    return _make(student, sno, date, [
        _set("BENCH_PRESS", 4, "8", 50.0),
        _set("OHP", 4, "8", 30.0),
    ])


def _balanced_session(student, sno, date) -> SessionInput:
    # 混 push / pull / legs
    return _make(student, sno, date, [
        _set("BENCH_PRESS", 4, "8", 50.0),     # push 1600
        _set("BB_ROW", 4, "8", 50.0),          # pull 1600
        _set("BB_BACK_SQUAT", 4, "8", 70.0),   # legs 2240
    ])


class TestDetectImbalanceWarning(unittest.TestCase):
    def test_no_sessions_returns_none(self) -> None:
        cur = _push_only_session("林阿明", 1, "2026-05-10")
        self.assertIsNone(detect_imbalance_warning([], "林阿明", cur))

    def test_too_few_sessions_returns_none(self) -> None:
        # 只當堂,不足 3
        cur = _push_only_session("林阿明", 1, "2026-05-10")
        self.assertIsNone(detect_imbalance_warning([cur], "林阿明", cur))

    def test_balanced_training_no_warning(self) -> None:
        sessions = [_balanced_session("林阿明", i, f"2026-05-0{i}")
                    for i in range(1, 4)]
        result = detect_imbalance_warning(sessions, "林阿明", sessions[-1])
        self.assertIsNone(result)

    def test_push_heavy_triggers_warning(self) -> None:
        # 連續 3 堂全 push → 100% > 70% 閾值
        sessions = [_push_only_session("林阿明", i, f"2026-05-0{i}")
                    for i in range(1, 4)]
        result = detect_imbalance_warning(sessions, "林阿明", sessions[-1])
        self.assertIsNotNone(result)
        self.assertEqual(result.dominant_category, "push")
        self.assertGreaterEqual(result.dominant_pct, 0.7)

    def test_legs_heavy_suggests_other_categories(self) -> None:
        sessions = [
            _make("林阿明", i, f"2026-05-0{i}",
                  [_set("BB_BACK_SQUAT", 4, "10", 70.0)])
            for i in range(1, 4)
        ]
        result = detect_imbalance_warning(sessions, "林阿明", sessions[-1])
        self.assertEqual(result.dominant_category, "legs")
        self.assertIn("push", result.suggested_categories)

    def test_other_students_not_counted(self) -> None:
        # 王小華 全 push,林阿明 只 1 堂 push → 林阿明 不該觸發
        sessions = [
            _push_only_session("王小華", 1, "2026-05-08"),
            _push_only_session("王小華", 2, "2026-05-09"),
            _push_only_session("王小華", 3, "2026-05-10"),
            _push_only_session("林阿明", 1, "2026-05-10"),
        ]
        cur = _push_only_session("林阿明", 1, "2026-05-10")
        result = detect_imbalance_warning(sessions, "林阿明", cur)
        self.assertIsNone(result)

    def test_no_weighted_sets_returns_none(self) -> None:
        # 全 BW (tonnage 0) → 沒 category breakdown 可算
        sessions = [
            _make("林阿明", i, f"2026-05-0{i}",
                  [_set("PULL_UP", 4, "8", None)])
            for i in range(1, 4)
        ]
        result = detect_imbalance_warning(sessions, "林阿明", sessions[-1])
        self.assertIsNone(result)

    def test_returns_imbalance_warning_dataclass(self) -> None:
        sessions = [_push_only_session("林阿明", i, f"2026-05-0{i}")
                    for i in range(1, 4)]
        result = detect_imbalance_warning(sessions, "林阿明", sessions[-1])
        self.assertIsInstance(result, ImbalanceWarning)


class TestRenderImbalanceWarning(unittest.TestCase):
    def test_none_returns_empty(self) -> None:
        self.assertEqual(render_imbalance_warning(None), "")

    def test_warning_format(self) -> None:
        w = ImbalanceWarning(
            dominant_category="push",
            dominant_pct=0.85,
            suggested_categories=["pull", "legs"],
        )
        result = render_imbalance_warning(w)
        self.assertIn("⚠️", result)
        self.assertIn("失衡", result)
        self.assertIn("推系", result)  # CATEGORY_ZH push → 推系
        self.assertIn("85%", result)
        self.assertIn("拉系", result)  # suggested
        self.assertIn("腿系", result)  # suggested


class TestCliBatchProducesImbalanceBanner(unittest.TestCase):
    def test_push_heavy_batch_triggers_warning(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            base["student"]["name"] = "林阿明"
            for i in range(1, 4):
                p = json.loads(json.dumps(base))
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-0{i}"
                # 全 push only sets
                p["session"]["sets"] = [
                    {"exercise_code": "BENCH_PRESS", "sets": 4,
                     "reps_or_duration": "8", "weight_kg": 50.0,
                     "rpe": 7, "note": ""},
                    {"exercise_code": "OHP", "sets": 4,
                     "reps_or_duration": "8", "weight_kg": 30.0,
                     "rpe": 7, "note": ""},
                ]
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            s3_md = (Path(out_td) / "s3.md").read_text(encoding="utf-8")
            self.assertIn("⚠️", s3_md)
            self.assertIn("失衡", s3_md)


if __name__ == "__main__":
    unittest.main()
