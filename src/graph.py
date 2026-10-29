"""Итеративный DFS: полный граф, фильтр имён и циклические рёбра."""

from dataclasses import dataclass, field
from typing import Iterator, Protocol


ACTIVE = 1
FINISHED = 2


class Repository(Protocol):
    """Источник прямых зависимостей одного узла."""

    def dependencies(self, node: str) -> list[str]:
        """Вернуть имена прямых зависимостей или сообщить об ошибке."""
        ...


@dataclass
class Graph:
    """Граф и порядок обнаружения вершин при DFS."""

    edges: dict[str, tuple[str, ...]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    cycles: list[tuple[str, str]] = field(default_factory=list)
    excluded: set[str] = field(default_factory=set)


def package_name(node: str) -> str:
    """Отделить имя Maven-пакета от версии, сохранив тестовое имя."""
    return ":".join(node.split(":")[:2])


class Walker:
    """Обойти зависимости стеком итераторов без рекурсивных вызовов."""

    def __init__(self, repository: Repository, substring: str = "") -> None:
        """Сохранить источник и правило исключения пакетов."""
        self.repository = repository
        self.substring = substring
        self.graph = Graph()
        self.states: dict[str, int] = {}
        self.stack: list[tuple[str, Iterator[str]]] = []

    def build(self, root: str) -> Graph:
        """Построить граф; исключённый корень не загружается."""
        self.graph = Graph()
        self.states.clear()
        self.stack.clear()
        if self._excluded(root):
            return self.graph
        self._enter(root)
        while self.stack:
            self._step()
        return self.graph

    def _excluded(self, node: str) -> bool:
        """Исключить узел по имени, не по номеру его версии."""
        if self.substring and self.substring in package_name(node):
            self.graph.excluded.add(node)
            return True
        return False

    def _enter(self, node: str) -> None:
        """Прочитать соседей и добавить кадр на явный стек."""
        children = self.repository.dependencies(node)
        neighbors = tuple(child for child in dict.fromkeys(children)
                          if not self._excluded(child))
        self.graph.edges[node] = neighbors
        self.graph.order.append(node)
        self.states[node] = ACTIVE
        self.stack.append((node, iter(neighbors)))

    def _step(self) -> None:
        """Обработать одно ребро или завершить текущую вершину."""
        node, children = self.stack[-1]
        try:
            child = next(children)
        except StopIteration:
            self.stack.pop()
            self.states[node] = FINISHED
            return
        state = self.states.get(child)
        if state == ACTIVE:
            self.graph.cycles.append((node, child))
        elif state != FINISHED:
            self._enter(child)
