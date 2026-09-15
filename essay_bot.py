"""
DİM İngilis dili yazı işi (esse) yoxlayan Telegram bot.
Şagird botа mövzunu, sonra minimum 100 sözlük paraqrafı göndərir (mətn və ya
şəkil formasında), bot onu Groq AI vasitəsilə DİM-in rəsmi qiymətləndirmə
meyarlarına (A/B/C/D, maks. 5 bal) əsasən yoxlayır. Dil seçimi və donat
düyməsi var.
"""

import logging
import re
import json
import os
import sys
import base64

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
from groq import Groq

# ============================================================
# 1. TƏNZİMLƏMƏLƏR
# ============================================================
# Açarlar kodun içində DEYİL — mühit dəyişənlərindən (env vars) oxunur.
# Lokal kompüterdə: bu faylla eyni qovluqda ".env" faylı yarat və içinə yaz:
#   TELEGRAM_TOKEN=sənin_tokenin
#   GROQ_API_KEY=sənin_açarın
#   DONATE_M10=nömrən (məsələn: +994501234567)
#   DONATE_ABB=kart nömrən (məsələn: 4169 xxxx xxxx xxxx)
# Render-də: Dashboard -> Environment bölməsində əlavə edilir.
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DONATE_M10 = os.environ.get("DONATE_M10", "tezliklə əlavə olunacaq")
DONATE_ABB = os.environ.get("DONATE_ABB", "tezliklə əlavə olunacaq")

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    sys.exit(
        "❌ TELEGRAM_TOKEN və ya GROQ_API_KEY tapılmadı.\n"
        "Lokal işlədirsənsə: bu faylla eyni qovluqda '.env' faylı yarat "
        "(nümunə üçün .env.example-a bax).\n"
        "Render-də işlədirsənsə: Dashboard -> Environment bölməsində əlavə et."
    )

client = Groq(api_key=GROQ_API_KEY)
# Mətn qiymətləndirməsi üçün model. Groq "llama-3.3-70b-versatile"-i
# 2026-08-16-da deaktiv edib, rəsmi əvəzedici: openai/gpt-oss-120b
MODEL_NAME = "openai/gpt-oss-120b"
# Şəkildən mətn oxumaq (OCR) üçün multimodal (vision) model
VISION_MODEL_NAME = "qwen/qwen3.6-27b"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
# 2. DİLLƏR VƏ MƏTNLƏR
# ============================================================
LANG_NAMES = {"az": "Azərbaycan dili", "ru": "Русский язык", "en": "English"}

