import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, REQUIRED_FIELDS, FIELD_NAMES, FIELD_QUESTIONS
from database import init_db, save_lead, save_conversation, get_conversation, reset_user
from ai_handler import generate_ai_response, generate_farewell, generate_questions_response, check_phone_number

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class Form(StatesGroup):
    work = State()
    object_type = State()
    area = State()
    address = State()
    timing = State()
    budget = State()
    confirm = State()
    questions = State()
    phone = State()
    chat = State()


# Маппинг состояний на поля
STATE_TO_FIELD = {
    Form.work: "work",
    Form.object_type: "object_type",
    Form.area: "area",
    Form.address: "address",
    Form.timing: "timing",
    Form.budget: "budget",
}

FIELD_TO_STATE = {v: k for k, v in STATE_TO_FIELD.items()}


def get_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )


def get_confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Всё верно")],
            [KeyboardButton(text="🔄 Заполнить заново")]
        ],
        resize_keyboard=True
    )


def format_summary(data: dict) -> str:
    """Форматирует собранные данные"""
    text = "📋 **Ваша заявка:**\n\n"
    for field in REQUIRED_FIELDS:
        name = FIELD_NAMES.get(field, field)
        value = data.get(field, "—")
        text += f"▫️ **{name}:** {value}\n"
    text += "\n**Всё верно?**"
    return text


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Начало диалога"""
    
    user_id = message.from_user.id
    name = message.from_user.first_name or "Клиент"
    username = message.from_user.username or ""
    
    logger.info(f"=== START from {user_id} ({name}) ===")
    
    # Сбрасываем состояние
    await state.clear()
    
    # Инициализируем данные
    await state.update_data(
        name=name,
        username=username,
        collected={}
    )
    
    # Устанавливаем первое состояние
    await state.set_state(Form.work)
    
    greeting = (
        f"Здравствуйте, {name}! 👋\n\n"
        "Я — помощник компании **СтройРемонтНН**.\n\n"
        "Мы делаем ремонт в Нижнем Новгороде:\n"
        "🔨 Демонтаж, электрика, сантехника\n"
        "🏗 Перегородки, потолки, плитка\n"
        "✨ Декоративная отделка\n\n"
        f"{FIELD_QUESTIONS['work']}"
    )
    
    await message.answer(greeting, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Сброс"""
    await state.clear()
    await reset_user(message.from_user.id)
    await message.answer("♻️ Сброшено. Напишите /start", reply_markup=ReplyKeyboardRemove())


@dp.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext):
    """Статус"""
    data = await state.get_data()
    collected = data.get("collected", {})
    current_state = await state.get_state()
    
    text = f"🔹 Состояние: {current_state}\n\n"
    for field in REQUIRED_FIELDS:
        value = collected.get(field)
        emoji = "✅" if value else "❌"
        text += f"{emoji} {FIELD_NAMES.get(field)}: {value or '—'}\n"
    
    await message.answer(text)


# === СБОР ДАННЫХ ===

@dp.message(Form.work)
async def process_work(message: Message, state: FSMContext):
    """Сохраняем работы, спрашиваем тип объекта"""
    
    logger.info(f"[work] {message.from_user.id}: {message.text}")
    
    data = await state.get_data()
    collected = data.get("collected", {})
    collected["work"] = message.text
    await state.update_data(collected=collected)
    
    # Генерируем ответ
    reply = await generate_ai_response(message.text, collected, FIELD_QUESTIONS["object_type"])
    if not reply:
        reply = f"Понял! {FIELD_QUESTIONS['object_type']}"
    
    await state.set_state(Form.object_type)
    await message.answer(reply)


@dp.message(Form.object_type)
async def process_object_type(message: Message, state: FSMContext):
    """Сохраняем тип объекта, спрашиваем площадь"""
    
    logger.info(f"[object_type] {message.from_user.id}: {message.text}")
    
    data = await state.get_data()
    collected = data.get("collected", {})
    collected["object_type"] = message.text
    await state.update_data(collected=collected)
    
    reply = await generate_ai_response(message.text, collected, FIELD_QUESTIONS["area"])
    if not reply:
        reply = f"Хорошо! {FIELD_QUESTIONS['area']}"
    
    await state.set_state(Form.area)
    await message.answer(reply)


