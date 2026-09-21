#!/usr/bin/env python3
"""DIM 2027 foreign-language paragraph checker Telegram bot."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO

from dotenv import load_dotenv
from groq import Groq
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

load_dotenv()

# Python 3.14 no longer creates an event loop automatically.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("essay_bot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DONATE_M10 = os.getenv("DONATE_M10", "").strip()
DONATE_ABB = os.getenv("DONATE_ABB", "").strip()

TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
VISION_MODEL = os.getenv(
    "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
)

STEP_LANG = "lang"
STEP_TOPIC = "topic"
STEP_ESSAY = "essay"

TEXTS = {
    "az": {
        "choose_lang": "Dil seçin / Choose language:",
        "welcome": (
            "Salam! Mən DIM 2027 xarici dil yazı tapşırığını yoxlayan botam.\n\n"
            "1) Əvvəlcə sualı / mövzunu göndər.\n"
            "2) Sonra paraqrafı göndər (minimum 100 söz).\n\n"
            "Mətn və ya şəkil qəbul edirəm."
        ),
        "ask_topic": "Əvvəlcə esse sualını və ya mövzunu yaz və ya şəkilini göndər.",
        "got_topic": "Mövzu qəbul olundu.\n\nİndi paraqrafı göndər (mətn və ya şəkil, minimum 100 söz).",
        "checking": "Yoxlayıram, bir az gözlə...",
        "need_topic_first": "Əvvəlcə mövzunu / sualı göndər.",
        "empty_ocr": "Şəkildə mətn oxunmadı. Daha aydın foto göndər və ya mətni yaz.",
        "error": "Xəta baş verdi. Bir az sonra yenidən yoxla.",
        "donate_btn": "Dəstək ol",
        "donate_title": "Dəstək üçün Stars, M10 və ya ABB:",
        "donate_stars": "Telegram Stars ilə dəstək",
        "donate_thanks": "Təşəkkür edirəm! Dəstəyiniz üçün minnətdaram.",
        "new_check": "Yeni yoxlama",
        "change_lang": "Dili dəyiş",
        "m10": "M10",
        "abb": "ABB kart",
        "lang_set": "Dil: Azərbaycan.",
        "invoice_title": "DIM Essay Bot dəstəyi",
        "invoice_desc": "Botun işləməsi üçün könüllü dəstək.",
    },
    "ru": {
        "choose_lang": "Dil seçin / Choose language:",
        "welcome": (
            "Привет! Я бот проверки письменного задания DIM 2027.\n\n"
            "1) Сначала пришли вопрос / тему эссе.\n"
            "2) Потом пришли сам абзац (минимум 100 слов).\n\n"
            "Принимаю текст и фото."
        ),
        "ask_topic": "Сначала отправь вопрос или тему эссе текстом или фото.",
        "got_topic": "Тема принята.\n\nТеперь пришли абзац (текст или фото, минимум 100 слов).",
        "checking": "Проверяю, подожди немного...",
        "need_topic_first": "Сначала пришли тему / вопрос.",
        "empty_ocr": "На фото текст не распознан. Пришли более чёткое фото или напиши текст.",
        "error": "Произошла ошибка. Попробуй ещё раз чуть позже.",
        "donate_btn": "Поддержать",
        "donate_title": "Поддержать Stars, M10 или картой ABB:",
        "donate_stars": "Поддержать Telegram Stars",
        "donate_thanks": "Спасибо за поддержку!",
        "new_check": "Новая проверка",
        "change_lang": "Сменить язык",
        "m10": "M10",
        "abb": "Карта ABB",
        "lang_set": "Язык: русский.",
        "invoice_title": "Поддержка DIM Essay Bot",
        "invoice_desc": "Добровольная поддержка работы бота.",
    },
    "en": {
        "choose_lang": "Dil seçin / Choose language:",
        "welcome": (
            "Hi! I check DIM 2027 foreign-language writing tasks.\n\n"
            "1) First send the essay question / topic.\n"
            "2) Then send your paragraph (at least 100 words).\n\n"
            "I accept text and photos."
        ),
        "ask_topic": "First send the question or topic as text or a photo.",
        "got_topic": "Topic received.\n\nNow send your paragraph (text or photo, at least 100 words).",
        "checking": "Checking, please wait...",
        "need_topic_first": "Please send the topic / question first.",
        "empty_ocr": "I could not read the text on the photo. Send a clearer picture or type the text.",
        "error": "Something went wrong. Please try again in a moment.",
        "donate_btn": "Donate",
        "donate_title": "Support with Stars, M10 or ABB card:",
        "donate_stars": "Donate with Telegram Stars",
        "donate_thanks": "Thank you for your support!",
        "new_check": "New check",
        "change_lang": "Change language",
        "m10": "M10",
        "abb": "ABB card",
        "lang_set": "Language: English.",
        "invoice_title": "Support DIM Essay Bot",
        "invoice_desc": "Voluntary support to keep the bot running.",
    },
}

DIM_RUBRIC = """
You are a strict but fair examiner for Azerbaijan DIM 2027 upper-secondary
foreign-language writing (one paragraph, minimum 100 words).

