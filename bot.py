import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, save_lead
from ai_handler import make_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния диалога
class Form(StatesGroup):
    work = State()        # Какие работы
    object_type = State() # Тип объекта
    area = State()        # Площадь
    address = State()     # Адрес
    timing = State()      # Сроки
    budget = State()      # Бюджет
    phone = State()       # Телефон
    chat = State()        # Свободный чат после заявки

# Вопросы для каждого шага
QUESTIONS = {
    "work": "Какие работы вас интересуют?",
    "object_type": "Квартира, дом или коммерческое помещение?",
    "area": "Какая примерно площадь?",
    "address": "В каком районе/адресе объект?",
    "timing": "Когда планируете начать работы?",
    "budget": "Какой примерный бюджет?",
    "phone": "Оставьте телефон — мастер свяжется для обсуждения деталей 📞",
}

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Form.work)
    
    name = message.from_user.first_name or "Клиент"
    await state.update_data(name=name, username=message.from_user.username or "")
    
    await message.answer(
        f"Здравствуйте, {name}! 👋\n\n"
        "Я помощник компании **СтройРемонтНН**.\n\n"
        "Делаем комплексные ремонты в Нижнем Новгороде:\n"
        "• Демонтаж, электрика, сантехника\n"
        "• Перегородки, потолки, плитка\n"
        "• Декоративная отделка\n\n"
        f"{QUESTIONS['work']} 🏠",
        parse_mode="Markdown"
    )

# ===== ШАГ 1: Работы =====
@dp.message(Form.work)
async def process_work(message: Message, state: FSMContext):
    await state.update_data(work=message.text)
    await state.set_state(Form.object_type)
    
    reply = await make_reply(
        f"Клиент хочет: {message.text}",
        f"Отреагируй кратко (1 предложение) и спроси: {QUESTIONS['object_type']}"
    )
    await message.answer(reply)

# ===== ШАГ 2: Тип объекта =====
@dp.message(Form.object_type)
async def process_object(message: Message, state: FSMContext):
    await state.update_data(object_type=message.text)
    await state.set_state(Form.area)
    
    reply = await make_reply(
        f"Объект: {message.text}",
        f"Подтверди кратко и спроси: {QUESTIONS['area']}"
    )
    await message.answer(reply)

# ===== ШАГ 3: Площадь =====
@dp.message(Form.area)
async def process_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    await state.set_state(Form.address)
    
    reply = await make_reply(
        f"Площадь: {message.text}",
        f"Отреагируй и спроси: {QUESTIONS['address']}"
    )
    await message.answer(reply)

# ===== ШАГ 4: Адрес =====
@dp.message(Form.address)
async def process_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(Form.timing)
    
    reply = await make_reply(
        f"Адрес: {message.text}",
        f"Отреагируй и спроси: {QUESTIONS['timing']}"
    )
    await message.answer(reply)

# ===== ШАГ 5: Сроки =====
@dp.message(Form.timing)
async def process_timing(message: Message, state: FSMContext):
    await state.update_data(timing=message.text)
    await state.set_state(Form.budget)
    
    reply = await make_reply(
        f"Сроки: {message.text}",
        f"Отреагируй и спроси: {QUESTIONS['budget']}"
    )
    await message.answer(reply)

# ===== ШАГ 6: Бюджет =====
@dp.message(Form.budget)
async def process_budget(message: Message, state: FSMContext):
    await state.update_data(budget=message.text)
    await state.set_state(Form.phone)
    
    reply = await make_reply(
        f"Бюджет: {message.text}",
        f"Скажи что отлично и спроси телефон: {QUESTIONS['phone']}"
    )
    await message.answer(reply)

# ===== ШАГ 7: Телефон — ФИНАЛ =====
@dp.message(Form.phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    
    # Получаем все данные
    data = await state.get_data()
    user_id = message.from_user.id
    
    logger.info(f"=== FINAL DATA for {user_id} ===")
    logger.info(f"{data}")
    
    # Отправляем заявку админу
    await send_lead(user_id, data)
    
    # Переходим в режим свободного чата
    await state.set_state(Form.chat)
    
    await message.answer(
        "Отлично! ✅ Я передал информацию мастеру.\n"
        "Он свяжется с вами в ближайшее время.\n\n"
        "Если есть вопросы — пишите, отвечу!"
    )

# ===== Свободный чат после заявки =====
@dp.message(Form.chat)
async def free_chat(message: Message, state: FSMContext):
    data = await state.get_data()
    
    reply = await make_reply(
        f"Клиент спрашивает: {message.text}",
        "Ответь как помощник СтройРемонтНН. Кратко, по делу. Если вопрос о цене — скажи что точную цену скажет мастер после осмотра."
    )
    await message.answer(reply)

# ===== Отправка заявки =====
async def send_lead(user_id: int, data: dict):
    # Оценка клиента
    budget_text = data.get('budget', '').lower()
    timing_text = data.get('timing', '').lower()
    
    # Простая оценка
    if any(word in timing_text for word in ['сейчас', 'срочно', 'неделя', 'этом месяце', 'скоро']):
        status = "✅ ЦЕЛЕВОЙ"
        reason = "Готов начать скоро"
    elif any(word in budget_text for word in ['50', '30', '20', '10']) and 'тыс' not in budget_text:
        status = "❌ НЕЦЕЛЕВОЙ"
        reason = "Маленький бюджет"
    else:
        status = "⚠️ ПОД ВОПРОСОМ"
        reason = "Требует уточнения"
    
    tg = f"@{data.get('username')}" if data.get('username') else "нет"
    
    lead_text = f"""
{'='*30}
📋 НОВАЯ ЗАЯВКА
{'='*30}

{status}
💬 {reason}

👤 Имя: {data.get('name', '—')}
📞 Телефон: {data.get('phone', '—')}
📱 Telegram: {tg}
🆔 ID: {user_id}

🔧 Работы: {data.get('work', '—')}
🏠 Объект: {data.get('object_type', '—')}
📐 Площадь: {data.get('area', '—')}
📍 Адрес: {data.get('address', '—')}
📅 Сроки: {data.get('timing', '—')}
💰 Бюджет: {data.get('budget', '—')}
{'='*30}
"""
    
    try:
        await bot.send_message(ADMIN_ID, lead_text)
        await save_lead(user_id, json.dumps(data, ensure_ascii=False), status, reason)
        logger.info(f"✅ LEAD SENT for {user_id}")
    except Exception as e:
        logger.error(f"❌ Failed: {e}")

async def main():
    await init_db()
    logger.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
