"""Представление полного графа в D2, PNG и текстовом дереве."""

import json
from os import SEEK_END
from pathlib import Path
import struct
import subprocess
import tempfile
from typing import Iterator

from src.graph import Graph


D2_TIMEOUT = 120
EMPTY_GRAPH = "(empty graph)"
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
PNG_END = b"\x00\x00\x00\x00IEND\xaeB`\x82"
PNG_DIMENSIONS = struct.Struct(">II")


def d2_source(graph: Graph, labels: dict[str, str]) -> str:
    """Описать все вершины и рёбра, включая обратные и повторные."""
    identifiers = {node: f"n{i}" for i, node in enumerate(graph.order, 1)}
    lines = ["direction: right"]
    if not identifiers:
        lines.append(f'empty: "{EMPTY_GRAPH}"')
    for node, identifier in identifiers.items():
        label = json.dumps(labels.get(node, node), ensure_ascii=False)
        label = label.replace("$", r"\$")
        lines.append(f"{identifier}: {label}")
    for node, children in graph.edges.items():
        for child in children:
            lines.append(f"{identifiers[node]} -> {identifiers[child]}")
    return "\n".join(lines) + "\n"


def _has_png_boundaries(path: Path) -> bool:
    """Проверить сигнатуру, размеры и завершающий блок PNG."""
    with path.open("rb") as stream:
        if stream.read(len(PNG_HEADER)) != PNG_HEADER:
            return False
        dimensions = stream.read(PNG_DIMENSIONS.size)
        if len(dimensions) != PNG_DIMENSIONS.size:
            return False
        if not all(PNG_DIMENSIONS.unpack(dimensions)):
            return False
        stream.seek(-len(PNG_END), SEEK_END)
        return stream.read() == PNG_END


def _render_png(source: Path, output: Path) -> None:
    """Запустить D2 и проверить, что он сформировал PNG."""
    command = ["d2", "--layout=dagre", str(source), str(output)]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, errors="replace",
            stdin=subprocess.DEVNULL, timeout=D2_TIMEOUT, check=False,
        )
    except FileNotFoundError as error:
        raise ValueError("D2: команда d2 не найдена в PATH") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"D2: превышен лимит {D2_TIMEOUT} секунд") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"D2: {detail or 'ошибка рендеринга'}")
    if not output.is_file() or not _has_png_boundaries(output):
        raise ValueError("D2: не получен корректный PNG")


def write_visualization(
    graph: Graph, output: Path, labels: dict[str, str],
) -> Path:
    """Сохранить PNG и соседний D2 после успешного рендеринга."""
    source = output.with_suffix(".d2")
    if any(path.exists() and not path.is_file() for path in (output, source)):
        raise ValueError("D2: путь PNG или D2 занят, требуется обычный файл")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        folder = Path(directory)
        draft_source = folder / "graph.d2"
        draft_output = folder / "graph.png"
        draft_source.write_text(d2_source(graph, labels), encoding="utf-8")
        _render_png(draft_source, draft_output)
        draft_source.replace(source)
        draft_output.replace(output)
    return source


def iter_ascii_tree(graph: Graph, labels: dict[str, str]) -> Iterator[str]:
    """Печатать каждое ребро, разворачивая вершину только один раз."""
    if not graph.order:
        yield EMPTY_GRAPH
        return
    root = graph.order[0]
    yield labels.get(root, root)
    stack = [(root, enumerate(graph.edges[root]))]
    prefixes = [""]
    visited = {root}
    active = {root}
    while stack:
        node, children = stack[-1]
        branch = next(children, None)
        if branch is None:
            active.remove(node)
            stack.pop()
            prefixes.pop()
            continue
        index, child = branch
        last = index + 1 == len(graph.edges[node])
        connector = "`-- " if last else "|-- "
        line = "".join(prefixes) + connector + labels.get(child, child)
        if child in active:
            yield line + " [cycle]"
        elif child in visited:
            yield line + " [shared]"
        else:
            yield line
            visited.add(child)
            active.add(child)
            stack.append((child, enumerate(graph.edges[child])))
            prefixes.append("    " if last else "|   ")
