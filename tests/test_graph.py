"""Проверки DFS без рекурсии, циклов и фильтрации имён."""

import unittest

from src.graph import Walker


class MemoryRepository:
    """Наблюдаемый источник без диска и сети."""

    def __init__(self, edges: dict[str, list[str]]) -> None:
        """Сохранить граф и журнал обращений."""
        self.edges = edges
        self.calls = []

    def dependencies(self, node: str) -> list[str]:
        """Вернуть прямые зависимости и отметить загрузку."""
        self.calls.append(node)
        if node not in self.edges:
            raise ValueError(f"нет пакета: {node}")
        return self.edges[node]


class GraphTests(unittest.TestCase):
    """Точный порядок обнаружения, рёбра и отсутствие повторных загрузок."""

    def test_chain(self) -> None:
        """Обойти цепочку до листа."""
        graph = Walker(MemoryRepository({"A": ["B"], "B": []})).build("A")
        self.assertEqual(graph.order, ["A", "B"])
        self.assertEqual(graph.edges, {"A": ("B",), "B": ()})
        self.assertEqual(graph.cycles, [])

    def test_diamond_is_not_cycle(self) -> None:
        """Общий потомок загружается один раз и не считается циклом."""
        repo = MemoryRepository({"A": ["B", "C"], "B": ["D"],
                                 "C": ["D"], "D": []})
        graph = Walker(repo).build("A")
        self.assertEqual(graph.order, ["A", "B", "D", "C"])
        self.assertEqual(repo.calls, graph.order)
        self.assertEqual(graph.edges["C"], ("D",))
        self.assertEqual(graph.cycles, [])

    def test_cycle_retains_edge(self) -> None:
        """Обнаружить обратное ребро без потери самого ребра."""
        repo = MemoryRepository({"A": ["B"], "B": ["C"], "C": ["A"]})
        graph = Walker(repo).build("A")
        self.assertEqual(graph.cycles, [("C", "A")])
        self.assertEqual(graph.edges["C"], ("A",))
        self.assertEqual(repo.calls, ["A", "B", "C"])

    def test_self_cycle(self) -> None:
        """Остановить самозависимость и сохранить её в результате."""
        graph = Walker(MemoryRepository({"A": ["A"]})).build("A")
        self.assertEqual(graph.cycles, [("A", "A")])

    def test_filter_cuts_subtree_without_fetch(self) -> None:
        """Исключённый пакет и доступные только через него узлы не читать."""
        repo = MemoryRepository({"A": ["B", "C"], "C": []})
        graph = Walker(repo, "B").build("A")
        self.assertEqual(graph.order, ["A", "C"])
        self.assertEqual(repo.calls, ["A", "C"])
        self.assertEqual(graph.edges["A"], ("C",))
        self.assertEqual(graph.excluded, {"B"})

    def test_root_excluded(self) -> None:
        """Исключённый корень не требует чтения репозитория."""
        repo = MemoryRepository({})
        graph = Walker(repo, "A").build("A")
        self.assertEqual(graph.order, [])
        self.assertEqual(repo.calls, [])
        self.assertEqual(graph.excluded, {"A"})

    def test_filter_ignores_maven_version(self) -> None:
        """Искать подстроку в group:artifact, не в версии."""
        repo = MemoryRepository({"g:a:17": []})
        graph = Walker(repo, "17").build("g:a:17")
        self.assertEqual(graph.order, ["g:a:17"])

    def test_filter_shared_descendant_still_reachable(self) -> None:
        """Достичь общего потомка через другую не исключённую ветвь."""
        repo = MemoryRepository({"A": ["B", "C"], "C": ["D"], "D": []})
        self.assertEqual(Walker(repo, "B").build("A").order,
                         ["A", "C", "D"])

    def test_duplicate_edges_and_reuse(self) -> None:
        """Убрать повтор ребра и сбросить состояние перед новым обходом."""
        repo = MemoryRepository({"A": ["B", "B"], "B": []})
        walker = Walker(repo)
        first = walker.build("A")
        second = walker.build("B")
        self.assertEqual(first.edges["A"], ("B",))
        self.assertEqual(second.order, ["B"])

    def test_missing_node_is_error(self) -> None:
        """Не заменять отсутствие данных пустым списком зависимостей."""
        with self.assertRaisesRegex(ValueError, "нет пакета"):
            Walker(MemoryRepository({"A": ["B"]})).build("A")

    def test_deep_graph_without_recursion(self) -> None:
        """Обойти 5001 вершину, превысив обычный предел рекурсии Python."""
        length = 5000
        edges = {f"N{i}": [f"N{i + 1}"] for i in range(length)}
        edges[f"N{length}"] = []
        graph = Walker(MemoryRepository(edges)).build("N0")
        self.assertEqual(len(graph.order), length + 1)
        self.assertEqual(graph.order[-1], f"N{length}")
