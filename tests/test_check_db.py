import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


class CheckDatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "sample.db"
        with sqlite3.connect(self.path) as connection:
            connection.execute("CREATE TABLE chats (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT, answer TEXT, created_at TEXT)")
            connection.executemany("INSERT INTO chats VALUES (?, ?, ?, ?, ?)", [
                (1, 1, "첫 질문", "첫 응답", "2026-10-04 01:00:00"),
                (2, 1, "둘째 질문", "둘째 응답", "2026-10-04 01:00:00"),
                (3, 2, "다른 사용자", "비공개", "2026-10-04 02:00:00"),
            ])
        connection.close()
        self.script = Path(__file__).resolve().parents[1] / "scripts" / "check_db.py"

    def run_script(self, *arguments):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.script), *map(str, arguments)], capture_output=True, encoding="utf-8")

    def test_reads_only_selected_user_and_preserves_file(self):
        before = self.path.read_bytes()
        result = self.run_script("--database", self.path, "--user-id", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual([row["id"] for row in rows], [2, 1])
        self.assertEqual({row["user_id"] for row in rows}, {1})
        self.assertEqual(self.path.read_bytes(), before)

    def test_limit_is_applied(self):
        result = self.run_script("--database", self.path, "--user-id", 1, "--limit", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row["id"] for row in json.loads(result.stdout)], [2])

    def test_missing_database_is_not_created(self):
        missing = self.path.with_name("missing.db")
        result = self.run_script("--database", missing, "--user-id", 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DB", result.stderr)
        self.assertFalse(missing.exists())

    def test_user_is_required_and_limit_must_be_positive(self):
        for arguments in (("--database", self.path), ("--database", self.path, "--user-id", 1, "--limit", 0)):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_script(*arguments).returncode, 2)


if __name__ == "__main__":
    unittest.main()
