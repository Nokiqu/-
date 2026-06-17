from __future__ import annotations

import argparse
import sys
from pathlib import Path

from data_export import export_data, import_data
from database import DEFAULT_DB_PATH, DeliveryDatabase
from logger_config import setup_logging
from models import VALID_STATUSES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI для системы учета заказов компании 'Быстрая доставка'",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Путь к SQLite-файлу базы данных",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Создать таблицы базы данных")
    init_parser.add_argument("--seed", action="store_true", help="Добавить демонстрационные данные")
    init_parser.add_argument("--drop", action="store_true", help="Пересоздать таблицы с нуля")

    list_parser = subparsers.add_parser("list-orders", help="Показать список заказов")
    list_parser.add_argument("--status", choices=VALID_STATUSES, help="Фильтр по статусу")
    list_parser.add_argument("--date-from", help="Дата начала периода YYYY-MM-DD")
    list_parser.add_argument("--date-to", help="Дата конца периода YYYY-MM-DD")

    report_parser = subparsers.add_parser("report", help="Показать отчет и аналитику")
    report_parser.add_argument("--period", choices=("day", "week", "month"), required=True)

    export_parser = subparsers.add_parser("export", help="Экспортировать данные в JSON или XML")
    export_parser.add_argument("--file", required=True, help="Путь к .json или .xml файлу")

    import_parser = subparsers.add_parser("import", help="Импортировать данные из JSON или XML")
    import_parser.add_argument("--file", required=True, help="Путь к .json или .xml файлу")

    return parser


def main(argv: list[str] | None = None) -> int:
    logger = setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    database = DeliveryDatabase(args.db)

    try:
        if args.command == "init-db":
            database.init_db(drop_existing=args.drop)
            if args.seed:
                database.seed_data()
            print(f"База данных готова: {Path(args.db)}")

        elif args.command == "list-orders":
            database.init_db()
            orders = database.list_orders(
                status=args.status,
                date_from=args.date_from,
                date_to=args.date_to,
            )
            if not orders:
                print("Заказы не найдены")
                return 0
            for order in orders:
                print(
                    f"#{order.id} | клиент={order.customer_id} | {order.order_date} | "
                    f"{order.status} | {order.total:.2f} руб."
                )

        elif args.command == "report":
            database.init_db()
            print_report(database.build_report(args.period))

        elif args.command == "export":
            database.init_db()
            path = export_data(database, args.file)
            print(f"Экспорт завершен: {path}")

        elif args.command == "import":
            database.init_db()
            result = import_data(database, args.file)
            print(
                "Импорт завершен: "
                f"клиентов={result['customers']}, заказов={result['orders']}"
            )

        logger.info("CLI command completed: %s", args.command)
        return 0
    except Exception as exc:
        logger.exception("CLI command failed: %s", args.command)
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


def print_report(report: dict) -> None:
    print("Количество заказов по статусам:")
    for status, count in report["orders_by_status"].items():
        print(f"  {status}: {count}")

    print("\nТоп-3 клиента по сумме заказов:")
    if not report["top_customers"]:
        print("  Нет данных")
    for index, customer in enumerate(report["top_customers"], start=1):
        print(
            f"  {index}. {customer['name']} - {customer['total_sum']:.2f} руб. "
            f"({customer['orders_count']} заказов)"
        )

    revenue = report["revenue"]
    print(
        "\nВыручка за период "
        f"{revenue['period']} ({revenue['date_from']} - {revenue['date_to']}): "
        f"{revenue['revenue']:.2f} руб."
    )


if __name__ == "__main__":
    raise SystemExit(main())
