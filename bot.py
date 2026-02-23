import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, MASTER_PHONE, SERVICES, OBJECTS, AREAS, TIMINGS
from database import init_db, save_lead

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === СОСТОЯНИЯ ===
class Form(StatesGroup):
    service = State()      # Выбор услуги
    object_type = State()  # Тип объекта
    area = State()         # Площадь
    timing = State()       # Сроки
    price_check = State()  # Проверка бюджета
    phone = State()        # Телефон
    done = State()         # Завершено


# === КЛАВИАТУРЫ ===

def services_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура услуг"""
    buttons = [[KeyboardButton(text=s["button"])] for s in SERVICES.values()]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def objects_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура типов объектов"""
    buttons = [[KeyboardButton(text=v)] for v in OBJECTS.values()]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def areas_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура площадей"""
    buttons = [[KeyboardButton(text=v)] for v in AREAS.values()]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def timings_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура сроков"""
    buttons = [[KeyboardButton(text=v)] for v in TIMINGS.values()]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def price_check_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура проверки цены"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, подходит")],
            [KeyboardButton(text="❌ Нет, дорого")]
        ],
        resize_keyboard=True
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для телефона"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text="⏭ Пропустить, просто дайте контакт мастера")]
        ],
        resize_keyboard=True
    )


def other_services_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора другой услуги"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Посмотреть другие услуги")],
            [KeyboardButton(text="👋 Завершить")]
        ],
        resize_keyboard=True
    )


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def get_service_by_button(text: str) -> dict | None:
    """Находит услугу по тексту кнопки"""
    for key, service in SERVICES.items():
        if service["button"] in text or service["name"] in text:
            return {"key": key, **service}
    return None


def get_service_key(text: str) -> str:
    """Получает ключ услуги"""
    for key, service in SERVICES.items():
        if service["button"] in text or service["name"] in text:
            return key
    return "unknown"


# === КОМАНДЫ ===

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Начало диалога"""
    
    await state.clear()
    
    name = message.from_user.first_name or "Клиент"
    username = message.from_user.username or ""
    
    await state.update_data(
        name=name,
        username=username
    )
    
    logger.info(f"START: {message.from_user.id} ({name})")
    
    await state.set_state(Form.service)
    
    await message.answer(
        f"Здравствуйте, {name}! 👋\n\n"
        "Я — бот компании **СтройРемонтНН**.\n\n"
        "🏆 Ремонт в Нижнем Новгороде\n"
        "📋 Гарантия 5 лет на все работы\n\n"
        "Выберите интересующую услугу:",
        parse_mode="Markdown",
        reply_markup=services_keyboard()
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Сброс диалога"""
    await state.clear()
    await message.answer("♻️ Сброшено. Нажмите /start", reply_markup=ReplyKeyboardRemove())


# === ШАГ 1: ВЫБОР УСЛУГИ ===

@dp.message(Form.service)
async def process_service(message: Message, state: FSMContext):
    """Обработка выбора услуги"""
    
    service = get_service_by_button(message.text)
    
    if not service:
        await message.answer("Пожалуйста, выберите услугу из списка 👇", reply_markup=services_keyboard())
        return
    
    logger.info(f"SERVICE: {message.from_user.id} -> {service['name']}")
    
    await state.update_data(
        service=service["name"],
        service_key=service["key"],
        service_price=service["price"]
    )
    
    await state.set_state(Form.object_type)
    
    # Показываем экспертный комментарий и следующий вопрос
    await message.answer(
        f"✅ **{service['name']}** — {service['price']}\n\n"
        f"{service['comment']}\n\n"
        "Какой у вас объект?",
        parse_mode="Markdown",
        reply_markup=objects_keyboard()
    )


# === ШАГ 2: ТИП ОБЪЕКТА ===

@dp.message(Form.object_type)
async def process_object(message: Message, state: FSMContext):
    """Обработка типа объекта"""
    
    # Проверяем валидность
    valid = any(v in message.text for v in OBJECTS.values())
    
    if not valid:
        await message.answer("Выберите тип объекта 👇", reply_markup=objects_keyboard())
        return
    
    logger.info(f"OBJECT: {message.from_user.id} -> {message.text}")
    
    await state.update_data(object_type=message.text)
    await state.set_state(Form.area)
    
    await message.answer(
        "Отлично! 👍\n\n"
        "Какая примерная площадь?",
        reply_markup=areas_keyboard()
    )


