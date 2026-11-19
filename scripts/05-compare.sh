#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec "${PYTHON:-python3}" -m scripts.compare_maven --tree "$@"
