"""Этап 2: получение прямых зависимостей Maven из POM."""

import argparse
from pathlib import Path
import sys

from src.config import load_config
from src.maven import MavenRepository


def run(path: Path) -> None:
    """Получить все прямые зависимости указанной версии через HTTP."""
    config = load_config(path)
    if config.test_mode:
        raise ValueError("тестовый режим доступен начиная с этапа 3")
    root = f"{config.package}:{config.version}"
    children = MavenRepository(config.repository).dependencies(root)
    print(f"Прямые зависимости {root}:")
    for child in children:
        print(child)
    if not children:
        print("(нет зависимостей)")


def main() -> int:
    """Прочитать путь CSV и сообщить об ошибке без traceback."""
    parser = argparse.ArgumentParser(
        description="Практическая работа 2, вариант 17, этап 2"
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
