"""Проверки вывода прямых зависимостей CLI второго этапа."""

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.config import Config
from src.main import run


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    """Точный запрос версии, вывод прямых зависимостей и ошибки."""

    def execute(self, *arguments: str):
        """Вызвать настоящий скрипт с выбранным Python."""
        return subprocess.run(
            [str(ROOT / "run.sh"), *arguments], cwd=ROOT,
            env=os.environ | {"PYTHON": sys.executable},
            capture_output=True, text=True, check=False,
        )

    def test_direct_dependencies(self) -> None:
        """Запросить указанную версию и вывести каждую прямую зависимость."""
        with patch("src.main.MavenRepository") as factory:
            instance = factory.return_value
            instance.dependencies.return_value = ["g:a:1", "g:b:2"]
            output = StringIO()
            with redirect_stdout(output):
                run(ROOT / "configs/maven.csv")
        instance.dependencies.assert_called_once_with("junit:junit:4.13.2")
        self.assertEqual(output.getvalue().splitlines(), [
            "Прямые зависимости junit:junit:4.13.2:", "g:a:1", "g:b:2",
        ])
        self.assertNotIn("package=", output.getvalue())

    def test_leaf(self) -> None:
        """Явно сообщить об отсутствии зависимостей."""
        with patch("src.main.MavenRepository") as factory:
            factory.return_value.dependencies.return_value = []
            output = StringIO()
            with redirect_stdout(output):
                run(ROOT / "configs/maven.csv")
        self.assertIn("(нет зависимостей)", output.getvalue())

    def test_test_mode_reserved_for_stage3(self) -> None:
        """Не имитировать чтение JSON до этапа 3."""
        config = Config("A", "graph.json", True, "1", Path("g.png"),
                        False, "")
        with patch("src.main.load_config", return_value=config):
            with self.assertRaisesRegex(ValueError, "этапа 3"):
                run(Path("unused.csv"))

    def test_invalid_config(self) -> None:
        """Сообщить об отсутствующем CSV с кодом 2 без traceback."""
        result = self.execute("--config", "missing.csv")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_help(self) -> None:
        """Показать параметр выбора конфигурации."""
        result = self.execute("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--config", result.stdout)
