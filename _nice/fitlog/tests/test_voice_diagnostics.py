"""紅色測試 — voice parser 無法辨識動作警示.

parse_voice_transcript 對「未識別 exercise」的行靜默跳過 — 設計上是為了
讓閒話混在裡面。但若某行明明有「組數×次數」訊號 (4x10 / 3組8下),卻
因 exercise 名字打錯 / 不在 db 而被丟掉,那是真的資料遺失,不是閒話。

本輪加 diagnose_voice_lines(text):回傳「看起來是 set 但動作沒被認出」
的行 (行號 + 內容)。CLI --voice 會把這些印到 stderr 提醒 PT。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice import diagnose_voice_lines  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDiagnoseVoiceLines(unittest.TestCase):
    def test_empty_text_no_warnings(self) -> None:
        self.assertEqual(diagnose_voice_lines(""), [])

    def test_clean_recognized_lines_no_warnings(self) -> None:
        text = "槓鈴臥推 4x8 50kg\n肩推 3組10下 30kg"
        self.assertEqual(diagnose_voice_lines(text), [])

    def test_chatter_line_not_flagged(self) -> None:
        # 純閒話 (沒組數×次數訊號) → 不該被當失敗 set
        text = "今天學員狀況不錯\n槓鈴臥推 4x8 50kg"
        self.assertEqual(diagnose_voice_lines(text), [])

    def test_unknown_exercise_with_sets_reps_flagged(self) -> None:
        # 「火箭推」不在 db,但有 4x10 → 疑似打錯/未知動作
        text = "火箭推 4x10 70kg"
        result = diagnose_voice_lines(text)
        self.assertEqual(len(result), 1)
        lineno, content = result[0]
        self.assertEqual(lineno, 1)
        self.assertIn("火箭推", content)

    def test_unknown_exercise_chinese_notation_flagged(self) -> None:
        text = "神秘動作 3組12下 40kg"
        result = diagnose_voice_lines(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 1)

    def test_line_number_is_one_based_and_correct(self) -> None:
        text = "槓鈴臥推 4x8 50kg\n\n亂寫動作 5x5 60kg\n肩推 3x10 30kg"
        result = diagnose_voice_lines(text)
        self.assertEqual(len(result), 1)
        # 「亂寫動作」在第 3 行
        self.assertEqual(result[0][0], 3)

    def test_known_exercise_no_sets_not_flagged(self) -> None:
        # 認得動作但沒組數 → 不是「失敗 set」,只是資訊不全,不在本警示範圍
        text = "槓鈴臥推 今天感覺不錯"
        self.assertEqual(diagnose_voice_lines(text), [])

    def test_multiple_unknown_lines(self) -> None:
        text = "動作A 4x10 50kg\n動作B 3組8下 40kg"
        result = diagnose_voice_lines(text)
        self.assertEqual(len(result), 2)


class TestCliVoiceDiagnostics(unittest.TestCase):
    def test_voice_cli_warns_unrecognized_line(self) -> None:
        with TemporaryDirectory() as td:
            txt = Path(td) / "transcript.txt"
            txt.write_text(
                "槓鈴臥推 4x8 50kg\n火箭推進器 5x5 80kg\n",
                encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "fitlog.py", "--voice", str(txt)],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            # stderr 應提醒未辨識的行
            self.assertIn("火箭推進器", r.stderr)
            # stdout 仍是合法 JSON skeleton (含認得的那筆)
            skeleton = json.loads(r.stdout)
            self.assertIn("session", skeleton)


if __name__ == "__main__":
    unittest.main()
