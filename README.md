# Практическая работа 2, вариант 17: этап 3

Дисциплина «Конфигурационное управление», ИКБО-40-25.
CLI-инструмент анализа зависимостей пакетов Java (Maven).
Источник задания: сборник практических работ №2, вариант 17, страницы56-58.
Оформление проверяется по правилам страниц4-7 первой и второй методичек.

Реализованы только первые три этапа. `main` совпадает с `stage-3`.
Каждая ветка содержит код своего этапа, один коммит на этап:

- [Этап 1: CSV-конфигурация](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-1)
- [Этап 2: прямые зависимости Maven](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-2)
- [Этап 3: итеративный DFS](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-3)

Текущий документ описывает снимок этапа 3. Параметры `output` и
`ascii_tree` проверяются, но создание PNG/D2 и ASCII-дерево относятся
к этапу5 и пока не выполняются. Порядок загрузки этапа4 не вычисляется.

## Подготовка и выбор этапа

Требуется Python3.10+. На Mac можно использовать `python3.12`.
Сборка не нужна. Runtime не требует внешних пакетов, Java, Maven или Tkinter.
Для получения зависимостей используются только urllib и XML-парсер Python.

Первое скачивание (если папки проекта ещё нет):

```sh
git clone https://github.com/AlexPanicev/practice-2-variant-17.git
cd practice-2-variant-17
```

Если проект уже скачан на этом Mac:

```sh
cd "/Users/alex/Desktop/Учеба/Конфиг/practice-2-variant-17"
```

Выбор именно этого этапа:

```sh
git fetch origin
git switch stage-3
```

Переключайте ветки при чистой рабочей папке (`git status --short` без вывода).
Все команды выполняются в настоящем терминале, графического окна нет.
`PYTHON=python3.12` выбирает интерпретатор для скрипта и вложенных запусков.
Без этой переменной `run.sh` вызывает `python3`.

## Конфигурация CSV

Параметры приложения берутся из CSV. CLI имеет только `--config`, который
выбирает файл настроек; `--help` выводит справку.
Пример `configs/maven.csv`:

```text
key,value
package,junit:junit
repository,https://repo.maven.apache.org/maven2
test_mode,false
version,4.13.2
output,../output.png
ascii_tree,false
filter,
```

Все семь ключей обязательны, неизвестные и повторяющиеся ключи запрещены.
Файл UTF-8, первая строка строго `key,value`. Значения с запятыми
заключаются в двойные кавычки по правилам CSV. Пути внутри CSV отсчитываются
от каталога самого CSV, а не от рабочего каталога терминала.

| Поле | Назначение и проверка |
| --- | --- |
| `package` | Maven groupId:artifactId; в тестовом режиме имя из A-Z. |
| `repository` | URL HTTP(S) либо путь к существующему файлу графа. |
| `test_mode` | Только true/false, регистр не важен. |
| `version` | Фиксированная release-версия; не диапазон и не SNAPSHOT. |
| `output` | Путь PNG с существующей доступной для записи папкой. |
| `ascii_tree` | Только true/false; функция появится на этапе5. |
| `filter` | Подстрока имени; пустая строка отключает фильтр. |

URL с учётными данными, запросом или фрагментом не принимается.
Некорректный CSV/параметр даёт понятную ошибку и код завершения2,
без traceback. Корректный запуск завершается с кодом0.
Проверка параметров не создаёт и не перезаписывает выходной PNG.

## Запуск этого этапа

Локальные сценарии без сети:

```sh
PYTHON=python3.12 ./scripts/03-demo.sh
```

Последовательно проверяются цепочка, ромб с общим потомком, цикл,
самозависимость, изолированная вершина и фильтрация ветви.
Все сценарии завершаются сами, ждать закрытия окна не нужно.
Отдельные запуски:

```sh
PYTHON=python3.12 ./run.sh --config configs/chain.csv
PYTHON=python3.12 ./run.sh --config configs/diamond.csv
PYTHON=python3.12 ./run.sh --config configs/cycle.csv
PYTHON=python3.12 ./run.sh --config configs/self.csv
PYTHON=python3.12 ./run.sh --config configs/isolated.csv
PYTHON=python3.12 ./run.sh --config configs/filter.csv
```

Для цепочки ожидается:

```text
Обход DFS: A B C
A -> B
B -> C
C -> (нет зависимостей)
```

Для ромба порядок `A B D C`: общая вершина D читается один раз,
но оба ребра к ней сохраняются. При цикле C->A выводится циклическое
ребро, обход не зацикливается. В фильтре B результат `A C`:
B не читается, а доступная только через B вершина D не посещается.
Пустой фильтр ничего не исключает; совпадение регистрозависимое.
Для Maven проверяется имя groupId:artifactId, а не версия.
Если фильтр исключает корень, результат пустой, зависимости не запрашиваются.
Файл JSON предварительно проверяется целиком; исключённые узлы не обходятся.

Для реального Maven-графа:

```sh
PYTHON=python3.12 ./run.sh --config configs/maven.csv
```

Ожидаемые рёбра JUnit4.13.2:

```text
junit:junit:4.13.2 -> org.hamcrest:hamcrest-core:1.3, org.hamcrest:hamcrest-library:1.3
org.hamcrest:hamcrest-core:1.3 -> (нет зависимостей)
org.hamcrest:hamcrest-library:1.3 -> org.hamcrest:hamcrest-core:1.3
```

