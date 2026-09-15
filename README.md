# DIM Essay Checker Bot

Telegram-бот проверки параграфа по модели DIM 2027 (xarici dil, yazılı tapşırıq).

## Что умеет

1. Выбор языка объяснения: Azərbaycan / Русский / English
2. Кнопка поддержки: M10 и карта ABB
3. Сначала принимает **вопрос/тему**, потом **эссе от 100 слов**
4. Принимает текст и фото
5. Оценивает по критериям DIM: A + B + C + D (максимум 5)
6. Пишет, что исправить

## Важно про секреты

Файл `.env` нельзя класть в GitHub. В нём токен бота, ключ Groq и реквизиты.

Если токен или ключ уже светились в чате, GitHub или `.env.example`:

1. BotFather → `/revoke` и новый токен
2. Groq Console → создать новый API key, старый удалить
3. На Render в Environment заново прописать переменные

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполни TELEGRAM_TOKEN, GROQ_API_KEY, DONATE_M10, DONATE_ABB
python essay_bot.py
```

## Render (чтобы бот работал при выключенном компьютере)

Лучший тип сервиса: **Background Worker**.

1. Залей проект на GitHub **без** файла `.env`
2. Render → New → Background Worker
3. Build command: `pip install -r requirements.txt`
4. Start command: `python essay_bot.py`
5. Environment:
   - `PYTHON_VERSION` = `3.13.5`
   - `TELEGRAM_TOKEN`
   - `GROQ_API_KEY`
   - `DONATE_M10`
   - `DONATE_ABB`
6. Deploy

Если уже создан Web Service:

- Start command всё равно `python essay_bot.py`
- в коде есть маленький health-сервер на `$PORT`, чтобы Render не считал сервис мёртвым
- всё равно поставь `PYTHON_VERSION=3.13.5`
- не запускай того же бота одновременно на компьютере и на Render

Файл `.python-version` уже стоит на `3.13`, чтобы не брать Python 3.14. На 3.14 старые версии `python-telegram-bot` падают с ошибкой:

`RuntimeError: There is no current event loop in thread 'MainThread'`

## Как пользоваться ботом

1. `/start`
2. Выбрать язык
3. Отправить вопрос эссе (текст или фото)
4. Отправить сам абзац (текст или фото)
5. Получить баллы и советы
6. При желании нажать «Поддержать»

Оценка ориентир для тренировки, не официальный балл DIM.