TEXTS = {
    "az": {
        "choose_lang": "Salam! 👋 Mən DİM İngilis dili yazı işini (esse) yoxlayan botam.\n\nZəhmət olmasa izahların hansı dildə olmasını seç:",
        "ask_topic": "Əla! ✅ İndi mənə esse mövzusunu / sualını göndər (mətn və ya şəkil ola bilər).",
        "ask_essay": "Qəbul edildi ✅\nİndi bu mövzuya dair minimum 100 sözlük paraqrafını göndər (mətn və ya şəkil ola bilər).",
        "reading_image": "🖼 Şəkil oxunur, gözlə...",
        "image_failed": "❌ Şəkli oxumaq mümkün olmadı. Daha aydın şəkil göndər və ya mətni özün yaz.",
        "checking": "⏳ Esse yoxlanılır, bir az gözlə...",
        "too_short": "❌ Yazının həcmi {wc} sözdür. DİM meyarlarına görə 70 sözdən az yazılar 'A' bəndi üzrə 0 bal alır (nəticədə ümumi bal da 0 olur). Ən azı 100 söz yazmağa çalış və yenidən göndər.",
        "word_count_label": "📝 Söz sayı:",
        "crit_a": "A — Tapşırığın yerinə yetirilməsi:",
        "crit_b": "B — Mövzunun əhatəsi və məntiq:",
        "crit_c": "C — Qrammatika:",
        "crit_d": "D — Söz ehtiyatı:",
        "total_label": "🏆 ÜMUMİ BAL:",
        "mistakes_label": "⚠️ Tapılan səhvlər:",
        "suggestions_label": "💡 Tövsiyələr:",
        "again_hint": "Yeni esse üçün /start yaz.",
        "donate_button": "☕ Botu dəstəklə",
        "donate_intro": "Necə dəstək olmaq istərdin? ⭐ Telegram Stars — heç bir kart/nömrə lazım deyil, ödəniş birbaşa Telegram daxilində gedir.",
        "stars_thanks": "Çox sağ ol! ⭐ Dəstəyinə görə minnətdaram!",
        "invoice_title": "Botu dəstəklə",
        "invoice_desc": "DİM Esse Checker botuna dəstək",
        "bank_option_button": "💳 M10 / ABB kartı ilə",
        "donate_text": "Bu bot pulsuz, tələbə layihəsi kimi hazırlanıb 🎓\nDəstək olmaq istəsən, minnətdar olaram:\n\n💳 M10: {m10}\n💳 ABB kart: {abb}\n\nÇox sağ ol! 🙏",
        "error": "⚠️ Xəta baş verdi: {err}\n\nZəhmət olmasa bir daha cəhd et.",
        "need_start": "Zəhmət olmasa əvvəlcə /start yaz.",
        "unknown": "Zəhmət olmasa mətn və ya şəkil göndər 🙂",
    },
    "ru": {
        "choose_lang": "Привет! 👋 Я бот для проверки письменного задания (эссе) по английскому для DİM.\n\nВыбери, на каком языке присылать объяснения:",
        "ask_topic": "Отлично! ✅ Теперь пришли тему / вопрос эссе (текстом или фото).",
        "ask_essay": "Принято ✅\nТеперь пришли сам абзац по этой теме, минимум 100 слов (текстом или фото).",
        "reading_image": "🖼 Читаю изображение, подожди...",
        "image_failed": "❌ Не удалось прочитать изображение. Пришли фото почётче или напиши текст сам.",
        "checking": "⏳ Проверяю эссе, подожди немного...",
        "too_short": "❌ Объём текста {wc} слов. По критериям DİM тексты короче 70 слов получают 0 баллов по пункту 'A' (и итог тоже 0). Постарайся написать минимум 100 слов и пришли заново.",
        "word_count_label": "📝 Количество слов:",
        "crit_a": "A — Выполнение задания:",
        "crit_b": "B — Раскрытие темы и логика:",
        "crit_c": "C — Грамматика:",
        "crit_d": "D — Словарный запас:",
        "total_label": "🏆 ИТОГОВЫЙ БАЛЛ:",
        "mistakes_label": "⚠️ Найденные ошибки:",
        "suggestions_label": "💡 Рекомендации:",
        "again_hint": "Для нового эссе напиши /start.",
        "donate_button": "☕ Поддержать бота",
        "donate_intro": "Как хочешь поддержать? ⭐ Telegram Stars — не нужна карта или номер телефона, оплата прямо внутри Telegram.",
        "stars_thanks": "Спасибо большое! ⭐ Очень ценю твою поддержку!",
        "invoice_title": "Поддержать бота",
        "invoice_desc": "Поддержка бота DİM Essay Checker",
        "bank_option_button": "💳 Через M10 / карту ABB",
        "donate_text": "Этот бот сделан бесплатно, как учебный проект 🎓\nЕсли хочешь поддержать — буду очень благодарна:\n\n💳 M10: {m10}\n💳 Карта ABB: {abb}\n\nСпасибо большое! 🙏",
        "error": "⚠️ Произошла ошибка: {err}\n\nПопробуй ещё раз.",
        "need_start": "Пожалуйста, сначала напиши /start.",
        "unknown": "Пожалуйста, пришли текст или фото 🙂",
    },
    "en": {
        "choose_lang": "Hi! 👋 I'm a bot that checks the DİM English writing task (essay).\n\nPlease choose the language for explanations:",
        "ask_topic": "Great! ✅ Now send me the essay topic / question (text or photo).",
        "ask_essay": "Got it ✅\nNow send your paragraph on this topic, minimum 100 words (text or photo).",
        "reading_image": "🖼 Reading the image, please wait...",
        "image_failed": "❌ Couldn't read the image. Please send a clearer photo or type the text yourself.",
        "checking": "⏳ Checking your essay, please wait...",
        "too_short": "❌ Your text is {wc} words. Under DİM criteria, texts under 70 words score 0 on part 'A' (so the total is also 0). Try to write at least 100 words and send again.",
        "word_count_label": "📝 Word count:",
        "crit_a": "A — Task fulfillment:",
        "crit_b": "B — Topic coverage & logic:",
        "crit_c": "C — Grammar:",
        "crit_d": "D — Vocabulary:",
        "total_label": "🏆 TOTAL SCORE:",
        "mistakes_label": "⚠️ Mistakes found:",
        "suggestions_label": "💡 Suggestions:",
        "again_hint": "Send /start for a new essay.",
        "donate_button": "☕ Support the bot",
        "donate_intro": "How would you like to support? ⭐ Telegram Stars — no card or phone number needed, payment happens right inside Telegram.",
        "stars_thanks": "Thank you so much! ⭐ I really appreciate your support!",
        "invoice_title": "Support the bot",
        "invoice_desc": "Support for the DİM Essay Checker bot",
        "bank_option_button": "💳 Via M10 / ABB card",
        "donate_text": "This bot was built for free, as a student project 🎓\nIf you'd like to support it, I'd be very grateful:\n\n💳 M10: {m10}\n💳 ABB card: {abb}\n\nThank you so much! 🙏",
        "error": "⚠️ An error occurred: {err}\n\nPlease try again.",
        "need_start": "Please type /start first.",
        "unknown": "Please send text or a photo 🙂",
    },
}

