"""Проверки D2, ASCII и сохранения изображений без внешнего D2."""

from base64 import b64decode
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.graph import Graph
from src.visualization import d2_source, iter_ascii_tree, write_visualization


PNG_SAMPLE = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)


def render_sample(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Сымитировать успешный D2 для проверки записи обоих файлов."""
    Path(command[-1]).write_bytes(PNG_SAMPLE)
    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


class VisualizationTests(unittest.TestCase):
    """Графовые форматы, корректный PNG и обработка ошибок."""

    def test_d2_nodes_edges_and_escaped_label(self) -> None:
        """Сохранить версии, безопасно заключить подписи в кавычки."""
        graph = Graph({"A": ("B",), "B": ("A", "B")}, ["A", "B"])
        labels = {"A": 'g:artifact:2.1+"extra"', "B": "B \\ ${one}"}
        lines = d2_source(graph, labels).splitlines()
        self.assertEqual(lines, [
            "direction: right",
            r'n1: "g:artifact:2.1+\"extra\""',
            r'n2: "B \\ \${one}"',
            "n1 -> n2", "n2 -> n1", "n2 -> n2",
        ])

    def test_ascii_marks_cycles_and_shared_nodes(self) -> None:
        """Отличить обратное ребро от общей зависимости двух ветвей."""
        graph = Graph({"A": ("B", "C"), "B": ("D",), "C": ("D", "A"),
                       "D": ()}, ["A", "B", "D", "C"])
        self.assertEqual(list(iter_ascii_tree(graph, {"A": "A:1"})), [
            "A:1", "|-- B", "|   `-- D", "`-- C", "    |-- D [shared]",
            "    `-- A:1 [cycle]",
        ])

    def test_ascii_deep_graph_uses_stack(self) -> None:
        """Развернуть длинную цепочку без рекурсивных вызовов."""
        depth = 1200
        nodes = [f"N{i}" for i in range(depth)]
        edges = {key: (value,) for key, value in zip(nodes, nodes[1:])}
        edges[nodes[-1]] = ()
        tree = iter_ascii_tree(Graph(edges, nodes), {})
        self.assertEqual(next(tree), "N0")
        self.assertEqual(sum(1 for _ in tree), depth - 1)

    def test_empty_graph(self) -> None:
        """Получить понятный результат после исключения корня."""
        graph = Graph(excluded={"A"})
        self.assertIn('empty: "(empty graph)"', d2_source(graph, {}))
        self.assertEqual(list(iter_ascii_tree(graph, {})), ["(empty graph)"])

    def test_isolated_node(self) -> None:
        """Показать вершину без исходящих рёбер в обоих форматах."""
        graph = Graph({"A": ()}, ["A"])
        self.assertEqual(d2_source(graph, {}), 'direction: right\nn1: "A"\n')
        self.assertEqual(list(iter_ascii_tree(graph, {})), ["A"])

    def test_write_creates_both_files_in_nested_folder(self) -> None:
        """Создать каталог и передать имена файлов отдельными аргументами."""
        graph = Graph({"A": ()}, ["A"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "with space" / "nested" / "a.png"
            with patch("src.visualization.subprocess.run", render_sample):
                source = write_visualization(graph, output, {"A": "A:1"})
            self.assertEqual(source, output.with_suffix(".d2"))
            self.assertEqual(output.read_bytes(), PNG_SAMPLE)
            self.assertIn('n1: "A:1"', source.read_text(encoding="utf-8"))
            self.assertEqual(set(output.parent.iterdir()), {source, output})

    def test_renderer_errors_preserve_existing_pair(self) -> None:
        """Сохранить предыдущую пару при отсутствии D2 и ошибках D2."""
        outcomes = (
            (FileNotFoundError(), "не найдена"),
            (subprocess.TimeoutExpired("d2", 120), "лимит"),
            (subprocess.CompletedProcess(["d2"], 1, "", "bad D2"), "bad D2"),
            (subprocess.CompletedProcess(["d2"], 0, "", ""), "корректный PNG"),
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "a.png"
            source = output.with_suffix(".d2")
            output.write_bytes(PNG_SAMPLE)
            source.write_text("previous D2", encoding="utf-8")
            for outcome, error in outcomes:
                with self.subTest(error=error):
                    self.assert_render_failure(output, outcome, error)
                    self.assertEqual(output.read_bytes(), PNG_SAMPLE)
                    self.assertEqual(source.read_text(), "previous D2")
            self.assertEqual(set(output.parent.iterdir()), {source, output})

    def assert_render_failure(self, output: Path, outcome, error: str) -> None:
        """Дать D2 результат или исключение и проверить сообщение CLI."""
        with patch("src.visualization.subprocess.run") as run:
            if isinstance(outcome, Exception):
                run.side_effect = outcome
            else:
                run.return_value = outcome
            with self.assertRaisesRegex(ValueError, error):
                write_visualization(Graph(), output, {})

    def test_truncated_png_is_rejected(self) -> None:
        """Отклонить обрезанный PNG, даже если рендерер завершился успешно."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "a.png"

            def render_truncated(command, **kwargs):
                """Сымитировать пропуск завершающего блока PNG."""
                Path(command[-1]).write_bytes(PNG_SAMPLE[:-12])
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("src.visualization.subprocess.run", render_truncated):
                with self.assertRaisesRegex(ValueError, "корректный PNG"):
                    write_visualization(Graph(), output, {})
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".d2").exists())

    def test_d2_directory_prevents_output(self) -> None:
        """Сообщить о конфликте пути D2 до запуска внешней команды."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "a.png"
            output.with_suffix(".d2").mkdir()
            with patch("src.visualization.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "обычный файл"):
                    write_visualization(Graph(), output, {})
            run.assert_not_called()
            self.assertFalse(output.exists())
