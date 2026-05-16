"""紅色測試 — 預生成 examples/ 必須含近期新功能段落.

專案規範:demo 不依賴 ANTHROPIC_API_KEY,reviewer 直接看 examples/。
但 examples/ 已落後 20+ 輪 — 缺 streak / 最常練 / 動作多樣性 / 強度分數 /
工作室週訓練量 / 開課日分布 等。本輪重新生成 examples 並用此測試鎖住:
往後新增報表段落時,examples 不同步就會 RED。

注意:examples 是用 --no-ai 重生 (骨架版),所以只檢查純函式段落,
不檢查 AI 散文。
"""
from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIMELINE = PROJECT_ROOT / "examples" / "timeline_demo"
BATCH = PROJECT_ROOT / "examples" / "batch_demo"


class TestTimelineStudentTrendFresh(unittest.TestCase):
    """timeline_demo 的 _student_林阿明.md (4 堂連續) 應含新趨勢段落。"""

    def setUp(self) -> None:
        self.content = (TIMELINE / "_student_林阿明.md").read_text(
            encoding="utf-8"
        )

    def test_has_training_streak(self) -> None:
        self.assertIn("連續訓練", self.content)

    def test_has_favorite_exercise(self) -> None:
        self.assertIn("最常練", self.content)

    def test_has_exercise_variety(self) -> None:
        self.assertIn("動作多樣性", self.content)

    def test_has_intensity_progression(self) -> None:
        self.assertIn("訓練強度分數趨勢", self.content)


class TestTimelineSessionReportFresh(unittest.TestCase):
    """個別 session .md 應含 RPE 強度分布 + 訓練強度分數。"""

    def test_session_has_rpe_zone(self) -> None:
        content = (TIMELINE / "s01_aming.md").read_text(encoding="utf-8")
        self.assertIn("強度分布", content)

    def test_session_has_intensity_score(self) -> None:
        content = (TIMELINE / "s01_aming.md").read_text(encoding="utf-8")
        self.assertIn("訓練強度分數", content)


class TestTimelineShowsBodyweightFeatures(unittest.TestCase):
    """timeline_demo 應展示 round 49-51 的體重 / 相對肌力 / 里程碑功能。"""

    def test_session_shows_relative_strength(self) -> None:
        content = (TIMELINE / "s01_aming.md").read_text(encoding="utf-8")
        self.assertIn("相對肌力", content)

    def test_student_trend_shows_bodyweight_trend(self) -> None:
        content = (TIMELINE / "_student_林阿明.md").read_text(encoding="utf-8")
        self.assertIn("體重趨勢", content)


class TestVoiceExampleShowsChineseNotation(unittest.TestCase):
    """voice_transcript.txt 應展示中文「組/下/次」記法 (round 29/31)。"""

    def test_transcript_uses_chinese_notation(self) -> None:
        txt = (PROJECT_ROOT / "examples" / "voice_transcript.txt").read_text(
            encoding="utf-8")
        self.assertIn("組", txt)

    def test_skeleton_parses_all_lines(self) -> None:
        # voice_skeleton.json 應與 transcript 的可解析行數一致
        import json as _json
        from voice import parse_voice_transcript
        txt = (PROJECT_ROOT / "examples" / "voice_transcript.txt").read_text(
            encoding="utf-8")
        skeleton = _json.loads(
            (PROJECT_ROOT / "examples" / "voice_skeleton.json").read_text(
                encoding="utf-8"))
        parsed = parse_voice_transcript(txt)
        self.assertEqual(len(parsed), len(skeleton["session"]["sets"]))


class TestTimelineHasLineReport(unittest.TestCase):
    """timeline_demo 應含 --batch-line 產出的 LINE 純文字報告範例。"""

    def test_line_txt_exists(self) -> None:
        line_files = list(TIMELINE.glob("*.line.txt"))
        self.assertTrue(line_files, "timeline_demo 缺 .line.txt LINE 報告範例")

    def test_line_report_has_line_format(self) -> None:
        line_files = sorted(TIMELINE.glob("*.line.txt"))
        content = line_files[0].read_text(encoding="utf-8")
        self.assertIn("課後報告", content)
        self.assertIn("━", content)
        self.assertNotIn("**", content)  # LINE 版去 markdown 粗體


class TestBatchSummaryFresh(unittest.TestCase):
    """_batch_summary.md 應含開課日分布 + 工作室週訓練量。"""

    def setUp(self) -> None:
        self.content = (TIMELINE / "_batch_summary.md").read_text(
            encoding="utf-8"
        )

    def test_has_day_of_week(self) -> None:
        self.assertIn("開課日分布", self.content)

    def test_has_studio_weekly(self) -> None:
        self.assertIn("工作室週訓練量", self.content)


if __name__ == "__main__":
    unittest.main()
