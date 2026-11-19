#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for name in chain diamond cycle self isolated filter; do
  printf '\n--- %s ---\n' "$name"
  ./run.sh --config "configs/$name.csv"
done
