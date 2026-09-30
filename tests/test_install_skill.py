"""Isolated installation tests; no changes to real user skills or credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "xiezhen-shoot-planner"


class InstallSkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xiezhen test 中文 ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.env = dict(os.environ, XIEZHEN_CONFIG=str(self.base / "config.json"),
                        HOME=str(self.base), USERPROFILE=str(self.base),
                        PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    def run_install(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts/install_skill.py"), *map(str, args)],
                              env=self.env, capture_output=True, text=True, encoding="utf-8")

    def test_codex_project_and_runtime_registration(self):
        result = self.run_install("--scope", "project", "--project-dir", self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.base / ".agents/skills" / NAME
        self.assertEqual((target / "SKILL.md").read_bytes(), (ROOT / "skill" / NAME / "SKILL.md").read_bytes())
        self.assertTrue((target / "agents/openai.yaml").is_file())
        config = json.loads((self.base / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(Path(config["root"]), ROOT)
        self.assertTrue(Path(config["python"]).is_file())

    def test_default_codex_user_install(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.base / ".agents/skills" / NAME / "SKILL.md").is_file())
        self.assertFalse((self.base / ".claude").exists())

    def test_claude_project(self):
        result = self.run_install("--agent", "claude", "--scope", "project", "--project-dir", self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.base / ".claude/skills" / NAME / "SKILL.md").is_file())

    def test_custom_directory_and_no_register(self):
        result = self.run_install("--skills-dir", self.base / "custom", "--no-register")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.base / "custom" / NAME / "SKILL.md").is_file())
        self.assertFalse((self.base / "config.json").exists())

    def test_refuses_overwrite_then_backs_up_on_update(self):
        args = ("--skills-dir", self.base / "skills", "--no-register")
        self.assertEqual(self.run_install(*args).returncode, 0)
        target = self.base / "skills" / NAME
        (target / "SKILL.md").write_text("local edits", encoding="utf-8")
        (target / "obsolete.txt").write_text("old resource", encoding="utf-8")
        self.assertNotEqual(self.run_install(*args).returncode, 0)
        self.assertEqual((target / "SKILL.md").read_text(), "local edits")
        result = self.run_install(*args, "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.base / ".xiezhen-skill-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "SKILL.md").read_text(), "local edits")
        self.assertFalse((target / "obsolete.txt").exists())

    def test_refuses_source_overwrite(self):
        result = self.run_install("--skills-dir", ROOT / "skill", "--force", "--no-register")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
