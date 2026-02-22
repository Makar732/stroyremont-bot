import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

COMPANY_INFO = """
Компания: СтройРемонтНН
Регион: Нижний Новгород и область
Специализация: комплексные ремонты
Минимальный бюджет: от 100 000 ₽
Мелкие работы (замена крана, розетки) — НЕ делаем.
Гарантия: 5 лет.
Сроки: от недели до нескольких месяцев.

ПРИМЕРНЫЕ ЦЕНЫ (называй как ориентир):
- Плитка: 900–1500 руб/м²
- Электрика: 500–800 руб/точка
- Сантехника: 3500–6000 руб/точка
- Штукатурка: 450–700 руб/м²
- Потолки: 500–1000 руб/м²
- Демонтаж: 300–600 руб/м²
- Комплексный ремонт: 6000–10000 руб/м²
"""


# Проверка при запуске
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set!")
if ADMIN_ID == 0:
    raise ValueError("ADMIN_ID not set!")

print(f"✅ Config loaded: ADMIN_ID={ADMIN_ID}")