# === ШАГ 3: ПЛОЩАДЬ ===

@dp.message(Form.area)
async def process_area(message: Message, state: FSMContext):
    """Обработка площади"""
    
    valid = any(v in message.text for v in AREAS.values())
    
    if not valid:
        await message.answer("Выберите площадь 👇", reply_markup=areas_keyboard())
        return
    
    logger.info(f"AREA: {message.from_user.id} -> {message.text}")
    
    await state.update_data(area=message.text)
    await state.set_state(Form.timing)
    
    await message.answer(
        "Понял! 📐\n\n"
        "Когда планируете начать работы?",
        reply_markup=timings_keyboard()
    )


# === ШАГ 4: СРОКИ ===

@dp.message(Form.timing)
async def process_timing(message: Message, state: FSMContext):
    """Обработка сроков"""
    
    valid = any(v in message.text for v in TIMINGS.values())
    
    if not valid:
        await message.answer("Выберите сроки 👇", reply_markup=timings_keyboard())
        return
    
    logger.info(f"TIMING: {message.from_user.id} -> {message.text}")
    
    await state.update_data(timing=message.text)
    await state.set_state(Form.price_check)
    
    # Получаем данные для показа цены
    data = await state.get_data()
    
    await message.answer(
        f"📋 **Ваш запрос:**\n\n"
        f"🔧 {data.get('service')}\n"
        f"🏠 {data.get('object_type')}\n"
        f"📐 {data.get('area')}\n"
        f"📅 {data.get('timing')}\n\n"
        f"💰 **Цена работ: {data.get('service_price')}**\n\n"
        "Вам подходят эти условия?",
        parse_mode="Markdown",
        reply_markup=price_check_keyboard()
    )


# === ШАГ 5: ПРОВЕРКА ЦЕНЫ ===

@dp.message(Form.price_check)
async def process_price_check(message: Message, state: FSMContext):
    """Проверка согласия с ценой"""
    
    text = message.text.lower()
    
    if "да" in text or "✅" in text or "подходит" in text:
        # Цена устраивает — просим контакт
        logger.info(f"PRICE OK: {message.from_user.id}")
        
        await state.update_data(price_accepted=True)
        await state.set_state(Form.phone)
        
        await message.answer(
            "Отлично! 🎉\n\n"
            "Оставьте ваш номер телефона, чтобы мастер мог связаться и обсудить детали.\n\n"
            "Или нажмите «Пропустить», чтобы сразу получить контакт мастера:",
            reply_markup=phone_keyboard()
        )
        
    elif "нет" in text or "❌" in text or "дорого" in text:
        # Цена не устраивает
        logger.info(f"PRICE NO: {message.from_user.id}")
        
        await state.update_data(price_accepted=False)
        
        await message.answer(
            "Понимаю! 🤝\n\n"
            "Эти цены минимальные для качественной работы с гарантией.\n\n"
            "Могу показать другие услуги — возможно, что-то подойдёт лучше:",
            reply_markup=other_services_keyboard()
        )
        
        # Сохраняем отказ в БД для аналитики
        data = await state.get_data()
        data["status"] = "PRICE_REJECTED"
        await save_lead(message.from_user.id, data)
        
    else:
        await message.answer("Выберите вариант 👇", reply_markup=price_check_keyboard())


# === ОБРАБОТКА "ДРУГИЕ УСЛУГИ" ===

@dp.message(F.text == "🔄 Посмотреть другие услуги")
async def show_other_services(message: Message, state: FSMContext):
    """Возврат к выбору услуг"""
    
    await state.set_state(Form.service)
    
    await message.answer(
        "Выберите другую услугу:",
        reply_markup=services_keyboard()
    )


@dp.message(F.text == "👋 Завершить")
async def finish_dialog(message: Message, state: FSMContext):
    """Завершение без заказа"""
    
    await state.clear()
    
    await message.answer(
        "Спасибо за интерес! 👋\n\n"
        "Если передумаете — напишите /start",
        reply_markup=ReplyKeyboardRemove()
    )


# === ШАГ 6: ТЕЛЕФОН ===

