"""紅色測試 — 多學員批次模式 (--batch DIR/).

PT 一天上 6-8 節 1 對 1 課,每節結束後要寫課後紀錄。如果還要 shell loop
跑 8 次 CLI,根本沒救到時間。--batch 一次跑整個目錄,把每個 student.json
產出對應的 student.md 報告寫在原檔旁。

純函式 discover_session_jsons 處理路徑掃描;CLI --batch 旗標串起整體流程。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batch import discover_session_jsons  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_sample_payload() -> dict:
    p = PROJECT_ROOT / "samples" / "sample_input.json"
    return json.loads(p.read_text(encoding="utf-8"))


class TestDiscoverSessionJsons(unittest.TestCase):
    def test_empty_directory_returns_empty(self) -> None:
        with TemporaryDirectory() as td:
            self.assertEqual(discover_session_jsons(Path(td)), [])

    def test_returns_only_json_files(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.json").write_text("{}", encoding="utf-8")
            (d / "b.json").write_text("{}", encoding="utf-8")
            (d / "readme.txt").write_text("notes", encoding="utf-8")
            result = discover_session_jsons(d)
            self.assertEqual([p.name for p in result], ["a.json", "b.json"])

    def test_results_are_sorted(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            for name in ["zeta.json", "alpha.json", "mike.json"]:
                (d / name).write_text("{}", encoding="utf-8")
            result = discover_session_jsons(d)
            self.assertEqual([p.name for p in result],
                             ["alpha.json", "mike.json", "zeta.json"])

    def test_nonexistent_directory_returns_empty(self) -> None:
        # 不該炸,讓 caller 自己決定要不要警告
        self.assertEqual(discover_session_jsons(Path("/no/such/path/xyz")), [])

    def test_skips_subdirectories(self) -> None:
        # batch 是 flat (一層),不遞迴掃子目錄
        with TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.json").write_text("{}", encoding="utf-8")
            sub = d / "subdir"
            sub.mkdir()
            (sub / "b.json").write_text("{}", encoding="utf-8")
            result = discover_session_jsons(d)
            self.assertEqual([p.name for p in result], ["a.json"])

    def test_results_are_path_objects(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.json").write_text("{}", encoding="utf-8")
            result = discover_session_jsons(d)
            self.assertIsInstance(result[0], Path)


class TestCliBatch(unittest.TestCase):
    def test_batch_produces_one_md_per_input(self) -> None:
        with TemporaryDirectory() as td:
            batch_dir = Path(td)
            # 寫 2 份 session JSON (改學員姓名以區別)
            base = _read_sample_payload()
            for i, name in enumerate(("aming", "bwen"), 1):
                payload = json.loads(json.dumps(base))  # deep copy
                payload["student"]["name"] = f"學員_{name}"
                payload["session"]["session_no"] = i
                (batch_dir / f"{name}.json").write_text(
                    json.dumps(payload, ensure_ascii=False),
                    encoding="utf-8",
                )
            result = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", str(batch_dir), "--no-ai"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            # 應該產生 aming.md 與 bwen.md
            self.assertTrue((batch_dir / "aming.md").exists())
            self.assertTrue((batch_dir / "bwen.md").exists())
            # 內容含正確學員名
            self.assertIn("學員_aming", (batch_dir / "aming.md").read_text(encoding="utf-8"))
            self.assertIn("學員_bwen", (batch_dir / "bwen.md").read_text(encoding="utf-8"))

    def test_batch_empty_dir_succeeds_with_warning(self) -> None:
        with TemporaryDirectory() as td:
            result = subprocess.run(
                [sys.executable, "fitlog.py", "--batch", str(td), "--no-ai"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            # stderr 該有警告告知沒檔案
            self.assertIn("找不到", result.stderr)

    def test_batch_does_not_overwrite_input_jsons(self) -> None:
        # 寫出去的 .md 不能蓋掉輸入 .json
        with TemporaryDirectory() as td:
            batch_dir = Path(td)
            base = _read_sample_payload()
            (batch_dir / "session1.json").write_text(
                json.dumps(base, ensure_ascii=False),
                encoding="utf-8",
            )
            content_before = (batch_dir / "session1.json").read_text(encoding="utf-8")
            subprocess.run(
                [sys.executable, "fitlog.py", "--batch", str(batch_dir), "--no-ai"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(content_before, (batch_dir / "session1.json").read_text(encoding="utf-8"))

    def test_no_input_or_batch_returns_error(self) -> None:
        # 既沒給 input 也沒給 --batch → 應該錯誤退出
        result = subprocess.run(
            [sys.executable, "fitlog.py"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
