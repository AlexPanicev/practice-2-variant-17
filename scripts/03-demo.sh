#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for name in chain diamond cycle self isolated filter; do
  ./run.sh --config "configs/$name.csv"
done
