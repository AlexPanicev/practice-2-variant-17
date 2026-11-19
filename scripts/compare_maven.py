"""Сравнить результаты с нативным Maven в отдельном проекте-потребителе."""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from src.config import load_config
from src.coordinates import Coordinate


ROOT = Path(__file__).resolve().parents[1]
POM = ROOT / "comparison/pom.xml"
OUTPUT = ROOT / "output/maven"
TIMEOUT_SECONDS = 300
TRANSFER = re.compile(r"Downloaded from [^:]+: (\S+\.jar)(?=\s|$)")
GOALS = {
    "classpath": ("dependency:build-classpath@runtime-classpath",),
    "tree": ("dependency:tree@console-tree", "dependency:tree@dot-tree"),
}


def run_maven(
    mode: str, package: Coordinate, repository: str, folder: Path, cache: Path,
) -> str:
    """Вызвать нужную цель Maven и вернуть журнал для сравнения."""
    maven = shutil.which(os.environ.get("MAVEN") or "mvn")
    if maven is None:
        raise ValueError("не найден mvn; установите Maven или задайте MAVEN")
    command = [
        str(Path(maven).absolute()), "-B", "-Dstyle.color=never",
        "-f", str(POM),
        f"-Dmaven.repo.local={cache}", f"-Dcompare.output={folder}",
        f"-Dcompare.repository={repository}",
        f"-Dcompare.group={package.group}",
        f"-Dcompare.artifact={package.artifact}",
        f"-Dcompare.version={package.version}", *GOALS[mode],
    ]
    try:
        result = subprocess.run(
            command, cwd=folder, capture_output=True, encoding="utf-8",
            errors="replace", timeout=TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired as error:
        message = f"Maven не завершился за {TIMEOUT_SECONDS} секунд"
        raise ValueError(message) from error
    if result.returncode:
        lines = (result.stdout + result.stderr).splitlines()
        messages = [line for line in lines if line.startswith("[ERROR]")]
        diagnostic = "\n".join(messages or lines[-1:])
        raise ValueError(f"Maven завершился с кодом {result.returncode}\n"
                         f"{diagnostic}")
    return result.stdout


def classpath_artifacts(path: Path, cache: Path) -> dict[str, str]:
    """Прочитать JAR в порядке classpath и восстановить координаты."""
    value = path.read_text(encoding="utf-8").strip()
    artifacts = {}
    for entry in filter(None, value.split(os.pathsep)):
        relative = Path(entry).relative_to(cache)
        group = ".".join(relative.parts[:-3])
        artifact, version, _ = relative.parts[-3:]
        artifacts[relative.as_posix()] = f"{group}:{artifact}:{version}"
    return artifacts


def completed_downloads(log: str, artifacts: dict[str, str]) -> list[str]:
    """Выделить завершённые передачи JAR, попавших в classpath."""
    downloads = []
    for url in TRANSFER.findall(log):
        path = unquote(urlsplit(url).path)
        match = next((label for jar, label in artifacts.items()
                      if path.endswith(f"/{jar}")), None)
        if match is not None:
            downloads.append(match)
    return downloads


def print_classpath(folder: Path, cache: Path, log: str) -> None:
    """Показать отдельно порядок classpath и завершение скачиваний."""
    artifacts = classpath_artifacts(folder / "classpath.txt", cache)
    print("Classpath Maven (runtime, порядок записи):")
    print("\n".join(artifacts.values()) or "(пусто)")
    print("JAR из classpath, скачанные в этом запуске (порядок завершения):")
    downloads = completed_downloads(log, artifacts)
    print("\n".join(downloads) or "(новых скачиваний не было)")


def show_tree(folder: Path, package: Coordinate) -> None:
    """Показать штатное дерево и сохранить текст и DOT."""
    report = OUTPUT / "reports" / package.group / package.artifact
    report /= package.version
    report.mkdir(parents=True, exist_ok=True)
    print((folder / "tree.txt").read_text(encoding="utf-8").rstrip())
    for name in ("tree.txt", "tree.dot"):
        (folder / name).replace(report / name)
    print(f"Штатный граф Maven (DOT): {report / 'tree.dot'}")


def compare(mode: str, path: Path, fresh: bool) -> None:
    """Выполнить контрольный запуск для реального пакета, указанного в CSV."""
    config = load_config(path)
    if config.test_mode:
        raise ValueError("сравнение Maven требует CSV с test_mode=false")
    package = Coordinate.parse(f"{config.package}:{config.version}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print(f"Пакет для сравнения: {package.label}", flush=True)
    with TemporaryDirectory(prefix="run-", dir=OUTPUT) as directory:
        folder = Path(directory)
        cache = (folder if fresh else OUTPUT) / "repository"
        log = run_maven(mode, package, config.repository, folder, cache)
        if mode == "classpath":
            print_classpath(folder, cache, log)
        else:
            show_tree(folder, package)


def main() -> int:
    """Разобрать параметры и завершиться с понятным сообщением при ошибке."""
    parser = argparse.ArgumentParser(description="Штатное сравнение с Maven")
    parser.add_argument(
        "config", type=Path, nargs="?", default=Path("configs/maven.csv"),
        help="CSV с координатами реального пакета",
    )
    parser.add_argument(
        "--fresh", action="store_true", help="использовать новый кэш Maven",
    )
    parser.add_argument(
        "--tree", action="store_true", help="вывести текст и DOT",
    )
    args = parser.parse_args()
    try:
        compare("tree" if args.tree else "classpath",
                args.config, args.fresh)
    except (OSError, ValueError) as error:
        print(f"Ошибка сравнения: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
