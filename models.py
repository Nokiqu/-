from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


VALID_STATUSES = ("новый", "в доставке", "выполнен", "отменён")


def validate_status(status: str) -> str:
    if status not in VALID_STATUSES:
        allowed = ", ".join(VALID_STATUSES)
        raise ValueError(f"Некорректный статус: {status}. Допустимые статусы: {allowed}")
    return status


def validate_order_date(order_date: str) -> str:
    try:
        parsed = date.fromisoformat(order_date)
    except ValueError as exc:
        raise ValueError("Дата заказа должна быть в формате YYYY-MM-DD") from exc

    if parsed.isoformat() != order_date:
        raise ValueError("Дата заказа должна быть в формате YYYY-MM-DD")
    return order_date


def calculate_total(items: list["OrderItem"]) -> float:
    return round(sum(item.total for item in items), 2)


@dataclass
class Customer:
    name: str
    phone: str = ""
    address: str = ""
    id: int | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.phone = self.phone.strip()
        self.address = self.address.strip()

        if not self.name:
            raise ValueError("Имя клиента не может быть пустым")
        if self.id is not None and self.id <= 0:
            raise ValueError("ID клиента должен быть положительным числом")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "address": self.address,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Customer":
        return cls(
            id=data.get("id"),
            name=str(data.get("name", "")),
            phone=str(data.get("phone", "")),
            address=str(data.get("address", "")),
        )


@dataclass
class OrderItem:
    product_name: str
    quantity: int
    price: float
    id: int | None = None
    order_id: int | None = None

    def __post_init__(self) -> None:
        self.product_name = self.product_name.strip()
        self.quantity = int(self.quantity)
        self.price = float(self.price)

        if not self.product_name:
            raise ValueError("Название товара не может быть пустым")
        if self.quantity <= 0:
            raise ValueError("Количество товара должно быть больше 0")
        if self.price < 0:
            raise ValueError("Цена товара не может быть отрицательной")
        if self.id is not None and self.id <= 0:
            raise ValueError("ID товара должен быть положительным числом")
        if self.order_id is not None and self.order_id <= 0:
            raise ValueError("ID заказа должен быть положительным числом")

    @property
    def total(self) -> float:
        return round(self.quantity * self.price, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "price": self.price,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderItem":
        return cls(
            id=data.get("id"),
            order_id=data.get("order_id"),
            product_name=str(data.get("product_name", "")),
            quantity=int(data.get("quantity", 0)),
            price=float(data.get("price", 0)),
        )


@dataclass
class Order:
    customer_id: int
    order_date: str
    status: str
    items: list[OrderItem] = field(default_factory=list)
    total: float | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        self.customer_id = int(self.customer_id)
        if self.customer_id <= 0:
            raise ValueError("ID клиента должен быть положительным числом")
        if self.id is not None and self.id <= 0:
            raise ValueError("ID заказа должен быть положительным числом")

        self.order_date = validate_order_date(self.order_date)
        self.status = validate_status(self.status)

        if not self.items:
            raise ValueError("Заказ должен содержать хотя бы один товар")

        normalized_items: list[OrderItem] = []
        for item in self.items:
            normalized_items.append(item if isinstance(item, OrderItem) else OrderItem.from_dict(item))
        self.items = normalized_items

        calculated_total = calculate_total(self.items)
        if self.total is None:
            self.total = calculated_total
        else:
            self.total = round(float(self.total), 2)
            if self.total < 0:
                raise ValueError("Итоговая сумма заказа не может быть отрицательной")
            if abs(self.total - calculated_total) > 0.01:
                raise ValueError("Итоговая сумма заказа не совпадает со стоимостью товаров")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "order_date": self.order_date,
            "status": self.status,
            "total": self.total,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Order":
        return cls(
            id=data.get("id"),
            customer_id=int(data.get("customer_id", 0)),
            order_date=str(data.get("order_date", "")),
            status=str(data.get("status", "")),
            total=data.get("total"),
            items=[OrderItem.from_dict(item) for item in data.get("items", [])],
        )