@dp.message(Form.phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    """Телефон через контакт"""
    
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    
    logger.info(f"PHONE: {message.from_user.id} -> {phone}")
    
    await finish_order(message, state, phone)


@dp.message(Form.phone, F.text.contains("Пропустить"))
async def skip_phone(message: Message, state: FSMContext):
    """Пропуск телефона — сразу даё�� контакт мастера"""
    
    logger.info(f"PHONE SKIP: {message.from_user.id}")
    
    await finish_order(message, state, None)


@dp.message(Form.phone)
async def process_phone_text(message: Message, state: FSMContext):
    """Телефон текстом"""
    
    import re
    clean = re.sub(r'[\s\-\(\)\+]', '', message.text)
    
    if re.search(r'\d{10,11}', clean):
        logger.info(f"PHONE TEXT: {message.from_user.id} -> {message.text}")
        await finish_order(message, state, message.text)
    else:
        await message.answer(
            "Нажмите кнопку или введите номер телефона:",
            reply_markup=phone_keyboard()
        )


# === ЗАВЕРШЕНИЕ ЗАКАЗА ===

async def finish_order(message: Message, state: FSMContext, phone: str | None):
    """Завершение заказа — выдача контакта"""
    
    user_id = message.from_user.id
    data = await state.get_data()
    data["phone"] = phone or "не указан"
    data["status"] = "COMPLETED"
    
    logger.info(f"=== ORDER COMPLETE: {user_id} ===")
    logger.info(f"Data: {data}")
    
    # Сохраняем в БД
    await save_lead(user_id, data)
    
    # Отправляем уведомление админу
    await send_to_admin(user_id, data)
    
    # Выдаём контакт мастера
    await message.answer(
        "✅ **Отлично!**\n\n"
        f"📞 **Контакт мастера:** `{MASTER_PHONE}`\n\n"
        "Позвоните или напишите в WhatsApp — мастер ответит в течение 30 минут.\n\n"
        "Можете скопировать номер нажатием ☝️",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Дополнительное сообщение
    await message.answer(
        "💡 **Что дальше:**\n\n"
        "1️⃣ Мастер уточнит детали по телефону\n"
        "2️⃣ Приедет на бесплатный замер\n"
        "3️⃣ Составит точную смету\n\n"
        "Спасибо, что выбрали нас! 🙏"
    )
    
    await state.set_state(Form.done)


async def send_to_admin(user_id: int, data: dict) -> bool:
    """Отправка уведомления админу"""
    
    timing = data.get('timing', '').lower()
    if 'сейчас' in timing or '🔥' in timing:
        status = "🔥 ГОРЯЧИЙ"
    elif 'месяц' in timing:
        status = "✅ ТЁПЛЫЙ"
    else:
        status = "📝 НОВЫЙ"
    
    tg = f"@{data.get('username')}" if data.get('username') else "—"
    phone = data.get('phone', '—')
    
    text = f"""
{'='*35}
📋 НОВАЯ ЗАЯВКА
{'='*35}

{status}

👤 Имя: {data.get('name', '—')}
📞 Телефон: {phone}
📱 Telegram: {tg}
🆔 ID: {user_id}

🔧 Услуга: {data.get('service', '—')}
💰 Цена: {data.get('service_price', '—')}
🏠 Объект: {data.get('object_type', '—')}
📐 Площадь: {data.get('area', '—')}
📅 Сроки: {data.get('timing', '—')}
✅ Цена ОК: {'Да' if data.get('price_accepted') else 'Нет'}
{'='*35}
"""
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
        logger.info(f"✅ Admin notified: {ADMIN_ID}")
        return True
    except Exception as e:
        logger.error(f"❌ Admin notify failed: {e}")
        return False


# === ОБРАБОТКА ПОСЛЕ ЗАВЕРШЕНИЯ ===

@dp.message(Form.done)
async def after_done(message: Message, state: FSMContext):
    """Сообщения после завершения"""
    
    await message.answer(
        "Если есть вопросы — звоните мастеру! 📞\n\n"
        f"Номер: `{MASTER_PHONE}`\n\n"
        "Или напишите /start чтобы оформить новую заявку.",
        parse_mode="Markdown"
    )


# === ЗАПУСК ===

async def main():
    await init_db()
    logger.info("🚀 BOT STARTING")
    logger.info(f"ADMIN: {ADMIN_ID}")
    logger.info(f"MASTER: {MASTER_PHONE}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
