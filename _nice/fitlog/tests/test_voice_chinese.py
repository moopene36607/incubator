"""紅色測試 — voice parser 支援中文「組/下/次/秒/分」記法.

現有 parser 只認 `4x10` 這種書寫式記法。但 PT 用語音口述 (未來接 Whisper
轉錄中文 Mandarin) 會講出「槓鈴背蹲舉 四組十下」→ 轉錄成「4組10下」。
本輪讓 parser 也吃中文量詞:

  N組M下 / N組M次  → sets=N, reps=M
  N組M秒           → reps_or_duration="Msec"
  N組M分           → reps_or_duration="Mmin"

書寫式 `NxM` 仍照舊運作 (向後相容)。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice import parse_voice_transcript  # noqa: E402


class TestChineseSetsReps(unittest.TestCase):
    def test_zu_xia_notation(self) -> None:
        # 「4組10下」→ sets=4, reps=10
        sets = parse_voice_transcript("槓鈴背蹲舉 4組10下 70kg RPE8")
        self.assertEqual(len(sets), 1)
        s = sets[0]
        self.assertEqual(s.exercise_code, "BB_BACK_SQUAT")
        self.assertEqual(s.sets, 4)
        self.assertEqual(s.reps_or_duration, "10")
        self.assertEqual(s.weight_kg, 70.0)
        self.assertEqual(s.rpe, 8)

    def test_zu_ci_notation(self) -> None:
        # 「3組8次」→ sets=3, reps=8
        sets = parse_voice_transcript("槓鈴臥推 3組8次 50kg")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].sets, 3)
        self.assertEqual(sets[0].reps_or_duration, "8")

    def test_zu_with_spaces(self) -> None:
        # 「4 組 10 下」中間有空白也要吃
        sets = parse_voice_transcript("槓鈴臥推 4 組 10 下 50kg")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].sets, 4)
        self.assertEqual(sets[0].reps_or_duration, "10")

    def test_zu_miao_duration(self) -> None:
        # 「3組60秒」→ reps_or_duration = "60sec"
        sets = parse_voice_transcript("棒式 3組60秒 BW")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].exercise_code, "PLANK")
        self.assertEqual(sets[0].sets, 3)
        self.assertEqual(sets[0].reps_or_duration, "60sec")

    def test_zu_fen_duration(self) -> None:
        # 「1組20分」→ "20min"
        sets = parse_voice_transcript("跑步機 1組20分 BW")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].reps_or_duration, "20min")

    def test_chinese_weight_gongjin(self) -> None:
        # 公斤 後綴 + 中文組下
        sets = parse_voice_transcript("肩推 4組8下 30公斤 RPE7")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].weight_kg, 30.0)
        self.assertEqual(sets[0].rpe, 7)


class TestBackwardCompatXNotation(unittest.TestCase):
    """書寫式 NxM 不可退化。"""

    def test_x_notation_still_works(self) -> None:
        sets = parse_voice_transcript("槓鈴背蹲舉 4x10 70kg RPE8")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].sets, 4)
        self.assertEqual(sets[0].reps_or_duration, "10")

    def test_x_notation_duration(self) -> None:
        sets = parse_voice_transcript("棒式 3x60sec BW")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].reps_or_duration, "60sec")

    def test_mixed_lines(self) -> None:
        # 同一份 transcript 混用兩種記法
        text = "槓鈴臥推 4x8 50kg\n肩推 3組10下 30kg"
        sets = parse_voice_transcript(text)
        self.assertEqual(len(sets), 2)
        self.assertEqual(sets[0].reps_or_duration, "8")
        self.assertEqual(sets[1].reps_or_duration, "10")
        self.assertEqual(sets[1].sets, 3)


if __name__ == "__main__":
    unittest.main()
