from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from database import DeliveryDatabase
from logger_config import setup_logging
from models import Customer, Order, calculate_total


logger = setup_logging()


def detect_format(file_path: str | Path) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".xml":
        return "xml"
    raise ValueError("Поддерживаются только файлы .json и .xml")


def export_data(database: DeliveryDatabase, file_path: str | Path) -> Path:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = validate_payload(database.dump_all())
    file_format = detect_format(path)

    if file_format == "json":
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        _write_xml(data, path)

    logger.info("Data exported: file=%s format=%s", path, file_format)
    return path


def import_data(database: DeliveryDatabase, file_path: str | Path) -> dict[str, int]:
    path = Path(file_path)
    file_format = detect_format(path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    if file_format == "json":
        raw_data = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        raw_data = _read_xml(path)

    data = validate_payload(raw_data)
    database.replace_all(data)
    result = {"customers": len(data["customers"]), "orders": len(data["orders"])}
    logger.info("Data imported: file=%s format=%s result=%s", path, file_format, result)
    return result


def validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Файл импорта должен содержать объект с customers и orders")
    if not isinstance(data.get("customers"), list):
        raise ValueError("Поле customers должно быть списком")
    if not isinstance(data.get("orders"), list):
        raise ValueError("Поле orders должно быть списком")

    customers = [_normalize_customer(item) for item in data["customers"]]
    customer_ids = _ensure_unique_positive_ids(customers, "customers")

    orders = [_normalize_order(item) for item in data["orders"]]
    order_ids = _ensure_unique_positive_ids(orders, "orders")

    for order in orders:
        if order["customer_id"] not in customer_ids:
            raise ValueError(f"Заказ {order['id']} ссылается на несуществующего клиента")
        _ensure_unique_positive_ids(order["items"], f"items заказа {order['id']}", allow_missing=True)
        calculated_total = calculate_total([item["_model"] for item in order["items"]])
        if abs(order["total"] - calculated_total) > 0.01:
            raise ValueError(f"Сумма заказа {order['id']} не совпадает со стоимостью товаров")

    for order in orders:
        for item in order["items"]:
            item.pop("_model", None)

    return {"customers": customers, "orders": orders}


def _normalize_customer(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Клиент должен быть объектом")
    customer = Customer.from_dict(data)
    if customer.id is None:
        raise ValueError("У клиента должен быть ID")
    return customer.to_dict()


def _normalize_order(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Заказ должен быть объектом")
    order = Order.from_dict(data)
    normalized = order.to_dict()
    normalized["total"] = round(float(normalized["total"]), 2)
    for source_item, normalized_item, model_item in zip(data["items"], normalized["items"], order.items):
        if isinstance(source_item, dict) and source_item.get("id") is not None:
            normalized_item["id"] = int(source_item["id"])
        else:
            normalized_item["id"] = None
        normalized_item.pop("order_id", None)
        normalized_item["_model"] = model_item
    return normalized


def _ensure_unique_positive_ids(
    rows: list[dict[str, Any]],
    label: str,
    allow_missing: bool = False,
) -> set[int]:
    ids: set[int] = set()
    for row in rows:
        row_id = row.get("id")
        if row_id is None and allow_missing:
            continue
        if row_id is None:
            raise ValueError(f"В {label} у всех записей должен быть ID")
        row_id = int(row_id)
        if row_id <= 0:
            raise ValueError(f"В {label} ID должен быть положительным")
        if row_id in ids:
            raise ValueError(f"В {label} найден повторяющийся ID: {row_id}")
        row["id"] = row_id
        ids.add(row_id)
    return ids


def _write_xml(data: dict[str, Any], path: Path) -> None:
    root = ET.Element("delivery_data")
    customers_el = ET.SubElement(root, "customers")
    for customer in data["customers"]:
        customer_el = ET.SubElement(customers_el, "customer", {"id": str(customer["id"])})
        ET.SubElement(customer_el, "name").text = customer["name"]
        ET.SubElement(customer_el, "phone").text = customer["phone"]
        ET.SubElement(customer_el, "address").text = customer["address"]

    orders_el = ET.SubElement(root, "orders")
    for order in data["orders"]:
        order_el = ET.SubElement(
            orders_el,
            "order",
            {
                "id": str(order["id"]),
                "customer_id": str(order["customer_id"]),
                "order_date": order["order_date"],
                "status": order["status"],
                "total": str(order["total"]),
            },
        )
        items_el = ET.SubElement(order_el, "items")
        for item in order["items"]:
            attributes = {
                "product_name": item["product_name"],
                "quantity": str(item["quantity"]),
                "price": str(item["price"]),
            }
            if item.get("id") is not None:
                attributes["id"] = str(item["id"])
            ET.SubElement(items_el, "item", attributes)

    _indent_xml(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _indent_xml(element: ET.Element, level: int = 0) -> None:
    indent = "\n" + level * "  "
    child_indent = "\n" + (level + 1) * "  "
    children = list(element)
    if children:
        if not element.text or not element.text.strip():
            element.text = child_indent
        for child in children:
            _indent_xml(child, level + 1)
        if not children[-1].tail or not children[-1].tail.strip():
            children[-1].tail = indent
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indent


def _read_xml(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    if root.tag != "delivery_data":
        raise ValueError("Корневой тег XML должен быть delivery_data")

    customers: list[dict[str, Any]] = []
    for customer_el in root.findall("./customers/customer"):
        customers.append(
            {
                "id": int(customer_el.attrib["id"]),
                "name": customer_el.findtext("name", default=""),
                "phone": customer_el.findtext("phone", default=""),
                "address": customer_el.findtext("address", default=""),
            }
        )

    orders: list[dict[str, Any]] = []
    for order_el in root.findall("./orders/order"):
        items = []
        for item_el in order_el.findall("./items/item"):
            item = {
                "product_name": item_el.attrib.get("product_name", ""),
                "quantity": int(item_el.attrib.get("quantity", 0)),
                "price": float(item_el.attrib.get("price", 0)),
            }
            if item_el.attrib.get("id"):
                item["id"] = int(item_el.attrib["id"])
            items.append(item)

        orders.append(
            {
                "id": int(order_el.attrib["id"]),
                "customer_id": int(order_el.attrib["customer_id"]),
                "order_date": order_el.attrib.get("order_date", ""),
                "status": order_el.attrib.get("status", ""),
                "total": float(order_el.attrib.get("total", 0)),
                "items": items,
            }
        )

    return {"customers": customers, "orders": orders}
