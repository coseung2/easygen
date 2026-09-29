"""Behavior checks for external Lab data paths and standalone script bootstrap."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class LabPathsTest(unittest.TestCase):
    def run_import(self, configured: str | None, **extra_env: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("MODAL_GUI_DATA_ROOT", None)
        env.pop("XDG_DATA_HOME", None)
        env["LOCALAPPDATA"] = str(REPO_ROOT / "test-local-appdata")
        env.update(extra_env)
        if configured is not None:
            env["MODAL_GUI_DATA_ROOT"] = configured
        return subprocess.run(
            [sys.executable, "-c", "from tools.lab_paths import DATA_ROOT; print(DATA_ROOT)"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_configured_root_is_used(self) -> None:
        configured = str(REPO_ROOT / "external-media")
        result = self.run_import(configured)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), Path(configured))

    def test_relative_configured_root_is_rejected(self) -> None:
        result = self.run_import("relative/media")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MODAL_GUI_DATA_ROOT must be an absolute path", result.stderr)

    def test_default_uses_os_user_data_directory(self) -> None:
        result = self.run_import(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), REPO_ROOT / "test-local-appdata" / "modal-gui")

    def test_attention_script_bootstrap_finds_tools_outside_repo_cwd(self) -> None:
        script = REPO_ROOT / "lab" / "h3_attention_compare.py"
        tree = ast.parse(script.read_text(encoding="utf-8"))
        bootstrap = [
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "REPO" for target in node.targets)
            or isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Attribute)
            and isinstance(node.value.func.value.value, ast.Name)
            and node.value.func.value.value.id == "sys"
            and node.value.func.value.attr == "path"
            and node.value.func.attr == "insert"
        ]
        bootstrap_source = "\n".join(ast.unparse(node) for node in bootstrap)
        probe = (
            "from pathlib import Path; import sys; "
            f"__file__ = {str(script)!r}; "
            "exec(" + repr(bootstrap_source) + "); "
            "import tools.lab_paths; print(tools.lab_paths.DATA_ROOT)"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=Path.home(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(result.stdout.strip()).is_absolute())


if __name__ == "__main__":
    unittest.main()
