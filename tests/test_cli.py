"""Проверки CLI первого этапа без сетевых обращений."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    """Печать параметров, справка и ошибки CSV."""

    def execute(self, *arguments: str):
        """Вызвать настоящий скрипт с выбранным Python."""
        return subprocess.run(
            [str(ROOT / "run.sh"), *arguments], cwd=ROOT,
            env=os.environ | {"PYTHON": sys.executable},
            capture_output=True, text=True, check=False,
        )

    def test_all_parameters(self) -> None:
        """Вывести ровно семь ключей из корректного CSV."""
        result = self.execute("--config", "configs/maven.csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = dict(row.split("=", 1) for row in result.stdout.splitlines())
        self.assertEqual(set(rows), {"package", "repository", "test_mode",
                                    "version", "output", "ascii_tree",
                                    "filter"})
        self.assertEqual(rows["package"], "junit:junit")
        self.assertEqual(rows["version"], "4.13.2")
        self.assertEqual(rows["test_mode"], "false")

    def test_invalid_config(self) -> None:
        """Сообщить об отсутствующем CSV с кодом 2."""
        result = self.execute("--config", "missing.csv")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_help(self) -> None:
        """Показать параметр выбора конфигурации."""
        result = self.execute("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--config", result.stdout)
