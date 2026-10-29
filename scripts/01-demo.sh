#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
./run.sh --config configs/maven.csv
