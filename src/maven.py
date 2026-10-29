"""Получение объявленных Maven-зависимостей напрямую из POM по HTTP."""

from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from src.coordinates import Coordinate
from src.pom import (
    Identity, Model, aliases, check_identity, declarations, dependency_key,
    expand, package_name, parent_coordinate, parse_document, properties,
)


TIMEOUT = 15
MAX_POM_BYTES = 4 * 1024 * 1024
MAX_MODEL_DEPTH = 32


def repository_url(url: str) -> str:
    """Проверить адрес репозитория без паролей, параметров и фрагментов."""
    if any(character.isspace() for character in url):
        raise ValueError("Maven: URL не должен содержать пробельные символы")
    try:
        parsed = urlsplit(url)
        parsed.port
    except ValueError as error:
        raise ValueError("Maven: некорректный URL репозитория") from error
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Maven: требуется HTTP(S)-адрес репозитория")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Maven: URL не должен содержать учётные данные")
    return url.rstrip("/") + "/"


class MavenRepository:
    """Кэш POM и моделей одного явно указанного Maven-репозитория."""

    def __init__(self, url: str) -> None:
        """Сохранить URL и создать отдельные кэши источников и моделей."""
        self.url = repository_url(url)
        self.documents = {}
        self.models = {}

    def dependencies(self, node: str) -> list[str]:
        """Вернуть все прямые объявления независимо от scope и optional."""
        coordinate = Coordinate.parse(node)
        model = self._model(coordinate, ())
        result = []
        for identity, item in model.declarations.items():
            name = identity[0]
            version = item.get("version") or model.managed.get(identity, "")
            if not version:
                raise ValueError(f"Maven: не задана версия зависимости {name}")
            label = Coordinate.parse(
                f"{name}:{expand(version, model.properties)}"
            ).label
            if label not in result:
                result.append(label)
        return result

    def _document(self, coordinate: Coordinate):
        """Загрузить и разобрать POM однократно для каждого артефакта."""
        if coordinate.label not in self.documents:
            self.documents[coordinate.label] = parse_document(
                self._download(coordinate)
            )
        return self.documents[coordinate.label]

    def _download(self, coordinate: Coordinate) -> bytes:
        """Загрузить только POM с ограничениями времени и размера."""
        request = Request(self.url + coordinate.pom_path,
                          headers={"User-Agent": "practice-2-variant-17/1.0"})
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                data = response.read(MAX_POM_BYTES + 1)
        except HTTPError as error:
            raise ValueError(f"Maven: HTTP {error.code}: "
                             f"{coordinate.label}") from error
        except (URLError, OSError, ValueError, HTTPException) as error:
            raise ValueError(f"Maven: ошибка сети для "
                             f"{coordinate.label}: {error}") from error
        if len(data) > MAX_POM_BYTES:
            raise ValueError("Maven: POM превышает допустимый размер")
        return data

    def _model(self, coordinate: Coordinate, trail: tuple[str, ...]) -> Model:
        """Собрать наследование POM с защитой от циклов родителей и BOM."""
        key = coordinate.label
        if key in trail:
            raise ValueError(f"Maven: цикл parent/BOM: {key}")
        if len(trail) >= MAX_MODEL_DEPTH:
            raise ValueError("Maven: слишком глубокое наследование parent/BOM")
        if key in self.models:
            return self.models[key]
        root = self._document(coordinate)
        local = properties(root)
        parent = parent_coordinate(root, local | aliases(coordinate))
        inherited = self._model(parent, trail + (key,)) if parent else Model()
        model = Model(inherited.properties | local | aliases(coordinate),
                      inherited.managed.copy(), inherited.declarations.copy())
        if parent:
            self._parent_aliases(model, parent)
        check_identity(root, coordinate, model.properties)
        self._managed(model, root, trail + (key,))
        self._declarations(model, root)
        self.models[key] = model
        return model

    @staticmethod
    def _parent_aliases(model: Model, parent: Coordinate) -> None:
        """Настроить ссылки на фактические координаты родителя проекта."""
        for key, item in aliases(parent).items():
            if "." not in key:
                model.properties["project.parent." + key] = item
                model.properties["parent." + key] = item

    def _managed(self, model: Model, root, trail: tuple[str, ...]) -> None:
        """Импортировать BOM и применить собственные управляемые версии."""
        path = "dependencyManagement/dependencies/dependency"
        entries = declarations(root, path)
        imported = {}
        local = {}
        for item in entries:
            identity = dependency_key(item, model.properties)
            if self._is_import(item, model.properties):
                self._import_bom(imported, item, model.properties, trail)
            else:
                local[identity] = item.get("version", "")
        model.managed.update(imported)
        for name, version in local.items():
            if version:
                model.managed[name] = version

    @staticmethod
    def _is_import(item: dict[str, str], values: dict[str, str]) -> bool:
        """Отличить импортированный POM-BOM от обычной зависимости."""
        return (expand(item.get("scope", ""), values) == "import"
                and expand(item.get("type", "jar"), values) == "pom")

    def _import_bom(self, imported: dict[Identity, str], item: dict[str, str],
                    values: dict[str, str], trail: tuple[str, ...]) -> None:
        """Добавить BOM, сохранив приоритет первого импорта при совпадении."""
        name = package_name(item, values)
        version = expand(item.get("version", ""), values)
        bom = self._model(Coordinate.parse(f"{name}:{version}"), trail)
        for key, expression in bom.managed.items():
            imported.setdefault(key, expand(expression, bom.properties))

    @staticmethod
    def _declarations(model: Model, root) -> None:
        """Унаследовать объявления и перекрыть их полями текущего POM."""
        items = list(model.declarations.values())
        items.extend(declarations(root, "dependencies/dependency"))
        model.declarations = {}
        for item in items:
            identity = dependency_key(item, model.properties)
            inherited = model.declarations.get(identity, {})
            model.declarations[identity] = inherited | item
