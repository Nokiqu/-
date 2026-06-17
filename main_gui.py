from __future__ import annotations

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from data_export import export_data, import_data
from database import DEFAULT_DB_PATH, DeliveryDatabase
from logger_config import setup_logging
from models import Customer, Order, OrderItem, VALID_STATUSES, calculate_total


class DeliveryApp:
    def __init__(self, root: tk.Tk, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.root = root
        self.root.title("Быстрая доставка")
        self.root.geometry("980x560")
        self.logger = setup_logging()
        self.database = DeliveryDatabase(db_path)
        self.database.init_db()
        self.orders_by_id: dict[int, Order] = {}

        self.status_var = tk.StringVar(value="Все")
        self._build_layout()
        self.refresh_orders()
        self.logger.info("GUI started")

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="Статус:").pack(side=tk.LEFT)
        status_filter = ttk.Combobox(
            toolbar,
            textvariable=self.status_var,
            values=("Все", *VALID_STATUSES),
            state="readonly",
            width=18,
        )
        status_filter.pack(side=tk.LEFT, padx=(6, 12))
        status_filter.bind("<<ComboboxSelected>>", lambda _event: self.refresh_orders())

        ttk.Button(toolbar, text="Обновить", command=self.refresh_orders).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Добавить", command=self.add_order).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Редактировать", command=self.edit_order).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Удалить", command=self.delete_order).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Клиенты", command=self.open_customers).pack(side=tk.LEFT, padx=12)
        ttk.Button(toolbar, text="Показать отчёт", command=self.show_report).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Экспорт", command=self.export_orders).pack(side=tk.RIGHT, padx=3)
        ttk.Button(toolbar, text="Импорт", command=self.import_orders).pack(side=tk.RIGHT, padx=3)

        table_frame = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "date", "customer", "status", "total", "items")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
        headings = {
            "id": "ID",
            "date": "Дата",
            "customer": "Клиент",
            "status": "Статус",
            "total": "Сумма",
            "items": "Товаров",
        }
        widths = {"id": 60, "date": 110, "customer": 250, "status": 130, "total": 120, "items": 80}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor=tk.W)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", lambda _event: self.edit_order())

    def refresh_orders(self) -> None:
        status = None if self.status_var.get() == "Все" else self.status_var.get()
        customers = {customer.id: customer.name for customer in self.database.list_customers()}
        orders = self.database.list_orders(status=status)
        self.orders_by_id = {int(order.id): order for order in orders if order.id is not None}

        for row in self.tree.get_children():
            self.tree.delete(row)

        for order in orders:
            customer_name = customers.get(order.customer_id, f"ID {order.customer_id}")
            self.tree.insert(
                "",
                tk.END,
                iid=str(order.id),
                values=(
                    order.id,
                    order.order_date,
                    customer_name,
                    order.status,
                    f"{order.total:.2f}",
                    len(order.items),
                ),
            )

    def selected_order(self) -> Order | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Выбор заказа", "Выберите заказ в таблице")
            return None
        return self.orders_by_id.get(int(selection[0]))

    def add_order(self) -> None:
        if not self.database.list_customers():
            messagebox.showwarning(
                "Клиенты",
                "Сначала добавьте клиента. После закрытия окна клиентов форма заказа откроется автоматически.",
            )
            CustomersWindow(self.root, self.database, on_close=self.open_order_if_customers_exist)
            return
        OrderForm(self.root, self.database, on_saved=self.refresh_orders)

    def open_order_if_customers_exist(self) -> None:
        self.refresh_orders()
        if self.database.list_customers():
            OrderForm(self.root, self.database, on_saved=self.refresh_orders)

    def edit_order(self) -> None:
        order = self.selected_order()
        if order is not None:
            OrderForm(self.root, self.database, order=order, on_saved=self.refresh_orders)

    def delete_order(self) -> None:
        order = self.selected_order()
        if order is None:
            return
        if not messagebox.askyesno("Удаление заказа", f"Удалить заказ #{order.id}?"):
            return
        try:
            self.database.delete_order(int(order.id))
            self.refresh_orders()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def open_customers(self) -> None:
        CustomersWindow(self.root, self.database)

    def show_report(self) -> None:
        report = self.database.build_report("month")
        window = tk.Toplevel(self.root)
        window.title("Отчёт за месяц")
        window.geometry("520x360")

        text = tk.Text(window, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, "Количество заказов по статусам:\n")
        for status, count in report["orders_by_status"].items():
            text.insert(tk.END, f"  {status}: {count}\n")

        text.insert(tk.END, "\nТоп-3 клиента по сумме заказов:\n")
        if not report["top_customers"]:
            text.insert(tk.END, "  Нет данных\n")
        for index, customer in enumerate(report["top_customers"], start=1):
            text.insert(
                tk.END,
                f"  {index}. {customer['name']} - {customer['total_sum']:.2f} руб.\n",
            )

        revenue = report["revenue"]
        text.insert(
            tk.END,
            "\nВыручка за месяц "
            f"({revenue['date_from']} - {revenue['date_to']}): "
            f"{revenue['revenue']:.2f} руб.\n",
        )
        text.configure(state=tk.DISABLED)

    def export_orders(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Экспорт",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("XML", "*.xml")),
        )
        if not path:
            return
        try:
            export_data(self.database, path)
            messagebox.showinfo("Экспорт", f"Данные сохранены:\n{path}")
        except Exception as exc:
            messagebox.showerror("Ошибка экспорта", str(exc))

    def import_orders(self) -> None:
        path = filedialog.askopenfilename(
            title="Импорт",
            filetypes=(("JSON/XML", "*.json *.xml"), ("JSON", "*.json"), ("XML", "*.xml")),
        )
        if not path:
            return
        try:
            result = import_data(self.database, path)
            self.refresh_orders()
            messagebox.showinfo(
                "Импорт",
                f"Импортировано: клиентов={result['customers']}, заказов={result['orders']}",
            )
        except Exception as exc:
            messagebox.showerror("Ошибка импорта", str(exc))


