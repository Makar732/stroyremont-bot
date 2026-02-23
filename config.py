import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MASTER_PHONE = os.getenv("MASTER_PHONE", "+7 999 123-45-67")
MASTER_WHATSAPP = os.getenv("MASTER_WHATSAPP", "https://wa.me/79991234567")

print(f"=== CONFIG ===")
print(f"ADMIN_ID: {ADMIN_ID}")
print(f"MASTER_PHONE: {MASTER_PHONE}")

# === УСЛУГИ ===
SERVICES = {
    "ceiling": {
        "emoji": "✨",
        "name": "Натяжные потолки",
        "price": "от 2 500 ₽/м²",
        "comment": "Установка за 1 день, без пыли и грязи. Гарантия 10 лет ✅"
    },
    "tiles": {
        "emoji": "🧱",
        "name": "Плитка",
        "price": "от 2 200 ₽/м²",
        "comment": "Ровные швы, качественная укладка. Работаем с любой сложностью ✅"
    },
    "electric": {
        "emoji": "⚡",
        "name": "Электромонтаж",
        "price": "от 800 ₽/точка",
        "comment": "Проводка по ГОСТу, безопасно и надёжно. Гарантия 5 лет ✅"
    },
    "plumbing": {
        "emoji": "🚿",
        "name": "Сантехника",
        "price": "от 3 500 ₽/точка",
        "comment": "Установка без протечек. Работаем аккуратно и чисто ✅"
    },
    "plaster": {
        "emoji": "🪨",
        "name": "Штукатурка",
        "price": "от 850 ₽/м²",
        "comment": "Машинная штукатурка — быстро и ровно. Выгодно при больших объёмах ✅"
    },
    "complex": {
        "emoji": "🏠",
        "name": "Комплексный ремонт",
        "price": "от 10 000 ₽/м²",
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

# === FAQ ===
FAQ = {
    "warranty": {
        "question": "🛡 Гарантия",
        "answer": "Даём гарантию 5 лет на все виды работ. Если что-то пойдёт не так — исправим бесплатно."
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
