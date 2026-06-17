from __future__ import annotations

import pytest

from models import Customer, Order, OrderItem, calculate_total


def test_order_calculates_total_from_items():
    items = [OrderItem("Пицца", 2, 750), OrderItem("Напиток", 1, 120.5)]
    order = Order(customer_id=1, order_date="2026-06-16", status="новый", items=items)

    assert calculate_total(items) == 1620.5
    assert order.total == 1620.5


def test_invalid_order_status_is_rejected():
    with pytest.raises(ValueError, match="Некорректный статус"):
        Order(
            customer_id=1,
            order_date="2026-06-16",
            status="ожидает",
            items=[OrderItem("Пицца", 1, 750)],
        )


def test_invalid_order_date_is_rejected():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        Order(
            customer_id=1,
            order_date="16.06.2026",
            status="новый",
            items=[OrderItem("Пицца", 1, 750)],
        )


def test_order_total_must_match_items():
    with pytest.raises(ValueError, match="не совпадает"):
        Order(
            customer_id=1,
            order_date="2026-06-16",
            status="новый",
            total=100,
            items=[OrderItem("Пицца", 1, 750)],
        )


def test_customer_name_is_required():
    with pytest.raises(ValueError, match="Имя клиента"):
        Customer(name="   ")


def test_item_quantity_and_price_are_validated():
    with pytest.raises(ValueError, match="Количество"):
        OrderItem("Пицца", 0, 750)

    with pytest.raises(ValueError, match="Цена"):
        OrderItem("Пицца", 1, -1)
