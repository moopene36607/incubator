"""紅色測試 — validate_session 抓 PT 在 JSON 輸入常見的 typo / 不合理值.

PT 用 CLI 餵 JSON 時最容易出錯的:
- 重量 typo (50.0 → 500.0)
- 動作代碼拼錯 (BB_BACK_SQT)
- 組數忘填或填 0
- RPE 超出 1–10 範圍

這些錯誤如果直接給 LLM 寫報告,會產出「你今天臥推 500 kg 突破紀錄」這
種荒唐句子。validate_session 在進 LLM 前先抓出來,讓 PT 確認一次再送。
"""
from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import SetRecord, parse_payload  # noqa: E402
from validation import (  # noqa: E402
    MAX_REASONABLE_REPS,
    MAX_REASONABLE_SETS,
    MAX_REASONABLE_WEIGHT_KG,
    validate_session,
)


def _set(code: str, sets: int, reps: str, weight: float | None,
         rpe: int | None = 7) -> SetRecord:
    return SetRecord(exercise_code=code, sets=sets, reps_or_duration=reps,
                     weight_kg=weight, rpe=rpe)


def _load_sample():
    p = Path(__file__).resolve().parent.parent / "samples" / "sample_input.json"
    return parse_payload(json.loads(p.read_text(encoding="utf-8")))


class TestValidateSession(unittest.TestCase):
    def test_clean_sample_returns_no_warnings(self) -> None:
        # 真實 sample 必須是乾淨的 (沒有警告) — 不然 README 範例會誤導
        self.assertEqual(validate_session(_load_sample()), [])

    def test_empty_sets_warns(self) -> None:
        s = _load_sample()
        s.sets = []
        result = validate_session(s)
        self.assertEqual(len(result), 1)
        self.assertIn("沒有任何 set", result[0])

    def test_negative_weight_flagged(self) -> None:
        s = _load_sample()
        s.sets = [_set("BENCH_PRESS", 4, "8", -50.0)]
        result = validate_session(s)
        self.assertTrue(any("為負" in w for w in result), result)

    def test_extreme_weight_flagged_as_typo(self) -> None:
        # 500 kg+ 臥推不可能,大概率打錯小數點
        s = _load_sample()
        s.sets = [_set("BENCH_PRESS", 4, "8", 500.5)]
        result = validate_session(s)
        self.assertTrue(any("typo" in w for w in result), result)
        self.assertTrue(any(str(MAX_REASONABLE_WEIGHT_KG) in w for w in result), result)

    def test_zero_sets_count_flagged(self) -> None:
        s = _load_sample()
        s.sets = [_set("BENCH_PRESS", 0, "8", 50.0)]
        result = validate_session(s)
        self.assertTrue(any("組數" in w for w in result), result)

    def test_extreme_sets_count_flagged(self) -> None:
        # 30 組單一動作 → 大概率 typo
        s = _load_sample()
        s.sets = [_set("BENCH_PRESS", MAX_REASONABLE_SETS + 5, "8", 50.0)]
        result = validate_session(s)
        self.assertTrue(any("typo" in w for w in result), result)

    def test_extreme_reps_flagged(self) -> None:
        # 200 reps 一組 → 大概率 typo
        s = _load_sample()
        s.sets = [_set("BENCH_PRESS", 4, str(MAX_REASONABLE_REPS + 50), 50.0)]
        result = validate_session(s)
        self.assertTrue(any("次數" in w for w in result), result)

    def test_zero_reps_flagged_when_numeric(self) -> None:
        s = _load_sample()
        s.sets = [_set("BENCH_PRESS", 4, "0", 50.0)]
        result = validate_session(s)
        self.assertTrue(any("次數" in w for w in result), result)

    def test_unknown_exercise_code_warned(self) -> None:
        s = _load_sample()
        s.sets = [_set("BB_BACK_SQT_TYPO", 4, "10", 70.0)]
        result = validate_session(s)
        self.assertTrue(any("不在 exercise_db" in w for w in result), result)

    def test_invalid_rpe_flagged(self) -> None:
        s = _load_sample()
        s.sets = [_set("BENCH_PRESS", 4, "8", 50.0, rpe=15)]
        result = validate_session(s)
        self.assertTrue(any("RPE" in w for w in result), result)

    def test_zero_duration_flagged(self) -> None:
        s = _load_sample()
        s.duration_min = 0
        result = validate_session(s)
        self.assertTrue(any("時長" in w for w in result), result)

    def test_time_based_reps_not_flagged(self) -> None:
        # "60 sec" 不是 numeric → 跳過數值範圍檢查 (不該被警告)
        s = _load_sample()
        s.sets = [_set("PLANK", 3, "60 sec", None, rpe=6)]
        result = validate_session(s)
        # 不該有「次數」相關警告 (因為不是 rep-based)
        self.assertFalse(any("次數" in w for w in result), result)

    def test_bodyweight_set_not_flagged(self) -> None:
        # weight_kg=None 是合法 BW set,不該警告
        s = _load_sample()
        s.sets = [_set("PULL_UP", 4, "8", None, rpe=9)]
        result = validate_session(s)
        # 不該警告 weight (None 是合法 BW)
        self.assertFalse(any("重量" in w for w in result), result)

    def test_multiple_issues_all_reported(self) -> None:
        # 同時有 4 個問題,應該每個都被列出
        s = _load_sample()
        s.duration_min = -10
        s.sets = [
            _set("BB_BACK_SQT_TYPO", 4, "10", 70.0),  # 未知代碼
            _set("BENCH_PRESS", 0, "8", 50.0),         # 0 組
            _set("OHP", 4, "8", 999.0),                # 重量 typo
        ]
        result = validate_session(s)
        # 4 個獨立警告 (時長 + 未知代碼 + 0 組 + 重量 typo)
        self.assertGreaterEqual(len(result), 4, result)

    def test_validation_does_not_modify_session(self) -> None:
        s = _load_sample()
        snapshot = deepcopy(s)
        validate_session(s)
        self.assertEqual(s.duration_min, snapshot.duration_min)
        self.assertEqual(len(s.sets), len(snapshot.sets))

    def test_warnings_include_set_index_for_debuggability(self) -> None:
        # 教練看到「第 3 set: ...」才知道要修哪一筆,不是「set: ...」
        s = _load_sample()
        s.sets = [
            _set("BENCH_PRESS", 4, "8", 50.0),  # 正常
            _set("OHP", 4, "8", 50.0),          # 正常
            _set("BENCH_PRESS", 4, "8", 999.0), # 第 3 set 有問題
        ]
        result = validate_session(s)
        self.assertTrue(any("第 3" in w for w in result), result)


if __name__ == "__main__":
    unittest.main()
