"""Чтение конфигурации CSV для варианта 17."""

import csv
from dataclasses import dataclass
from pathlib import Path

from src import validation


FIELDS = (
    "package", "repository", "test_mode", "version", "output",
    "ascii_tree", "filter",
)
ROW_WIDTH = 2


@dataclass(frozen=True)
class Config:
    """Семь параметров пользователя с нормализованными путями."""

    package: str
    repository: str
    test_mode: bool
    version: str
    output: Path
    ascii_tree: bool
    filter: str


def _read_rows(path: Path) -> list[list[str]]:
    """Прочитать строгий UTF-8 CSV и сообщить об ошибке файла."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.reader(stream, strict=True))
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        raise ValueError("config: невозможно прочитать корректный UTF-8 CSV") \
            from error


def _values(rows: list[list[str]]) -> dict[str, str]:
    """Проверить заголовок, форму строк и набор уникальных ключей."""
    if not rows or rows[0] != ["key", "value"]:
        raise ValueError("config: первая строка должна быть key,value")
    result = {}
    for number, row in enumerate(rows[1:], 2):
        if len(row) != ROW_WIDTH:
            raise ValueError(f"config: строка {number} должна иметь два поля")
        key = row[0].strip()
        value = validation.clean_text(row[1], key, True).strip()
        if key not in FIELDS:
            raise ValueError(f"config: неизвестный ключ в строке {number}")
        if key in result:
            raise ValueError(f"config: повторяющийся ключ {key}")
        result[key] = value
    missing = set(FIELDS) - result.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError("config: отсутствуют ключи " + names)
    return result


def load_config(path: Path) -> Config:
    """Загрузить и проверить все семь настроек, не изменяя файлов."""
    path = Path(path)
    values = _values(_read_rows(path))
    base = path.resolve().parent
    test_mode = validation.boolean(values["test_mode"], "test_mode")
    return Config(
        package=validation.package_name(values["package"], test_mode),
        repository=validation.repository(values["repository"], test_mode, base),
        test_mode=test_mode,
        version=validation.fixed_version(values["version"]),
        output=validation.output_path(values["output"], base),
        ascii_tree=validation.boolean(values["ascii_tree"], "ascii_tree"),
        filter=validation.clean_text(values["filter"], "filter", True),
    )
