"""CLI первых трёх этапов практической работы 2, вариант 17."""

import argparse
from pathlib import Path
import sys

from src.config import load_config
from src.graph import Walker
from src.maven import MavenRepository
from src.test_repository import TestRepository


def print_graph(graph) -> None:
    """Показать порядок DFS, рёбра, циклы и исключённые пакеты."""
    print("Обход DFS: " + (" ".join(graph.order) or "пустой граф"))
    for node, children in graph.edges.items():
        print(f"{node} -> {', '.join(children) or '(нет зависимостей)'}")
    for left, right in graph.cycles:
        print(f"Циклическое ребро: {left} -> {right}")
    if graph.excluded:
        print("Исключены: " + ", ".join(sorted(graph.excluded)))


def run(path: Path) -> None:
    """Загрузить настройки и построить граф без создания изображений."""
    config = load_config(path)
    if config.test_mode:
        repository = TestRepository(Path(config.repository))
        root = config.package
    else:
        repository = MavenRepository(config.repository)
        root = f"{config.package}:{config.version}"
    print_graph(Walker(repository, config.filter).build(root))


def main() -> int:
    """Прочитать путь CSV и сообщить об ошибке без traceback."""
    parser = argparse.ArgumentParser(
        description="Практическая работа 2, вариант 17, этап 3"
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
