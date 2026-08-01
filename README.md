# Telegram AI Assistant Bot

Простой Telegram-бот с AI-ассистентом на Python, который отвечает на сообщения через OpenAI.

## Что умеет бот

- Команда /start
- Команда /help
- Обработка любых текстовых сообщений
- Ответы через OpenAI GPT
- Готовность к запуску на Railway

## 1. Создание Telegram бота

1. Откройте Telegram и найдите @BotFather.
2. Отправьте команду /newbot.
3. Следуйте инструкциям и получите BOT_TOKEN.

## 2. Получение OpenAI API ключа

1. Перейдите на https://platform.openai.com/
2. Создайте API key.
3. Скопируйте ключ в переменную OPENAI_API_KEY.

## 3. Локальный запуск

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Создайте файл .env на основе .env.example:
   ```bash
   cp .env.example .env
   ```
3. Заполните .env:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   WEBHOOK_URL=https://your-railway-app.up.railway.app
   PORT=8000
   ```
4. Запустите бота:
   ```bash
   python bot/main.py
   ```

## 4. Деплой на Railway

1. Создайте новый проект на Railway.
2. Подключите репозиторий.
3. Укажите переменные окружения:
   - BOT_TOKEN
   - OPENAI_API_KEY
   - WEBHOOK_URL=https://bffai-production.up.railway.app
   - PORT=8000
4. Railway автоматически использует Dockerfile и запустит команду:
   ```bash
   python bot/main.py
   ```

## 5. Проверка работы

1. Запустите бота.
2. Напишите ему в Telegram.
3. Проверьте ответ на команду /start и на обычное сообщение.

## Структура проекта

- bot/main.py — точка входа
- bot/handlers.py — обработчики команд и сообщений
- bot/openai_client.py — интеграция с OpenAI
- bot/config.py — конфигурация из env
- bot/prompts.py — системный промпт
