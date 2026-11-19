"""CLI этапа 5 практической работы 2, вариант 17."""

import argparse
from pathlib import Path
import sys

from src.config import Config, load_config
from src.graph import Graph, Walker
from src.maven import MavenRepository
from src.test_repository import TestRepository
from src.visualization import iter_ascii_tree, write_visualization


def print_graph(graph: Graph) -> None:
    """Показать порядок DFS, рёбра, циклы и исключённые пакеты."""
    print("Обход DFS: " + (" ".join(graph.order) or "пустой граф"))
    for node, children in graph.edges.items():
        print(f"{node} -> {', '.join(children) or '(нет зависимостей)'}")
    for left, right in graph.cycles:
        print(f"Циклическое ребро: {left} -> {right}")
    if graph.excluded:
        print("Исключены: " + ", ".join(sorted(graph.excluded)))


def build_graph(config: Config) -> Graph:
    """Выбрать источник и обойти граф для заданного пакета."""
    if config.test_mode:
        repository = TestRepository(Path(config.repository))
        root = config.package
    else:
        repository = MavenRepository(config.repository)
        root = f"{config.package}:{config.version}"
    return Walker(repository, config.filter).build(root)


def run(path: Path) -> None:
    """Построить граф, сохранить D2/PNG и при запросе вывести ASCII."""
    config = load_config(path)
    input_paths = {path.resolve()}
    if config.test_mode:
        input_paths.add(Path(config.repository))
    outputs = {config.output, config.output.with_suffix(".d2")}
    if input_paths & outputs:
        raise ValueError("output: результат совпадает с входным файлом")
    graph = build_graph(config)
    package = f"{config.package}:{config.version}"
    labels = {config.package: package} if config.test_mode else {}
    source = write_visualization(graph, config.output, labels)
    print(f"Пакет: {package}")
    print_graph(graph)
    if config.ascii_tree:
        print("ASCII-дерево:")
        for line in iter_ascii_tree(graph, labels):
            print(line)
    print(f"D2: {source}")
    print(f"PNG: {config.output}")


def main() -> int:
    """Прочитать путь CSV и сообщить об ошибке без traceback."""
    parser = argparse.ArgumentParser(
        description="Практическая работа 2, вариант 17, этап 5"
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