Это список рёбер и порядок DFS, не визуализация D2/PNG и не ASCII-дерево.
DFS использует явный стек итераторов, без рекурсии. Активные и завершённые
узлы различаются: ребро в активную вершину означает цикл, общий потомок
завершённой ветви не считается циклом. Исключённые узлы не загружаются.

## Тестовый репозиторий

JSON-объект: ключ является именем пакета, значение списком зависимостей.
Все имена состоят из больших латинских букв A-Z, каждая вершина должна
быть описана явно. Повторяющиеся ключи, неизвестные вершины и неверные
типы дают ошибку. Пример `fixtures/chain.json`:

```text
{"A": ["B"], "B": ["C"], "C": []}
```

В CSV задайте `package,A`, `repository,../fixtures/chain.json`,
`test_mode,true`, `version,1`. Поля output/ascii_tree/filter также обязательны.
Примеры готовых настроек находятся в `configs/`.

## Как читаются зависимости Maven

Адрес POM строится по стандартной схеме репозитория:
`groupId` с точками, заменёнными на `/`, затем artifactId/version и
файл artifactId-version.pom. Версия берётся строго из CSV.
JAR-файлы не скачиваются, Maven и менеджеры пакетов не запускаются.

Поддерживаются XML namespace, свойства `${...}`, наследование parent,
управляемые версии dependencyManagement и импорт BOM. Сам раздел
management/BOM не создаёт ребро графа. Метаданные кэшируются в рамках
запуска. Есть таймаут15с, предел POM4MiB, защита от DTD/XML-сущностей,
циклов и чрезмерной глубины parent/BOM, ошибок HTTP и повреждённого XML.
Рекурсия метаданных parent/BOM ограничена32 уровнями; это отдельно
от нерекурсивного DFS графа пакетов в этапе3.

Анализируются все объявленные зависимости корневого раздела dependencies,
включая test/provided/optional, а не только runtime-classpath.
Идентичность объявления учитывает group/artifact, type и classifier;
разные версии не теряются. Узел графа обозначается G:A:V, одинаковые GAV
объединяются. Профили и плагины не активируются, exclusions и Maven conflict
mediation не моделируются. Это анализ объявлений POM, не замена Maven build.
Диапазоны версий, LATEST/RELEASE и SNAPSHOT явно отклоняются; отсутствие
версии или неизвестное свойство также является ошибкой, а не пустым листом.

Официальные источники:

- [Формат POM](https://maven.apache.org/pom.html)
- [Структура репозитория](https://maven.apache.org/repository/layout.html)

## Проверки

Все функциональные тесты текущей ветки:

```sh
python3.12 -m unittest discover -s tests -v
```

Для этого этапа ожидается 71 тестов и итог `OK`.
Тесты используют временные файлы; начиная с этапа2, HTTP проверяется
локальным сервером. Внешняя сеть для unittest не нужна.

Только проверки конфигурации:

```sh
python3.12 -m unittest discover -s tests -p test_config.py -v
```

Только HTTP/POM-проверки:

```sh
python3.12 -m unittest discover -s tests -p test_maven.py -v
```

Только алгоритм графа:

```sh
python3.12 -m unittest discover -s tests -p test_graph.py -v
```

Включён обход5001 вершины, превышающий обычный предел рекурсии Python.
Также проверены ромб, циклы, фильтр, повторный обход и ошибки данных.

Все проверки оформления, тестов и shell-синтаксиса:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/check_quality.py &&
.venv/bin/python -m unittest discover -s tests -v &&
sh -n run.sh &&
(for script in scripts/*.sh; do sh -n "$script" || exit 1; done)
```

Radon и Ruff нужны только для проверки, не для получения зависимостей.
Проверяются структура, Conventional Commits, отсутствие архивов/бинарных
и служебных файлов, файлы до1000 строк, Python-строки до80 символов,
функции до40 строк с декораторами, до7 аргументов, сложность до10,
docstrings, имена PEP8 и числовые литералы в сравнениях.
GitHub Actions запускает те же проверки при каждом push в каждую ветку.

## Как показать другой этап

Сначала переключитесь на соответствующую ветку, потом запускайте её скрипт:

```sh
git switch stage-1
PYTHON=python3.12 ./scripts/01-demo.sh
PYTHON=python3.12 ./scripts/01-errors.sh
```

```sh
git switch stage-2
PYTHON=python3.12 ./scripts/02-demo.sh
```

```sh
git switch stage-3
PYTHON=python3.12 ./scripts/03-demo.sh
```

Сценарий использует программу текущей ветки, номер файла не переключает Git.
В ветке stage-1 нет скриптов02/03. В stage-2 ещё нет03.
Полная реализованная версия первых трёх этапов:

```sh
git switch main
```

## Структура

```text
README.md                 описание и команды запуска
run.sh                    запуск CLI через выбранный Python
src/config.py             чтение CSV
src/validation.py         проверки всех семи параметров
src/main.py               точка входа текущего этапа
configs/                  примеры CSV
fixtures/                 локальные описания графов
scripts/                  демонстрации и проверка качества
tests/                    автоматические тесты
requirements-dev.txt      инструменты только для проверки
.github/workflows/        GitHub Actions
.gitignore                исключения для кэша и артефактов
```

`src/coordinates.py`, `src/pom.py`, `src/maven.py` читают Maven POM.
`src/graph.py` реализует DFS, `src/test_repository.py` читает JSON.
