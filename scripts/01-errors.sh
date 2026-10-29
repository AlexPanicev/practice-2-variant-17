#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec "${PYTHON:-python3}" - <<'PY'
"""Показать по одной ожидаемой ошибке для каждого из семи полей CSV."""
import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile

EXPECTED_ERROR = 2
root = Path.cwd()
values = {
    "package": "junit:junit",
    "repository": "https://repo.maven.apache.org/maven2",
    "test_mode": "false", "version": "4.13.2",
    "output": "graph.png", "ascii_tree": "false", "filter": "",
}
invalid = {
    "package": "wrong", "repository": "ftp://repo.example",
    "test_mode": "maybe", "version": "[1,2)",
    "output": "graph.svg", "ascii_tree": "yes", "filter": "bad\nfilter",
}
with tempfile.TemporaryDirectory() as directory:
    config = Path(directory) / "invalid.csv"
    for field, value in invalid.items():
        with config.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["key", "value"])
            writer.writerows((values | {field: value}).items())
        result = subprocess.run(
            [str(root / "run.sh"), "--config", str(config)],
            env=os.environ | {"PYTHON": sys.executable},
            capture_output=True, text=True, check=False,
        )
        if result.returncode != EXPECTED_ERROR:
            raise SystemExit(f"{field}: ожидался код ошибки {EXPECTED_ERROR}")
        print(f"{field}: ожидаемая ошибка")
        print(result.stderr.strip())
print("Все семь ошибок параметров обработаны; рабочие файлы не менялись.")
PY
