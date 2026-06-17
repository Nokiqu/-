from __future__ import annotations

import json

import pytest

from data_export import detect_format, export_data, import_data
from database import DeliveryDatabase
from models import Customer, Order, OrderItem


def populate(database):
    customer_id = database.create_customer(Customer("Иван Петров", "+7 900 111-22-33", "Москва"))
    database.create_order(
        Order(
            customer_id=customer_id,
            order_date="2026-06-16",
            status="новый",
            items=[OrderItem("Пицца", 2, 700), OrderItem("Сок", 1, 100)],
        )
    )


def test_json_export_import_roundtrip(database, runtime_dir):
    populate(database)
    export_path = runtime_dir / "orders.json"

    export_data(database, export_path)

    target = DeliveryDatabase(runtime_dir / "target.db")
    target.init_db()
    result = import_data(target, export_path)

    assert result == {"customers": 1, "orders": 1}
    assert target.list_customers()[0].name == "Иван Петров"
    assert target.list_orders()[0].total == 1500


def test_xml_export_import_roundtrip(database, runtime_dir):
    populate(database)
    export_path = runtime_dir / "orders.xml"

    export_data(database, export_path)

    target = DeliveryDatabase(runtime_dir / "target_xml.db")
    target.init_db()
    result = import_data(target, export_path)

    assert result["customers"] == 1
    assert result["orders"] == 1
    assert target.list_orders()[0].status == "новый"


def test_import_rejects_invalid_payload_without_changing_database(database, runtime_dir):
    populate(database)
    invalid_path = runtime_dir / "invalid.json"
    payload = {
        "customers": [{"id": 1, "name": "Иван", "phone": "", "address": ""}],
        "orders": [
            {
                "id": 1,
                "customer_id": 1,
                "order_date": "2026-06-16",
                "status": "неизвестно",
                "total": 100,
                "items": [{"id": 1, "product_name": "Товар", "quantity": 1, "price": 100}],
            }
        ],
    }
    invalid_path.write_text(
        "\ufeff" + json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Некорректный статус"):
        import_data(database, invalid_path)

    assert len(database.list_customers()) == 1
    assert len(database.list_orders()) == 1


def test_unknown_export_format_is_rejected():
    with pytest.raises(ValueError, match=".json"):
        detect_format("orders.csv")
