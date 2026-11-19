#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mode=${1:-all}
case $mode in
  test) names="chain diamond cycle self isolated filter" ;;
  maven) names="maven gson slf4j" ;;
  all) names="chain diamond cycle self isolated filter maven gson slf4j" ;;
  *)
    printf 'Использование: %s [test|maven|all]\n' "$0" >&2
    exit 2
    ;;
esac
for name in $names; do
  printf '\n--- %s ---\n' "$name"
  ./run.sh --config "configs/$name.csv"
done
