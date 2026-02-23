import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Проверка при запуске
print(f"=== CONFIG LOADED ===")
print(f"ADMIN_ID: {ADMIN_ID}")
print(f"BOT_TOKEN exists: {bool(BOT_TOKEN)}")
print(f"OPENROUTER_API_KEY exists: {bool(OPENROUTER_API_KEY)}")

COMPANY_INFO = """
Компания: СтройРемонтНН
Регион: Нижний Новгород и область
Специализация: ремонт квартир, домов, коммерческих помещений
Гарантия: 5 лет

УСЛУГИ:
- Демонтажные работы
- Электромонтаж
- Сантехника
- Перегородки и потолки
- Плиточные работы
- Декоративная отделка

ПРИМЕРНЫЕ ЦЕНЫ:
- Плитка: 900-1500 руб/м²
- Электрика: 500-800 руб/точка
- Сантехника: 3500-6000 руб/точка
- Штукатурка: 450-700 руб/м²
- Потолки: 500-1000 руб/м²
- Демонтаж: 300-600 руб/м²
- Комплексный ремонт: 6000-10000 руб/м²
"""

# Поля которые нужно собрать
REQUIRED_FIELDS = {
    "work": "какие работы нужны",
    "object_type": "тип объекта (квартира/дом/коммерция)",
    "area": "площадь объекта",
    "address": "район или адрес",
    "timing": "сроки начала работ",
    "budget": "примерный бюджет"
}
