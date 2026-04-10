from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from storage import DATE_FORMAT, DEFAULT_CATEGORIES, add_record, compute_totals, delete_record, load_records, save_records


PORT = int(os.getenv("PORT", "8080"))
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_TOKEN = os.getenv("BUDGET_API_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
DATA_FILE = Path(os.getenv("BUDGET_DATA_FILE", str(Path("data") / "budget_data.json"))).resolve()
PUBLIC_BASE_URL = os.getenv("BUDGET_PUBLIC_BASE_URL", "").rstrip("/")

records_lock = threading.Lock()


def load_current_records() -> list[dict[str, Any]]:
    with records_lock:
        return load_records(DATA_FILE)


def save_current_records(records: list[dict[str, Any]]) -> None:
    with records_lock:
        save_records(DATA_FILE, records)


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def get_request_token(handler: BaseHTTPRequestHandler) -> str:
    parsed = parse.urlparse(handler.path)
    params = parse.parse_qs(parsed.query)
    token = params.get("token", [""])[0].strip()
    return token or handler.headers.get("X-API-Token", "").strip()


class BudgetApiHandler(BaseHTTPRequestHandler):
    server_version = "BudgetBot/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/health":
            json_response(self, HTTPStatus.OK, {"ok": True, "service": "budget-bot"})
            return
        if parsed.path == "/categories":
            if not self._authorized():
                return
            json_response(self, HTTPStatus.OK, {"categories": DEFAULT_CATEGORIES})
            return
        if parsed.path == "/records":
            if not self._authorized():
                return
            json_response(self, HTTPStatus.OK, {"records": load_current_records()})
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден."})

    def do_POST(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path != "/records":
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден."})
            return
        if not self._authorized():
            return

        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Некорректный JSON."})
            return

        records = load_current_records()
        try:
            updated, record = add_record(records, payload)
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        save_current_records(updated)
        json_response(self, HTTPStatus.CREATED, {"ok": True, "record": record})

    def do_DELETE(self) -> None:
        parsed = parse.urlparse(self.path)
        if not parsed.path.startswith("/records/"):
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден."})
            return
        if not self._authorized():
            return

        record_id = parse.unquote(parsed.path.rsplit("/", 1)[-1])
        records = load_current_records()
        updated, removed = delete_record(records, record_id)
        if removed is None:
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Запись не найдена."})
            return

        save_current_records(updated)
        json_response(self, HTTPStatus.OK, {"ok": True, "record": removed})

    def _authorized(self) -> bool:
        if not API_TOKEN:
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "На сервере не настроен BUDGET_API_TOKEN."})
            return False
        if get_request_token(self) != API_TOKEN:
            json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "Неверный токен API."})
            return False
        return True


def telegram_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not BOT_TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = parse.urlencode(payload).encode("utf-8")
    req = request.Request(url, data=data, method="POST")
    with request.urlopen(req, timeout=70) as response:
        body = response.read().decode("utf-8")
    parsed_body = json.loads(body)
    if not parsed_body.get("ok"):
        raise RuntimeError(str(parsed_body))
    return parsed_body


def send_message(chat_id: str, text: str) -> None:
    telegram_api("sendMessage", {"chat_id": chat_id, "text": text})


def category_lookup() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for record_type, categories in DEFAULT_CATEGORIES.items():
        for category in categories:
            rows.append((record_type, category))
    return sorted(rows, key=lambda item: len(item[1]), reverse=True)


def parse_expense_or_income(text: str) -> dict[str, Any]:
    raw = " ".join(text.strip().split())
    if not raw:
        raise ValueError("Пустое сообщение.")

    lowered = raw.casefold()
    record_type = "Расход"
    remainder = raw
    if lowered.startswith("доход "):
        record_type = "Доход"
        remainder = raw[6:].strip()
    elif lowered.startswith("расход "):
        record_type = "Расход"
        remainder = raw[7:].strip()

    parts = remainder.split(maxsplit=1)
    if not parts:
        raise ValueError("Не вижу сумму. Пример: 2500 продукты")

    amount_token = parts[0].replace(",", ".")
    try:
        amount = float(amount_token)
    except ValueError as exc:
        raise ValueError("Не удалось распознать сумму. Пример: 2500 продукты") from exc

    tail = parts[1].strip() if len(parts) > 1 else ""
    if not tail:
        raise ValueError("После суммы укажите категорию. Пример: 2500 продукты")

    matched_category = None
    note = ""
    for category_type, category_name in category_lookup():
        if category_type != record_type:
            continue
        category_key = category_name.casefold()
        if tail.casefold() == category_key:
            matched_category = category_name
            break
        if tail.casefold().startswith(category_key + " "):
            matched_category = category_name
            note = tail[len(category_name):].strip()
            break

    if not matched_category:
        categories = ", ".join(DEFAULT_CATEGORIES[record_type])
        raise ValueError(f"Не удалось найти категорию. Доступные категории для '{record_type}': {categories}")

    return {
        "date": datetime.now().strftime(DATE_FORMAT),
        "type": record_type,
        "category": matched_category,
        "amount": amount,
        "note": note,
    }