Structure expected:
- topic sentence (limited topic + controlling idea)
- 2 supporting ideas, each with example/fact/evidence
- opposite opinion + short response
- concluding sentence
- linking words, unity, coherence

Official criteria (max 5 points):

A Task fulfilment (0 / 0.5 / 1)
  1: foreign language, on topic, >=100 words, topic+support+conclusion present, fluent links
  0.5: mostly on topic, 70-99 words, only part of the structure, weak links
  0: unreadable / off-topic / <70 words / memorized template / copied prompt
  NOTE: if A = 0, B/C/D must also be 0. Total = 0.

B Topic coverage and logic (0 / 1 / 2)
  2: at least two clear arguments with examples, linking devices, BOTH sides (for and against), logical flow
  1: limited arguments, only one side, one weak example, few linkers, some irrelevance
  0: does not meet band 1

C Grammar (0 / 0.5 / 1)
  1: simple AND complex sentences used correctly
  0.5: mostly simple/short/template sentences; errors sometimes block meaning
  0: word pile, cannot build sentences

D Vocabulary (0 / 0.5 / 1)
  1: rich topic vocabulary, paraphrase, little repetition
  0.5: enough words but some repetition / inaccuracy
  0: very poor / heavy repetition

Answer ONLY valid JSON with this schema:
{
  "word_count": 0,
  "score_a": 0,
  "score_b": 0,
  "score_c": 0,
  "score_d": 0,
  "total": 0,
  "topic_sentence_ok": true,
  "has_two_supports": true,
  "has_counter": true,
  "has_conclusion": true,
  "strengths": ["..."],
  "problems": ["..."],
  "advice": ["specific action 1", "specific action 2", "specific action 3"],
  "improved_topic_sentence": "...",
  "comment": "short overall comment"
}
"""


def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["az"]).get(key, key)


def lang_of(context: ContextTypes.DEFAULT_TYPE) -> str:
    return (context.user_data or {}).get("lang", "az")


STAR_PACKS = (15, 50, 100, 250)


def main_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(lang, "new_check"), callback_data="new_check"),
                InlineKeyboardButton(t(lang, "donate_btn"), callback_data="donate"),
            ],
            [InlineKeyboardButton(t(lang, "change_lang"), callback_data="change_lang")],
        ]
    )


def donate_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"⭐ {n}", callback_data=f"star_{n}") for n in STAR_PACKS[:2]],
        [InlineKeyboardButton(f"⭐ {n}", callback_data=f"star_{n}") for n in STAR_PACKS[2:]],
        [
            InlineKeyboardButton(t(lang, "new_check"), callback_data="new_check"),
            InlineKeyboardButton(t(lang, "change_lang"), callback_data="change_lang"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Azərbaycan dili", callback_data="lang_az")],
            [InlineKeyboardButton("Русский язык", callback_data="lang_ru")],
            [InlineKeyboardButton("English Language", callback_data="lang_en")],
            [InlineKeyboardButton("Dəstək / Поддержать / Donate", callback_data="donate")],
        ]
    )


def donate_text(lang: str) -> str:
    lines = [t(lang, "donate_title"), ""]
    if DONATE_M10:
        lines.append(f"{t(lang, 'm10')}: `{DONATE_M10}`")
    if DONATE_ABB:
        lines.append(f"{t(lang, 'abb')}: `{DONATE_ABB}`")
    if not DONATE_M10 and not DONATE_ABB:
        lines.append("—")
    return "\n".join(lines)


def groq_client() -> Groq:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing")
    return Groq(api_key=GROQ_API_KEY)


async def extract_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    msg = update.effective_message
    if not msg:
        return ""
    if msg.text and not msg.text.startswith("/"):
        return msg.text.strip()
    if msg.caption and not msg.photo:
        return msg.caption.strip()
    if msg.photo:
        photo = msg.photo[-1]
        tg_file = await context.bot.get_file(photo.file_id)
        raw = BytesIO()
        await tg_file.download_to_memory(raw)
        image_bytes = raw.getvalue()
        caption = (msg.caption or "").strip()
        ocr = await ocr_image(image_bytes)
        if caption and ocr:
            return f"{caption}\n{ocr}".strip()
        return (ocr or caption).strip()
    if msg.document and (msg.document.mime_type or "").startswith("image/"):
        tg_file = await context.bot.get_file(msg.document.file_id)
        raw = BytesIO()
        await tg_file.download_to_memory(raw)
        return (await ocr_image(raw.getvalue())).strip()
    return ""


async def ocr_image(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"
    client = groq_client()

    def _call() -> str:
        completion = client.chat.completions.create(
            model=VISION_MODEL,
            temperature=0.1,
            max_completion_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Transcribe ALL readable text from this student photo. "
                                "Keep original language and line breaks. "
                                "Do not translate, do not correct, do not add comments. "
                                "If there is almost no text, return EMPTY."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        return (completion.choices[0].message.content or "").strip()

    text = await asyncio.to_thread(_call)
    if text.upper() in {"EMPTY", "N/A", "NONE"}:
        return ""
    return text


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        raise ValueError("Model did not return JSON")
    return json.loads(match.group(0))


async def evaluate_essay(topic: str, essay: str, lang: str) -> dict:
    words = len(re.findall(r"\w+", essay, flags=re.UNICODE))
    lang_name = {"az": "Azerbaijani", "ru": "Russian", "en": "English"}[lang]
    prompt = (
        f"Reply language for comment/advice: {lang_name}.\n"
        f"QUESTION / TOPIC:\n{topic}\n\n"
        f"STUDENT PARAGRAPH ({words} raw tokens):\n{essay}\n"
    )
    client = groq_client()

    def _call() -> str:
        completion = client.chat.completions.create(
            model=TEXT_MODEL,
            temperature=0.2,
            max_completion_tokens=1400,
            messages=[
                {"role": "system", "content": DIM_RUBRIC},
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content or ""

    raw = await asyncio.to_thread(_call)
    data = parse_json(raw)
    data["word_count"] = int(data.get("word_count") or words)
    try:
        a = float(data.get("score_a", 0))
        b = float(data.get("score_b", 0))
        c = float(data.get("score_c", 0))
        d = float(data.get("score_d", 0))
    except (TypeError, ValueError):
        a = b = c = d = 0
    if a <= 0:
        b = c = d = 0
    data["score_a"], data["score_b"], data["score_c"], data["score_d"] = a, b, c, d
    data["total"] = round(a + b + c + d, 1)
    return data


def format_result(data: dict, lang: str, topic: str) -> str:
    titles = {
        "az": {
            "head": "Nəticə (DIM 2027)",
            "topic": "Mövzu",
            "words": "Söz sayı",
            "total": "Ümumi bal",
            "struct": "Struktur",
            "good": "Güclü tərəflər",
            "bad": "Problemlər",
            "advice": "Nə etməli",
            "topic_s": "Daha yaxşı baş cümlə",
        },
        "ru": {
            "head": "Результат (DIM 2027)",
            "topic": "Тема",
            "words": "Количество слов",
            "total": "Итого",
            "struct": "Структура",
            "good": "Сильные стороны",
            "bad": "Проблемы",
            "advice": "Что сделать",
            "topic_s": "Лучшее первое предложение",
        },
        "en": {
            "head": "Result (DIM 2027)",
            "topic": "Topic",
            "words": "Word count",
            "total": "Total",
            "struct": "Structure",
            "good": "Strengths",
            "bad": "Problems",
            "advice": "What to do",
            "topic_s": "Better topic sentence",
        },
    }[lang]

    yes = {"az": "var", "ru": "есть", "en": "yes"}[lang]
    no = {"az": "yox", "ru": "нет", "en": "no"}[lang]
    flags = [
        f"topic sentence: {yes if data.get('topic_sentence_ok') else no}",
        f"2 supports: {yes if data.get('has_two_supports') else no}",
        f"counter-argument: {yes if data.get('has_counter') else no}",
        f"conclusion: {yes if data.get('has_conclusion') else no}",
    ]
    strengths = data.get("strengths") or []
    problems = data.get("problems") or []
    advice = data.get("advice") or []

    parts = [
        titles["head"],
        f"{titles['topic']}: {topic[:180]}",
        f"{titles['words']}: {data.get('word_count')}",
        "",
        f"A (task): {data.get('score_a')} / 1",
        f"B (logic): {data.get('score_b')} / 2",
        f"C (grammar): {data.get('score_c')} / 1",
        f"D (vocab): {data.get('score_d')} / 1",
        f"{titles['total']}: {data.get('total')} / 5",
        "",
        titles["struct"],
        *[f"- {x}" for x in flags],
    ]
    if strengths:
        parts += ["", titles["good"], *[f"- {x}" for x in strengths[:4]]]
    if problems:
        parts += ["", titles["bad"], *[f"- {x}" for x in problems[:5]]]
    if advice:
        parts += ["", titles["advice"], *[f"- {x}" for x in advice[:5]]]
    if data.get("improved_topic_sentence"):
        parts += ["", titles["topic_s"], data["improved_topic_sentence"]]
    if data.get("comment"):
        parts += ["", data["comment"]]
    return "\n".join(parts)


async def safe_reply(message, text: str, **kwargs) -> None:
    try:
        await message.reply_text(text, **kwargs)
    except Exception:
        kwargs.pop("parse_mode", None)
        await message.reply_text(text, **kwargs)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data is not None:
        context.user_data.clear()
    context.user_data["step"] = STEP_LANG
    if update.message:
        await update.message.reply_text(
            TEXTS["az"]["choose_lang"],
            reply_markup=lang_keyboard(),
        )


async def on_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    code = query.data.split("_", 1)[1]
    context.user_data["lang"] = code
    context.user_data["topic"] = None
    context.user_data["step"] = STEP_TOPIC
    try:
        await query.edit_message_text(
            f"{t(code, 'lang_set')}\n\n{t(code, 'welcome')}",
            reply_markup=main_keyboard(code),
        )
    except Exception:
        pass
    await query.message.reply_text(t(code, "ask_topic"))


async def on_donate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = lang_of(context)
    text = f"{t(lang, 'donate_stars')}\n\n{donate_text(lang)}"
    try:
        await query.message.reply_text(
            text, parse_mode="Markdown", reply_markup=donate_keyboard(lang)
        )
    except Exception:
        await query.message.reply_text(text, reply_markup=donate_keyboard(lang))


async def on_star(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = lang_of(context)
    amount = int(query.data.split("_", 1)[1])
    try:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=t(lang, "invoice_title"),
            description=t(lang, "invoice_desc"),
            payload=f"stars_{amount}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{amount} Stars", amount=amount)],
        )
    except Exception:
        log.exception("stars invoice failed")
        await query.message.reply_text(t(lang, "error"), reply_markup=donate_keyboard(lang))


async def on_precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)


async def on_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = lang_of(context)
    await update.effective_message.reply_text(
        t(lang, "donate_thanks"), reply_markup=main_keyboard(lang)
    )


async def on_change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["step"] = STEP_LANG
    context.user_data["topic"] = None
    await query.edit_message_text(TEXTS["az"]["choose_lang"], reply_markup=lang_keyboard())


async def on_new_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["topic"] = None
    if not context.user_data.get("lang"):
        context.user_data["step"] = STEP_LANG
        await query.message.reply_text(TEXTS["az"]["choose_lang"], reply_markup=lang_keyboard())
        return
    context.user_data["step"] = STEP_TOPIC
    lang = lang_of(context)
    await query.message.reply_text(t(lang, "ask_topic"), reply_markup=main_keyboard(lang))


async def receive_any(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("lang"):
        context.user_data["step"] = STEP_LANG
        await update.effective_message.reply_text(
            TEXTS["az"]["choose_lang"], reply_markup=lang_keyboard()
        )
        return

    lang = lang_of(context)
    step = context.user_data.get("step") or STEP_TOPIC

    if step != STEP_ESSAY:
        text = await extract_user_text(update, context)
        if not text:
            await update.effective_message.reply_text(t(lang, "empty_ocr"))
            return
        context.user_data["topic"] = text
        context.user_data["step"] = STEP_ESSAY
        await update.effective_message.reply_text(t(lang, "got_topic"))
        return

    topic = context.user_data.get("topic")
    if not topic:
        context.user_data["step"] = STEP_TOPIC
        await update.effective_message.reply_text(t(lang, "need_topic_first"))
        return

    wait_msg = await update.effective_message.reply_text(t(lang, "checking"))
    try:
        essay = await extract_user_text(update, context)
        if not essay:
            await wait_msg.edit_text(t(lang, "empty_ocr"))
            return
        result = await evaluate_essay(topic, essay, lang)
        text = format_result(result, lang, topic)
        try:
            await wait_msg.edit_text(text, reply_markup=main_keyboard(lang))
        except Exception:
            await update.effective_message.reply_text(
                text, reply_markup=main_keyboard(lang)
            )
    except Exception as exc:
        log.exception("evaluate failed")
        hint = str(exc)[:180].replace(GROQ_API_KEY or "", "").replace(TELEGRAM_TOKEN or "", "")
        await wait_msg.edit_text(
            f"{t(lang, 'error')}\n{hint}",
            reply_markup=main_keyboard(lang),
        )
    context.user_data["topic"] = None
    context.user_data["step"] = STEP_TOPIC


def start_health_server() -> None:
    port_raw = os.getenv("PORT")
    if not port_raw:
        return
    port = int(port_raw)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            return

    def _run():
        HTTPServer(("0.0.0.0", port), Handler).serve_forever()

    threading.Thread(target=_run, daemon=True).start()
    log.info("Health server on port %s", port)


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN is not set")
    if not GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY is not set")

    start_health_server()

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    incoming = (filters.TEXT | filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(on_lang, pattern=r"^lang_(az|ru|en)$"))
    application.add_handler(CallbackQueryHandler(on_donate, pattern=r"^donate$"))
    application.add_handler(CallbackQueryHandler(on_star, pattern=r"^star_\d+$"))
    application.add_handler(CallbackQueryHandler(on_change_lang, pattern=r"^change_lang$"))
    application.add_handler(CallbackQueryHandler(on_new_check, pattern=r"^new_check$"))
    application.add_handler(PreCheckoutQueryHandler(on_precheckout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment))
    application.add_handler(MessageHandler(incoming, receive_any))
    log.info("Bot starting (polling)")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
