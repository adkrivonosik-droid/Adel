from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


DATE_FORMAT = "%Y-%m-%d"
DEFAULT_CATEGORIES = {
    "Доход": ["Зарплата", "Подработка", "Подарок", "Накопление на отпуск", "Другое"],
    "Расход": [
        "Продукты",
        "Транспорт",
        "Бензин",
        "Жилье",
        "Здоровье",
        "Детский сад",
        "Бьюти",
        "Развлечения",
        "Одежда",
        "Кредитка Халва",
        "Кредитка Тинькофф",
        "Другое",
    ],
}
VALID_TYPES = tuple(DEFAULT_CATEGORIES.keys())


def sort_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda item: (item.get("date", ""), item.get("created_at", ""), item.get("id", "")),
        reverse=True,
    )


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    record_type = str(raw.get("type", "")).strip().title()
    if record_type not in VALID_TYPES:
        raise ValueError("Тип должен быть 'Доход' или 'Расход'.")

    amount_raw = str(raw.get("amount", "")).replace(",", ".").strip()
    try:
        amount = round(float(amount_raw), 2)
    except ValueError as exc:
        raise ValueError("Введите корректную сумму.") from exc
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")

    date_value = str(raw.get("date", "")).strip()
    try:
        datetime.strptime(date_value, DATE_FORMAT)
    except ValueError as exc:
        raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД.") from exc

    category = str(raw.get("category", "")).strip()
    if not category:
        raise ValueError("Категория не должна быть пустой.")

    note = str(raw.get("note", "")).strip()
    created_at = str(raw.get("created_at") or datetime.utcnow().isoformat(timespec="seconds"))

    return {
        "id": str(raw.get("id") or uuid.uuid4().hex),
        "date": date_value,
        "type": record_type,
        "category": category,
        "amount": amount,
        "note": note,
        "created_at": created_at,
    }


def migrate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for raw in records:
        try:
            normalized.append(normalize_record(raw))
        except ValueError:
            continue
    return sort_records(normalized)


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    records = migrate_records(raw)
    if records != raw:
        save_records(path, records)
    return records


def save_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sort_records(records), ensure_ascii=False, indent=2), encoding="utf-8")


def add_record(records: list[dict[str, Any]], raw_record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    record = normalize_record(raw_record)
    updated = sort_records([*records, record])
    return updated, record


def delete_record(records: list[dict[str, Any]], record_id: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    removed = None
    remaining = []
    for record in records:
        if record["id"] == record_id and removed is None:
            removed = record
            continue
        remaining.append(record)
    return sort_records(remaining), removed


def compute_totals(records: list[dict[str, Any]]) -> dict[str, float]:
    income = sum(record["amount"] for record in records if record["type"] == "Доход")
    expense = sum(record["amount"] for record in records if record["type"] == "Расход")
    return {"income": income, "expense": expense, "balance": income - expense}
