"""Координаты и фиксированные версии артефактов Maven."""

import re
from dataclasses import dataclass


PART = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*\Z")
MAX_VERSION_LENGTH = 256


@dataclass(frozen=True)
class Coordinate:
    """Адрес артефакта groupId:artifactId:version."""

    group: str
    artifact: str
    version: str

    @classmethod
    def parse(cls, text: str) -> "Coordinate":
        """Разобрать три компонента без динамических версий и путей."""
        parts = text.split(":")
        if len(parts) != len(cls.__dataclass_fields__):
            raise ValueError("Maven: ожидается groupId:artifactId:version")
        result = cls(*parts)
        if not all(PART.fullmatch(p) for p in (result.group, result.artifact)):
            raise ValueError("Maven: недопустимые groupId или artifactId")
        if any(not part for part in result.group.split(".")):
            raise ValueError("Maven: пустая часть groupId")
        validate_version(result.version)
        return result

    @property
    def label(self) -> str:
        """Получить строковое представление координат."""
        return f"{self.group}:{self.artifact}:{self.version}"

    @property
    def package(self) -> str:
        """Получить имя пакета без версии."""
        return f"{self.group}:{self.artifact}"

    @property
    def pom_path(self) -> str:
        """Получить относительный путь POM в репозитории Maven."""
        group_path = self.group.replace(".", "/")
        filename = f"{self.artifact}-{self.version}.pom"
        return f"{group_path}/{self.artifact}/{self.version}/{filename}"


def validate_version(value: str) -> None:
    """Требовать конкретную release-версию вместо диапазона или SNAPSHOT."""
    if not VERSION.fullmatch(value) or len(value) > MAX_VERSION_LENGTH:
        raise ValueError("Maven: требуется точная фиксированная версия")
    if value.upper() in ("LATEST", "RELEASE"):
        raise ValueError("Maven: динамические версии не поддерживаются")
    if value.upper().endswith("-SNAPSHOT"):
        raise ValueError("Maven: SNAPSHOT не поддерживается, задайте release")
