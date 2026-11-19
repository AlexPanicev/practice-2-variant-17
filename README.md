# Практическая работа 2, вариант 17. Этап 5

Конфигурационное управление, ИКБО-40-25.
CLI анализирует зависимости пакетов Java (Maven) по метаданным POM.
Этап 5 сохраняет граф на языке D2 и изображение PNG, показывает версии
пакетов и по запросу печатает ASCII-дерево.
Задание находится на страницах 56-58 методички, оформление на страницах 4-7.

## Быстрый запуск на Mac

Команды выполняются в обычном Терминале macOS в папке репозитория.
Если проект уже скачан, перейдите в его папку, например
`cd ~/practice-2-variant-17`. Если папки ещё нет:

```sh
git clone https://github.com/AlexPanicev/practice-2-variant-17.git
cd practice-2-variant-17
```

```sh
git fetch origin
git switch stage-5
git pull --ff-only
```

Нужны Python 3.10+ и D2. Команды ниже используют Python 3.12.
Сборка проекта не требуется. Установите D2 через Homebrew при необходимости.
Maven и JDK нужны для отдельного сравнения со штатным инструментом.

```sh
brew install d2
PYTHON=python3.12 ./scripts/05-versions.sh
PYTHON=python3.12 ./run.sh --help
```

Команда версий показывает Python и D2, а при установленном Maven также
его версию и версию используемой Java. Для проверки использованы
Python 3.12.14, D2 0.9.0, Maven 3.9.16, Java 21.0.12.1 и
Maven Dependency Plugin 3.11.0.
Примеры установки и экспорта есть в
[документации D2](https://d2lang.com/tour/exports/).

## Что показать преподавателю

```sh
PYTHON=python3.12 ./run.sh --config configs/chain.csv
PYTHON=python3.12 ./run.sh --config configs/maven.csv
open output/chain.png output/maven.png
cat output/maven.d2
```

Первая команда строит локальную цепочку из `fixtures/chain.json` и выводит
ASCII-дерево. Вторая запрашивает POM JUnit 4.13.2 из Maven Central.
Программа печатает абсолютные пути к PNG и D2. `open` показывает PNG,
а `cat` выводит исходный текст D2 в терминал. Пример для цепочки:

```text
ASCII-дерево:
A:1
`-- B
    `-- C
```

Вершина `A:1` показывает корневой пакет A с версией из CSV. Остальные
имена тестовых вершин остаются буквами из JSON. Для Maven каждый узел
подписан координатами `groupId:artifactId:version`, например
`org.hamcrest:hamcrest-core:1.3`. Версии видны в терминале, D2 и PNG.

```sh
PYTHON=python3.12 ./scripts/05-demo.sh test
PYTHON=python3.12 ./scripts/05-demo.sh maven
PYTHON=python3.12 ./scripts/05-demo.sh all
```

`test` строит шесть локальных графов без сети. `maven` строит три графа
реальных пакетов, нужен интернет. `all` запускает обе группы.
У каждого сценария отдельные PNG и D2 в `output/`.

| Конфигурация | Пакет или тестовый случай | Пара файлов в `output/` |
| --- | --- | --- |
| `maven.csv` | `junit:junit:4.13.2` | `maven.png`, `maven.d2` |
| `gson.csv` | `com.google.code.gson:gson:2.10.1` | `gson.png`, `gson.d2` |
| `slf4j.csv` | `org.slf4j:slf4j-simple:2.0.17` | `slf4j.png`, `slf4j.d2` |
| `chain.csv` | Цепочка A → B → C | `chain.png`, `chain.d2` |
| `diamond.csv` | Общий потомок D | `diamond.png`, `diamond.d2` |
| `cycle.csv` | C снова зависит от A | `cycle.png`, `cycle.d2` |
| `self.csv` | A зависит от себя | `self.png`, `self.d2` |
| `isolated.csv` | У A нет зависимостей | `isolated.png`, `isolated.d2` |
| `filter.csv` | Ветвь B отфильтрована | `filter.png`, `filter.d2` |

В D2/PNG стрелка идёт от пакета к его зависимости. Все рёбра сохраняются,
включая обратные. В ASCII пометка `[cycle]` означает ребро к активному
предку, `[shared]` означает общую зависимость, которая уже раскрыта.
Пустой граф имеет подпись `(empty graph)`. Для порядка загрузки
переключитесь на ветку `stage-4`.

## Сравнение со штатным деревом Maven

Для сравнения установите Maven и JDK. Maven автоматически скачивает
артефакты и плагин в локальный кэш проекта. На Mac с Homebrew:

```sh
brew install maven
PYTHON=python3.12 ./scripts/05-compare.sh configs/maven.csv
PYTHON=python3.12 ./scripts/05-compare.sh configs/gson.csv
PYTHON=python3.12 ./scripts/05-compare.sh configs/slf4j.csv
```

Сценарий запускает штатный `dependency:tree` у проекта-потребителя,
выводит дерево в терминал и сохраняет `tree.txt` и `tree.dot` в
`output/maven/reports/<groupId>/<artifactId>/<version>/`.
Первый узел Maven `coursework.demo:maven-consumer:jar:1` является
проектом-потребителем. Его первый потомок является выбранным пакетом.
Официальное описание цели доступно в
[документации Dependency Plugin](https://maven.apache.org/plugins/maven-dependency-plugin/usage.html).

| Пакет | Наша визуализация POM | Штатное дерево потребителя |
| --- | --- | --- |
| JUnit 4.13.2 | Hamcrest Core 1.3 и Library 1.3; Library использует Core. | Только Hamcrest Core 1.3. |
| Gson 2.10.1 | JUnit 4.13.2 и его зависимости. | У Gson нет транзитивных зависимостей. |
| SLF4J Simple 2.0.17 | SLF4J API 2.0.17 и JUnit 4.13.1 с зависимостями. | Только SLF4J API 2.0.17. |

Разницу в этих примерах дают тестовые зависимости POM. Hamcrest Library
объявлена с `scope=test` в JUnit. Gson и SLF4J используют JUnit для своих
тестов. Maven не передаёт эти зависимости потребителю транзитивно.
Анализатор включает такие объявления, поэтому они отображаются на графе.
У SLF4J версия JUnit унаследована из родительского POM.

## Запуск своего пакета или графа

```sh
cp configs/maven.csv configs/my-package.csv
nano configs/my-package.csv
PYTHON=python3.12 ./run.sh --config configs/my-package.csv
PYTHON=python3.12 ./scripts/05-compare.sh configs/my-package.csv
```

Измените `package`, `version` и `output` на свои значения. В `nano`
сохраните через Ctrl+O, Enter и выйдите через Ctrl+X. Чтобы получить
ASCII-дерево для реального пакета, задайте `ascii_tree,true`.
Сравнение с Maven выполняется для реального CSV с `test_mode,false`.
Для своего тестового графа скопируйте `configs/chain.csv`, укажите
`test_mode,true`, путь к JSON в `repository` и корневой пакет в `package`.
Пример JSON: `{"A": ["B"], "B": ["C"], "C": []}`. Объявите все вершины.
Имена пакетов в JSON состоят из заглавных латинских букв.

| Ключ CSV | Назначение |
| --- | --- |
| `package` | Maven-координаты без версии или тестовый корень. |
| `repository` | URL репозитория Maven или путь к тестовому JSON. |
| `test_mode` | `true` читает JSON, `false` запрашивает Maven POM. |
| `version` | Конкретная release-версия пакета. |
| `output` | Путь к PNG. Программа создаёт папку и соседний файл D2. |
| `ascii_tree` | `true` дополнительно выводит ASCII-дерево. |
| `filter` | Регистрозависимая подстрока имени. Пустое поле отключает фильтр. |

CSV в UTF-8, заголовок `key,value`, все семь ключей обязательны. Относительные
пути внутри CSV считаются от папки CSV. Путь `--config`, если относительный,
интерпретируется от корня репозитория при запуске через `run.sh`.
Если фильтр исключает корень, программа создаёт пустой граф. Фильтр
сравнивается с именем Maven-пакета без версии.

Ошибка параметров, метаданных, пути или D2 выдаёт сообщение и код 2.
Успешный повторный запуск заменяет выбранный PNG и соседний D2. Ошибка
рендеринга сохраняет предыдущие файлы. Если `d2` не найден, установите D2
и проверьте `d2 version` в том же терминале.

Данные зависимостей читаются через HTTP и XML стандартной библиотекой
Python. Поддерживаются свойства, parent, dependencyManagement и BOM.
DFS использует явный стек. Профили, плагины, exclusions, разрешение
конфликтов версий, диапазоны и SNAPSHOT выходят за рамки анализатора.
D2 используется только для рендеринга, Maven только для сравнения.

## Тесты и оформление

```sh
python3.12 -m unittest discover -s tests -v
python3.12 -m unittest discover -s tests -p test_visualization.py -v
python3.12 -m unittest discover -s tests -p test_visualization.py -k test_empty_graph -v
```

Первая команда запускает все 87 тестов, вторая выбирает файл тестов
визуализации, третья запускает один из него. Эти тесты используют локальные
данные, localhost и подмену рендерера. Проверка с реальным D2 выполняется
через `05-demo.sh test` и в GitHub Actions.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/check_quality.py
(for script in run.sh scripts/*.sh; do sh -n "$script" || exit 1; done)
```

Проверяются структура Git, Conventional Commits, отсутствие генерируемых
файлов, лимиты 80 символов на строку Python, 40 строк и 7 аргументов
на функцию, сложность до 10, имена PEP 8 и docstrings.

## Ветки и структура

- [Этап 1. CSV-конфигурация](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-1)
- [Этап 2. Прямые зависимости](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-2)
- [Этап 3. Итеративный DFS](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-3)
- [Этап 4. Порядок загрузки](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-4)
- [Этап 5. Визуализация](https://github.com/AlexPanicev/practice-2-variant-17/tree/stage-5)

Для демонстрации другого этапа сначала переключитесь на его ветку.
`run.sh` запускает программу из текущей ветки.

| Путь | Содержимое |
| --- | --- |
| `src/` | Настройки, CLI, чтение POM/JSON, DFS, D2/PNG и ASCII. |
| `configs/` | Примеры тестовых и реальных запросов. |
| `fixtures/` | Шесть локальных графов для демонстрации. |
| `comparison/pom.xml` | Проект-потребитель для штатного Maven. |
| `scripts/` | Демонстрации, сравнение, версии и проверка оформления. |
| `tests/` | Автоматические проверки. |
| `output/` | Результаты генерации и сравнения, игнорируются Git. |
