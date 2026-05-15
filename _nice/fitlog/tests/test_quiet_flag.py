"""紅色測試 — `--quiet` 旗標靜音 info / 進度訊息.

PT 把 fitlog 接進 cron / LINE bot pipeline 時,stderr 一堆「已寫入 X」
「info: ...」會洗 log。本輪加 --quiet:靜音 info 與「已寫入」進度訊息,
但 **warning: / error: 一定保留** (資料品質與除錯不能被吃掉)。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PAYLOAD = json.loads(
    (PROJECT_ROOT / "samples" / "sample_input.json").read_text(encoding="utf-8")
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "fitlog.py", *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )


class TestQuietSingleSession(unittest.TestCase):
    def test_without_quiet_prints_progress(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = _run([str(in_path), "--out", str(out_path), "--no-ai"],
                     Path(td))
            self.assertEqual(r.returncode, 0, r.stderr)
            # 預設會印「已寫入」進度
            self.assertIn("已寫入", r.stderr)

    def test_quiet_suppresses_progress(self) -> None:
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = _run([str(in_path), "--out", str(out_path), "--no-ai",
                      "--quiet"], Path(td))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("已寫入", r.stderr)

    def test_quiet_still_writes_output_file(self) -> None:
        # 靜音只是不印 log,檔案照常產
        with TemporaryDirectory() as td:
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = _run([str(in_path), "--out", str(out_path), "--no-ai",
                      "--quiet"], Path(td))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(out_path.exists())
            self.assertIn("課後訓練報告",
                          out_path.read_text(encoding="utf-8"))

    def test_quiet_keeps_warnings(self) -> None:
        # 餵一個重量超標的 JSON → warning 仍要印
        with TemporaryDirectory() as td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["session"]["sets"][0]["weight_kg"] = 999.0  # 超 500 kg
            in_path = Path(td) / "in.json"
            in_path.write_text(json.dumps(p, ensure_ascii=False),
                               encoding="utf-8")
            out_path = Path(td) / "out.md"
            r = _run([str(in_path), "--out", str(out_path), "--no-ai",
                      "--quiet"], Path(td))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("warning", r.stderr)

    def test_quiet_keeps_errors(self) -> None:
        # 不存在的 input → error 仍要印
        with TemporaryDirectory() as td:
            r = _run([str(Path(td) / "nope.json"), "--no-ai", "--quiet"],
                     Path(td))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("error", r.stderr)


class TestQuietBatch(unittest.TestCase):
    def test_batch_quiet_suppresses_progress(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["session"]["session_no"] = 1
            (Path(in_td) / "s1.json").write_text(
                json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = _run(["--batch", in_td, "--out-dir", out_td, "--no-ai",
                      "--quiet"], Path(in_td))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("已寫入", r.stderr)
            # 但檔案照產
            self.assertTrue((Path(out_td) / "_batch_summary.md").exists())

    def test_batch_without_quiet_prints_progress(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            p = json.loads(json.dumps(SAMPLE_PAYLOAD))
            p["session"]["session_no"] = 1
            (Path(in_td) / "s1.json").write_text(
                json.dumps(p, ensure_ascii=False), encoding="utf-8")
            r = _run(["--batch", in_td, "--out-dir", out_td, "--no-ai"],
                     Path(in_td))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("已寫入", r.stderr)


if __name__ == "__main__":
    unittest.main()
