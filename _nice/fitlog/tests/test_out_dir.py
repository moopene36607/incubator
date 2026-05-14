"""紅色測試 — --out-dir 旗標 (批次模式分離輸入/輸出).

目前批次模式把 .md 寫在輸入 .json 旁,實際 PT 工作流是:
- inputs/ 放當日課表 JSON
- reports/ 放產出的 markdown
- 不混在一起方便 .gitignore reports/

加 --out-dir DIR 後,所有報告 + _batch_summary.md 都寫到指定目錄,
原 inputs 目錄完全不被改。
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


def _seed_inputs(input_dir: Path, names: list[str]) -> None:
    """寫 N 份 session JSON 到 input_dir,各以對應 stem 命名 + 不同學員。"""
    for stem, name in zip(("aming", "wang", "chen"), names):
        payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
        payload["student"]["name"] = name
        (input_dir / f"{stem}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "fitlog.py", *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )


class TestBatchOutDir(unittest.TestCase):
    def test_out_dir_writes_to_specified_dir(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed_inputs(Path(in_td), ["林阿明", "王小華"])
            r = _run_cli("--batch", in_td, "--out-dir", out_td, "--no-ai")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(out_td) / "aming.md").exists())
            self.assertTrue((Path(out_td) / "wang.md").exists())

    def test_out_dir_does_not_pollute_input_dir(self) -> None:
        # 啟用 --out-dir 後,輸入目錄該保持只有原 .json (沒有任何新 .md)
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed_inputs(Path(in_td), ["林阿明", "王小華"])
            _run_cli("--batch", in_td, "--out-dir", out_td, "--no-ai")
            files = sorted(p.name for p in Path(in_td).iterdir())
            # 只有原本的 .json,不該出現 .md / _batch_summary.md
            self.assertEqual(files, ["aming.json", "wang.json"])

    def test_out_dir_writes_batch_summary(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as out_td:
            _seed_inputs(Path(in_td), ["林阿明", "王小華"])
            _run_cli("--batch", in_td, "--out-dir", out_td, "--no-ai")
            summary = Path(out_td) / "_batch_summary.md"
            self.assertTrue(summary.exists())
            content = summary.read_text(encoding="utf-8")
            self.assertIn("批次彙總", content)
            self.assertIn("林阿明", content)

    def test_out_dir_created_if_missing(self) -> None:
        with TemporaryDirectory() as in_td, TemporaryDirectory() as parent_td:
            _seed_inputs(Path(in_td), ["林阿明"])
            new_out = Path(parent_td) / "reports" / "today"
            self.assertFalse(new_out.exists())
            r = _run_cli("--batch", in_td, "--out-dir", str(new_out), "--no-ai")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(new_out.exists())
            self.assertTrue((new_out / "aming.md").exists())

    def test_without_out_dir_existing_behavior_unchanged(self) -> None:
        # 沒給 --out-dir → 報告寫原檔旁 (上輪契約不破)
        with TemporaryDirectory() as in_td:
            _seed_inputs(Path(in_td), ["林阿明", "王小華"])
            r = _run_cli("--batch", in_td, "--no-ai")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(in_td) / "aming.md").exists())
            self.assertTrue((Path(in_td) / "wang.md").exists())
            self.assertTrue((Path(in_td) / "_batch_summary.md").exists())


if __name__ == "__main__":
    unittest.main()
