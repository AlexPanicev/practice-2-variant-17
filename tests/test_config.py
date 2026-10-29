"""Проверки CSV, семи параметров и отсутствия побочных записей."""

import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.config import load_config


class ConfigTests(unittest.TestCase):
    """Проверить каждый параметр и ошибки структуры на временных файлах."""

    def setUp(self) -> None:
        """Подготовить независимую папку с CSV и тестовым репозиторием."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.path = self.root / "config.csv"
        (self.root / "graph.json").write_text('{"A": []}')
        self.values = {
            "package": "junit:junit",
            "repository": "https://repo.maven.apache.org/maven2",
            "test_mode": "false", "version": "4.13.2",
            "output": "graph.png", "ascii_tree": "false", "filter": "",
        }

    def write_config(self, **changes: str) -> None:
        """Записать набор CSV, заменив только выбранные параметры."""
        values = self.values | changes
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["key", "value"])
            writer.writerows(values.items())

    def test_unresolvable_home(self) -> None:
        """Преобразовать ошибку ~user в ValueError для обоих путей."""
        cases = ({"output": "~missing/graph.png"},
                 {"package": "A", "test_mode": "true",
                  "repository": "~missing/graph.json"})
        for changes in cases:
            with self.subTest(changes=changes):
                self.write_config(**changes)
                with patch("src.validation.Path.expanduser",
                           side_effect=RuntimeError("missing user")):
                    with self.assertRaisesRegex(ValueError, "путь"):
                        load_config(self.path)

    def test_remote_config(self) -> None:
        """Прочитать семь параметров и не создать зарезервированный PNG."""
        self.write_config()
        config = load_config(self.path)
        self.assertEqual(config.package, "junit:junit")
        self.assertEqual(config.version, "4.13.2")
        self.assertFalse(config.test_mode)
        self.assertFalse(config.ascii_tree)
        self.assertEqual(config.filter, "")
        self.assertEqual(config.output, self.root / "graph.png")
        self.assertFalse(config.output.exists())

    def test_test_mode_and_relative_paths(self) -> None:
        """Разрешать пути относительно CSV независимо от текущей папки."""
        self.write_config(package="A", test_mode="true",
                          repository="graph.json")
        previous = Path.cwd()
        try:
            os.chdir(self.root.parent)
            config = load_config(self.path)
        finally:
            os.chdir(previous)
        self.assertEqual(config.repository, str(self.root / "graph.json"))
        self.assertEqual(config.output, self.root / "graph.png")
        self.assertTrue(config.test_mode)

    def test_booleans(self) -> None:
        """Допустить true/false без зависимости от регистра."""
        self.write_config(ascii_tree="TRUE", test_mode="FALSE")
        self.assertTrue(load_config(self.path).ascii_tree)

    def test_invalid_booleans(self) -> None:
        """Отклонить неоднозначные значения обоих логических полей."""
        for field in ("test_mode", "ascii_tree"):
            for value in ("", "yes", "1", "null"):
                with self.subTest(field=field, value=value):
                    self.write_config(**{field: value})
                    with self.assertRaisesRegex(ValueError, field):
                        load_config(self.path)

    def test_invalid_maven_names(self) -> None:
        """Отклонить отсутствующие координаты и компоненты пути."""
        for name in ("", "junit", ":a", "a:", "../a:b", "a:b/c", "a:b:c"):
            with self.subTest(name=name):
                self.write_config(package=name)
                with self.assertRaisesRegex(ValueError, "package"):
                    load_config(self.path)

    def test_invalid_test_names(self) -> None:
        """В тестовом режиме требовать только заглавные латинские буквы."""
        for name in ("a", "A1", "A_B", "А", "A:B"):
            with self.subTest(name=name):
                self.write_config(package=name, test_mode="true",
                                  repository="graph.json")
                with self.assertRaisesRegex(ValueError, "package"):
                    load_config(self.path)

    def test_fixed_versions(self) -> None:
        """Разрешить фиксированную версию с квалификатором release."""
        self.write_config(version="1.0.0-RC1")
        self.assertEqual(load_config(self.path).version, "1.0.0-RC1")

    def test_invalid_versions(self) -> None:
        """Отклонить диапазоны, динамические версии и опасные пути."""
        for value in ("", "LATEST", "RELEASE", "1-SNAPSHOT", "[1,2)",
                      "../1", "1/2", "1 2", "1" * 257):
            with self.subTest(value=value):
                self.write_config(version=value)
                with self.assertRaisesRegex(ValueError, "version"):
                    load_config(self.path)

    def test_repository_urls(self) -> None:
        """Принять HTTP(S), убрать лишь завершающий слеш."""
        for value in ("https://repo.example/maven/", "http://localhost:8080/"):
            with self.subTest(value=value):
                self.write_config(repository=value)
                self.assertEqual(load_config(self.path).repository,
                                 value.rstrip("/"))

    def test_invalid_repository_urls(self) -> None:
        """Отклонить неподходящую схему, пустой хост, запрос и порт."""
        for value in ("", "file:///tmp/repo", "https:///path", "https://x:bad",
                      "https://x:99999", "https://x:0", "https://x?q=1",
                      "https://x#part", "https://x?", "https://x/a b",
                      "https://x\\path"):
            with self.subTest(value=value):
                self.write_config(repository=value)
                with self.assertRaisesRegex(ValueError, "repository"):
                    load_config(self.path)

    def test_repository_credentials_not_echoed(self) -> None:
        """Сообщить о запрещённых credentials, не повторяя значение."""
        self.write_config(repository="https://name:private-token@repo.example")
        with self.assertRaises(ValueError) as caught:
            load_config(self.path)
        self.assertNotIn("private-token", str(caught.exception))

    def test_missing_test_repository(self) -> None:
        """Отклонить отсутствующий путь и каталог вместо тестового файла."""
        for value in ("missing.json", "."):
            with self.subTest(value=value):
                self.write_config(package="A", test_mode="true",
                                  repository=value)
                with self.assertRaisesRegex(ValueError, "repository"):
                    load_config(self.path)

    def test_unreadable_test_repository(self) -> None:
        """Сообщить об отсутствии разрешения читать тестовый файл."""
        self.write_config(package="A", test_mode="true",
                          repository="graph.json")
        with patch("src.validation.os.access", return_value=False):
            with self.assertRaisesRegex(ValueError, "repository"):
                load_config(self.path)

    def test_invalid_output(self) -> None:
        """Отклонить пустой путь, неверное расширение и отсутствующую папку."""
        for value in ("", "graph.svg", ".png", "missing/graph.png",
                      "graph.png/", "graph.png\\"):
            with self.subTest(value=value):
                self.write_config(output=value)
                with self.assertRaisesRegex(ValueError, "output"):
                    load_config(self.path)

    def test_output_directory(self) -> None:
        """Отклонить каталог с расширением PNG вместо выходного файла."""
        (self.root / "directory.png").mkdir()
        self.write_config(output="directory.png")
        with self.assertRaisesRegex(ValueError, "output"):
            load_config(self.path)

    def test_existing_output_not_overwritten(self) -> None:
        """Проверка пути не должна изменять существующий файл."""
        output = self.root / "graph.png"
        output.write_text("original")
        self.write_config()
        load_config(self.path)
        self.assertEqual(output.read_text(), "original")

    def test_nonwritable_output(self) -> None:
        """Отклонить недоступную для записи папку результата."""
        self.write_config()
        with patch("src.validation.os.access", return_value=False):
            with self.assertRaisesRegex(ValueError, "output"):
                load_config(self.path)

    def test_filter_and_csv_quoting(self) -> None:
        """Сохранить подстроку с запятой, экранированную по правилам CSV."""
        self.write_config(filter="part,other")
        self.assertEqual(load_config(self.path).filter, "part,other")

    def test_control_characters(self) -> None:
        """Отклонить управляющие символы, включая крайние в строке."""
        for field in self.values:
            with self.subTest(field=field):
                self.write_config(**{field: self.values[field] + "\n"})
                with self.assertRaises(ValueError):
                    load_config(self.path)

    def test_missing_unknown_and_duplicate_keys(self) -> None:
        """Отклонить неполные, неизвестные и повторяющиеся ключи CSV."""
        self.write_config()
        original = self.path.read_text()
        cases = (
            original.replace("filter,\n", ""),
            original + "unknown,value\n",
            original + "package,junit:junit\n",
        )
        for source in cases:
            with self.subTest(source=source):
                self.path.write_text(source)
                with self.assertRaisesRegex(ValueError, "config"):
                    load_config(self.path)

    def test_invalid_csv_shape(self) -> None:
        """Проверить обязательный заголовок и ширину CSV-строк."""
        for source in ("", "name,value\n", "key,value\npackage\n",
                       "key,value\npackage,a,b\n", "key,value\n\n"):
            with self.subTest(source=source):
                self.path.write_text(source)
                with self.assertRaisesRegex(ValueError, "config"):
                    load_config(self.path)

    def test_invalid_quotes_and_encoding(self) -> None:
        """Отклонить повреждённые кавычки и байты не в UTF-8."""
        for data in (b'key,value\npackage,"never closed', b'\xff\xfe'):
            with self.subTest(data=data):
                self.path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "config"):
                    load_config(self.path)

    def test_missing_config(self) -> None:
        """Сообщить об отсутствии файла конфигурации."""
        with self.assertRaisesRegex(ValueError, "config"):
            load_config(self.path)

    def test_utf8_bom(self) -> None:
        """Поддержать CSV с обычным UTF-8 BOM из табличного редактора."""
        self.write_config()
        source = self.path.read_text()
        self.path.write_text(source, encoding="utf-8-sig")
        self.assertEqual(load_config(self.path).package, "junit:junit")


if __name__ == "__main__":
    unittest.main()
