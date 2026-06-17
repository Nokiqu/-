from __future__ import annotations

from datetime import date

import pytest

from models import Customer, Order, OrderItem


def make_customer(database, name="Иван Петров"):
    return database.create_customer(Customer(name=name, phone="+7 900 000-00-00", address="Москва"))


def make_order(database, customer_id, status="новый", order_date="2026-06-16"):
    return database.create_order(
        Order(
            customer_id=customer_id,
            order_date=order_date,
            status=status,
            items=[OrderItem("Пицца", 2, 500), OrderItem("Сок", 1, 120)],
        )
    )


def test_customer_crud(database):
    customer_id = make_customer(database)

    customer = database.get_customer(customer_id)
    assert customer.name == "Иван Петров"

    database.update_customer(
        customer_id,
        Customer(name="Иван Иванов", phone="+7 999 111-22-33", address="Санкт-Петербург"),
    )
    updated = database.get_customer(customer_id)
    assert updated.name == "Иван Иванов"
    assert updated.address == "Санкт-Петербург"

    database.delete_customer(customer_id)
    assert database.get_customer(customer_id) is None


def test_customers_are_listed_by_id(database):
    first_id = make_customer(database, "Мария Смирнова")
    second_id = make_customer(database, "Анна Кузнецова")

    customers = database.list_customers()

    assert [customer.id for customer in customers] == [first_id, second_id]


def test_order_crud_and_filter(database):
    customer_id = make_customer(database)
    order_id = make_order(database, customer_id, status="новый")

    order = database.get_order(order_id)
    assert order.total == 1120
    assert len(order.items) == 2

    database.update_order(
        order_id,
        Order(
            customer_id=customer_id,
            order_date="2026-06-17",
            status="в доставке",
            items=[OrderItem("Роллы", 1, 1500)],
        ),
    )
    filtered = database.list_orders(status="в доставке")
    assert [order.id for order in filtered] == [order_id]
    assert filtered[0].total == 1500

    database.delete_order(order_id)
    assert database.get_order(order_id) is None


def test_customer_with_orders_cannot_be_deleted(database):
    customer_id = make_customer(database)
    make_order(database, customer_id)

    with pytest.raises(ValueError, match="нельзя удалить"):
        database.delete_customer(customer_id)


def test_reports(database):
    customer_one = make_customer(database, "Иван Петров")
    customer_two = make_customer(database, "Мария Смирнова")
    make_order(database, customer_one, status="новый", order_date="2026-06-16")
    make_order(database, customer_one, status="выполнен", order_date="2026-06-15")
    make_order(database, customer_two, status="отменён", order_date="2026-06-14")

    counts = database.count_orders_by_status()
    assert counts["новый"] == 1
    assert counts["выполнен"] == 1
    assert counts["отменён"] == 1

    top_customers = database.top_customers()
    assert top_customers[0]["name"] == "Иван Петров"
    assert top_customers[0]["orders_count"] == 2
    assert all(customer["name"] != "Мария Смирнова" for customer in top_customers)

    revenue = database.revenue_for_period("week", today=date(2026, 6, 16))
    assert revenue["revenue"] == 2240

    month_revenue = database.revenue_for_period("month", today=date(2026, 6, 16))
    assert month_revenue["date_from"] == "2026-06-01"
    assert month_revenue["date_to"] == "2026-06-30"


def test_seed_data_creates_demo_records(database):
    database.seed_data()

    assert len(database.list_customers()) == 3
    assert len(database.list_orders()) == 4
