# Быстрая доставка

Учебный проект для семестровой практики: внутреннее приложение учета заказов службы доставки.

## Возможности

- SQLite-база данных с клиентами, заказами и товарами заказа.
- CRUD для клиентов и заказов.
- Запрет удаления клиента, если у него есть заказы.
- CLI через `argparse`.
- GUI на Tkinter.
- Отчеты: количество заказов по статусам, топ-3 клиента по сумме заказов, выручка за день/неделю/месяц.
- Импорт и экспорт данных в JSON и XML.
- Логирование действий в `logs/app.log`.
- Pytest-тесты с целевым покрытием не менее 60%.

## Структура

```text
delivery_system/
├── main_cli.py
├── main_gui.py
├── database.py
├── models.py
├── data_export.py
├── logger_config.py
├── tests/
├── data/
├── logs/
├── requirements.txt
└── README.md
```

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Если виртуальное окружение не используется, зависимости для тестов можно установить так:

```bash
python -m pip install -r requirements.txt
```

## Быстрый запуск

Создать базу данных и заполнить демонстрационными данными:

```bash
python main_cli.py init-db --seed
```

Запустить GUI:

```bash
python main_gui.py
```

## CLI-команды

Отчет за месяц:

```bash
python main_cli.py report --period month
```

Список заказов с фильтром по статусу:

```bash
python main_cli.py list-orders --status "новый"
```

Экспорт в JSON или XML:

```bash
python main_cli.py export --file orders_backup.json
python main_cli.py export --file orders_backup.xml
```

Импорт из JSON или XML:

```bash
python main_cli.py import --file orders_backup.json
python main_cli.py import --file orders_backup.xml
```

## GUI

В GUI доступны:

- просмотр заказов в таблице;
- фильтр по статусу;
- добавление, редактирование и удаление заказов;
- управление клиентами;
- автоматический расчет суммы заказа по товарам;
- просмотр отчета за текущий месяц;
- импорт и экспорт JSON/XML.

## Тесты

Запуск тестов:

```bash
python -m pytest
```

Запуск тестов с покрытием:

```bash
python -m pytest --cov=. --cov-report=term-missing
```

GUI проверяется вручную, поэтому файл `main_gui.py` исключен из автоматического расчета покрытия в `.coveragerc`.

## Примечания для сдачи

- Основная БД: SQLite.
- Поддерживаются оба формата импорта/экспорта: JSON и XML.
- Перед импортом файл полностью валидируется; если есть ошибка, текущие данные не заменяются.
- Файлы базы данных и логов не добавляются в репозиторий, потому что создаются при запуске.
