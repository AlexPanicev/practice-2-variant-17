"""Проверки запуска, выбора конфигурации и визуализации этапа 5."""

import csv
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.main import run


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    """Проверить вход CLI, передачу графа в рендерер и ASCII."""

    def execute(self, *arguments: str, cwd: Path = ROOT):
        """Запустить run.sh из выбранного рабочего каталога."""
        return subprocess.run(
            [str(ROOT / "run.sh"), *arguments], cwd=cwd,
            env=os.environ | {"PYTHON": sys.executable},
            capture_output=True, text=True, check=False,
        )

    def render(self, path: Path, output: Path):
        """Выполнить run с наблюдаемым рендерером без записи файлов."""
        stdout = StringIO()
        with patch("src.main.write_visualization") as renderer:
            renderer.return_value = output.with_suffix(".d2")
            with redirect_stdout(stdout):
                run(path)
        return stdout.getvalue(), renderer.call_args.args

    def write_config(self, path: Path, output: Path) -> None:
        """Подготовить локальную цепочку с ASCII и нестандартной версией."""
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerows([
                ["key", "value"], ["package", "A"],
                ["repository", str(ROOT / "fixtures/chain.json")],
                ["test_mode", "true"], ["version", "2.1"],
                ["output", str(output)], ["ascii_tree", "true"],
                ["filter", ""],
            ])

    def test_chain_ascii_and_output(self) -> None:
        """Передать заданный путь и показать версию тестового корня."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            path = folder / "settings.csv"
            output = folder / "with space" / "chain.png"
            self.write_config(path, output)
            stdout, args = self.render(path, output)
        graph, destination, labels = args
        self.assertEqual(graph.order, ["A", "B", "C"])
        self.assertEqual(destination, output)
        self.assertEqual(labels, {"A": "A:2.1"})
        self.assertIn("ASCII-дерево:\nA:2.1\n", stdout)
        self.assertIn(f"D2: {output.with_suffix('.d2')}", stdout)
        self.assertIn(f"PNG: {output}", stdout)
        self.assertNotIn("Порядок загрузки:", stdout)

    def test_no_ascii_if_disabled(self) -> None:
        """При ascii_tree=false создать граф без текстового дерева."""
        path = ROOT / "configs/maven.csv"
        with patch("src.main.MavenRepository") as repository:
            repository.return_value.dependencies.return_value = []
            stdout, args = self.render(path, ROOT / "output/maven.png")
        self.assertEqual(args[0].order, ["junit:junit:4.13.2"])
        self.assertEqual(args[2], {})
        self.assertNotIn("ASCII-дерево:", stdout)

    def test_cycle_and_filter(self) -> None:
        """Сохранить цикл и исключение ветви при визуализации."""
        path = ROOT / "configs/cycle.csv"
        stdout, args = self.render(path, ROOT / "output/cycle.png")
        self.assertIn("Циклическое ребро: C -> A", stdout)
        self.assertEqual(args[0].edges["C"], ("A",))
        path = ROOT / "configs/filter.csv"
        stdout, args = self.render(path, ROOT / "output/filter.png")
        self.assertIn("Обход DFS: A C", stdout)
        self.assertNotIn("B ->", stdout)
        self.assertNotIn("B", args[0].edges)

    def test_source_path_conflict(self) -> None:
        """Не заменять входной CSV, если его имя совпадает с D2."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "same.d2"
            self.write_config(path, path.with_suffix(".png"))
            with self.assertRaisesRegex(ValueError, "входным"):
                run(path)
            self.assertTrue(path.read_text().startswith("key,value"))

    def test_invalid_config_and_arguments(self) -> None:
        """Завершиться с кодом 2 и понятным сообщением без traceback."""
        for arguments in (("--config", "missing.csv"), ("--wrong",)):
            with self.subTest(arguments=arguments):
                result = self.execute(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)

    def test_help(self) -> None:
        """Показать справку вне корня проекта и без запуска D2."""
        with tempfile.TemporaryDirectory() as directory:
            result = self.execute("--help", cwd=Path(directory))
        self.assertEqual(result.returncode, 0)
        self.assertIn("--config", result.stdout)
