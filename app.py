from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from storage import DATE_FORMAT, DEFAULT_CATEGORIES, add_record, compute_totals, delete_record, load_records, save_records
from sync_client import SyncClient, load_sync_settings


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "budget_data.json"

COLORS = {
    "bg": "#f6f1e8",
    "panel": "#fffaf2",
    "panel_alt": "#f0e6d8",
    "text": "#2f2419",
    "muted": "#7a6a57",
    "accent": "#c46a2f",
    "accent_dark": "#9f4f1d",
    "income": "#2f7d4a",
    "expense": "#af4337",
    "balance": "#345d7c",
    "line": "#decdb7",
    "table_even": "#fffaf4",
    "table_odd": "#f8efe3",
    "select": "#efd5bb",
}


class BudgetApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Учет бюджета")
        self.root.geometry("1240x800")
        self.root.minsize(1000, 700)
        self.root.configure(bg=COLORS["bg"])

        self.sync_client = SyncClient(load_sync_settings())
        self.records = load_records(DATA_FILE)
        self.metric_values: dict[str, ttk.Label] = {}
        self.metric_subtitles: dict[str, ttk.Label] = {}

        self.type_var = tk.StringVar(value="Расход")
        self.amount_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.now().strftime(DATE_FORMAT))
        self.note_var = tk.StringVar()
        self.month_var = tk.StringVar(value="Все")
        self.status_var = tk.StringVar(value="Готово к работе")
        self.sync_var = tk.StringVar(value=self._sync_label())

        self.configure_styles()
        self.build_ui()
        self.refresh_categories()
        self.refresh_months()
        self.refresh_table()
        self.update_summary()

        if self.sync_client.enabled:
            self.root.after(350, lambda: self.sync_records(show_message=False))

    def _sync_label(self) -> str:
        return "Синхронизация: подключена" if self.sync_client.enabled else "Синхронизация: локальный режим"

    def configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            if "vista" in style.theme_names():
                style.theme_use("vista")
            elif "clam" in style.theme_names():
                style.theme_use("clam")
        except tk.TclError:
            pass

        default_font = ("Segoe UI", 10)
        self.root.option_add("*Font", default_font)
        self.root.option_add("*TCombobox*Listbox.font", default_font)

        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("PanelAlt.TFrame", background=COLORS["panel_alt"])
        style.configure("HeaderTitle.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI Semibold", 27))
        style.configure("HeaderMeta.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 11))
        style.configure("SectionTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI Semibold", 13))
        style.configure("Body.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("MetricTitle.TLabel", background=COLORS["panel_alt"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("MetricValue.TLabel", background=COLORS["panel_alt"], foreground=COLORS["text"], font=("Segoe UI Semibold", 19))
        style.configure("MetricSub.TLabel", background=COLORS["panel_alt"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Field.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI Semibold", 10))
        style.configure("App.TButton", padding=(16, 10), font=("Segoe UI Semibold", 10), background=COLORS["accent"], foreground="#ffffff", borderwidth=0)
        style.map("App.TButton", background=[("active", COLORS["accent_dark"]), ("pressed", COLORS["accent_dark"])])
        style.configure("Secondary.TButton", padding=(14, 10), font=("Segoe UI", 10), background=COLORS["panel_alt"], foreground=COLORS["text"], borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#e8d8c4"), ("pressed", "#e0cfba")])
        style.configure("App.TEntry", fieldbackground="#fffdf9", foreground=COLORS["text"], bordercolor=COLORS["line"], lightcolor=COLORS["line"], darkcolor=COLORS["line"], padding=8)
        style.configure("App.TCombobox", fieldbackground="#fffdf9", foreground=COLORS["text"], bordercolor=COLORS["line"], lightcolor=COLORS["line"], darkcolor=COLORS["line"], padding=6)
        style.map("App.TCombobox", fieldbackground=[("readonly", "#fffdf9")])
        style.configure("Budget.Treeview", background=COLORS["table_even"], fieldbackground=COLORS["table_even"], foreground=COLORS["text"], bordercolor=COLORS["line"], rowheight=34, font=("Segoe UI", 10))
        style.configure("Budget.Treeview.Heading", background=COLORS["panel_alt"], foreground=COLORS["text"], font=("Segoe UI Semibold", 10), relief="flat", padding=(10, 10))
        style.map("Budget.Treeview", background=[("selected", COLORS["select"])], foreground=[("selected", COLORS["text"])])
        style.map("Budget.Treeview.Heading", background=[("active", "#eadcca")])

    def build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, style="App.TFrame", padding=(28, 24, 28, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Домашний бюджет", style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Программа может работать сама по себе или синхронизироваться с телеграм-ботом через Railway.", style="HeaderMeta.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))

        body = ttk.Frame(self.root, style="App.TFrame", padding=(24, 12, 24, 24))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        left.grid_propagate(False)
        left.configure(width=340)

        left_inner = ttk.Frame(left, style="Panel.TFrame", padding=20)
        left_inner.pack(fill="both", expand=True)
        left_inner.columnconfigure(0, weight=1)
        left_inner.columnconfigure(1, weight=1)

        ttk.Label(left_inner, text="Новая операция", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(left_inner, text="Добавляйте покупки, доходы и платежи в пару кликов.", style="Body.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 18))

        self._build_field(left_inner, "Тип", 2)
        type_box = ttk.Combobox(left_inner, textvariable=self.type_var, values=["Доход", "Расход"], state="readonly", style="App.TCombobox")
        type_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_categories())

        self._build_field(left_inner, "Сумма", 4)
        ttk.Entry(left_inner, textvariable=self.amount_var, style="App.TEntry").grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._build_field(left_inner, "Категория", 6)
        self.category_box = ttk.Combobox(left_inner, textvariable=self.category_var, state="readonly", style="App.TCombobox")
        self.category_box.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._build_field(left_inner, "Дата", 8)
        ttk.Entry(left_inner, textvariable=self.date_var, style="App.TEntry").grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._build_field(left_inner, "Комментарий", 10)
        ttk.Entry(left_inner, textvariable=self.note_var, style="App.TEntry").grid(row=11, column=0, columnspan=2, sticky="ew", pady=(0, 18))

        ttk.Button(left_inner, text="Добавить запись", command=self.add_record_from_form, style="App.TButton").grid(row=12, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(left_inner, text="Очистить", command=self.clear_form, style="Secondary.TButton").grid(row=12, column=1, sticky="ew", padx=(6, 0))

        sync_card = tk.Frame(left_inner, bg=COLORS["panel_alt"], highlightbackground=COLORS["line"], highlightthickness=1)
        sync_card.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        sync_inner = ttk.Frame(sync_card, style="PanelAlt.TFrame", padding=14)
        sync_inner.pack(fill="both", expand=True)
        ttk.Label(sync_inner, text="Связь с ботом", style="MetricTitle.TLabel").pack(anchor="w")
        ttk.Label(sync_inner, textvariable=self.sync_var, style="MetricSub.TLabel", wraplength=260, justify="left").pack(anchor="w", pady=(6, 8))
        ttk.Button(sync_inner, text="Синхронизировать сейчас", command=lambda: self.sync_records(show_message=True), style="Secondary.TButton").pack(anchor="w")

        tips = tk.Frame(left_inner, bg=COLORS["panel_alt"], highlightbackground=COLORS["line"], highlightthickness=1)
        tips.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        tips_inner = ttk.Frame(tips, style="PanelAlt.TFrame", padding=14)
        tips_inner.pack(fill="both", expand=True)
        ttk.Label(tips_inner, text="Подсказка", style="MetricTitle.TLabel").pack(anchor="w")
        ttk.Label(tips_inner, text="Через Telegram можно писать, например: 2500 продукты или доход 50000 зарплата.", style="MetricSub.TLabel", wraplength=260, justify="left").pack(anchor="w", pady=(6, 0))

        right = ttk.Frame(body, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        metrics_wrap = ttk.Frame(right, style="App.TFrame")
        metrics_wrap.grid(row=0, column=0, sticky="ew")
        for i in range(3):
            metrics_wrap.columnconfigure(i, weight=1)

        self._create_metric_card(metrics_wrap, 0, "Доходы", "income", "income", "Все поступления за выбранный период")
        self._create_metric_card(metrics_wrap, 1, "Расходы", "expense", "expense", "Покупки, платежи и обязательные траты")
        self._create_metric_card(metrics_wrap, 2, "Баланс", "balance", "balance", "Разница между доходами и расходами")

        table_shell = tk.Frame(right, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
        table_shell.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        table_shell.grid_rowconfigure(1, weight=1)
        table_shell.grid_columnconfigure(0, weight=1)

        top_panel = ttk.Frame(table_shell, style="Panel.TFrame", padding=(18, 18, 18, 8))
        top_panel.grid(row=0, column=0, sticky="ew")
        top_panel.columnconfigure(0, weight=1)
        top_panel.columnconfigure(1, weight=0)

        text_block = ttk.Frame(top_panel, style="Panel.TFrame")
        text_block.grid(row=0, column=0, sticky="w")
        ttk.Label(text_block, text="История операций", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(text_block, text="Фильтруйте по месяцу и смотрите сводку без лишних действий.", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        controls = ttk.Frame(top_panel, style="Panel.TFrame")
        controls.grid(row=0, column=1, sticky="e")
        ttk.Label(controls, text="Месяц", style="Field.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.month_box = ttk.Combobox(controls, textvariable=self.month_var, state="readonly", width=14, style="App.TCombobox")
        self.month_box.grid(row=0, column=1, sticky="w", padx=(0, 10))
        self.month_box.bind("<<ComboboxSelected>>", lambda _event: self.apply_filter())
        ttk.Button(controls, text="Показать все", command=self.show_all, style="Secondary.TButton").grid(row=0, column=2, sticky="w", padx=(0, 10))
        ttk.Button(controls, text="Удалить", command=self.delete_selected, style="App.TButton").grid(row=0, column=3, sticky="w")

        table_area = ttk.Frame(table_shell, style="Panel.TFrame", padding=(18, 0, 18, 18))
        table_area.grid(row=1, column=0, sticky="nsew")
        table_area.columnconfigure(0, weight=1)
        table_area.rowconfigure(0, weight=1)
        table_area.rowconfigure(1, weight=0)

        columns = ("date", "type", "category", "amount", "note")
        self.tree = ttk.Treeview(table_area, columns=columns, show="headings", height=14, style="Budget.Treeview")
        headings = {"date": "Дата", "type": "Тип", "category": "Категория", "amount": "Сумма", "note": "Комментарий"}
        widths = {"date": 108, "type": 102, "category": 190, "amount": 120, "note": 430}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="e" if column == "amount" else "w")

        self.tree.tag_configure("even", background=COLORS["table_even"])
        self.tree.tag_configure("odd", background=COLORS["table_odd"])
        self.tree.tag_configure("income", foreground=COLORS["income"])
        self.tree.tag_configure("expense", foreground=COLORS["expense"])

        scrollbar = ttk.Scrollbar(table_area, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        monthly_wrap = tk.Frame(table_area, bg=COLORS["panel_alt"], highlightbackground=COLORS["line"], highlightthickness=1)
        monthly_wrap.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        monthly_inner = ttk.Frame(monthly_wrap, style="PanelAlt.TFrame", padding=14)
        monthly_inner.pack(fill="both", expand=True)
        ttk.Label(monthly_inner, text="Сводка по месяцам", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(monthly_inner, text="Короткая аналитика по месяцам, чтобы быстро видеть динамику.", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 10))

        monthly_text = tk.Text(monthly_inner, height=7, wrap="word", font=("Consolas", 10), bg="#fffdf8", fg=COLORS["text"], bd=0, highlightthickness=0, insertbackground=COLORS["text"], padx=4, pady=4)
        monthly_text.grid(row=2, column=0, sticky="ew")
        monthly_text.configure(state="disabled")
        self.monthly_text = monthly_text

        footer = ttk.Frame(self.root, style="App.TFrame", padding=(28, 0, 28, 14))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.status_var, style="HeaderMeta.TLabel").grid(row=0, column=0, sticky="w")

    def _build_field(self, parent: ttk.Frame, text: str, row: int) -> None:
        ttk.Label(parent, text=text, style="Field.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))

    def _create_metric_card(self, parent: ttk.Frame, column: int, title: str, key: str, color_key: str, subtitle: str) -> None:
        card = tk.Frame(parent, bg=COLORS["panel_alt"], highlightbackground=COLORS["line"], highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 9, 0), pady=0)
        inner = ttk.Frame(card, style="PanelAlt.TFrame", padding=(18, 16))
        inner.pack(fill="both", expand=True)
        ttk.Label(inner, text=title, style="MetricTitle.TLabel").grid(row=0, column=0, sticky="w")
        value = ttk.Label(inner, text="0 ₽", style="MetricValue.TLabel", foreground=COLORS[color_key])
        value.grid(row=1, column=0, sticky="w", pady=(8, 4))
        subtitle_label = ttk.Label(inner, text=subtitle, style="MetricSub.TLabel", wraplength=260, justify="left")
        subtitle_label.grid(row=2, column=0, sticky="w")
        self.metric_values[key] = value
        self.metric_subtitles[key] = subtitle_label

    def refresh_categories(self) -> None:
        categories = DEFAULT_CATEGORIES[self.type_var.get()]
        self.category_box["values"] = categories
        if self.category_var.get() not in categories:
            self.category_var.set(categories[0])
        self.status_var.set(f"Выбран тип: {self.type_var.get()}")

    def refresh_months(self) -> None:
        months = sorted({record["date"][:7] for record in self.records}, reverse=True)
        self.month_box["values"] = ["Все", *months]
        if self.month_var.get() not in self.month_box["values"]:
            self.month_var.set("Все")

    def set_records(self, records: list[dict]) -> None:
        self.records = records
        save_records(DATA_FILE, self.records)
        self.refresh_months()
        self.refresh_table()
        self.update_summary()

    def sync_records(self, show_message: bool) -> None:
        if not self.sync_client.enabled:
            self.sync_var.set("Синхронизация: локальный режим")
            if show_message:
                messagebox.showinfo("Синхронизация", "Сначала заполните sync_config.json или переменные окружения для подключения к Railway.")
            return
        try:
            records = self.sync_client.fetch_records()
        except RuntimeError as exc:
            self.sync_var.set("Синхронизация: ошибка подключения")
            self.status_var.set(str(exc))
            if show_message:
                messagebox.showerror("Синхронизация", str(exc))
            return

        self.set_records(records)
        self.sync_var.set("Синхронизация: подключена")
        self.status_var.set(f"Синхронизировано записей: {len(records)}")
        if show_message:
            messagebox.showinfo("Синхронизация", "Данные успешно обновлены из облака.")

    def add_record_from_form(self) -> None:
        raw_record = {"date": self.date_var.get(), "type": self.type_var.get(), "category": self.category_var.get(), "amount": self.amount_var.get(), "note": self.note_var.get().strip()}
        try:
            updated, record = add_record(self.records, raw_record)
        except ValueError as exc:
            messagebox.showerror("Ошибка", str(exc))
            return

        if self.sync_client.enabled:
            try:
                self.sync_client.add_record(record)
                updated = self.sync_client.fetch_records()
            except RuntimeError as exc:
                messagebox.showerror("Синхронизация", str(exc))
                self.status_var.set(str(exc))
                return

        self.set_records(updated)
        self.clear_form(keep_date=True)
        self.status_var.set(f"Запись добавлена: {record['category']} на {record['amount']:.2f} ₽")

    def clear_form(self, keep_date: bool = False) -> None:
        self.type_var.set("Расход")
        self.amount_var.set("")
        self.note_var.set("")
        if not keep_date:
            self.date_var.set(datetime.now().strftime(DATE_FORMAT))
        self.refresh_categories()

    def delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Удаление", "Сначала выберите запись в таблице.")
            return

        record_id = selected[0]
        if not messagebox.askyesno("Подтверждение", "Удалить выбранную запись?"):
            return

        updated, removed = delete_record(self.records, record_id)
        if removed is None:
            messagebox.showerror("Удаление", "Не удалось найти запись.")
            return

        if self.sync_client.enabled:
            try:
                self.sync_client.delete_record(record_id)
                updated = self.sync_client.fetch_records()
            except RuntimeError as exc:
                messagebox.showerror("Синхронизация", str(exc))
                self.status_var.set(str(exc))
                return

        self.set_records(updated)
        self.status_var.set(f"Удалена запись: {removed['category']} на {removed['amount']:.2f} ₽")

    def filtered_records(self) -> list[dict]:
        month = self.month_var.get()
        if month == "Все":
            return list(self.records)
        return [record for record in self.records if record["date"].startswith(month)]

    def refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, record in enumerate(self.filtered_records()):
            row_tag = "even" if index % 2 == 0 else "odd"
            type_tag = "income" if record["type"] == "Доход" else "expense"
            self.tree.insert("", "end", iid=record["id"], values=(record["date"], record["type"], record["category"], f"{record['amount']:.2f} ₽", record["note"] or "-"), tags=(row_tag, type_tag))

    def apply_filter(self) -> None:
        self.refresh_table()
        self.update_summary()
        self.status_var.set("Показаны все операции" if self.month_var.get() == "Все" else f"Фильтр по месяцу: {self.month_var.get()}")

    def show_all(self) -> None:
        self.month_var.set("Все")
        self.apply_filter()

    def update_summary(self) -> None:
        visible = self.filtered_records()
        totals = compute_totals(visible)
        self.metric_values["income"].config(text=f"{totals['income']:,.2f} ₽".replace(",", " "))
        self.metric_values["expense"].config(text=f"{totals['expense']:,.2f} ₽".replace(",", " "))
        self.metric_values["balance"].config(text=f"{totals['balance']:,.2f} ₽".replace(",", " "))

        self.metric_subtitles["income"].config(text=f"Операций в выборке: {len(visible)}")
        self.metric_subtitles["expense"].config(text=f"Всего записей в журнале: {len(self.records)}")
        balance_text = "Баланс положительный или нулевой" if totals["balance"] >= 0 else "Расходы сейчас превышают доходы"
        self.metric_subtitles["balance"].config(text=balance_text)
        self.metric_values["balance"].config(foreground=COLORS["balance"] if totals["balance"] >= 0 else COLORS["expense"])

        monthly = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
        for record in self.records:
            month = record["date"][:7]
            key = "income" if record["type"] == "Доход" else "expense"
            monthly[month][key] += record["amount"]

        lines = []
        for month in sorted(monthly.keys(), reverse=True):
            income_value = monthly[month]["income"]
            expense_value = monthly[month]["expense"]
            balance_value = income_value - expense_value
            lines.append(f"{month}: доход {income_value:,.2f} ₽ | расход {expense_value:,.2f} ₽ | баланс {balance_value:,.2f} ₽".replace(",", " "))
        if not lines:
            lines.append("Пока нет данных. Добавьте первую операцию.")

        self.monthly_text.configure(state="normal")
        self.monthly_text.delete("1.0", "end")
        self.monthly_text.insert("1.0", "\n".join(lines))
        self.monthly_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    BudgetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
