"""紅色測試 — 語音/口述轉文字 → SetRecord parser (純規則,no LLM).

PT 上完課想立刻把訓練紀錄打成文字 (或未來接 Whisper 轉錄結果),手打
完整 JSON 太累。本模組接受結構化文字,每行一個 set,語法:

  <name> <sets>x<reps> <weight|BW> [RPE<n>] [#<note>]

範例:
  槓鈴背蹲舉 4x10 70kg RPE8 #深度突破
  Bench Press 4x8 50kg RPE8
  Pull-up 3x6 BW RPE9
  Plank 3x60sec BW

純規則 parser,不靠 LLM (LLM 整合留下輪)。未識別的 exercise 直接跳過,
不破壞整體解析。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice import build_session_skeleton, parse_voice_transcript  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestParseVoiceTranscript(unittest.TestCase):
    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(parse_voice_transcript(""), [])

    def test_blank_lines_ignored(self) -> None:
        self.assertEqual(parse_voice_transcript("\n\n   \n"), [])

    def test_single_chinese_line(self) -> None:
        result = parse_voice_transcript("槓鈴背蹲舉 4x10 70kg")
        self.assertEqual(len(result), 1)
        s = result[0]
        self.assertEqual(s.exercise_code, "BB_BACK_SQUAT")
        self.assertEqual(s.sets, 4)
        self.assertEqual(s.reps_or_duration, "10")
        self.assertEqual(s.weight_kg, 70.0)
        self.assertIsNone(s.rpe)

    def test_english_name_resolved(self) -> None:
        # 用 db 全名;短名 alias (e.g. "Bench Press") 因 Barbell/Dumbbell
        # 兩種版本衝突無法自動推測,留下輪做 alias 表
        result = parse_voice_transcript("Barbell Bench Press 4x8 50kg")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].exercise_code, "BENCH_PRESS")

    def test_english_name_case_insensitive(self) -> None:
        result = parse_voice_transcript("BARBELL BENCH PRESS 4x8 50kg")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].exercise_code, "BENCH_PRESS")

    def test_bw_marker_yields_none_weight(self) -> None:
        result = parse_voice_transcript("引體向上 3x6 BW")
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0].weight_kg)
        self.assertEqual(result[0].sets, 3)
        self.assertEqual(result[0].reps_or_duration, "6")

    def test_time_based_reps(self) -> None:
        result = parse_voice_transcript("棒式 3x60sec BW")
        self.assertEqual(len(result), 1)
        s = result[0]
        self.assertEqual(s.exercise_code, "PLANK")
        self.assertEqual(s.reps_or_duration, "60sec")
        self.assertIsNone(s.weight_kg)

    def test_rpe_extracted(self) -> None:
        result = parse_voice_transcript("槓鈴臥推 4x8 50kg RPE8")
        self.assertEqual(result[0].rpe, 8)

    def test_rpe_with_space(self) -> None:
        result = parse_voice_transcript("槓鈴臥推 4x8 50kg RPE 8")
        self.assertEqual(result[0].rpe, 8)

    def test_note_extracted(self) -> None:
        result = parse_voice_transcript("槓鈴臥推 4x8 50kg RPE8 #突破前次瓶頸")
        self.assertEqual(result[0].note, "突破前次瓶頸")

    def test_multiple_lines(self) -> None:
        text = """
        槓鈴背蹲舉 4x10 70kg RPE8
        槓鈴臥推 4x8 50kg RPE8
        引體向上 3x6 BW RPE9
        """
        result = parse_voice_transcript(text)
        self.assertEqual(len(result), 3)
        self.assertEqual([s.exercise_code for s in result],
                         ["BB_BACK_SQUAT", "BENCH_PRESS", "PULL_UP"])

    def test_unknown_exercise_skipped(self) -> None:
        # 不在 exercise_db 的名字 → 跳過,不破壞整體
        text = "未知動作XXX 3x10 50kg\n槓鈴臥推 4x8 50kg"
        result = parse_voice_transcript(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].exercise_code, "BENCH_PRESS")

    def test_x_separator_variants(self) -> None:
        # x / X / × 都接受
        for sep in ("x", "X", "×"):
            text = f"槓鈴臥推 4{sep}8 50kg"
            result = parse_voice_transcript(text)
            self.assertEqual(len(result), 1, sep)

    def test_decimal_weight(self) -> None:
        result = parse_voice_transcript("槓鈴臥推 4x8 47.5kg")
        self.assertEqual(result[0].weight_kg, 47.5)

    def test_chinese_unit_公斤(self) -> None:
        result = parse_voice_transcript("槓鈴臥推 4x8 50公斤")
        self.assertEqual(result[0].weight_kg, 50.0)

    def test_weight_without_unit(self) -> None:
        # "50" 也應該被當重量
        result = parse_voice_transcript("槓鈴臥推 4x8 50")
        self.assertEqual(result[0].weight_kg, 50.0)

    def test_longest_name_match_priority(self) -> None:
        # "槓鈴臥推" 不該被誤認為「臥推」之類的子字串 (本 db 沒有但測 invariant)
        # 用 BB_BACK_SQUAT 不該被誤認為其他短名
        result = parse_voice_transcript("槓鈴背蹲舉 4x10 70kg")
        self.assertEqual(result[0].exercise_code, "BB_BACK_SQUAT")


class TestBuildSessionSkeleton(unittest.TestCase):
    def test_skeleton_has_required_top_level_keys(self) -> None:
        from fitlog import SetRecord
        sets = [SetRecord(exercise_code="BENCH_PRESS", sets=4,
                          reps_or_duration="8", weight_kg=50.0, rpe=8)]
        result = build_session_skeleton(sets)
        for key in ("student", "coach", "session"):
            self.assertIn(key, result)

    def test_skeleton_includes_parsed_sets(self) -> None:
        from fitlog import SetRecord
        sets = [
            SetRecord(exercise_code="BENCH_PRESS", sets=4,
                      reps_or_duration="8", weight_kg=50.0, rpe=8),
            SetRecord(exercise_code="PULL_UP", sets=3,
                      reps_or_duration="6", weight_kg=None, rpe=9),
        ]
        skeleton = build_session_skeleton(sets)
        self.assertEqual(len(skeleton["session"]["sets"]), 2)
        self.assertEqual(skeleton["session"]["sets"][0]["exercise_code"], "BENCH_PRESS")
        self.assertEqual(skeleton["session"]["sets"][0]["weight_kg"], 50.0)
        self.assertEqual(skeleton["session"]["sets"][1]["weight_kg"], None)

    def test_skeleton_passes_schema_validation(self) -> None:
        # build_session_skeleton 出來的 dict 必須通過 schema 檢查
        from fitlog import SetRecord
        from schema import validate_payload_schema
        sets = [SetRecord(exercise_code="BENCH_PRESS", sets=4,
                          reps_or_duration="8", weight_kg=50.0, rpe=8)]
        skeleton = build_session_skeleton(sets)
        # name 是 placeholder 但須非空
        skeleton["student"]["name"] = "請填寫"
        skeleton["coach"]["name"] = "請填寫"
        skeleton["coach"]["studio_name"] = "請填寫"
        self.assertEqual(validate_payload_schema(skeleton), [])


class TestCliVoiceFlag(unittest.TestCase):
    def test_voice_flag_outputs_json_skeleton(self) -> None:
        with NamedTemporaryFile(suffix=".txt", mode="w", delete=False,
                                encoding="utf-8") as f:
            f.write("槓鈴背蹲舉 4x10 70kg RPE8\n槓鈴臥推 4x8 50kg RPE8\n")
            txt_path = f.name
        try:
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--voice", txt_path],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertEqual(len(payload["session"]["sets"]), 2)
            codes = [s["exercise_code"] for s in payload["session"]["sets"]]
            self.assertIn("BB_BACK_SQUAT", codes)
            self.assertIn("BENCH_PRESS", codes)
        finally:
            Path(txt_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
