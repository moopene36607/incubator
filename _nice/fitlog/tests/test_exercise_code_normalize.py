"""紅色測試 — parse_payload 正規化 exercise_code 為大寫.

lookup() 會自動 upper-case,所以小寫 'bench_press' 查得到 exercise_db。
但 SetRecord.exercise_code 存的是原始字串 — 若 PT 同一堂一個 set 寫
'BENCH_PRESS' 另一個寫 'bench_press',compute_total_tonnage 按 code 分組
時會把它們當兩個動作,排行 / PR / progression 全部分裂。

本輪:parse_payload 在建 SetRecord 時把 exercise_code 正規化成
strip().upper(),與 lookup 的行為一致。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import parse_payload  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _payload_with_codes(codes: list[str]) -> dict:
    p = json.loads(json.dumps(SAMPLE_PAYLOAD))
    p["session"]["sets"] = [
        {"exercise_code": c, "sets": 4, "reps_or_duration": "8",
         "weight_kg": 50.0, "rpe": 8}
        for c in codes
    ]
    return p


class TestExerciseCodeNormalization(unittest.TestCase):
    def test_lowercase_code_uppercased(self) -> None:
        session = parse_payload(_payload_with_codes(["bench_press"]))
        self.assertEqual(session.sets[0].exercise_code, "BENCH_PRESS")

    def test_mixed_case_code_uppercased(self) -> None:
        session = parse_payload(_payload_with_codes(["Bench_Press"]))
        self.assertEqual(session.sets[0].exercise_code, "BENCH_PRESS")

    def test_whitespace_stripped(self) -> None:
        session = parse_payload(_payload_with_codes(["  BENCH_PRESS  "]))
        self.assertEqual(session.sets[0].exercise_code, "BENCH_PRESS")

    def test_already_uppercase_unchanged(self) -> None:
        session = parse_payload(_payload_with_codes(["BB_BACK_SQUAT"]))
        self.assertEqual(session.sets[0].exercise_code, "BB_BACK_SQUAT")

    def test_mixed_case_same_exercise_not_split_in_tonnage(self) -> None:
        from metrics import compute_total_tonnage
        # 'bench_press' 與 'BENCH_PRESS' 同堂 → 正規化後是同一動作
        session = parse_payload(
            _payload_with_codes(["bench_press", "BENCH_PRESS"]))
        codes = {s.exercise_code for s in session.sets}
        self.assertEqual(codes, {"BENCH_PRESS"})
        # 兩 set 都正常計入 tonnage (4×8×50 ×2 = 3200)
        self.assertEqual(compute_total_tonnage(session.sets), 3200.0)

    def test_unknown_code_still_uppercased(self) -> None:
        # 未知代碼也正規化 (一致性 > 保留原樣)
        session = parse_payload(_payload_with_codes(["mystery_move"]))
        self.assertEqual(session.sets[0].exercise_code, "MYSTERY_MOVE")


if __name__ == "__main__":
    unittest.main()
