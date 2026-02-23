import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, 
    CallbackQuery,
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, COMPANY_INFO
from database import init_db, save_lead

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === СОСТОЯНИЯ ===
class Form(StatesGroup):
    work = State()
    object_type = State()
    area = State()
    address = State()
    timing = State()
    budget = State()
    confirm = State()
    phone = State()
    questions = State()


# === ДАННЫЕ ДЛЯ КНОПОК ===

WORKS = [
    ["🔨 Комплексный ремонт"],
    ["🚿 Ванная и санузел", "🍳 Кухня"],
    ["⚡ Электрика", "🚰 Сантехника"],
    ["🧱 Плитка", "🎨 Штукатурка/покраска"],
    ["📦 Демонтаж", "🚪 Перегородки"],
    ["✏️ Другое (напишу)"]
]

OBJECTS = [
    ["🏢 Квартира", "🏠 Дом/коттедж"],
    ["🏪 Коммерция (офис/магазин)"]
]

AREAS = [
    ["До 30 м²", "30-50 м²"],
    ["50-80 м²", "80-120 м²"],
    ["Более 120 м²"],
    ["✏️ Напишу точнее"]
]

TIMINGS = [
    ["🔥 Срочно (на этой неделе)"],
    ["📅 В этом месяце"],
    ["📆 В ближайшие 2-3 месяца"],
    ["🤔 Пока планирую"]
]

BUDGETS = [
    ["До 100 тыс", "100-300 тыс"],
    ["300-500 тыс", "500-1000 тыс"],
    ["Более 1 млн"],
    ["💬 Нужна оценка"]
]

CONFIRM = [
    ["✅ Всё верно, отправить"],
    ["🔄 Заполнить заново"]
]

QUESTIONS = [
    ["💰 Узнать цены"],
    ["📋 Что входит в ремонт?"],
    ["⏱ Сколько займёт времени?"],
    ["✅ Вопросов нет, жду звонка"]
]


def make_keyboard(buttons: list) -> ReplyKeyboardMarkup:
    """Создаёт клавиатуру из списка кнопок"""
    keyboard = [[KeyboardButton(text=btn) for btn in row] for row in buttons]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True
    )


