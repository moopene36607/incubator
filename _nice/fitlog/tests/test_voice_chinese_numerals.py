"""紅色測試 — voice parser 支援中文數字 (零一二三...十百兩).

round 29 加了中文量詞 (組/下/次),但數字還只認阿拉伯。Whisper 轉錄中文
口述時小數字常出中文字:「槓鈴背蹲舉 四組十下 七十公斤 RPE八」。
本輪讓 parser 把中文數字轉成阿拉伯後再解析。

關鍵 edge case:「三頭下壓」這個 exercise 名字含「三」,中文數字轉換
必須在 exercise name 抽出**之後**才做,否則名字會被破壞。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice import parse_voice_transcript  # noqa: E402


class TestChineseNumerals(unittest.TestCase):
    def test_full_chinese_line(self) -> None:
        sets = parse_voice_transcript("槓鈴背蹲舉 四組十下 七十公斤 RPE八")
        self.assertEqual(len(sets), 1)
        s = sets[0]
        self.assertEqual(s.exercise_code, "BB_BACK_SQUAT")
        self.assertEqual(s.sets, 4)
        self.assertEqual(s.reps_or_duration, "10")
        self.assertEqual(s.weight_kg, 70.0)
        self.assertEqual(s.rpe, 8)

    def test_chinese_ci_notation(self) -> None:
        sets = parse_voice_transcript("槓鈴臥推 三組八次 五十公斤")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].sets, 3)
        self.assertEqual(sets[0].reps_or_duration, "8")
        self.assertEqual(sets[0].weight_kg, 50.0)

    def test_chinese_duration(self) -> None:
        sets = parse_voice_transcript("棒式 三組六十秒 BW")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].reps_or_duration, "60sec")

    def test_compound_numeral_over_twenty(self) -> None:
        # 二十五下 → 25
        sets = parse_voice_transcript("啞鈴側平舉 三組二十五下 八公斤")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].reps_or_duration, "25")
        self.assertEqual(sets[0].weight_kg, 8.0)

    def test_hundred_weight(self) -> None:
        # 一百二十公斤 → 120
        sets = parse_voice_transcript("傳統硬舉 三組五下 一百二十公斤")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].weight_kg, 120.0)

    def test_exercise_name_with_numeral_not_corrupted(self) -> None:
        # 「三頭下壓」名字含「三」— 不可被數字轉換破壞
        sets = parse_voice_transcript("三頭下壓 三組十二下 二十公斤")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].exercise_code, "TRICEP_PUSHDOWN")
        self.assertEqual(sets[0].sets, 3)
        self.assertEqual(sets[0].reps_or_duration, "12")
        self.assertEqual(sets[0].weight_kg, 20.0)

    def test_liang_colloquial_two(self) -> None:
        # 「兩組」口語 = 2 組
        sets = parse_voice_transcript("肩推 兩組十下 三十公斤")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].sets, 2)


class TestArabicStillWorks(unittest.TestCase):
    """阿拉伯數字 + 既有記法不可退化。"""

    def test_arabic_x_notation(self) -> None:
        sets = parse_voice_transcript("槓鈴臥推 4x8 50kg RPE8")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].sets, 4)
        self.assertEqual(sets[0].reps_or_duration, "8")
        self.assertEqual(sets[0].weight_kg, 50.0)

    def test_arabic_zh_quantifier(self) -> None:
        sets = parse_voice_transcript("肩推 3組10下 30kg")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].sets, 3)

    def test_mixed_arabic_and_chinese_lines(self) -> None:
        text = "槓鈴臥推 4x8 50kg\n肩推 三組十下 三十公斤"
        sets = parse_voice_transcript(text)
        self.assertEqual(len(sets), 2)
        self.assertEqual(sets[0].sets, 4)
        self.assertEqual(sets[1].sets, 3)
        self.assertEqual(sets[1].weight_kg, 30.0)


if __name__ == "__main__":
    unittest.main()
