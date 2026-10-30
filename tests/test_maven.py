"""Maven-провайдер: настоящий HTTP на loopback, без внешней сети в тестах."""

import tempfile
import threading
import unittest
from functools import partial
from http.client import BadStatusLine, IncompleteRead
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from src.coordinates import Coordinate
from src.maven import MavenRepository, repository_url
from src.pom import expand, parse_document


def pom(name: str, dependencies: str = "", extra: str = "",
        group: str = "test", version: str = "1") -> str:
    """Создать небольшой POM с явно заданными координатами."""
    return (f'<project xmlns="http://maven.apache.org/POM/4.0.0">'
            f'<modelVersion>4.0.0</modelVersion><groupId>{group}</groupId>'
            f'<artifactId>{name}</artifactId><version>{version}</version>'
            f'{extra}<dependencies>{dependencies}</dependencies></project>')


def dependency(name: str, version: str = "1", extra: str = "") -> str:
    """Создать объявление зависимости с необязательной версией."""
    version_xml = f"<version>{version}</version>" if version else ""
    return (f'<dependency><groupId>test</groupId>'
            f'<artifactId>{name}</artifactId>'
            f'{version_xml}{extra}</dependency>')


class Handler(SimpleHTTPRequestHandler):
    """Выдать POM из временной папки и записывать обращения к серверу."""

    def log_request(self, code="-", size="-") -> None:
        """Сохранить путь каждого HTTP-запроса для проверки кэширования."""
        self.server.requests.append(self.path)

    def log_message(self, _format: str, *args) -> None:
        """Не печатать служебные запросы тестового сервера."""