class OrderForm:
    def __init__(
        self,
        parent: tk.Tk,
        database: DeliveryDatabase,
        order: Order | None = None,
        on_saved=None,
    ) -> None:
        self.database = database
        self.order = order
        self.on_saved = on_saved
        self.customers = self.database.list_customers()
        if not self.customers:
            messagebox.showwarning("Клиенты", "Сначала добавьте клиента")
            return

        self.window = tk.Toplevel(parent)
        self.window.title("Редактирование заказа" if order else "Новый заказ")
        self.window.geometry("720x430")
        self.item_rows: list[tuple[ttk.Entry, tk.StringVar, tk.StringVar, tk.StringVar]] = []

        self.customer_var = tk.StringVar()
        self.date_var = tk.StringVar(value=order.order_date if order else date.today().isoformat())
        self.status_var = tk.StringVar(value=order.status if order else VALID_STATUSES[0])
        self.total_var = tk.StringVar(value="0.00")

        self._build_form()
        self._fill_initial_values()
        self.update_total()

    def _build_form(self) -> None:
        form = ttk.Frame(self.window, padding=10)
        form.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form, text="Клиент").grid(row=0, column=0, sticky=tk.W, pady=4)
        customer_values = [f"{customer.id} | {customer.name}" for customer in self.customers]
        self.customer_box = ttk.Combobox(
            form,
            textvariable=self.customer_var,
            values=customer_values,
            state="readonly",
            width=42,
        )
        self.customer_box.grid(row=0, column=1, sticky=tk.EW, pady=4, columnspan=3)

        ttk.Label(form, text="Дата").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.date_var, width=18).grid(row=1, column=1, sticky=tk.W, pady=4)

        ttk.Label(form, text="Статус").grid(row=1, column=2, sticky=tk.W, pady=4)
        ttk.Combobox(
            form,
            textvariable=self.status_var,
            values=VALID_STATUSES,
            state="readonly",
            width=18,
        ).grid(row=1, column=3, sticky=tk.W, pady=4)

        items_frame = ttk.LabelFrame(form, text="Товары", padding=8)
        items_frame.grid(row=2, column=0, columnspan=4, sticky=tk.NSEW, pady=8)
        form.columnconfigure(1, weight=1)
        form.rowconfigure(2, weight=1)

        ttk.Label(items_frame, text="Название").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(items_frame, text="Количество").grid(row=0, column=1, sticky=tk.W)
        ttk.Label(items_frame, text="Цена").grid(row=0, column=2, sticky=tk.W)
        self.items_frame = items_frame

        ttk.Button(form, text="Добавить товар", command=self.add_item_row).grid(row=3, column=0, sticky=tk.W)
        ttk.Label(form, text="Итого:").grid(row=3, column=2, sticky=tk.E)
        ttk.Label(form, textvariable=self.total_var).grid(row=3, column=3, sticky=tk.W)

        buttons = ttk.Frame(form)
        buttons.grid(row=4, column=0, columnspan=4, sticky=tk.E, pady=(12, 0))
        ttk.Button(buttons, text="Сохранить", command=self.save).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Отмена", command=self.window.destroy).pack(side=tk.LEFT, padx=4)

    def _fill_initial_values(self) -> None:
        if self.order:
            for customer in self.customers:
                if customer.id == self.order.customer_id:
                    self.customer_var.set(f"{customer.id} | {customer.name}")
                    break
            for item in self.order.items:
                self.add_item_row(item)
        else:
            first = self.customers[0]
            self.customer_var.set(f"{first.id} | {first.name}")
            self.add_item_row()

    def add_item_row(self, item: OrderItem | None = None) -> None:
        row_index = len(self.item_rows) + 1
        name_var = tk.StringVar(value=item.product_name if item else "")
        quantity_var = tk.StringVar(value=str(item.quantity) if item else "1")
        price_var = tk.StringVar(value=str(item.price) if item else "0")

        name_entry = ttk.Entry(self.items_frame, textvariable=name_var, width=36)
        quantity_entry = ttk.Entry(self.items_frame, textvariable=quantity_var, width=12)
        price_entry = ttk.Entry(self.items_frame, textvariable=price_var, width=12)
        name_entry.grid(row=row_index, column=0, sticky=tk.EW, padx=(0, 6), pady=3)
        quantity_entry.grid(row=row_index, column=1, sticky=tk.W, padx=(0, 6), pady=3)
        price_entry.grid(row=row_index, column=2, sticky=tk.W, pady=3)
        self.items_frame.columnconfigure(0, weight=1)

        for var in (name_var, quantity_var, price_var):
            var.trace_add("write", lambda *_args: self.update_total())
        self.item_rows.append((name_entry, name_var, quantity_var, price_var))

    def update_total(self) -> None:
        try:
            items = self.collect_items(allow_empty=True)
            self.total_var.set(f"{calculate_total(items):.2f}")
        except Exception:
            self.total_var.set("0.00")

    def collect_items(self, allow_empty: bool = False) -> list[OrderItem]:
        items: list[OrderItem] = []
        for _entry, name_var, quantity_var, price_var in self.item_rows:
            name = name_var.get().strip()
            quantity = quantity_var.get().strip()
            price = price_var.get().strip().replace(",", ".")
            if not name and not quantity and not price:
                continue
            if not name:
                continue
            items.append(OrderItem(name, int(quantity), float(price)))
        if not items and not allow_empty:
            raise ValueError("Добавьте хотя бы один товар")
        return items

    def save(self) -> None:
        try:
            customer_id = int(self.customer_var.get().split("|", 1)[0].strip())
            order = Order(
                customer_id=customer_id,
                order_date=self.date_var.get().strip(),
                status=self.status_var.get(),
                items=self.collect_items(),
            )
            if self.order:
                self.database.update_order(int(self.order.id), order)
            else:
                self.database.create_order(order)
            if self.on_saved:
                self.on_saved()
            self.window.destroy()
        except Exception as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))


