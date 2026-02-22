import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7451333839"))

# Проверка при запуске
print(f"=== CONFIG LOADED ===")
print(f"ADMIN_ID: {ADMIN_ID}")
print(f"BOT_TOKEN exists: {bool(BOT_TOKEN)}")
print(f"OPENROUTER_API_KEY exists: {bool(OPENROUTER_API_KEY)}")

COMPANY_INFO = """
Компания: СтройРемонтНН
Регион: Нижний Новгород и область
Специализация: комплексные ремонты
Минимальный бюджет: от 100 000 руб
Мелкие работы (замена крана, розетки) — НЕ делаем.
Гарантия: 5 лет.

ПРИМЕРНЫЕ ЦЕНЫ:
- Плитка: 900-1500 руб/м2
- Электрика: 500-800 руб/точка
- Сантехника: 3500-6000 руб/точка
- Штукатурка: 450-700 руб/м2
- Потолки: 500-1000 руб/м2
- Демонтаж: 300-600 руб/м2
- Комплексный ремонт: 6000-10000 руб/м2
"""
