"""Этап 1: CSV-конфигурация и вывод всех семи параметров."""

import argparse
from dataclasses import fields
from pathlib import Path
import sys

from src.config import load_config


def run(path: Path) -> None:
    """Проверить CSV и вывести семь пар ключ-значение без сети."""
    config = load_config(path)
    for item in fields(config):
        value = getattr(config, item.name)
        if isinstance(value, bool):
            value = str(value).lower()
        print(f"{item.name}={value}")


def main() -> int:
    """Прочитать путь CSV и сообщить об ошибке без traceback."""
    parser = argparse.ArgumentParser(
        description="Практическая работа 2, вариант 17, этап 1"
    )
    parser.add_argument(
        "--config", type=Path, default=Path("configs/maven.csv"),
        help="путь к CSV с параметрами",
    )
    args = parser.parse_args()
    try:
        run(args.config)
    except (ValueError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
