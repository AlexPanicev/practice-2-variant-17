#!/bin/sh
set -eu
"${PYTHON:-python3}" --version
if command -v d2 >/dev/null 2>&1; then
  printf 'D2 '
  d2 version
else
  printf 'D2: команда d2 не найдена в PATH\n'
fi
maven=${MAVEN:-mvn}
if command -v "$maven" >/dev/null 2>&1; then
  "$maven" --version
else
  printf 'Maven: команда mvn не найдена в PATH\n'
  if command -v java >/dev/null 2>&1; then
    java -version
  fi
fi
