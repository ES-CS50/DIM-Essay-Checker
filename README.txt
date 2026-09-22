DIM Essay Bot — как собрать заново

Файлы которые должны лежать НА ГЛАВНОЙ странице GitHub
(не внутри другой папки):

  essay_bot.py
  requirements.txt
  .python-version
  .gitignore
  .env.example
  render.yaml

Файл .env на GitHub НЕ загружать.

Render
1. Оставь только ОДИН сервис. Второй нажми Suspend.
2. Environment:
   PYTHON_VERSION = 3.13.5
   TELEGRAM_TOKEN = токен BotFather
   GEMINI_API_KEY = ключ Gemini (aistudio.google.com/api-keys)
   DONATE_M10 = номер M10
   DONATE_ABB = номер карты
3. Root Directory — пусто
4. Build Command:
   pip install -r requirements.txt
5. Start Command:
   python essay_bot.py
6. Manual Deploy → Deploy latest commit

В Telegram
/start → язык → сначала ТЕМА → потом ЭССЕ

Компьютер можно выключить. Бота дома не запускай.