def month_records(records: list[dict[str, Any]], month: str) -> list[dict[str, Any]]:
    return [record for record in records if record["date"].startswith(month)]


def summary_text(records: list[dict[str, Any]]) -> str:
    totals = compute_totals(records)
    return (
        f"Доходы: {totals['income']:,.2f} ₽\n"
        f"Расходы: {totals['expense']:,.2f} ₽\n"
        f"Баланс: {totals['balance']:,.2f} ₽"
    ).replace(",", " ")


def handle_message(chat_id: str, text: str) -> None:
    clean = (text or "").strip()
    if not clean:
        return

    if clean.startswith("/"):
        command = clean.split()[0].split("@", 1)[0]
        if command in {"/start", "/help"}:
            send_message(chat_id, "Команды:\n/help\n/categories\n/balance\n/month\n/last\n\nБыстрый ввод:\n2500 продукты\nрасход 1500 бензин\nдоход 50000 зарплата\nдоход 3000 подарок от бабушки")
            return
        if command == "/categories":
            lines = [f"{kind}: " + ", ".join(categories) for kind, categories in DEFAULT_CATEGORIES.items()]
            send_message(chat_id, "\n\n".join(lines))
            return
        if command in {"/balance", "/month"}:
            month = datetime.now().strftime("%Y-%m")
            records = month_records(load_current_records(), month)
            send_message(chat_id, f"Месяц: {month}\nЗаписей: {len(records)}\n" + summary_text(records))
            return
        if command == "/last":
            records = load_current_records()[:5]
            if not records:
                send_message(chat_id, "Пока нет записей.")
                return
            lines = [f"{item['date']} | {item['type']} | {item['category']} | {item['amount']:.2f} ₽ | {item['note'] or '-'}" for item in records]
            send_message(chat_id, "Последние записи:\n" + "\n".join(lines))
            return
        send_message(chat_id, "Неизвестная команда. Напишите /help")
        return

    try:
        new_record = parse_expense_or_income(clean)
        records = load_current_records()
        updated, record = add_record(records, new_record)
        save_current_records(updated)
    except ValueError as exc:
        send_message(chat_id, f"Не получилось добавить запись. {exc}")
        return

    month = datetime.now().strftime("%Y-%m")
    totals = compute_totals(month_records(updated, month))
    send_message(chat_id, (f"Записала: {record['type']} {record['amount']:.2f} ₽\nКатегория: {record['category']}\nКомментарий: {record['note'] or '-'}\n\nТекущий месяц {month}:\nДоходы: {totals['income']:,.2f} ₽\nРасходы: {totals['expense']:,.2f} ₽\nБаланс: {totals['balance']:,.2f} ₽").replace(",", " "))


def poll_updates() -> None:
    offset = 0
    while True:
        try:
            result = telegram_api("getUpdates", {"timeout": 50, "offset": offset})
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                chat_id = str(message.get("chat", {}).get("id", ""))
                if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
                    send_message(chat_id, "Этот бот настроен только для одного владельца.")
                    continue
                handle_message(chat_id, message.get("text", ""))
        except Exception as exc:
            print(f"Polling error: {exc}", flush=True)
            time.sleep(5)


def start_http_server() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), BudgetApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


def startup_message() -> str:
    base = PUBLIC_BASE_URL or f"http://localhost:{PORT}"
    return f"Budget bot service started\nHTTP: {base}\nData file: {DATA_FILE}\nChat restriction: {'enabled' if ALLOWED_CHAT_ID else 'disabled'}"


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")
    if not API_TOKEN:
        raise SystemExit("BUDGET_API_TOKEN is required")

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_current_records(load_current_records())
    start_http_server()
    print(startup_message(), flush=True)
    poll_updates()


if __name__ == "__main__":
    main()