# ============================================================
# 3. DİM-in RƏSMİ QİYMƏTLƏNDİRMƏ MEYARLARI
# ============================================================
CRITERIA_TEXT = """
A — Tapşırığın yerinə yetirilməsi (maks 1 bal):
1 bal: seçilmiş xarici dildə, mövzuya/suala uyğun; həcm minimum 100 söz;
aydın topic sentence, onu dəstəkləyən fikirlər və yekun fikir (concluding sentence)
var; tərkib hissələri arasında əlaqə tamdır, mətn axıcıdır.
0.5 bal: dil düzgün, mövzuya əsasən uyğun, lakin həcm 70-99 söz arası;
struktur elementlərindən yalnız biri var; əlaqə qismən gözlənilib.
0 bal: fikirlər mövzuya uyğun deyil və ya anlaşılmır; həcm 70 sözdən az;
strukturu yoxdur; tamamilə şablon/əzbər cümlələrdən ibarətdir.

B — Mövzunun əhatə edilməsi və məntiqi ardıcıllıq (maks 2 bal):
2 bal: ən azı 2 aydın fikir/arqument, nümunə və ya izahla əsaslandırılıb;
HƏM müsbət, HƏM mənfi tərəflər qeyd olunub; cümlələr arasında linking words
ilə əlaqə var; fikirlər arasında məntiqi ardıcıllıq var.
1 bal: mövzu əsasən əhatə olunub, lakin arqumentlər məhduddur; yalnız bir
tərəf təqdim olunub; məhdud sayda linking word; məntiqi əlaqə bəzən pozulur.
0 bal: 1 balın tələblərinə cavab vermir.

C — Qrammatik qaydalara əməl olunma (maks 1 bal):
1 bal: müxtəlif qrammatik formalar və sintaktik strukturlar (sadə VƏ mürəkkəb
cümlələr) düzgün istifadə olunub.
0.5 bal: əsasən sadə/şablon cümlələr; buraxılan səhvlər bəzən mənanı korlayır.
0 bal: cümlə qurmaqda çətinlik var, mətn söz yığınına bənzəyir.

D — Söz ehtiyatının müxtəlifliyi (maks 1 bal):
1 bal: mövzuya uyğun zəngin lüğət, sinonimlər/parafraz istifadə olunur,
lüğəvi təkrar yoxdur.
0.5 bal: kifayət qədər söz ehtiyatı var, bəzən təkrara yol verilir.
0 bal: söz ehtiyatı çox məhduddur, yersiz təkrarlar var.

VACIB KASKAD QAYDASI (bunu tətbiq etmə — proqram özü tətbiq edəcək,
sən sadəcə hər bəndi MÜSTƏQİL qiymətləndir):
Əgər A=0 olarsa, B,C,D avtomatik 0 sayılır. Əgər B=0 olarsa, C,D avtomatik
0 sayılır. Sən bunu düşünmədən, hər meyarı əsse özü üzrə obyektiv qiymətləndir.
"""

OCR_PROMPT = (
    "Extract exactly the text visible in this image, verbatim, preserving "
    "line breaks. Do not translate, summarize, explain or add anything else "
    "— output ONLY the raw text you see in the image."
)

