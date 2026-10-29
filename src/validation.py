"""Проверки пользовательских значений конфигурации."""

import os
from pathlib import Path
import re
from urllib.parse import urlsplit


MAX_VERSION_LENGTH = 256
COMPONENT = r"[A-Za-z0-9_]+(?:[.-][A-Za-z0-9_]+)*"
VERSION = r"[A-Za-z0-9][A-Za-z0-9_.+-]*"


def clean_text(value: str, name: str, allow_empty: bool = False) -> str:
    """Отклонить пустое значение и управляющие символы."""
    if not value and not allow_empty:
        raise ValueError(f"{name}: значение не должно быть пустым")
    if any(not char.isprintable() for char in value):
        raise ValueError(f"{name}: управляющие символы запрещены")
    return value


def boolean(value: str, name: str) -> bool:
    """Принять только однозначные значения true и false."""
    clean_text(value, name)
    if value.lower() not in ("true", "false"):
        raise ValueError(f"{name}: допустимы только true и false")
    return value.lower() == "true"


def package_name(value: str, test_mode: bool) -> str:
    """Проверить Maven groupId:artifactId или тестовое имя A-Z."""
    clean_text(value, "package")
    pattern = r"[A-Z]+" if test_mode else f"{COMPONENT}:{COMPONENT}"
    if not re.fullmatch(pattern, value):
        expected = "имя из букв A-Z" if test_mode else "groupId:artifactId"
        raise ValueError(f"package: требуется {expected}")
    return value


def fixed_version(value: str) -> str:
    """Проверить фиксированную версию, без диапазонов и SNAPSHOT."""
    clean_text(value, "version")
    if len(value) > MAX_VERSION_LENGTH:
        raise ValueError("version: слишком длинная версия")
    if value.upper() in ("LATEST", "RELEASE", "SNAPSHOT"):
        raise ValueError("version: требуется фиксированная release-версия")
    if value.upper().endswith("-SNAPSHOT"):
        raise ValueError("version: SNAPSHOT пока не поддерживается")
    if not re.fullmatch(VERSION, value):
        raise ValueError("version: неверная фиксированная версия")
    return value


def resolved_path(value: str, base: Path) -> Path:
    """Разрешить относительный путь от каталога файла CSV."""
    try:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else base / path).resolve()
    except (OSError, RuntimeError) as error:
        raise ValueError("путь: невозможно разрешить путь") from error


def repository(value: str, test_mode: bool, base: Path) -> str:
    """Проверить локальный файл либо HTTP(S) URL репозитория."""
    clean_text(value, "repository")
    if test_mode:
        path = resolved_path(value, base)
        if not _readable_file(path):
            message = "repository: тестовый файл не найден или недоступен"
            raise ValueError(message)
        return str(path)
    return repository_url(value)


def _readable_file(path: Path) -> bool:
    """Проверить чтение файла, не пропуская ошибки файловой системы."""
    try:
        return path.is_file() and os.access(path, os.R_OK)
    except OSError as error:
        raise ValueError("repository: недоступный путь к файлу") from error


def repository_url(value: str) -> str:
    """Отклонить URL без хоста, с паролем, запросом или неверным портом."""
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as error:
        raise ValueError("repository: неверный URL или порт") from error
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("repository: требуется URL http:// или https://")
    if parts.username is not None or parts.password is not None:
        raise ValueError("repository: учётные данные в URL запрещены")
    _url_tail(value)
    if port == 0:
        raise ValueError("repository: порт должен быть положительным")
    return value.rstrip("/")


def _url_tail(value: str) -> None:
    """Запретить добавочные URI-компоненты и пробельные символы."""
    if any(char in value for char in "?#\\"):
        message = "repository: запрос, фрагмент и обратный слеш запрещены"
        raise ValueError(message)
    if any(char.isspace() for char in value):
        raise ValueError("repository: пробелы в URL запрещены")


def output_path(value: str, base: Path) -> Path:
    """Проверить путь PNG, не создавая и не перезаписывая файл."""
    clean_text(value, "output")
    if value.endswith(("/", "\\")):
        raise ValueError("output: требуется имя файла, не каталог")
    path = resolved_path(value, base)
    if path.suffix.lower() != ".png" or path.name.lower() == ".png":
        raise ValueError("output: требуется имя файла с расширением .png")
    _output_location(path)
    return path


def _output_location(path: Path) -> None:
    """Проверить доступность папки и тип существующего пути."""
    try:
        if not path.parent.is_dir() or not os.access(path.parent, os.W_OK):
            raise ValueError("output: родительская папка недоступна для записи")
        if path.exists() and not path.is_file():
            raise ValueError("output: путь указывает не на обычный файл")
    except OSError as error:
        raise ValueError("output: недоступный путь к файлу") from error
