# Практическая работа 2, вариант 17. Этап 4

Конфигурационное управление, ИКБО-40-25.
CLI анализирует зависимости пакетов Java (Maven). Этап 4 показывает порядок
загрузки, при котором зависимости предшествуют пакетам, использующим их.
Задание находится на страницах 56–58 методички, оформление на страницах 4–7.

## Запуск на Mac

Команды выполняются в обычном Терминале macOS. Если репозиторий уже скачан,
перейдите в его папку, например `cd ~/practice-2-variant-17`. Сборка не нужна.
Для приложения нужен Python 3.10+. Команды ниже используют Python 3.12.

```sh
git fetch origin
git switch stage-4
git pull --ff-only
PYTHON=python3.12 ./run.sh --help
```

Для первого скачивания:

```sh
git clone https://github.com/AlexPanicev/practice-2-variant-17.git
cd practice-2-variant-17
git switch stage-4
```

## Что показать преподавателю

```sh
PYTHON=python3.12 ./scripts/04-demo.sh
PYTHON=python3.12 ./run.sh --config configs/chain.csv
PYTHON=python3.12 ./run.sh --config configs/maven.csv
```

Первый запуск выполняет все шесть локальных сценариев без интернета.
Второй читает цепочку из `fixtures/chain.json`. Третий скачивает POM
реального пакета `junit:junit:4.13.2` из Maven Central и выводит версии.

| CSV в `configs/` | Граф | Порядок загрузки |
| --- | --- | --- |
| `chain.csv` | Цепочка A → B → C | C B |
| `diamond.csv` | Ветви B и C используют D | D B C |
| `cycle.csv` | C снова зависит от A | Невозможен из-за цикла |
| `self.csv` | A зависит от себя | Невозможен из-за цикла |
| `isolated.csv` | У A нет зависимостей | Пустой |
| `filter.csv` | Ветвь B отфильтрована | C |

Ребро `A -> B` означает, что A зависит от B. Строка «Обход DFS» показывает
порядок обнаружения вершин, например `A B C`. Для порядка загрузки вершины
добавляются по завершении DFS, поэтому получаем `C B`. Корневой пакет A
в строку загрузки его зависимостей не входит. Общий потомок появляется
один раз. Порядок соседей стабилен и следует входному файлу или POM.
Для циклического графа программа показывает цикл и сообщает, что такой
порядок невозможен. Пустой граф и цикл являются корректными результатами
анализа, поэтому в обоих случаях код завершения равен 0.

## Сравнение с Maven

Для отдельного сравнения нужны JDK и Maven. На Mac с Homebrew:

```sh
brew install maven
mvn --version
PYTHON=python3.12 ./scripts/04-compare.sh configs/maven.csv
PYTHON=python3.12 ./scripts/04-compare.sh configs/maven.csv --fresh
```

Приложение вычисляет порядок из POM, полученных через стандартную библиотеку
Python. Сценарий сравнения отдельно вызывает штатную цель Maven
`dependency:build-classpath` для проекта-потребителя. Сценарий показывает
порядок записи JAR в runtime classpath и порядок завершения их скачиваний
по журналу Maven. Ключ `--fresh` даёт новый временный кэш. Обычный запуск
повторно использует кэш в `output/maven/repository`. При прогретом кэше
строка о новых скачиваниях может быть пустой.

В проверке с Maven 3.9.16, Dependency Plugin 3.11.0 и Java 21.0.12.1
получились такие результаты:

| Источник | Последовательность |
| --- | --- |
| Наш порядок зависимостей | `hamcrest-core:1.3`, `hamcrest-library:1.3` |
| Maven runtime classpath | `junit:4.13.2`, `hamcrest-core:1.3` |
| Maven, завершение JAR-загрузок с новым кэшем | `junit:4.13.2`, `hamcrest-core:1.3` |

JUnit выступает прямой зависимостью проекта-потребителя Maven.
Его `hamcrest-library` имеет scope `test`, поэтому в runtime classpath
потребителя она не попадает. В анализируемом POM это объявленное ребро,
а `hamcrest-core` предшествует использующей его `hamcrest-library`.
Скачивание файла JAR может завершиться до скачивания его зависимостей,
поскольку Maven разрешает граф по метаданным и может выполнять передачи
параллельно. Итоговый порядок передач зависит от сети и кэша.
[Документация build-classpath](https://maven.apache.org/plugins/maven-dependency-plugin/build-classpath-mojo.html)

## Как выбрать другой пакет или тестовый граф

```sh
cp configs/maven.csv configs/my-package.csv
nano configs/my-package.csv
PYTHON=python3.12 ./run.sh --config configs/my-package.csv
PYTHON=python3.12 ./scripts/04-compare.sh configs/my-package.csv
```

Укажите `package` как `groupId:artifactId` и точную версию в `version`.
Для своего тестового графа скопируйте `configs/chain.csv`, укажите
`test_mode,true`, путь к JSON в `repository` и корневой пакет в `package`.
Пример JSON: `{"A": ["B"], "B": ["C"], "C": []}`. Объявите все вершины.
Имена пакетов в JSON состоят из заглавных латинских букв.

| Ключ CSV | Назначение |
| --- | --- |
| `package` | Анализируемый Maven-пакет или тестовый корень. |
| `repository` | URL Maven-репозитория или путь к локальному JSON. |
| `test_mode` | `true` читает JSON, `false` запрашивает Maven POM. |
| `version` | Конкретная release-версия. В тестовом режиме поле обязательно. |
| `output` | Путь к PNG. На этом этапе только проверяется. |
| `ascii_tree` | `true` или `false`. ASCII-вывод появляется на этапе 5. |
| `filter` | Регистрозависимая подстрока имени. Пустое поле отключает фильтр. |

CSV в UTF-8, заголовок `key,value`, все семь ключей обязательны. Относительные
пути внутри CSV считаются от папки CSV. Путь `--config`, если относительный,
интерпретируется от корня репозитория при запуске через `run.sh`.
При исключении пакета по фильтру его ветвь не обходится. Общий потомок
сохраняется, если доступен через другую ветвь. Фильтр проверяет имя Maven
пакета без версии. Некорректные настройки или POM дают ошибку и код 2.

Утилита учитывает объявления зависимостей из POM, включая test, provided
и optional. Для разрешения версий используются свойства, parent,
dependencyManagement и импорт BOM. Узлы Maven имеют формат
`groupId:artifactId:version`. Профили, плагины, exclusions, разрешение
конфликтов версий, диапазоны и SNAPSHOT выходят за рамки этого анализатора.
Поддержка Maven для сравнения находится в сценариях, в самом приложении
используются стандартные HTTP и XML-инструменты Python.

## Тесты и оформление

```sh
python3.12 -m unittest discover -s tests -v
python3.12 -m unittest discover -s tests -p test_graph.py -v
python3.12 -m unittest discover -s tests -p test_graph.py -k load_order -v
```

Первая команда запускает все 75 тестов. Остальные выбирают файл
и тесты порядка загрузки. Тесты используют локальные данные и localhost.

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
| `src/` | CLI, настройки CSV, чтение POM/JSON и итеративный DFS. |
| `configs/` | Готовые настройки для отдельных запусков. |
| `fixtures/` | Данные шести локальных графов. |
| `scripts/` | Демонстрации, сравнение с Maven и проверка оформления. |
| `tests/` | Автоматические проверки. |
| `output/` | Локальные результаты сравнения, игнорируются Git. |
