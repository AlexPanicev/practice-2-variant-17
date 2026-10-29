"""Чтение POM и подстановка свойств средствами стандартной библиотеки."""

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree

from src.coordinates import Coordinate


PROPERTY = re.compile(r"\$\{([^}]+)\}")
MAX_EXPANSIONS = 32
Identity = tuple[str, str, str]


@dataclass
class Model:
    """Эффективные свойства, управляемые версии и объявления зависимостей."""

    properties: dict[str, str] = field(default_factory=dict)
    managed: dict[Identity, str] = field(default_factory=dict)
    declarations: dict[Identity, dict[str, str]] = field(default_factory=dict)


def parse_document(data: bytes) -> ElementTree.Element:
    """Прочитать POM, отклоняя DTD, сущности и неверный корень."""
    scan = data.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in scan or b"<!ENTITY" in scan:
        raise ValueError("Maven: DTD и XML-сущности не поддерживаются")
    try:
        root = ElementTree.fromstring(data)
    except (ElementTree.ParseError, LookupError, ValueError) as error:
        raise ValueError(f"Maven: повреждённый POM: {error}") from error
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    if root.tag != "project":
        raise ValueError("Maven: корневой элемент POM должен быть project")
    return root


def value(element: ElementTree.Element, name: str) -> str:
    """Прочитать строковое поле XML без окружающих пробелов."""
    return (element.findtext(name) or "").strip()


def properties(root: ElementTree.Element) -> dict[str, str]:
    """Извлечь свойства только из корневого properties, без профилей."""
    return {item.tag: (item.text or "").strip()
            for item in root.findall("properties/*")}


def expand(text: str, values: dict[str, str]) -> str:
    """Подставить вложенные свойства с обнаружением циклов и неизвестных."""
    seen = set()
    for _ in range(MAX_EXPANSIONS):
        if not PROPERTY.search(text):
            return text
        if text in seen:
            raise ValueError("Maven: цикл подстановки свойств")
        seen.add(text)
        text = PROPERTY.sub(lambda match: property_value(match, values), text)
    raise ValueError("Maven: слишком глубокая подстановка свойств")


def property_value(match: re.Match, values: dict[str, str]) -> str:
    """Вернуть значение свойства, не обращаясь к окружению компьютера."""
    key = match.group(1)
    if key not in values:
        raise ValueError(f"Maven: неизвестное свойство ${{{key}}}")
    return values[key]


def aliases(coordinate: Coordinate) -> dict[str, str]:
    """Создать project.*, pom.* и краткие имена координат проекта."""
    fields = {"groupId": coordinate.group, "artifactId": coordinate.artifact,
              "version": coordinate.version}
    return {prefix + key: item for prefix in ("", "project.", "pom.")
            for key, item in fields.items()}


def parent_coordinate(root: ElementTree.Element,
                      values: dict[str, str]) -> Coordinate | None:
    """Прочитать ссылку на родителя без использования relativePath."""
    parent = root.find("parent")
    if parent is None:
        return None
    parts = [expand(value(parent, key), values)
             for key in ("groupId", "artifactId", "version")]
    return Coordinate.parse(":".join(parts))


def declarations(root: ElementTree.Element,
                 path: str) -> list[dict[str, str]]:
    """Прочитать объявления из заданного корневого раздела зависимостей."""
    return [{child.tag: (child.text or "").strip() for child in item
             if len(child) == 0}
            for item in root.findall(path)]


def package_name(item: dict[str, str], values: dict[str, str]) -> str:
    """Разрешить groupId и artifactId объявления зависимости."""
    group = expand(item.get("groupId", ""), values)
    artifact = expand(item.get("artifactId", ""), values)
    Coordinate.parse(f"{group}:{artifact}:1")
    return f"{group}:{artifact}"


def dependency_key(item: dict[str, str],
                   values: dict[str, str]) -> Identity:
    """Различать объявления по groupId:artifactId, type и classifier."""
    return (package_name(item, values),
            expand(item.get("type") or "jar", values),
            expand(item.get("classifier", ""), values))


def check_identity(root: ElementTree.Element, coordinate: Coordinate,
                   values: dict[str, str]) -> None:
    """Проверить соответствие POM запрошенным координатам."""
    actual = []
    for key, fallback in (("groupId", "parent/groupId"),
                          ("artifactId", "artifactId"),
                          ("version", "parent/version")):
        actual.append(expand(value(root, key) or value(root, fallback),
                             values))
    if ":".join(actual) != coordinate.label:
        raise ValueError(f"Maven: координаты POM не совпадают: "
                         f"{coordinate.label}")
