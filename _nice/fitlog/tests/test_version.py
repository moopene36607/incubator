"""紅色測試 — `--version` flag.

成熟 CLI 工具標配。PT 跑出問題時 support 第一句:「你裝的是哪個版本?」
本輪加 `__version__` 常數 + argparse 自帶 --version action,
`python fitlog.py --version` 印版本字串並退出 0。

不依賴 setuptools / pyproject.toml metadata (此原型沒 packaging),
直接寫死常數即可。版本格式採 calver (YYYY.MM.N) 或 semver (X.Y.Z),
本輪選 semver 起步。
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitlog import __version__  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestVersionConstant(unittest.TestCase):
    def test_version_is_string(self) -> None:
        self.assertIsInstance(__version__, str)
        self.assertTrue(__version__.strip())

    def test_version_matches_semver_format(self) -> None:
        # X.Y.Z 三段數字,允許 pre-release (e.g. 0.1.0-dev)
        m = re.match(r"^\d+\.\d+\.\d+(-[\w.]+)?$", __version__)
        self.assertIsNotNone(
            m, f"version {__version__!r} should be semver-like"
        )


class TestCliVersionFlag(unittest.TestCase):
    def test_version_flag_prints_version_and_exits_zero(self) -> None:
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--version"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        # argparse 預設將版本印到 stdout
        combined = r.stdout + r.stderr
        self.assertIn(__version__, combined)

    def test_version_flag_without_input_file(self) -> None:
        # --version 不該要求 input 檔
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--version"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0)

    def test_version_includes_program_name(self) -> None:
        r = subprocess.run(
            [sys.executable, "fitlog.py", "--version"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        combined = r.stdout + r.stderr
        # 該行該認得出是 fitlog (argparse 預設用 prog name)
        self.assertIn("fitlog", combined.lower())


if __name__ == "__main__":
    unittest.main()
