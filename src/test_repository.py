"""Тестовый репозиторий: JSON-объект со списками зависимостей."""

import json
from pathlib import Path
import re


NAME_PATTERN = re.compile(r"[A-Z]+")


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Отклонить повторяющиеся ключи JSON вместо тихой перезаписи."""
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"повторяющийся пакет: {name}")
        result[name] = value
    return result


def validate_graph(data: object) -> dict[str, list[str]]:
    """Проверить имена, списки и наличие всех упомянутых вершин."""
    if not isinstance(data, dict) or not data:
        raise ValueError("тестовый репозиторий: нужен непустой JSON-объект")
    for name, children in data.items():
        validate_node(name, children)
    missing = {child for children in data.values() for child in children
               if child not in data}
    if missing:
        raise ValueError("не описаны пакеты: " + ", ".join(sorted(missing)))
    return data


def validate_node(name: str, children: object) -> None:
    """Потребовать имена из больших латинских букв и список строк."""
    if not NAME_PATTERN.fullmatch(name):
        raise ValueError(f"недопустимое имя тестового пакета: {name}")
    if not isinstance(children, list):
        raise ValueError(f"зависимости {name}: требуется список")
    if any(not isinstance(child, str) for child in children):
        raise ValueError(f"зависимости {name}: имена должны быть строками")
    if any(not NAME_PATTERN.fullmatch(child) for child in children):
        raise ValueError(f"зависимости {name}: нужны большие латинские буквы")


class TestRepository:
    """Загрузить локальный граф без сетевых обращений."""

    def __init__(self, path: Path) -> None:
        """Прочитать и проверить весь файл описания графа."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"),
                              object_pairs_hook=unique_object)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"тестовый репозиторий: {error}") from error
        self.graph = validate_graph(data)

    def dependencies(self, node: str) -> list[str]:
        """Вернуть копию списка, не позволяя менять источник."""
        if node not in self.graph:
            raise ValueError(f"пакет отсутствует в тестовом графе: {node}")
        return list(self.graph[node])
