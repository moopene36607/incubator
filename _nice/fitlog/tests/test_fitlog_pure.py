"""鎖 fitlog.py 主模組的純函式 contracts (parse_payload + 5 個 render_*).

過去 41 輪這些函式只有整合測試覆蓋。本輪加直接單元測試,鎖契約防止
未來重構破壞既有行為 (TDD safety net)。

測的是 *已存在* 的行為 — 不是新功能,所以紅階段就是「函式現在的行為
與 assertion 對齊」(若已對齊就直接綠;若不對齊,代表測試假設錯,需修)。
"""
from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import (  # noqa: E402
    SessionInput,
    SetRecord,
    parse_payload,
    render_full_report,
    render_line_friendly,
    render_session_table,
    render_skeleton_body,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None = 7, note: str = "") -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe, note=note)


def _make(student: str = "TestStudent", session_no: int = 1,
          sets: list[SetRecord] | None = None) -> SessionInput:
    return SessionInput(
        student_name=student, student_age=30, student_goal="goal",
        session_no=session_no, session_date="2026-05-13", duration_min=60,
        coach_name="Coach", studio_name="Studio", contact="contact",
        theme="主題", sets=sets or [],
        coach_observations=[], student_subjective=[],
        next_session={}, recovery_diet={},
    )


class TestParsePayload(unittest.TestCase):
    def test_basic_sample_parses(self) -> None:
        s = parse_payload(SAMPLE_PAYLOAD)
        self.assertEqual(s.student_name, "林阿明")
        self.assertEqual(s.session_no, 12)
        self.assertEqual(s.duration_min, 60)
        self.assertEqual(len(s.sets), 6)

    def test_sets_count_correct(self) -> None:
        s = parse_payload(SAMPLE_PAYLOAD)
        self.assertEqual(len(s.sets), len(SAMPLE_PAYLOAD["session"]["sets"]))

    def test_optional_age_can_be_missing(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"].pop("age", None)
        s = parse_payload(p)
        self.assertIsNone(s.student_age)

    def test_optional_targets_default_empty(self) -> None:
        p = deepcopy(SAMPLE_PAYLOAD)
        p["student"].pop("targets", None)
        s = parse_payload(p)
        self.assertEqual(s.student_targets, [])

    def test_set_weight_kg_string_converts_to_float(self) -> None:
        # parse_payload 接受 str→float 轉換 (與 schema 對齊)
        p = deepcopy(SAMPLE_PAYLOAD)
        p["session"]["sets"][1]["weight_kg"] = "70"
        s = parse_payload(p)
        self.assertEqual(s.sets[1].weight_kg, 70.0)

    def test_bw_set_weight_is_none(self) -> None:
        s = parse_payload(SAMPLE_PAYLOAD)
        # PULL_UP 是 BW (索引 4)
        self.assertIsNone(s.sets[4].weight_kg)


class TestRenderSessionTable(unittest.TestCase):
    def test_empty_sets_returns_header_only(self) -> None:
        sess = _make(sets=[])
        rows = render_session_table(sess)
        # 回傳 list of strings,至少有 header + separator
        self.assertGreaterEqual(len(rows), 2)
        self.assertIn("動作", rows[0])

    def test_single_weighted_set(self) -> None:
        sess = _make(sets=[_set("BENCH_PRESS", 4, "8", 50.0)])
        rows = render_session_table(sess)
        # header + separator + 1 data row = 3
        self.assertEqual(len(rows), 3)
        self.assertIn("槓鈴臥推", rows[2])
        self.assertIn("50.0 kg", rows[2])

    def test_bw_set_displays_bw(self) -> None:
        sess = _make(sets=[_set("PULL_UP", 4, "8", None)])
        rows = render_session_table(sess)
        self.assertIn("BW", rows[2])

    def test_unknown_exercise_code_falls_back(self) -> None:
        # exercise_db.lookup 找不到 → 顯示「代碼未知」hint
        sess = _make(sets=[_set("MADE_UP_CODE", 4, "8", 50.0)])
        rows = render_session_table(sess)
        self.assertIn("MADE_UP_CODE", rows[2])
        self.assertIn("代碼未知", rows[2])

    def test_no_rpe_shows_dash(self) -> None:
        sess = _make(sets=[_set("BENCH_PRESS", 4, "8", 50.0, rpe=None)])
        rows = render_session_table(sess)
        # RPE 欄該顯示 — 而非 None
        self.assertIn("—", rows[2])
        self.assertNotIn("None", rows[2])


class TestRenderSkeletonBody(unittest.TestCase):
    def test_contains_5_section_headers(self) -> None:
        body = render_skeleton_body()
        for header in ("一、今日訓練摘要", "二、本次主要進步",
                       "三、身體反應與觀察", "四、下次課程重點",
                       "五、本週恢復"):
            self.assertIn(header, body)

    def test_uses_h3_markdown(self) -> None:
        # 5 段都是 ### h3
        body = render_skeleton_body()
        self.assertGreaterEqual(body.count("### "), 5)

    def test_placeholders_explicitly_marked(self) -> None:
        # 含 "(待 AI 填" 字樣讓教練知道是 placeholder
        body = render_skeleton_body()
        self.assertIn("待 AI 填", body)


class TestRenderFullReport(unittest.TestCase):
    def setUp(self) -> None:
        self.session = parse_payload(SAMPLE_PAYLOAD)
        self.body = render_skeleton_body()

    def test_contains_h1_with_student_and_session_no(self) -> None:
        out = render_full_report(self.session, self.body)
        self.assertIn("# 林阿明", out)
        self.assertIn("第 12 堂", out)

    def test_contains_session_metadata(self) -> None:
        out = render_full_report(self.session, self.body)
        self.assertIn("2026-05-10", out)  # date
        self.assertIn("60 分鐘", out)     # duration
        self.assertIn("Day A", out)        # theme partial

    def test_contains_session_table(self) -> None:
        out = render_full_report(self.session, self.body)
        self.assertIn("| # | 動作", out)

    def test_contains_coach_signature_footer(self) -> None:
        out = render_full_report(self.session, self.body)
        self.assertIn("陳威廷", out)        # coach_name
        self.assertIn("F1 Fitness", out)    # studio_name

    def test_body_section_embedded(self) -> None:
        out = render_full_report(self.session, self.body)
        self.assertIn("一、今日訓練摘要", out)


class TestRenderLineFriendly(unittest.TestCase):
    def setUp(self) -> None:
        self.session = parse_payload(SAMPLE_PAYLOAD)
        self.body = render_skeleton_body()

    def test_starts_with_emoji_and_student_name(self) -> None:
        out = render_line_friendly(self.session, self.body)
        self.assertTrue(out.startswith("💪"))
        self.assertIn("林阿明", out)

    def test_contains_emoji_section_dividers(self) -> None:
        out = render_line_friendly(self.session, self.body)
        for emoji in ("📅", "📌", "📊"):
            self.assertIn(emoji, out)

    def test_strips_markdown_bold_syntax(self) -> None:
        # ** 不該出現在 LINE 純文字版
        out = render_line_friendly(self.session, self.body)
        # body 經過 .replace("**", "") 處理
        # 注意 ━ 線條本身不該帶 markdown 符號
        self.assertNotIn("**", out)


if __name__ == "__main__":
    unittest.main()
