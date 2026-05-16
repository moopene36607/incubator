"""紅色測試 — voice parser 也辨識 exercise code.

voice parser 目前只認中文名 (槓鈴臥推) 與英文全名 (Barbell Bench Press)。
但若轉錄文字 / PT 手打直接用代碼 (BENCH_PRESS),目前會被當未識別跳過。
本輪讓 _NAME_INDEX 也收 code,代碼也能解析。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice import parse_voice_transcript, diagnose_voice_lines  # noqa: E402


class TestVoiceCodeMatch(unittest.TestCase):
    def test_uppercase_code_resolves(self) -> None:
        sets = parse_voice_transcript("BENCH_PRESS 4x8 50kg RPE8")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].exercise_code, "BENCH_PRESS")
        self.assertEqual(sets[0].sets, 4)
        self.assertEqual(sets[0].weight_kg, 50.0)

    def test_lowercase_code_resolves(self) -> None:
        sets = parse_voice_transcript("bb_back_squat 4x10 70kg")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].exercise_code, "BB_BACK_SQUAT")

    def test_code_with_chinese_notation(self) -> None:
        sets = parse_voice_transcript("PULL_UP 3組8下 BW")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].exercise_code, "PULL_UP")
        self.assertEqual(sets[0].sets, 3)

    def test_chinese_name_still_works(self) -> None:
        sets = parse_voice_transcript("槓鈴臥推 4x8 50kg")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].exercise_code, "BENCH_PRESS")

    def test_code_line_not_flagged_as_unrecognized(self) -> None:
        # diagnose 不該把合法 code 行當未識別
        problems = diagnose_voice_lines("BENCH_PRESS 4x8 50kg")
        self.assertEqual(problems, [])

    def test_mixed_code_and_name_lines(self) -> None:
        text = "BENCH_PRESS 4x8 50kg\n槓鈴背蹲舉 4x10 70kg"
        sets = parse_voice_transcript(text)
        self.assertEqual(len(sets), 2)
        self.assertEqual(sets[0].exercise_code, "BENCH_PRESS")
        self.assertEqual(sets[1].exercise_code, "BB_BACK_SQUAT")


if __name__ == "__main__":
    unittest.main()
