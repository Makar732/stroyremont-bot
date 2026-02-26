import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MASTER_PHONE = os.getenv("MASTER_PHONE", "+7 999 123-45-67")
PORTFOLIO_LINK = "https://t.me/StroiRemontNN"

# Рабочее время мастера
WORK_HOUR_START = 9   # с 9:00
WORK_HOUR_END = 20    # до 20:00

# Проверка токена
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found!")
    print("Please set BOT_TOKEN in Railway Variables or .env file")
    sys.exit(1)

if ADMIN_ID == 0:
    print("⚠️ WARNING: ADMIN_ID not set, notifications disabled")

print(f"=== CONFIG ===")
print(f"BOT_TOKEN: {BOT_TOKEN[:20]}...")
print(f"ADMIN_ID: {ADMIN_ID}")
print(f"MASTER_PHONE: {MASTER_PHONE}")

# === УСЛУГИ (обновлено) ===
SERVICES = {
    "ceiling": {
        "emoji": "✨",
        "name": "Натяжные потолки",
        "price": "от объёма работ",
        "comment": "Установка за 1 день, без пыли и грязи. Гарантия ✅"
    },
    "tiles": {
        "emoji": "🧱",
        "name": "Плитка",
        "price": "от объёма работ",
        "comment": "Ровные швы, качественная укладка. Работаем с любой сложностью ✅"
    },
    "electric": {
        "emoji": "⚡",
        "name": "Электромонтаж",
        "price": "от объёма работ",
        "comment": "Проводка по ГОСТу, безопасно и надёжно. Гарантия ✅"
    },
    "plumbing": {
        "emoji": "🚿",
        "name": "Сантехника",
        "price": "от объёма работ",
        "comment": "Установка без протечек. Работаем аккуратно и чисто ✅"
    },
    "plaster": {
        "emoji": "🪨",
        "name": "Штукатурные работы",
        "price": "от объёма работ",
        "comment": "Машинная штукатурка — быстро и ровно. Выгодно при больших объёмах ✅"
    },
    "painting": {
        "emoji": "🎨",
        "name": "Малярные работы",
        "price": "от объёма работ",
        "comment": "Покраска, шпаклёвка, поклейка обоев. Ровно и аккуратно ✅"
    },
    "complex": {
        "emoji": "🏠",
        "name": "Комплексный ремонт",
        "price": "от объёма работ",
        "comment": "Ремонт под ключ — вы получаете готовое жильё. Всё включено ✅"
    }
}

# === ОБЪЕКТЫ ===
OBJECTS = {
    "apartment": {"emoji": "🏢", "name": "Квартира"},
    "house": {"emoji": "🏡", "name": "Дом / Коттедж"},
    "commercial": {"emoji": "🏪", "name": "Коммерция"},
    "other": {"emoji": "📦", "name": "Другое"}
}

# === ПЛОЩАДИ ===
AREAS = {
    "small": {"emoji": "📐", "name": "До 50 м²"},
    "medium": {"emoji": "📏", "name": "50–100 м²"},
    "large": {"emoji": "📐", "name": "Более 100 м²"}
}

# === СРОКИ ===
TIMINGS = {
    "now": {"emoji": "🔥", "name": "Нужно сейчас"},
    "month": {"emoji": "📅", "name": "В течение месяца"},
    "quarter": {"emoji": "📆", "name": "Через 1–3 месяца"},
    "later": {"emoji": "🤔", "name": "Более 3 месяцев"}
}

# === FAQ (обновлено) ===
FAQ = {
    "warranty": {
        "question": "🛡 Гарантия",
        "answer": "Даём гарантию на все виды работ. Если что-то пойдёт не так — исправим бесплатно."
    },
    "timing": {
        "question": "⏱ Сроки работ",
        "answer": "• Натяжной потолок: 1 день\n• Ванная под ключ: 2-3 недели\n• Квартира до 50м²: 1-2 месяца\n• Квартира 50-100м²: 2-3 месяца"
    },
    "payment": {
        "question": "💳 Оплата",
        "answer": "Оплата поэтапная: 30% предоплата, остальное по факту. Принимаем наличные и переводы."
    },
    "materials": {
        "question": "🧱 Материалы",
        "answer": "Работаем с вашими материалами или поможем закупить со скидкой у проверенных поставщиков."
    }
}
