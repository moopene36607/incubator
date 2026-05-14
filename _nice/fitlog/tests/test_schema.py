"""紅色測試 — JSON payload schema 結構驗證 (純函式).

PT 在 CLI 餵 JSON 時最差的 UX 是「漏一個欄位 → KeyError stack trace」。
本模組在進 parse_payload 前先檢查結構,給出 path-prefixed 人話錯誤
(例如 'session.sets[0].exercise_code: 缺失'),教練看了能直接修。

驗證 vs validate_session 分工:
- validate_payload_schema (本模組): 結構 / 型別 (KeyError 預防)
- validate_session: 業務合理性 (重量 typo / 動作代碼存在性 / RPE 範圍)
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema import validate_payload_schema  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


class TestValidatePayloadSchemaHappyPath(unittest.TestCase):
    def test_clean_sample_returns_no_errors(self) -> None:
        self.assertEqual(validate_payload_schema(SAMPLE_PAYLOAD), [])

    def test_clean_prev_sample_also_passes(self) -> None:
        prev = json.loads(
            (PROJECT_ROOT / "samples" / "sample_prev_input.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_payload_schema(prev), [])


class TestTopLevelStructure(unittest.TestCase):
    def test_non_dict_payload(self) -> None:
        result = validate_payload_schema([])  # type: ignore[arg-type]
        self.assertEqual(len(result), 1)
        self.assertIn("payload", result[0])

    def test_missing_student(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["student"]
        result = validate_payload_schema(p)
        self.assertTrue(any("student" in e and "缺失" in e for e in result), result)

    def test_missing_coach(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["coach"]
        result = validate_payload_schema(p)
        self.assertTrue(any("coach" in e and "缺失" in e for e in result), result)

    def test_missing_session(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session" in e and "缺失" in e for e in result), result)


class TestStudentSchema(unittest.TestCase):
    def test_missing_student_name(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["student"]["name"]
        result = validate_payload_schema(p)
        self.assertTrue(any("student.name" in e for e in result), result)

    def test_student_name_empty_string(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["name"] = ""
        result = validate_payload_schema(p)
        self.assertTrue(any("student.name" in e for e in result), result)

    def test_student_name_wrong_type(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"]["name"] = 123
        result = validate_payload_schema(p)
        self.assertTrue(any("student.name" in e for e in result), result)


class TestCoachSchema(unittest.TestCase):
    def test_missing_coach_name(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["coach"]["name"]
        result = validate_payload_schema(p)
        self.assertTrue(any("coach.name" in e for e in result), result)

    def test_missing_coach_studio_name(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["coach"]["studio_name"]
        result = validate_payload_schema(p)
        self.assertTrue(any("coach.studio_name" in e for e in result), result)


class TestSessionSchema(unittest.TestCase):
    def test_missing_session_no(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["session_no"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session.session_no" in e for e in result), result)

    def test_session_no_string_int_accepted(self) -> None:
        # int(...) 接 "12" 也能轉 → 應接受 (與 parse_payload 行為一致)
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["session_no"] = "12"
        self.assertEqual(validate_payload_schema(p), [])

    def test_session_no_non_numeric_string(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["session_no"] = "abc"
        result = validate_payload_schema(p)
        self.assertTrue(any("session_no" in e for e in result), result)

    def test_missing_duration_min(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["duration_min"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session.duration_min" in e for e in result), result)

    def test_missing_session_date(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["date"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session.date" in e for e in result), result)

    def test_missing_session_theme(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["theme"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session.theme" in e for e in result), result)


class TestSetsSchema(unittest.TestCase):
    def test_missing_sets_list(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["sets"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session.sets" in e for e in result), result)

    def test_sets_not_a_list(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["sets"] = "not a list"
        result = validate_payload_schema(p)
        self.assertTrue(any("session.sets" in e for e in result), result)

    def test_sets_empty_list_flagged(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["sets"] = []
        result = validate_payload_schema(p)
        self.assertTrue(any("session.sets" in e and "空" in e for e in result), result)

    def test_set_missing_exercise_code(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["sets"][0]["exercise_code"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session.sets[0].exercise_code" in e for e in result), result)

    def test_set_missing_sets_count(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["sets"][0]["sets"]
        result = validate_payload_schema(p)
        self.assertTrue(any("session.sets[0].sets" in e for e in result), result)

    def test_set_missing_reps_or_duration(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["session"]["sets"][0]["reps_or_duration"]
        result = validate_payload_schema(p)
        self.assertTrue(any("reps_or_duration" in e for e in result), result)

    def test_set_weight_kg_null_allowed(self) -> None:
        # weight_kg=None 是合法 BW set
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["sets"][0]["weight_kg"] = None
        self.assertEqual(validate_payload_schema(p), [])

    def test_set_weight_kg_string_non_numeric_flagged(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["sets"][0]["weight_kg"] = "重重的"
        result = validate_payload_schema(p)
        self.assertTrue(any("weight_kg" in e for e in result), result)

    def test_set_rpe_null_allowed(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["sets"][0]["rpe"] = None
        self.assertEqual(validate_payload_schema(p), [])


class TestMultipleErrorsAllReported(unittest.TestCase):
    def test_three_errors_all_in_output(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        del p["student"]
        del p["session"]["session_no"]
        p["session"]["sets"] = "broken"
        result = validate_payload_schema(p)
        self.assertGreaterEqual(len(result), 3, result)


class TestCliIntegration(unittest.TestCase):
    def test_invalid_json_exits_nonzero_with_error(self) -> None:
        # 缺 session 整個 → 應該 abort 而不是 KeyError stack trace
        bad = deepcopy(SAMPLE_PAYLOAD)
        del bad["session"]
        with NamedTemporaryFile(suffix=".json", mode="w", delete=False,
                                encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
            bad_path = f.name
        try:
            r = subprocess.run(
                [sys.executable, "fitlog.py", bad_path, "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("schema", r.stderr.lower())
            # 應沒有 Python stack trace 噴出
            self.assertNotIn("Traceback", r.stderr)
        finally:
            Path(bad_path).unlink(missing_ok=True)

    def test_batch_skips_invalid_json_continues_others(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            # 一個 valid, 一個 invalid (缺 student)
            (d / "good.json").write_text(
                json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False), encoding="utf-8")
            bad = deepcopy(SAMPLE_PAYLOAD)
            del bad["student"]
            (d / "bad.json").write_text(
                json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", str(d), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0)
            # good 應該被處理,bad 應該被跳過
            self.assertTrue((d / "good.md").exists())
            self.assertFalse((d / "bad.md").exists())


if __name__ == "__main__":
    unittest.main()