@dp.message(Form.area)
async def process_area(message: Message, state: FSMContext):
    """Сохраняем площадь, спрашиваем адрес"""
    
    logger.info(f"[area] {message.from_user.id}: {message.text}")
    
    data = await state.get_data()
    collected = data.get("collected", {})
    collected["area"] = message.text
    await state.update_data(collected=collected)
    
    reply = await generate_ai_response(message.text, collected, FIELD_QUESTIONS["address"])
    if not reply:
        reply = f"Отлично! {FIELD_QUESTIONS['address']}"
    
    await state.set_state(Form.address)
    await message.answer(reply)


@dp.message(Form.address)
async def process_address(message: Message, state: FSMContext):
    """Сохраняем адрес, спрашиваем сроки"""
    
    logger.info(f"[address] {message.from_user.id}: {message.text}")
    
    data = await state.get_data()
    collected = data.get("collected", {})
    collected["address"] = message.text
    await state.update_data(collected=collected)
    
    reply = await generate_ai_response(message.text, collected, FIELD_QUESTIONS["timing"])
    if not reply:
        reply = f"Понял! {FIELD_QUESTIONS['timing']}"
    
    await state.set_state(Form.timing)
    await message.answer(reply)


@dp.message(Form.timing)
async def process_timing(message: Message, state: FSMContext):
    """Сохраняем сроки, спрашиваем бюджет"""
    
    logger.info(f"[timing] {message.from_user.id}: {message.text}")
    
    data = await state.get_data()
    collected = data.get("collected", {})
    collected["timing"] = message.text
    await state.update_data(collected=collected)
    
    reply = await generate_ai_response(message.text, collected, FIELD_QUESTIONS["budget"])
    if not reply:
        reply = f"Хорошо! {FIELD_QUESTIONS['budget']}"
    
    await state.set_state(Form.budget)
    await message.answer(reply)


@dp.message(Form.budget)
async def process_budget(message: Message, state: FSMContext):
    """Сохраняем бюджет, показываем сводку"""
    
    logger.info(f"[budget] {message.from_user.id}: {message.text}")
    
    data = await state.get_data()
    collected = data.get("collected", {})
    collected["budget"] = message.text
    await state.update_data(collected=collected)
    
    # Сохраняем в БД
    await save_conversation(
        user_id=message.from_user.id,
        username=data.get("username", ""),
        first_name=data.get("name", ""),
        messages="[]",
        collected_data=json.dumps(collected, ensure_ascii=False)
    )
    
    # Показываем сводку
    summary = format_summary(collected)
    
    await state.set_state(Form.confirm)
    await message.answer(summary, parse_mode="Markdown", reply_markup=get_confirm_keyboard())
    
    logger.info(f"✅ All data collected for {message.from_user.id}: {collected}")


# === ПОДТВЕРЖДЕНИЕ ===

@dp.message(Form.confirm)
async def process_confirm(message: Message, state: FSMContext):
    """Обработка подтверждения"""
    
    text = message.text.lower()
    logger.info(f"[confirm] {message.from_user.id}: {text}")
    
    if "верно" in text or "да" in text or "✅" in text:
        # Подтверждено - спрашиваем про вопросы
        await state.set_state(Form.questions)
        await message.answer(
            "Отлично! 👍\n\nЕсть вопросы по ценам или услугам?",
            reply_markup=ReplyKeyboardRemove()
        )
        
    elif "заново" in text or "🔄" in text or "изменить" in text:
        # Заново
        await state.update_data(collected={})
        await state.set_state(Form.work)
        await message.answer(
            f"Хорошо, начнём заново! 📝\n\n{FIELD_QUESTIONS['work']}",
            reply_markup=ReplyKeyboardRemove()
        )
        
    else:
        await message.answer(
            "Нажмите кнопку ниже 👇",
            reply_markup=get_confirm_keyboard()
        )


# === ВОПРОСЫ ===

@dp.message(Form.questions)
async def process_questions(message: Message, state: FSMContext):
    """Обработка вопросов"""
    
    text = message.text.lower().strip()
    logger.info(f"[questions] {message.from_user.id}: {text}")
    
    no_words = ['нет', 'нету', 'не', 'понятно', 'ок', 'хорошо', 'давай', 'готов', 'ясно', 'норм']
    
    if any(text.startswith(w) or text == w for w in no_words):
        # Нет вопросов - просим телефон
        await state.set_state(Form.phone)
        await message.answer(
            "📱 Отлично! Нажмите кнопку, чтобы оставить номер телефона.\n"
            "Мастер свяжется с вами для уточнения деталей:",
            reply_markup=get_phone_keyboard()
        )
    else:
        # Есть вопрос
        reply = await generate_questions_response(message.text)
        await message.answer(reply)
        await message.answer("Ещё вопросы? Или готовы оставить заявку?")