# ============================================================
# 4. GROQ-A GÖNDƏRİLƏN PROMPT (esse qiymətləndirmə)
# ============================================================
def build_prompt(topic: str, essay: str, word_count: int, lang_name: str) -> str:
    return f"""Sən Azərbaycanın Dövlət İmtahan Mərkəzinin (DİM) rəsmi ingilis dili
yazı işi (esse) qiymətləndiricisisən. Aşağıdakı rəsmi meyarlara əsasən şagirdin
yazdığı paraqrafı ciddi və obyektiv qiymətləndir.

QİYMƏTLƏNDİRMƏ MEYARLARI:
{CRITERIA_TEXT}

ESSENİN MÖVZUSU / SUALI:
\"\"\"{topic}\"\"\"

ŞAGİRDİN ESSESİ (söz sayı: {word_count}):
\"\"\"{essay}\"\"\"

VACIB: "A_comment", "B_comment", "C_comment", "D_comment",
"grammar_mistakes" və "suggestions" sahələrinin HAMISINI {lang_name} dilində yaz.

Cavabını YALNIZ aşağıdakı JSON formatında ver, başqa heç nə yazma,
markdown kodu işarələri (```), başlıq, izah — heç nə əlavə etmə:

{{
  "A_score": <0, 0.5 və ya 1>,
  "A_comment": "<{lang_name} dilində 1-2 cümləlik qısa izah>",
  "B_score": <0, 1 və ya 2>,
  "B_comment": "<{lang_name} dilində 1-2 cümləlik qısa izah>",
  "C_score": <0, 0.5 və ya 1>,
  "C_comment": "<{lang_name} dilində 1-2 cümləlik qısa izah>",
  "D_score": <0, 0.5 və ya 1>,
  "D_comment": "<{lang_name} dilində 1-2 cümləlik qısa izah>",
  "grammar_mistakes": ["<{lang_name} dilində tapılan konkret qrammatik səhv 1>", "..."],
  "suggestions": ["<{lang_name} dilində konkret təkmilləşdirmə tövsiyəsi 1>", "..."]
}}

Hər bəndi meyarlara ƏSASƏN, güzəştsiz qiymətləndir. "grammar_mistakes" boş ola bilər.
"""


def parse_and_score(raw_text: str, word_count: int) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError("Model JSON formatında cavab vermədi")
    data = json.loads(match.group())

    a = float(data.get("A_score", 0))
    b = float(data.get("B_score", 0))
    c = float(data.get("C_score", 0))
    d = float(data.get("D_score", 0))

    # Rəsmi Qeyd 2 qaydası: A=0 -> hamısı 0; B=0 -> C,D qiymətləndirilmir
    if a == 0:
        b = c = d = 0
    elif b == 0:
        c = d = 0

    total = round(a + b + c + d, 1)
    data["A_score"], data["B_score"], data["C_score"], data["D_score"] = a, b, c, d
    data["total"] = total
    data["word_count"] = word_count
    return data


def format_reply(data: dict, t: dict) -> str:
    lines = [
        f"{t['word_count_label']} {data['word_count']}",
        "",
        f"*{t['crit_a']}* {data['A_score']}/1",
        f"_{data.get('A_comment','')}_",
        "",
        f"*{t['crit_b']}* {data['B_score']}/2",
        f"_{data.get('B_comment','')}_",
        "",
        f"*{t['crit_c']}* {data['C_score']}/1",
        f"_{data.get('C_comment','')}_",
        "",
        f"*{t['crit_d']}* {data['D_score']}/1",
        f"_{data.get('D_comment','')}_",
        "",
        f"*{t['total_label']} {data['total']}/5*",
    ]

    mistakes = data.get("grammar_mistakes") or []
    if mistakes:
        lines.append(f"\n{t['mistakes_label']}")
        for m in mistakes[:6]:
            lines.append(f"• {m}")

    suggestions = data.get("suggestions") or []
    if suggestions:
        lines.append(f"\n{t['suggestions_label']}")
        for s in suggestions[:5]:
            lines.append(f"• {s}")

    lines.append(f"\n{t['again_hint']}")
    return "\n".join(lines)


# ============================================================
# 5. KÖMƏKÇİ FUNKSİYALAR
# ============================================================
def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "en")


def get_texts(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return TEXTS[get_lang(context)]


STAR_AMOUNTS = [50, 100, 300]


def donate_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    t = get_texts(context)
    star_row = [
        InlineKeyboardButton(f"⭐ {amount}", callback_data=f"stars_{amount}")
        for amount in STAR_AMOUNTS
    ]
    return InlineKeyboardMarkup(
        [
            star_row,
            [InlineKeyboardButton(t["bank_option_button"], callback_data="bank_info")],
        ]
    )


async def extract_text_from_photo(update: Update) -> str:
    """Telegram-a göndərilən şəklin ən böyük ölçülüsünü Groq vision modeli ilə oxuyur."""
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    file_bytes = await tg_file.download_as_bytearray()
    b64_image = base64.b64encode(bytes(file_bytes)).decode("utf-8")

    completion = client.chat.completions.create(
        model=VISION_MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": OCR_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                    },
                ],
            }
        ],
        temperature=0.0,
    )
    return completion.choices[0].message.content.strip()


