"""紅色測試 — exercise lookup / 正規化容忍連字號.

exercise_db 的 code 一律用底線 (T_BAR_ROW)。但 PT 手打或 Whisper 轉錄
可能寫成連字號 (T-BAR-ROW) — 連字號與底線在英文鍵入上常混用。
本輪讓 lookup 與 parse_payload 把 '-' 視同 '_'。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercise_db import lookup  # noqa: E402
from fitlog import parse_payload  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


class TestLookupHyphenTolerance(unittest.TestCase):
    def test_hyphen_code_resolves(self) -> None:
        ex = lookup("T-BAR-ROW")
        self.assertIsNotNone(ex)
        self.assertEqual(ex.code, "T_BAR_ROW")

    def test_lowercase_hyphen_resolves(self) -> None:
        ex = lookup("bb-back-squat")
        self.assertIsNotNone(ex)
        self.assertEqual(ex.code, "BB_BACK_SQUAT")

    def test_underscore_still_works(self) -> None:
        self.assertIsNotNone(lookup("T_BAR_ROW"))
        self.assertIsNotNone(lookup("BB_BACK_SQUAT"))

    def test_genuinely_unknown_still_none(self) -> None:
        self.assertIsNone(lookup("not-a-real-move"))


class TestParsePayloadHyphenNormalize(unittest.TestCase):
    def _payload(self, code: str) -> dict:
        p = json.loads(json.dumps(SAMPLE_PAYLOAD))
        p["session"]["sets"] = [
            {"exercise_code": code, "sets": 4, "reps_or_duration": "8",
             "weight_kg": 50.0, "rpe": 8}
        ]
        return p

    def test_hyphen_code_normalized_to_underscore(self) -> None:
        session = parse_payload(self._payload("T-BAR-ROW"))
        self.assertEqual(session.sets[0].exercise_code, "T_BAR_ROW")

    def test_mixed_hyphen_lowercase(self) -> None:
        session = parse_payload(self._payload("bb-back-squat"))
        self.assertEqual(session.sets[0].exercise_code, "BB_BACK_SQUAT")


if __name__ == "__main__":
    unittest.main()
