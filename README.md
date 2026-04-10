# Учет бюджета + Telegram бот

Теперь проект состоит из двух частей:

- `app.py` — программа для просмотра бюджета и ручного ввода;
- `telegram_budget_service.py` — сервис для Railway, который принимает сообщения из Telegram и хранит общий бюджет.

## Как это работает

1. Вы пишете боту в Telegram: `2500 продукты` или `доход 50000 зарплата`.
2. Бот сохраняет запись в общее хранилище на Railway.
3. Программа `app.py` по кнопке или при запуске синхронизирует записи из облака.

## Команды бота

- `/help`
- `/categories`
- `/balance`
- `/month`
- `/last`

Примеры обычных сообщений:

- `2500 продукты`
- `расход 1800 бензин`
- `доход 50000 зарплата`
- `доход 3000 подарок от бабушки`

## Настройка Railway

### 1. Создайте Telegram-бота

У `@BotFather` создайте бота и получите `TELEGRAM_BOT_TOKEN`.

### 2. Придумайте секретный API-токен

Это любая длинная секретная строка. Она нужна для связи локальной программы с вашим сервисом.

### 3. Загрузите проект на Railway

Для сервиса задайте переменные окружения:

- `TELEGRAM_BOT_TOKEN`
- `BUDGET_API_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_ID`
- `BUDGET_DATA_FILE=/data/budget_data.json`
- `BUDGET_PUBLIC_BASE_URL=https://your-budget-bot.up.railway.app`

Стартовая команда:

```text
python telegram_budget_service.py
```

### 4. Добавьте Volume в Railway

Чтобы данные не пропадали после перезапуска:

- создайте `Volume`;
- смонтируйте его в `/data`;
- используйте `BUDGET_DATA_FILE=/data/budget_data.json`.

## Подключение программы к облаку

1. Скопируйте `sync_config.example.json` в `sync_config.json`.
2. Заполните:

```json
{
  "base_url": "https://your-budget-bot.up.railway.app",
  "api_token": "ваш-секретный-токен",
  "timeout": 15
}
```

После этого `app.py` будет синхронизировать записи из облака.

## Локальный запуск для проверки

- `run_budget_app.bat`
- `run_budget_bot_local.bat`

Локальный запуск бота работает только пока включен компьютер.