async def get_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesajdan mətni çıxarır: adi mətndirsə birbaşa, şəkildirsə OCR ilə."""
    if update.message.text:
        return update.message.text.strip()

    if update.message.photo:
        t = get_texts(context)
        reading_msg = await update.message.reply_text(t["reading_image"])
        try:
            extracted = await extract_text_from_photo(update)
            await reading_msg.delete()
            if not extracted:
                raise ValueError("empty OCR result")
            return extracted
        except Exception:
            logger.exception("Image OCR failed")
            await reading_msg.edit_text(t["image_failed"])
            return None

    return None


# ============================================================
# 6. TELEGRAM HANDLER-LƏRİ
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇦🇿 Azərbaycan dili", callback_data="lang_az")],
            [InlineKeyboardButton("🇷🇺 Русский язык", callback_data="lang_ru")],
            [InlineKeyboardButton("🇬🇧 English Language", callback_data="lang_en")],
        ]
    )
    # Dil hələ seçilməyib deyə mesajı üç dildə birdən göstəririk
    await update.message.reply_text(
        "Salam! 👋 / Привет! 👋 / Hi! 👋\n\n"
        "Zəhmət olmasa dil seç / Выбери язык / Please choose a language:",
        reply_markup=keyboard,
    )


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = get_texts(context)
    await update.message.reply_text(t["donate_intro"], reply_markup=donate_keyboard(context))


async def send_star_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    t = get_texts(context)
    chat_id = update.callback_query.message.chat_id
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=t["invoice_title"],
        description=t["invoice_desc"],
        payload=f"donate_{amount}_stars",
        provider_token="",  # Telegram Stars (XTR) üçün boş saxlanılır
        currency="XTR",
        prices=[LabeledPrice(label="⭐", amount=amount)],
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("lang_"):
        lang = query.data.split("_", 1)[1]
        context.user_data["lang"] = lang
        context.user_data["stage"] = "await_topic"
        t = TEXTS[lang]
        await query.edit_message_text(t["choose_lang"].split("\n\n")[0])
        await query.message.reply_text(t["ask_topic"])

    elif query.data.startswith("stars_"):
        amount = int(query.data.split("_", 1)[1])
        await send_star_invoice(update, context, amount)

    elif query.data == "bank_info":
        t = get_texts(context)
        await query.message.reply_text(
            t["donate_text"].format(m10=DONATE_M10, abb=DONATE_ABB)
        )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Telegram Stars ödənişi təsdiqlənməzdən əvvəl mütləq cavab verilməlidir
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = get_texts(context)
    await update.message.reply_text(t["stars_thanks"])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stage = context.user_data.get("stage")

    if not stage:
        # Dil hələ seçilməyib / /start yazılmayıb — üç dildə xəbərdarlıq
        await update.message.reply_text(
            f"{TEXTS['az']['need_start']}\n{TEXTS['ru']['need_start']}\n{TEXTS['en']['need_start']}"
        )
        return

    t = get_texts(context)
    text = await get_message_text(update, context)
    if text is None:
        return  # get_message_text artıq xəta mesajı göndərdi

    if stage == "await_topic":
        context.user_data["topic"] = text
        context.user_data["stage"] = "await_essay"
        await update.message.reply_text(t["ask_essay"])
        return

    if stage == "await_essay":
        word_count = len(text.split())
        if word_count < 70:
            await update.message.reply_text(t["too_short"].format(wc=word_count))
            return

        waiting_msg = await update.message.reply_text(t["checking"])
        topic = context.user_data.get("topic", "")
        lang_name = LANG_NAMES[get_lang(context)]

        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": build_prompt(topic, text, word_count, lang_name),
                    }
                ],
                temperature=0.2,
            )
            raw_text = completion.choices[0].message.content
            data = parse_and_score(raw_text, word_count)
            reply = format_reply(data, t)
            await waiting_msg.edit_text(
                reply, parse_mode="Markdown", reply_markup=donate_keyboard(context)
            )
        except Exception as e:
            logger.exception("Essay check failed")
            await waiting_msg.edit_text(t["error"].format(err=e))
        return


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = get_texts(context)
    await update.message.reply_text(t["unknown"])


# ============================================================
# 7. BOTU İŞƏ SAL
# ============================================================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("donate", donate_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(
        MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.PHOTO, handle_message)
    )
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.PHOTO, unknown))

    # Render.com bu env-i avtomatik yaradır -> webhook rejimi.
    # Kompüterdə lokal işlədəndə bu env yoxdur -> adi polling rejimi.
render_url = os.environ.get("RENDER_EXTERNAL_URL")

application.run_polling()

if __name__ == "__main__":
    main()
    

