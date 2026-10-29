"""Проверки локального описания графа JSON."""

from pathlib import Path
import tempfile
import unittest

from src.test_repository import TestRepository


class TestRepositoryTests(unittest.TestCase):
    """Ошибки формата и независимость данных репозитория."""

    def setUp(self) -> None:
        """Создать отдельную временную папку."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "graph.json"

    def load(self, text: str) -> TestRepository:
        """Записать временный JSON и прочитать репозиторий."""
        self.path.write_text(text, encoding="utf-8")
        return TestRepository(self.path)

    def test_valid_and_copy(self) -> None:
        """Вернуть копию зависимостей и сохранить файл неизменным."""
        source = '{"A": ["B"], "B": []}'
        repo = self.load(source)
        repo.dependencies("A").clear()
        self.assertEqual(repo.dependencies("A"), ["B"])
        self.assertEqual(self.path.read_text(), source)

    def test_missing_invalid_and_utf8(self) -> None:
        """Сообщить об отсутствующем файле и ошибках декодирования."""
        with self.assertRaises(ValueError):
            TestRepository(self.path)
        with self.assertRaises(ValueError):
            self.load("{")
        self.path.write_bytes(b"\xff")
        with self.assertRaises(ValueError):
            TestRepository(self.path)

    def test_invalid_shapes_names_and_unknown_nodes(self) -> None:
        """Отклонить неверные типы, имена и неописанные вершины."""
        sources = ('[]', '{}', '{"a": []}', '{"A": "B"}',
                   '{"A": [1]}', '{"A": ["b"]}', '{"A": ["B"]}',
                   '{"A": [], "A": []}')
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    self.load(source)

    def test_absent_root(self) -> None:
        """Не выдавать неизвестный корень за изолированную вершину."""
        repo = self.load('{"A": []}')
        with self.assertRaisesRegex(ValueError, "отсутствует"):
            repo.dependencies("B")