# === КОМАНДЫ ===

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    name = message.from_user.first_name or "Клиент"
    
    await state.update_data(
        name=name,
        username=message.from_user.username or ""
    )
    
    logger.info(f"START: {message.from_user.id} ({name})")
    
    await state.set_state(Form.work)
    
    await message.answer(
        f"Здравствуйте, {name}! 👋\n\n"
        "Я — помощник компании **СтройРемонтНН**.\n\n"
        "Помогу оформить заявку на ремонт.\n"
        "Выберите, что вас интересует:",
        parse_mode="Markdown",
        reply_markup=make_keyboard(WORKS)
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("♻️ Сброшено. Нажмите /start", reply_markup=ReplyKeyboardRemove())


# === СБОР ДАННЫХ ===

@dp.message(Form.work)
async def get_work(message: Message, state: FSMContext):
    work = message.text.replace("🔨", "").replace("🚿", "").replace("🍳", "").replace("⚡", "").replace("🚰", "").replace("🧱", "").replace("🎨", "").replace("📦", "").replace("🚪", "").replace("✏️", "").strip()
    
    await state.update_data(work=work)
    await state.set_state(Form.object_type)
    
    logger.info(f"WORK: {message.from_user.id} -> {work}")
    
    await message.answer(
        f"Отлично! {message.text}\n\n"
        "Какой тип объекта?",
        reply_markup=make_keyboard(OBJECTS)
    )


@dp.message(Form.object_type)
async def get_object(message: Message, state: FSMContext):
    obj = message.text.replace("🏢", "").replace("🏠", "").replace("🏪", "").strip()
    
    await state.update_data(object_type=obj)
    await state.set_state(Form.area)
    
    logger.info(f"OBJECT: {message.from_user.id} -> {obj}")
    
    await message.answer(
        "Хорошо! 👍\n\n"
        "Какая площадь объекта?",
        reply_markup=make_keyboard(AREAS)
    )


@dp.message(Form.area)
async def get_area(message: Message, state: FSMContext):
    area = message.text.replace("✏️", "").strip()
    
    await state.update_data(area=area)
    await state.set_state(Form.address)
    
    logger.info(f"AREA: {message.from_user.id} -> {area}")
    
    await message.answer(
        "Записал! 📐\n\n"
        "В каком районе объект?\n"
        "Напишите район или адрес:",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Form.address)
async def get_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(Form.timing)
    
    logger.info(f"ADDRESS: {message.from_user.id} -> {message.text}")
    
    await message.answer(
        "Отлично! 📍\n\n"
        "Когда планируете начать?",
        reply_markup=make_keyboard(TIMINGS)
    )


@dp.message(Form.timing)
async def get_timing(message: Message, state: FSMContext):
    timing = message.text.replace("🔥", "").replace("📅", "").replace("📆", "").replace("🤔", "").strip()
    
    await state.update_data(timing=timing)
    await state.set_state(Form.budget)
    
    logger.info(f"TIMING: {message.from_user.id} -> {timing}")
    
    await message.answer(
        "Понял! ⏰\n\n"
        "Какой примерный бюджет?",
        reply_markup=make_keyboard(BUDGETS)
    )


@dp.message(Form.budget)
async def get_budget(message: Message, state: FSMContext):
    budget = message.text.replace("💬", "").strip()
    
    await state.update_data(budget=budget)
    await state.set_state(Form.confirm)
    
    logger.info(f"BUDGET: {message.from_user.id} -> {budget}")
    
    # Показываем сводку
    data = await state.get_data()
    
    summary = (
        "📋 **Ваша заявка:**\n\n"
        f"🔧 **Работы:** {data.get('work', '—')}\n"
        f"🏠 **Объект:** {data.get('object_type', '—')}\n"
        f"📐 **Площадь:** {data.get('area', '—')}\n"
        f"📍 **Адрес:** {data.get('address', '—')}\n"
        f"⏰ **Сроки:** {data.get('timing', '—')}\n"
        f"💰 **Бюджет:** {data.get('budget', '—')}\n\n"
        "**Всё верно?**"
    )
    
    await message.answer(summary, parse_mode="Markdown", reply_markup=make_keyboard(CONFIRM))


# === ПОДТВЕРЖДЕНИЕ ===

@dp.message(Form.confirm)
async def confirm_data(message: Message, state: FSMContext):
    text = message.text.lower()
    
    if "верно" in text or "✅" in text:
        await state.set_state(Form.questions)
        
        await message.answer(
            "Отлично! 🎉\n\n"
            "Есть вопросы перед отправкой заявки?",
            reply_markup=make_keyboard(QUESTIONS)
        )
        
    elif "заново" in text or "🔄" in text:
        await state.update_data(work=None, object_type=None, area=None, address=None, timing=None, budget=None)
        await state.set_state(Form.work)
        
        await message.answer(
            "Хорошо, начнём заново! 📝\n\n"
            "Выберите тип работ:",
            reply_markup=make_keyboard(WORKS)
        )
    else:
        await message.answer("Выберите вариант 👇", reply_markup=make_keyboard(CONFIRM))


# === ВОПРОСЫ ===

@dp.message(Form.questions)
async def handle_questions(message: Message, state: FSMContext):
    text = message.text
    
    if "нет" in text.lower() or "✅" in text or "жду" in text.lower():
        # Переходим к телефону
        await state.set_state(Form.phone)
        
        await message.answer(
            "📱 Отлично!\n\n"
            "Нажмите кнопку, чтобы оставить номер телефона.\n"
            "Мастер свяжется в течение 30 минут:",
            reply_markup=phone_keyboard()
        )
        
    elif "цен" in text.lower() or "💰" in text:
        await message.answer(
            "💰 **Примерные цены:**\n\n"
            "• Комплексный ремонт: 6000-10000 руб/м²\n"
            "• Плитка: 900-1500 руб/м²\n"
            "• Электрика: 500-800 руб/точка\n"
            "• Сантехника: 3500-6000 руб/точка\n"
            "• Штукатурка: 450-700 руб/м²\n"
            "• Потолки: 500-1000 руб/м²\n\n"
            "Точную смету мастер составит после осмотра.",
            parse_mode="Markdown",
            reply_markup=make_keyboard(QUESTIONS)
        )
        
    elif "входит" in text.lower() or "📋" in text:
        await message.answer(
            "📋 **Что входит в комплексный ремонт:**\n\n"
            "• Демонтаж старых покрытий\n"
            "• Электромонтаж\n"
            "• Сантехника\n"
            "• Штукатурка и шпаклёвка\n"
            "• Укладка плитки\n"
            "• Покраска/обои\n"
            "• Установка дверей\n"
            "• Укладка напольных покрытий\n\n"
            "Всё включено в стоимость работ.",
            parse_mode="Markdown",
            reply_markup=make_keyboard(QUESTIONS)
        )
        
    elif "времени" in text.lower() or "⏱" in text or "сколько" in text.lower():
        await message.answer(
            "⏱ **Примерные сроки:**\n\n"
            "• Ванная комната: 2-3 недели\n"
            "• Кухня: 2-3 недели\n"
            "• Комната: 1-2 недели\n"
            "• Квартира до 50м²: 1-2 месяца\n"
            "• Квартира 50-100м²: 2-3 месяца\n\n"
            "Точные сроки — после осмотра.",
            parse_mode="Markdown",
            reply_markup=make_keyboard(QUESTIONS)
        )
        
    else:
        await message.answer(
            "Выберите вопрос из списка или нажмите «Вопросов нет» 👇",
            reply_markup=make_keyboard(QUESTIONS)
        )


# === ТЕЛЕФОН ===

@dp.message(Form.phone, F.contact)
async def get_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    
    await finish_order(message, state, phone)


@dp.message(Form.phone)
async def get_phone_text(message: Message, state: FSMContext):
    # Проверяем на телефон
    import re
    clean = re.sub(r'[\s\-\(\)\+]', '', message.text)
    
    if re.search(r'\d{10,11}', clean):
        await finish_order(message, state, message.text)
    else:
        await message.answer(
            "📱 Нажмите кнопку ниже, чтобы поделиться номером:",
            reply_markup=phone_keyboard()
        )


async def finish_order(message: Message, state: FSMContext, phone: str):
    """Завершение заказа"""
    
    user_id = message.from_user.id
    data = await state.get_data()
    data["phone"] = phone
    
    logger.info(f"=== LEAD COMPLETE: {user_id} ===")
    logger.info(f"Data: {data}")
    
    await message.answer("✅ Отлично! Заявка принята!", reply_markup=ReplyKeyboardRemove())
    
    # Отправляем админу
    success = await send_to_admin(user_id, data)
    
    # Сохраняем в БД
    await save_lead(user_id, data)
    
    if success:
        await message.answer(
            "🎉 **Спасибо за заявку!**\n\n"
            "Мастер свяжется с вами в течение 30 минут "
            "для уточнения деталей и согласования времени осмотра.\n\n"
            "Если будут вопросы — пишите! 😊",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "Спасибо! Мы получили вашу заявку.\n"
            "Мастер скоро свяжется с вами!"
        )
    
    await state.clear()


async def send_to_admin(user_id: int, data: dict) -> bool:
    """Отправка админу"""
    
    # Определяем статус
    timing = data.get('timing', '').lower()
    if 'срочно' in timing or 'этой неделе' in timing:
        status = "🔥 ГОРЯЧИЙ"
    elif 'этом месяце' in timing:
        status = "✅ ЦЕЛЕВОЙ"
    else:
        status = "📝 НОВАЯ"
    
    data["status"] = status
    
    tg = f"@{data.get('username')}" if data.get('username') else "—"
    
    text = f"""
{'='*35}
📋 НОВАЯ ЗАЯВКА
{'='*35}

{status}

👤 Имя: {data.get('name', '—')}
📞 Телефон: {data.get('phone', '—')}
📱 Telegram: {tg}
🆔 ID: {user_id}

🔧 Работы: {data.get('work', '—')}
🏠 Объект: {data.get('object_type', '—')}
📐 Площадь: {data.get('area', '—')}
📍 Адрес: {data.get('address', '—')}
⏰ Сроки: {data.get('timing', '—')}
💰 Бюджет: {data.get('budget', '—')}
{'='*35}
"""
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
        logger.info(f"✅ Sent to admin {ADMIN_ID}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send: {e}")
        return False


# === ЗАПУСК ===

async def main():
    await init_db()
    logger.info("🚀 BOT STARTING")
    logger.info(f"ADMIN: {ADMIN_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
