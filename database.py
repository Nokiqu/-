from __future__ import annotations

import calendar
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from logger_config import setup_logging
from models import Customer, Order, OrderItem, VALID_STATUSES, validate_order_date, validate_status


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "delivery.db"


class DeliveryDatabase:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = setup_logging()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init_db(self, drop_existing: bool = False) -> None:
        with self._connect() as connection:
            if drop_existing:
                connection.executescript(
                    """
                    DROP TABLE IF EXISTS order_items;
                    DROP TABLE IF EXISTS orders;
                    DROP TABLE IF EXISTS customers;
                    """
                )

            status_sql = ",".join(f"'{status}'" for status in VALID_STATUSES)
            connection.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT,
                    address TEXT
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
                    order_date TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ({status_sql})),
                    total REAL NOT NULL CHECK(total >= 0)
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    price REAL NOT NULL CHECK(price >= 0)
                );
                """
            )

        self.logger.info("Database initialized: %s", self.db_path)

    def seed_data(self) -> None:
        if self.list_customers():
            self.logger.info("Seed skipped: database already contains customers")
            return

        customer_ids = [
            self.create_customer(Customer("Иван Петров", "+7 900 111-22-33", "ул. Ленина, 10")),
            self.create_customer(Customer("Мария Смирнова", "+7 900 222-33-44", "пр. Мира, 5")),
            self.create_customer(Customer("Анна Кузнецова", "+7 900 333-44-55", "ул. Садовая, 7")),
        ]

        today = date.today()
        self.create_order(
            Order(
                customer_id=customer_ids[0],
                order_date=today.isoformat(),
                status="новый",
                items=[
                    OrderItem("Пицца Маргарита", 2, 750),
                    OrderItem("Морс", 1, 180),
                ],
            )
        )
        self.create_order(
            Order(
                customer_id=customer_ids[1],
                order_date=(today - timedelta(days=2)).isoformat(),
                status="в доставке",
                items=[
                    OrderItem("Суши сет", 1, 2100),
                    OrderItem("Соевый соус", 2, 60),
                ],
            )
        )
        self.create_order(
            Order(
                customer_id=customer_ids[0],
                order_date=(today - timedelta(days=10)).isoformat(),
                status="выполнен",
                items=[OrderItem("Бургер", 3, 420)],
            )
        )
        self.create_order(
            Order(
                customer_id=customer_ids[2],
                order_date=(today - timedelta(days=35)).isoformat(),
                status="отменён",
                items=[OrderItem("Салат Цезарь", 1, 540)],
            )
        )
        self.logger.info("Seed data created")

    def create_customer(self, customer: Customer) -> int:
        customer = Customer(customer.name, customer.phone, customer.address, customer.id)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)",
                (customer.name, customer.phone, customer.address),
            )
            customer_id = int(cursor.lastrowid)
        self.logger.info("Customer created: id=%s name=%s", customer_id, customer.name)
        return customer_id

    def get_customer(self, customer_id: int) -> Customer | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return self._row_to_customer(row) if row else None

    def list_customers(self) -> list[Customer]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM customers ORDER BY id").fetchall()
        return [self._row_to_customer(row) for row in rows]

    def update_customer(self, customer_id: int, customer: Customer) -> None:
        customer = Customer(customer.name, customer.phone, customer.address, customer.id)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE customers
                SET name = ?, phone = ?, address = ?
                WHERE id = ?
                """,
                (customer.name, customer.phone, customer.address, customer_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Клиент не найден")
        self.logger.info("Customer updated: id=%s", customer_id)

    def delete_customer(self, customer_id: int) -> None:
        with self._connect() as connection:
            orders_count = connection.execute(
                "SELECT COUNT(*) AS count FROM orders WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()["count"]
            if orders_count:
                raise ValueError("Клиента нельзя удалить, если у него есть заказы")

            cursor = connection.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            if cursor.rowcount == 0:
                raise ValueError("Клиент не найден")
        self.logger.info("Customer deleted: id=%s", customer_id)

    def create_order(self, order: Order) -> int:
        order = Order(
            customer_id=order.customer_id,
            order_date=order.order_date,
            status=order.status,
            items=order.items,
            total=order.total,
            id=order.id,
        )
        self._ensure_customer_exists(order.customer_id)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO orders (customer_id, order_date, status, total)
                VALUES (?, ?, ?, ?)
                """,
                (order.customer_id, order.order_date, order.status, order.total),
            )
            order_id = int(cursor.lastrowid)
            self._insert_order_items(connection, order_id, order.items)

        self.logger.info("Order created: id=%s customer_id=%s", order_id, order.customer_id)
        return order_id

    def get_order(self, order_id: int) -> Order | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                return None
            items = self._load_order_items(connection, order_id)
        return self._row_to_order(row, items)

    def list_orders(
        self,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Order]:
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            validate_status(status)
            conditions.append("status = ?")
            params.append(status)
        if date_from:
            validate_order_date(date_from)
            conditions.append("order_date >= ?")
            params.append(date_from)
        if date_to:
            validate_order_date(date_to)
            conditions.append("order_date <= ?")
            params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM orders {where_clause} ORDER BY order_date DESC, id DESC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            result = [
                self._row_to_order(row, self._load_order_items(connection, row["id"]))
                for row in rows
            ]
        return result

    def update_order(self, order_id: int, order: Order) -> None:
        order = Order(
            customer_id=order.customer_id,
            order_date=order.order_date,
            status=order.status,
            items=order.items,
            total=order.total,
            id=order_id,
        )
        self._ensure_customer_exists(order.customer_id)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE orders
                SET customer_id = ?, order_date = ?, status = ?, total = ?
                WHERE id = ?
                """,
                (order.customer_id, order.order_date, order.status, order.total, order_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Заказ не найден")
            connection.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            self._insert_order_items(connection, order_id, order.items)

        self.logger.info("Order updated: id=%s", order_id)

    def delete_order(self, order_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            if cursor.rowcount == 0:
                raise ValueError("Заказ не найден")
        self.logger.info("Order deleted: id=%s", order_id)

    def count_orders_by_status(self) -> dict[str, int]:
        result = {status: 0 for status in VALID_STATUSES}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
            ).fetchall()
        for row in rows:
            result[row["status"]] = int(row["count"])
        return result

    def top_customers(self, limit: int = 3) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.name, COALESCE(SUM(o.total), 0) AS total_sum, COUNT(o.id) AS orders_count
                FROM customers c
                JOIN orders o ON o.customer_id = c.id
                WHERE o.status != 'отменён'
                GROUP BY c.id, c.name
                ORDER BY total_sum DESC, orders_count DESC, c.name ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "customer_id": row["id"],
                "name": row["name"],
                "total_sum": round(float(row["total_sum"]), 2),
                "orders_count": int(row["orders_count"]),
            }
            for row in rows
        ]

    def revenue_between(self, date_from: str, date_to: str) -> float:
        validate_order_date(date_from)
        validate_order_date(date_to)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(total), 0) AS revenue
                FROM orders
                WHERE status != 'отменён' AND order_date BETWEEN ? AND ?
                """,
                (date_from, date_to),
            ).fetchone()
        return round(float(row["revenue"]), 2)

    def revenue_for_period(self, period: str, today: date | None = None) -> dict[str, Any]:
        today = today or date.today()
        if period == "day":
            start = today
            end = today
        elif period == "week":
            start = today - timedelta(days=6)
            end = today
        elif period == "month":
            start = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day)
        else:
            raise ValueError("Период должен быть day, week или month")

        return {
            "period": period,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "revenue": self.revenue_between(start.isoformat(), end.isoformat()),
        }

    def build_report(self, period: str) -> dict[str, Any]:
        return {
            "orders_by_status": self.count_orders_by_status(),
            "top_customers": self.top_customers(3),
            "revenue": self.revenue_for_period(period),
        }

    def dump_all(self) -> dict[str, Any]:
        customers = [customer.to_dict() for customer in self.list_customers()]
        orders = [order.to_dict() for order in self.list_orders()]
        return {"customers": customers, "orders": orders}

    def replace_all(self, data: dict[str, Any]) -> None:
        customers = [Customer.from_dict(item) for item in data["customers"]]
        orders = [Order.from_dict(item) for item in data["orders"]]
        customer_ids = {customer.id for customer in customers}

        if None in customer_ids:
            raise ValueError("При импорте у всех клиентов должен быть ID")
        for order in orders:
            if order.id is None:
                raise ValueError("При импорте у всех заказов должен быть ID")
            if order.customer_id not in customer_ids:
                raise ValueError("Заказ ссылается на несуществующего клиента")

        with self._connect() as connection:
            connection.execute("DELETE FROM order_items")
            connection.execute("DELETE FROM orders")
            connection.execute("DELETE FROM customers")

            for customer in customers:
                connection.execute(
                    "INSERT INTO customers (id, name, phone, address) VALUES (?, ?, ?, ?)",
                    (customer.id, customer.name, customer.phone, customer.address),
                )

            for order in orders:
                connection.execute(
                    """
                    INSERT INTO orders (id, customer_id, order_date, status, total)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (order.id, order.customer_id, order.order_date, order.status, order.total),
                )
                self._insert_order_items(connection, order.id, order.items)

        self.logger.info(
            "Database replaced from import: customers=%s orders=%s",
            len(customers),
            len(orders),
        )

    def _ensure_customer_exists(self, customer_id: int) -> None:
        if self.get_customer(customer_id) is None:
            raise ValueError("Клиент не найден")

    def _insert_order_items(
        self,
        connection: sqlite3.Connection,
        order_id: int,
        items: list[OrderItem],
    ) -> None:
        for item in items:
            connection.execute(
                """
                INSERT INTO order_items (order_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, item.product_name, item.quantity, item.price),
            )

    def _load_order_items(self, connection: sqlite3.Connection, order_id: int) -> list[OrderItem]:
        rows = connection.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()
        return [
            OrderItem(
                id=row["id"],
                order_id=row["order_id"],
                product_name=row["product_name"],
                quantity=row["quantity"],
                price=row["price"],
            )
            for row in rows
        ]

    @staticmethod
    def _row_to_customer(row: sqlite3.Row) -> Customer:
        return Customer(id=row["id"], name=row["name"], phone=row["phone"] or "", address=row["address"] or "")

    @staticmethod
    def _row_to_order(row: sqlite3.Row, items: list[OrderItem]) -> Order:
        return Order(
            id=row["id"],
            customer_id=row["customer_id"],
            order_date=row["order_date"],
            status=row["status"],
            total=row["total"],
            items=items,
        )