class MavenTests(unittest.TestCase):
    """Проверить загрузку и эффективные зависимости через HTTP."""

    def setUp(self) -> None:
        """Запустить изолированный HTTP-сервер на свободном порту."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        handler = partial(Handler, directory=self.directory)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.requests = []
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01}, daemon=True,
        )
        self.thread.start()
        self.addCleanup(self.close_server)
        port = self.server.server_address[1]
        self.repository = MavenRepository(f"http://127.0.0.1:{port}/repo")

    def close_server(self) -> None:
        """Завершить сервер и поток после каждого теста."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def add(self, coordinate: str, source: str) -> None:
        """Опубликовать POM по реальному Maven-пути тестового сервера."""
        path = self.directory / "repo" / Coordinate.parse(coordinate).pom_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def test_versioned_direct_dependencies(self) -> None:
        """Соблюдать запрошенную версию и вывести все scope и optional."""
        extras = '<scope>test</scope><optional>true</optional>'
        source = dependency("compile") + dependency("testing", extra=extras)
        self.add("test:root:1", pom("root", source))
        self.add("test:root:2", pom("root", dependency("other"), version="2"))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:compile:1", "test:testing:1"])
        self.assertEqual(self.repository.dependencies("test:root:2"),
                         ["test:other:1"])
        self.assertEqual(self.server.requests, [
            "/repo/test/root/1/root-1.pom", "/repo/test/root/2/root-2.pom",
        ])

    def test_cache_and_non_namespace_pom(self) -> None:
        """Не скачивать и не разбирать успешный POM повторно."""
        self.add("test:root:1", pom("root").replace(
            ' xmlns="http://maven.apache.org/POM/4.0.0"', ""))
        self.assertEqual(self.repository.dependencies("test:root:1"), [])
        self.assertEqual(self.repository.dependencies("test:root:1"), [])
        self.assertEqual(len(self.server.requests), 1)

    def test_properties_and_management_not_edges(self) -> None:
        """Разрешить вложенные свойства и не считать management ребром."""
        extra = ('<properties><lib.version>${project.version}</lib.version>'
                 '</properties><dependencyManagement><dependencies>'
                 + dependency("lib", "${lib.version}")
                 + dependency("unused", "2")
                 + '</dependencies></dependencyManagement>')
        self.add("test:root:1", pom("root", dependency("lib", ""), extra))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:1"])

    def test_parent_inheritance_and_child_properties(self) -> None:
        """Наследовать объявления и применять свойства дочернего POM."""
        extra = ('<properties><lib.version>2</lib.version></properties>'
                 '<dependencyManagement><dependencies>'
                 + dependency("lib", "${lib.version}")
                 + '</dependencies></dependencyManagement>')
        self.add("test:parent:1", pom("parent", dependency("base"), extra))
        child = ('<project><parent><groupId>test</groupId>'
                 '<artifactId>parent</artifactId><version>1</version>'
                 '</parent><artifactId>root</artifactId><properties>'
                 '<lib.version>3</lib.version></properties><dependencies>'
                 + dependency("lib", "") + '</dependencies></project>')
        self.add("test:root:1", child)
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:base:1", "test:lib:3"])

    def test_imported_bom_and_local_priority(self) -> None:
        """Использовать первый BOM и локальное переопределение версии."""
        managed = ('<properties><v>2</v></properties>'
                   '<dependencyManagement><dependencies>'
                   + dependency("lib", "${v}") + dependency("other", "2")
                   + '</dependencies></dependencyManagement>')
        self.add("test:bom:1", pom("bom", extra=managed))
        managed2 = ('<dependencyManagement><dependencies>'
                    + dependency("lib", "9")
                    + '</dependencies></dependencyManagement>')
        self.add("test:bom2:1", pom("bom2", extra=managed2))
        imported = '<scope>import</scope><type>pom</type>'
        extra = ('<dependencyManagement><dependencies>'
                 + dependency("bom", extra=imported)
                 + dependency("bom2", extra=imported)
                 + dependency("other", "3")
                 + '</dependencies></dependencyManagement>')
        deps = dependency("lib", "") + dependency("other", "")
        self.add("test:root:1", pom("root", deps, extra))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:2", "test:other:3"])

    def test_parent_and_bom_cycles(self) -> None:
        """Сообщить о цикле метаданных вместо переполнения стека."""
        parent = ('<parent><groupId>test</groupId><artifactId>root</artifactId>'
                  '<version>1</version></parent>')
        self.add("test:root:1", pom("root", extra=parent))
        with self.assertRaisesRegex(ValueError, "цикл parent/BOM"):
            self.repository.dependencies("test:root:1")
        imported = '<scope>import</scope><type>pom</type>'
        extra = ('<dependencyManagement><dependencies>'
                 + dependency("bom", extra=imported)
                 + '</dependencies></dependencyManagement>')
        self.add("test:bom:1", pom("bom", extra=extra))
        with self.assertRaisesRegex(ValueError, "цикл parent/BOM"):
            self.repository.dependencies("test:bom:1")

    def test_missing_versions_and_unknown_properties(self) -> None:
        """Не скрывать отсутствие версии и неизвестные свойства."""
        self.add("test:root:1", pom("root", dependency("lib", "")))
        with self.assertRaisesRegex(ValueError, "не задана версия"):
            self.repository.dependencies("test:root:1")
        self.add("test:other:1", pom("other", dependency("lib", "${missing}")))
        with self.assertRaisesRegex(ValueError, "неизвестное свойство"):
            self.repository.dependencies("test:other:1")

    def test_wrong_identity_and_broken_xml(self) -> None:
        """Отклонить неверный артефакт и повреждённый XML."""
        self.add("test:root:1", pom("wrong"))
        with self.assertRaisesRegex(ValueError, "не совпадают"):
            self.repository.dependencies("test:root:1")
        self.add("test:broken:1", "<project>")
        with self.assertRaisesRegex(ValueError, "повреждённый POM"):
            self.repository.dependencies("test:broken:1")

    def test_http_and_network_errors(self) -> None:
        """Понятно сообщить об HTTP 404 и недоступной сети."""
        with self.assertRaisesRegex(ValueError, "HTTP 404: test:absent:1"):
            self.repository.dependencies("test:absent:1")
        with patch("src.maven.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(ValueError, "ошибка сети"):
                self.repository.dependencies("test:offline:1")

    def test_malformed_http_response(self) -> None:
        """Преобразовать неверный HTTP и оборванный ответ в ошибку сети."""
        for error in (BadStatusLine("NOT_HTTP"), IncompleteRead(b"short", 9)):
            with self.subTest(error=type(error).__name__):
                with patch("src.maven.urlopen", side_effect=error):
                    with self.assertRaisesRegex(ValueError, "ошибка сети"):
                        self.repository.dependencies("test:brokenhttp:1")

    def test_size_limit(self) -> None:
        """Не читать POM без ограничения размера."""
        self.add("test:root:1", pom("root"))
        with patch("src.maven.MAX_POM_BYTES", 32):
            with self.assertRaisesRegex(ValueError, "превышает"):
                self.repository.dependencies("test:root:1")

    def test_profiles_and_plugins_are_not_dependencies(self) -> None:
        """Не принимать неактивированные профили и плагины за зависимости."""
        extra = ('<profiles><profile><dependencies>'
                 + dependency("profile")
                 + '</dependencies></profile></profiles><build><plugins>'
                 '<plugin><dependencies>' + dependency("plugin")
                 + '</dependencies></plugin></plugins></build>')
        self.add("test:root:1", pom("root", dependency("lib"), extra))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:1"])

    def test_partial_management_keeps_inherited_version(self) -> None:
        """Не терять версию родителя при переопределении только scope."""
        managed = ('<dependencyManagement><dependencies>'
                   + dependency("lib", "2")
                   + '</dependencies></dependencyManagement>')
        self.add("test:parent:1", pom("parent", extra=managed))
        extra = ('<parent><groupId>test</groupId>'
                 '<artifactId>parent</artifactId>'
                 '<version>1</version></parent><dependencyManagement>'
                 '<dependencies>'
                 + dependency("lib", "", "<scope>runtime</scope>")
                 + '</dependencies></dependencyManagement>')
        self.add("test:root:1", pom("root", dependency("lib", ""), extra))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:2"])

    def test_parent_aliases(self) -> None:
        """Разрешить project.parent.version независимо от версии ребёнка."""
        self.add("test:parent:2", pom("parent", version="2"))
        extra = ('<parent><groupId>test</groupId>'
                 '<artifactId>parent</artifactId>'
                 '<version>2</version></parent>')
        self.add("test:root:1", pom(
            "root", dependency("lib", "${project.parent.version}"), extra
        ))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:2"])

    def test_metadata_depth_limit(self) -> None:
        """Ограничить глубокую цепочку родителей до переполнения стека."""
        for name, parent in (("root", "parent"), ("parent", "grandparent")):
            extra = ('<parent><groupId>test</groupId>'
                     f'<artifactId>{parent}</artifactId>'
                     '<version>1</version></parent>')
            self.add(f"test:{name}:1", pom(name, extra=extra))
        with patch("src.maven.MAX_MODEL_DEPTH", 2):
            with self.assertRaisesRegex(ValueError, "глубокое наследование"):
                self.repository.dependencies("test:root:1")

    def test_classifiers_keep_distinct_versions(self) -> None:
        """Не терять версии одного GA с разными type и classifier."""
        classified = '<type>test-jar</type><classifier>tests</classifier>'
        deps = dependency("lib", "1") + dependency("lib", "2", classified)
        self.add("test:root:1", pom("root", deps))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:1", "test:lib:2"])

    def test_managed_versions_are_classifier_specific(self) -> None:
        """Подбирать управляемую версию по GA, type и classifier."""
        classified = '<type>test-jar</type><classifier>tests</classifier>'
        managed = ('<dependencyManagement><dependencies>'
                   + dependency("lib", "2")
                   + dependency("lib", "3", classified)
                   + '</dependencies></dependencyManagement>')
        deps = dependency("lib", "") + dependency("lib", "", classified)
        self.add("test:root:1", pom("root", deps, managed))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:2", "test:lib:3"])

    def test_parent_override_preserves_other_classifiers(self) -> None:
        """Переопределять только совпавший тип и классификатор родителя."""
        classified = '<type>test-jar</type><classifier>tests</classifier>'
        deps = dependency("lib", "1") + dependency("lib", "2", classified)
        self.add("test:parent:1", pom("parent", deps))
        parent = ('<parent><groupId>test</groupId>'
                  '<artifactId>parent</artifactId><version>1</version>'
                  '</parent>')
        self.add("test:root:1", pom(
            "root", dependency("lib", "3", classified), parent
        ))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:1", "test:lib:3"])

    def test_bom_keeps_classifier_versions(self) -> None:
        """Сохранить классифицированные версии BOM при локальном override."""
        classified = '<type>test-jar</type><classifier>tests</classifier>'
        managed = ('<dependencyManagement><dependencies>'
                   + dependency("lib", "2")
                   + dependency("lib", "3", classified)
                   + '</dependencies></dependencyManagement>')
        self.add("test:bom:1", pom("bom", extra=managed))
        imported = '<scope>import</scope><type>pom</type>'
        extra = ('<dependencyManagement><dependencies>'
                 + dependency("bom", extra=imported) + dependency("lib", "4")
                 + '</dependencies></dependencyManagement>')
        deps = dependency("lib", "") + dependency("lib", "", classified)
        self.add("test:root:1", pom("root", deps, extra))
        self.assertEqual(self.repository.dependencies("test:root:1"),
                         ["test:lib:4", "test:lib:3"])


class ParsingTests(unittest.TestCase):
    """Проверки координат, XML и подстановок без HTTP."""

    def test_coordinates_and_layout(self) -> None:
        """Построить Maven-путь из точных координат."""
        coordinate = Coordinate.parse("org.example:sample:2.1.0")
        self.assertEqual(coordinate.package, "org.example:sample")
        self.assertEqual(coordinate.pom_path,
                         "org/example/sample/2.1.0/sample-2.1.0.pom")

    def test_invalid_coordinates(self) -> None:
        """Отклонить пути, диапазоны, динамические и snapshot-версии."""
        values = ("x", "a:b", "a:b:1:2", "../a:b:1", "a..b:c:1",
                  "a:b:[1,2)", "a:b:LATEST", "a:b:RELEASE",
                  "a:b:1-SNAPSHOT", "a:b:", "a:b:1/2")
        for item in values:
            with self.subTest(value=item):
                with self.assertRaises(ValueError):
                    Coordinate.parse(item)

    def test_invalid_repository_urls(self) -> None:
        """Требовать URL без паролей и посторонних частей."""
        for url in ("file:///tmp", "https://", "https://host:bad/",
                    "https://user:password@host", "https://host?q=1",
                    "https://host/#fragment", "https://host/a b",
                    "https://host/\npath"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    repository_url(url)

    def test_property_cycles_and_parent_aliases(self) -> None:
        """Разрешать вложенные свойства и явно отклонять их циклы."""
        self.assertEqual(expand("${a}", {"a": "${b}", "b": "2"}), "2")
        with self.assertRaisesRegex(ValueError, "цикл"):
            expand("${a}", {"a": "${b}", "b": "${a}"})
        with self.assertRaisesRegex(ValueError, "неизвестное"):
            expand("${env.SECRET}", {})

    def test_wrong_root_and_entities(self) -> None:
        """Не принимать не-POM XML и определения DTD."""
        for source in (b"<html/>", b'<!DOCTYPE project><project/>',
                       b'<!ENTITY x "text"><project/>'):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    parse_document(source)

    def test_utf16_entities(self) -> None:
        """Проверять DTD также при представлении XML в UTF-16."""
        source = '<!DOCTYPE project [<!ENTITY x "a">]><project/>'
        with self.assertRaisesRegex(ValueError, "DTD"):
            parse_document(source.encode("utf-16"))

    def test_unknown_and_unsupported_encodings(self) -> None:
        """Преобразовать ошибки кодировки XML в понятную ошибку POM."""
        for encoding in ("NONEXISTENT", "UTF-7"):
            with self.subTest(encoding=encoding):
                source = (f'<?xml version="1.0" encoding="{encoding}"?>'
                          '<project/>')
                with self.assertRaisesRegex(ValueError, "повреждённый POM"):
                    parse_document(source.encode("ascii"))


if __name__ == "__main__":
    unittest.main()