# === ТЕЛЕФОН ===

@dp.message(Form.phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    """Телефон через контакт"""
    
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    
    logger.info(f"[phone] {message.from_user.id}: {phone} (contact)")
    
    await finish_lead(message, state, phone)


@dp.message(Form.phone, F.text)
async def process_phone_text(message: Message, state: FSMContext):
    """Телефон текстом"""
    
    if check_phone_number(message.text):
        logger.info(f"[phone] {message.from_user.id}: {message.text} (text)")
        await finish_lead(message, state, message.text.strip())
    else:
        await message.answer(
            "📱 Нажмите кнопку ниже:",
            reply_markup=get_phone_keyboard()
        )


async def finish_lead(message: Message, state: FSMContext, phone: str):
    """Завершение - отправка заявки"""
    
    user_id = message.from_user.id
    data = await state.get_data()
    collected = data.get("collected", {})
    collected["phone"] = phone
    
    logger.info(f"=== FINISHING LEAD for {user_id} ===")
    logger.info(f"Data: {collected}")
    
    await message.answer("✅ Номер получен!", reply_markup=ReplyKeyboardRemove())
    
    # Отправляем админу
    success = await send_lead_to_admin(
        user_id=user_id,
        name=data.get("name", ""),
        username=data.get("username", ""),
        collected=collected
    )
    
    # Генерируем прощание
    farewell = await generate_farewell(data.get("name", "Клиент"))
    await message.answer(farewell)
    
    # Переходим в чат
    await state.set_state(Form.chat)
    
    if success:
        logger.info(f"✅ Lead sent successfully for {user_id}")
    else:
        logger.error(f"❌ Failed to send lead for {user_id}")


async def send_lead_to_admin(user_id: int, name: str, username: str, collected: dict) -> bool:
    """Отправка заявки админу"""
    
    logger.info(f"📤 Sending to admin {ADMIN_ID}")
    
    # Оценка
    timing = collected.get('timing', '').lower()
    budget = collected.get('budget', '').lower()
    
    if any(w in timing for w in ['сейчас', 'срочно', 'завтра']):
        status = "🔥 ГОРЯЧИЙ"
        reason = "Срочно"
    elif any(w in timing for w in ['месяц', 'скоро', 'неделю']):
        status = "✅ ЦЕЛЕВОЙ"
        reason = "Скоро"
    else:
        status = "📝 НОВАЯ"
        reason = "Обработать"
    
    tg = f"@{username}" if username else "нет"
    
    text = f"""
{'='*35}
📋 **НОВАЯ ЗАЯВКА**
{'='*35}

{status} — {reason}

👤 **Имя:** {name}
📞 **Телефон:** {collected.get('phone', '—')}
📱 **Telegram:** {tg}
🆔 **ID:** `{user_id}`

🔧 **Работы:** {collected.get('work', '—')}
🏠 **Объект:** {collected.get('object_type', '—')}
📐 **Площадь:** {collected.get('area', '—')}
📍 **Адрес:** {collected.get('address', '—')}
📅 **Сроки:** {collected.get('timing', '—')}
💰 **Бюджет:** {collected.get('budget', '—')}
{'='*35}
"""
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
        
        await save_lead(
            user_id=user_id,
            data=json.dumps({**collected, "name": name, "username": username}, ensure_ascii=False),
            score=status,
            score_reason=reason
        )
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Send error: {e}")
        
        # Пробуем без Markdown
        try:
            plain_text = text.replace("**", "").replace("`", "").replace("_", "")
            await bot.send_message(chat_id=ADMIN_ID, text=plain_text)
            return True
        except Exception as e2:
            logger.error(f"❌ Send plain error: {e2}")
            return False


# === ЧАТ ===

@dp.message(Form.chat)
async def process_chat(message: Message, state: FSMContext):
    """Свободный чат после заявки"""
    
    reply = await generate_questions_response(message.text)
    if not reply:
        reply = "Спасибо! Если будут вопросы — пишите. 😊"
    await message.answer(reply)


# === ЗАПУСК ===

async def main():
    await init_db()
    
    logger.info("=" * 50)
    logger.info("🚀 BOT STARTING")
    logger.info(f"ADMIN_ID: {ADMIN_ID}")
    logger.info("=" * 50)
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