class CustomersWindow:
    def __init__(self, parent: tk.Tk, database: DeliveryDatabase, on_close=None) -> None:
        self.database = database
        self.on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title("Клиенты")
        self.window.geometry("760x420")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.customers_by_id: dict[int, Customer] = {}
        self._build_layout()
        self.refresh()

    def close(self) -> None:
        self.window.destroy()
        if self.on_close:
            self.on_close()

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.window, padding=8)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Добавить", command=self.add_customer).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Редактировать", command=self.edit_customer).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Удалить", command=self.delete_customer).pack(side=tk.LEFT, padx=3)

        columns = ("id", "name", "phone", "address")
        self.tree = ttk.Treeview(self.window, columns=columns, show="headings")
        for column, title, width in (
            ("id", "ID", 60),
            ("name", "Имя", 220),
            ("phone", "Телефон", 160),
            ("address", "Адрес", 280),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _event: self.edit_customer())

    def refresh(self) -> None:
        self.customers_by_id = {}
        for row in self.tree.get_children():
            self.tree.delete(row)
        for customer in self.database.list_customers():
            self.customers_by_id[int(customer.id)] = customer
            self.tree.insert(
                "",
                tk.END,
                iid=str(customer.id),
                values=(customer.id, customer.name, customer.phone, customer.address),
            )

    def selected_customer(self) -> Customer | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Выбор клиента", "Выберите клиента в таблице")
            return None
        return self.customers_by_id.get(int(selection[0]))

    def add_customer(self) -> None:
        CustomerForm(self.window, self.database, on_saved=self.refresh)

    def edit_customer(self) -> None:
        customer = self.selected_customer()
        if customer:
            CustomerForm(self.window, self.database, customer=customer, on_saved=self.refresh)

    def delete_customer(self) -> None:
        customer = self.selected_customer()
        if not customer:
            return
        if not messagebox.askyesno("Удаление клиента", f"Удалить клиента {customer.name}?"):
            return
        try:
            self.database.delete_customer(int(customer.id))
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Ошибка удаления", str(exc))


