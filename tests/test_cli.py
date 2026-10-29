"""Запуск настоящего CLI и shell-обёртки без внешней сети."""

import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    """Команды README, циклы, ошибки и отсутствие записи PNG."""

    def execute(self, *arguments: str, cwd: Path = ROOT):
        """Запустить run.sh из выбранного рабочего каталога."""
        return subprocess.run(
            [str(ROOT / "run.sh"), *arguments], cwd=cwd,
            env=os.environ | {"PYTHON": sys.executable},
            capture_output=True, text=True, check=False,
        )

    def test_chain_and_outside_cwd(self) -> None:
        """Найти конфигурацию и JSON даже при запуске из чужой папки."""
        with tempfile.TemporaryDirectory() as directory:
            result = self.execute("--config", "configs/chain.csv",
                                  cwd=Path(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Обход DFS: A B C", result.stdout)
        self.assertNotIn("package=", result.stdout)

    def test_cycle_and_filter(self) -> None:
        """Продемонстрировать цикл и отсутствие отфильтрованной ветви."""
        result = self.execute("--config", "configs/cycle.csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Циклическое ребро: C -> A", result.stdout)
        result = self.execute("--config", "configs/filter.csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Обход DFS: A C", result.stdout)
        self.assertNotIn("B ->", result.stdout)

    def test_invalid_config_and_arguments(self) -> None:
        """Завершиться с кодом 2 и понятным сообщением без traceback."""
        for arguments in (("--config", "missing.csv"), ("--wrong",)):
            with self.subTest(arguments=arguments):
                result = self.execute(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)

    def test_reserved_visualization_does_not_write(self) -> None:
        """Параметры этапа 5 валидируются, но пока не создают PNG."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / "settings.csv"
            output = folder / "image.png"
            with path.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerows([
                    ["key", "value"], ["package", "A"],
                    ["repository", str(ROOT / "fixtures/chain.json")],
                    ["test_mode", "true"], ["version", "1"],
                    ["output", str(output)], ["ascii_tree", "true"],
                    ["filter", ""],
                ])
            result = self.execute("--config", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(output.exists())

    def test_help(self) -> None:
        """Показать справку без обращения к репозиторию."""
        result = self.execute("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--config", result.stdout)
