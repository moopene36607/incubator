"""紅色測試 — `--batch-json` 批次層級結構化 JSON 匯總.

round 21 的 --out-json 只處理單堂。工作室經營者想把整批彙總接 dashboard
(每週工作室總量曲線、學員出席、動作排行),需要批次層級的結構化資料。
本輪加 build_batch_metrics_json(sessions) → dict + --batch-json 旗標
(與 --batch-csv / --batch-html 平行,寫 _batch.json)。

純函式組裝既有 aggregate 結果,no LLM。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggregate import build_batch_metrics_json  # noqa: E402
from fitlog import SessionInput, SetRecord  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _make(student: str, sno: int, date: str,
          weight: float = 50.0) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="",
        session_no=sno, session_date=date, duration_min=60,
        coach_name="C", studio_name="S", contact="",
        theme="t",
        sets=[SetRecord(exercise_code="BENCH_PRESS", sets=4,
                        reps_or_duration="8", weight_kg=weight, rpe=7)],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestBuildBatchMetricsJson(unittest.TestCase):
    def test_empty_sessions(self) -> None:
        result = build_batch_metrics_json([])
        self.assertEqual(result["n_sessions"], 0)
        self.assertEqual(result["n_students"], 0)
        json.dumps(result)  # serializable

    def test_json_serializable(self) -> None:
        result = build_batch_metrics_json([_make("林阿明", 1, "2026-05-11")])
        json.dumps(result)  # 不噴錯

    def test_session_and_student_counts(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-05-11"),
            _make("林阿明", 2, "2026-05-13"),
            _make("王小華", 1, "2026-05-12"),
        ]
        result = build_batch_metrics_json(sessions)
        self.assertEqual(result["n_sessions"], 3)
        self.assertEqual(result["n_students"], 2)

    def test_total_tonnage(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-05-11", 50.0),  # 4×8×50 = 1600
            _make("王小華", 1, "2026-05-12", 60.0),  # 4×8×60 = 1920
        ]
        result = build_batch_metrics_json(sessions)
        self.assertEqual(result["total_tonnage_kg"], 3520.0)

    def test_includes_students_session_counts(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-05-11"),
            _make("林阿明", 2, "2026-05-13"),
            _make("王小華", 1, "2026-05-12"),
        ]
        result = build_batch_metrics_json(sessions)
        self.assertEqual(result["students"]["林阿明"], 2)
        self.assertEqual(result["students"]["王小華"], 1)

    def test_includes_top_exercises(self) -> None:
        result = build_batch_metrics_json([_make("林阿明", 1, "2026-05-11")])
        top = result["top_exercises"]
        self.assertIsInstance(top, list)
        # BENCH_PRESS 應在內
        codes = [row[0] for row in top]
        self.assertIn("BENCH_PRESS", codes)

    def test_includes_studio_weekly(self) -> None:
        sessions = [
            _make("林阿明", 1, "2026-04-27"),  # W18
            _make("王小華", 1, "2026-05-04"),  # W19
        ]
        result = build_batch_metrics_json(sessions)
        weekly = result["studio_weekly"]
        self.assertEqual(len(weekly), 2)
        self.assertEqual(weekly[0]["week_start"], "2026-04-27")

    def test_includes_day_of_week(self) -> None:
        result = build_batch_metrics_json([_make("林阿明", 1, "2026-05-11")])
        dow = result["day_of_week"]
        # 2026-05-11 Monday → key "0" (json 化後 key 是字串) 或 0
        self.assertEqual(sum(dow.values()), 1)


class TestCliBatchJsonFlag(unittest.TestCase):
    def test_batch_json_flag_writes_batch_json(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            base = json.loads(json.dumps(SAMPLE_PAYLOAD))
            for i in range(1, 3):
                p = json.loads(json.dumps(base))
                p["student"]["name"] = f"Stu{i}"
                p["session"]["session_no"] = i
                p["session"]["date"] = f"2026-05-1{i}"
                (Path(in_td) / f"s{i}.json").write_text(
                    json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai", "--batch-json"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            json_path = Path(out_td) / "_batch.json"
            self.assertTrue(json_path.exists(),
                            f"_batch.json missing. stdout={r.stdout}")
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["n_sessions"], 2)
            self.assertIn("total_tonnage_kg", data)
            self.assertIn("studio_weekly", data)

    def test_no_batch_json_flag_no_file(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["session"]["session_no"] = 1
            (Path(in_td) / "s1.json").write_text(
                json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", in_td,
                 "--out-dir", out_td, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((Path(out_td) / "_batch.json").exists())


if __name__ == "__main__":
    unittest.main()