class CustomerForm:
    def __init__(
        self,
        parent: tk.Toplevel,
        database: DeliveryDatabase,
        customer: Customer | None = None,
        on_saved=None,
    ) -> None:
        self.database = database
        self.customer = customer
        self.on_saved = on_saved
        self.window = tk.Toplevel(parent)
        self.window.title("Редактирование клиента" if customer else "Новый клиент")
        self.window.geometry("420x220")

        self.name_var = tk.StringVar(value=customer.name if customer else "")
        self.phone_var = tk.StringVar(value=customer.phone if customer else "")
        self.address_var = tk.StringVar(value=customer.address if customer else "")
        self._build_form()

    def _build_form(self) -> None:
        form = ttk.Frame(self.window, padding=12)
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Имя").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.name_var).grid(row=0, column=1, sticky=tk.EW, pady=5)
        ttk.Label(form, text="Телефон").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.phone_var).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Label(form, text="Адрес").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.address_var).grid(row=2, column=1, sticky=tk.EW, pady=5)

        buttons = ttk.Frame(form)
        buttons.grid(row=3, column=0, columnspan=2, sticky=tk.E, pady=(12, 0))
        ttk.Button(buttons, text="Сохранить", command=self.save).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Отмена", command=self.window.destroy).pack(side=tk.LEFT, padx=4)

    def save(self) -> None:
        try:
            customer = Customer(
                name=self.name_var.get(),
                phone=self.phone_var.get(),
                address=self.address_var.get(),
            )
            if self.customer:
                self.database.update_customer(int(self.customer.id), customer)
            else:
                self.database.create_customer(customer)
            if self.on_saved:
                self.on_saved()
            self.window.destroy()
        except Exception as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))


def main() -> None:
    root = tk.Tk()
    DeliveryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
