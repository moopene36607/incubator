"""紅色測試 — validate_session 偵測未來日期 (年份 typo 預防).

PT 在手打 JSON 時,把 2026-05-15 typo 成 2027-05-15 是常見錯誤
(年份輸入錯一鍵)。整批跑下去這堂課會被歸到「未來」週,污染 weekly
tonnage / streak / sparkline 排序。本輪在 validate_session 新增可選的
today_iso 參數,session.session_date > today_iso 時 warn。

純函式;today_iso=None 時不檢查 (向後相容),CLI 在 boundary 注入今日日期。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SessionInput, SetRecord  # noqa: E402
from validation import validate_session  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _session(date_str: str) -> SessionInput:
    return SessionInput(
        student_name="林阿明", student_age=30, student_goal="",
        session_no=1, session_date=date_str, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=1,
                        reps_or_duration="8", weight_kg=50.0, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestFutureDateValidation(unittest.TestCase):
    def test_today_iso_none_skips_check_backward_compat(self) -> None:
        # 未來日期但 today_iso=None → 不警告 (向後相容)
        sess = _session("2030-01-01")
        warns = validate_session(sess)
        future_warns = [w for w in warns if "未來" in w]
        self.assertEqual(future_warns, [])

    def test_past_date_no_warning(self) -> None:
        sess = _session("2026-04-15")
        warns = validate_session(sess, today_iso="2026-05-15")
        future_warns = [w for w in warns if "未來" in w]
        self.assertEqual(future_warns, [])

    def test_today_no_warning(self) -> None:
        sess = _session("2026-05-15")
        warns = validate_session(sess, today_iso="2026-05-15")
        future_warns = [w for w in warns if "未來" in w]
        self.assertEqual(future_warns, [])

    def test_future_date_warns(self) -> None:
        sess = _session("2027-05-15")  # 年份 typo
        warns = validate_session(sess, today_iso="2026-05-15")
        future_warns = [w for w in warns if "未來" in w]
        self.assertEqual(len(future_warns), 1)
        self.assertIn("2027-05-15", future_warns[0])

    def test_one_day_in_future_warns(self) -> None:
        sess = _session("2026-05-16")
        warns = validate_session(sess, today_iso="2026-05-15")
        future_warns = [w for w in warns if "未來" in w]
        self.assertEqual(len(future_warns), 1)

    def test_future_warning_doesnt_block_other_warnings(self) -> None:
        # 未來 + 重量超標,兩個 warn 都該觸發
        sess = SessionInput(
            student_name="林阿明", student_age=30, student_goal="",
            session_no=1, session_date="2027-05-15", duration_min=60,
            coach_name="C", studio_name="S", contact="",
            theme="t",
            sets=[SetRecord(exercise_code="BENCH_PRESS", sets=1,
                            reps_or_duration="8", weight_kg=900.0, rpe=7)],
            coach_observations=[], student_subjective=[],
            next_session={}, recovery_diet={},
        )
        warns = validate_session(sess, today_iso="2026-05-15")
        self.assertTrue(any("未來" in w for w in warns))
        self.assertTrue(any("typo" in w or "超過" in w for w in warns))


class TestCliEmitsFutureWarning(unittest.TestCase):
    def test_single_session_future_date_logs_warning_to_stderr(self) -> None:
        with TemporaryDirectory() as td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            # 把 session date 改成明顯未來
            from datetime import date, timedelta
            future = (date.today() + timedelta(days=365)).isoformat()
            p["session"]["date"] = future
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(p, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = subprocess.run(
                [sys.executable, "fitlog.py", str(in_path),
                 "--out", str(out_path), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            # 不該 fail,只是 warn
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("未來", r.stderr)


if __name__ == "__main__":
    unittest.main()
