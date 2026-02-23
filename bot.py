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

from config import (
    BOT_TOKEN, ADMIN_ID, MASTER_PHONE, MASTER_WHATSAPP,
    SERVICES, OBJECTS, AREAS, TIMINGS, FAQ
)
from database import init_db, save_lead

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === СОСТОЯНИЯ ===
class Form(StatesGroup):
    main_menu = State()
    service = State()
    object_type = State()
    area = State()
    timing = State()
    price_check = State()
    contact = State()
    faq = State()


# === КНОПКИ НАВИГАЦИИ ===
BTN_BACK_CATALOG = "⬅️ Каталог услуг"
BTN_BACK = "⬅️ Назад"
BTN_HOME = "🏠 Главное меню"
BTN_FAQ = "❓ Частые вопросы"


# === КЛАВИАТУРЫ ===

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 Выбрать услугу")],
            [KeyboardButton(text=BTN_FAQ)],
        ],
        resize_keyboard=True
    )


def services_keyboard() -> ReplyKeyboardMarkup:
    """Каталог услуг"""
    buttons = []
    for key, s in SERVICES.items():
        buttons.append([KeyboardButton(text=f"{s['emoji']} {s['name']} — {s['price']}")])
    buttons.append([KeyboardButton(text=BTN_HOME)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def objects_keyboard() -> ReplyKeyboardMarkup:
    """Тип объекта"""
    buttons = [[KeyboardButton(text=f"{o['emoji']} {o['name']}")] for o in OBJECTS.values()]
    buttons.append([KeyboardButton(text=BTN_BACK_CATALOG), KeyboardButton(text=BTN_HOME)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def areas_keyboard() -> ReplyKeyboardMarkup:
    """Площадь"""
    buttons = [[KeyboardButton(text=f"{a['emoji']} {a['name']}")] for a in AREAS.values()]
    buttons.append([KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_HOME)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def timings_keyboard() -> ReplyKeyboardMarkup:
    """Сроки"""
    buttons = [[KeyboardButton(text=f"{t['emoji']} {t['name']}")] for t in TIMINGS.values()]
    buttons.append([KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_HOME)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def price_check_keyboard() -> ReplyKeyboardMarkup:
    """Подтверждение цены"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, подходит!")],
            [KeyboardButton(text="❌ Хочу посмотреть другое")],
            [KeyboardButton(text=BTN_HOME)]
        ],
        resize_keyboard=True
    )


def contact_keyboard() -> ReplyKeyboardMarkup:
    """Контакт мастера"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Позвонить мастеру")],
            [KeyboardButton(text="💬 Написать в WhatsApp")],
            [KeyboardButton(text="🔧 Заказать другую услугу")],
            [KeyboardButton(text=BTN_HOME)]
        ],
        resize_keyboard=True
    )


def faq_keyboard() -> ReplyKeyboardMarkup:
    """FAQ"""
    buttons = [[KeyboardButton(text=f["question"])] for f in FAQ.values()]
    buttons.append([KeyboardButton(text=BTN_HOME)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def back_to_services_keyboard() -> ReplyKeyboardMarkup:
    """После отказа от цены"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Посмотреть другие услуги")],
            [KeyboardButton(text=BTN_HOME)]
        ],
        resize_keyboard=True
    )


# === ВСПОМОГАТЕЛЬНЫЕ ===

def get_service_by_text(text: str) -> dict | None:
    """Находит услугу по тексту кнопки"""
    for key, s in SERVICES.items():
        if s["name"] in text:
            return {"key": key, **s}
    return None


def get_name(message: Message) -> str:
    """Получает имя пользователя"""
    return message.from_user.first_name or "друг"


# === ГЛАВНОЕ МЕНЮ ===

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Старт"""
    await state.clear()
    
    name = get_name(message)
    username = message.from_user.username or ""
    
    await state.update_data(name=name, username=username)
    await state.set_state(Form.main_menu)
    
    logger.info(f"START: {message.from_user.id} ({name})")
    
    await message.answer(
        f"Привет, {name}! 👋\n\n"
        "Я — бот **СтройРемонтНН**\n\n"
        "🏆 Ремонт в Нижнем Новгороде\n"
        "📋 Гарантия 5 лет\n"
        "⚡ Мастер ответит за 30 минут\n\n"
        "Чем могу помочь?",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


@dp.message(F.text == BTN_HOME)
async def go_home(message: Message, state: FSMContext):
    """Возврат в главное меню"""
    
    data = await state.get_data()
    name = data.get("name", get_name(message))
    
    await state.set_state(Form.main_menu)
    
    await message.answer(
        f"🏠 Главное меню\n\n"
        f"Что будем делать, {name}?",
        reply_markup=main_menu_keyboard()
    )


@dp.message(Form.main_menu, F.text.contains("Выбрать услугу"))
async def show_services(message: Message, state: FSMContext):
    """Показать каталог"""
    await state.set_state(Form.service)
    
    await message.answer(
        "🔧 **Наши услуги:**\n\n"
        "Выберите, что вас интересует 👇",
        parse_mode="Markdown",
        reply_markup=services_keyboard()
    )


# === КАТАЛОГ УСЛУГ ===

@dp.message(F.text == BTN_BACK_CATALOG)
async def back_to_catalog(message: Message, state: FSMContext):
    """Возврат в каталог"""
    await state.set_state(Form.service)
    
    await message.answer(
        "🔧 **Каталог услуг**\n\n"
        "Выберите услугу:",
        parse_mode="Markdown",
        reply_markup=services_keyboard()
    )


@dp.message(Form.service)
async def process_service(message: Message, state: FSMContext):
    """Выбор услуги"""
    
    if message.text == BTN_HOME:
        await go_home(message, state)
        return
    
    service = get_service_by_text(message.text)
    
    if not service:
        await message.answer("Выбери услугу из списка 👇", reply_markup=services_keyboard())
        return
    
    logger.info(f"SERVICE: {message.from_user.id} -> {service['name']}")
    
    await state.update_data(
        service=service["name"],
        service_key=service["key"],
        service_price=service["price"],
        service_emoji=service["emoji"]
    )
    
    await state.set_state(Form.object_type)
    
    await message.answer(
        f"{service['emoji']} **{service['name']}** — {service['price']}\n\n"
        f"💬 _{service['comment']}_\n\n"
        "Какой у вас объект?",
        parse_mode="Markdown",
        reply_markup=objects_keyboard()
    )


# === ТИП ОБЪЕКТА ===

@dp.message(Form.object_type)
async def process_object(message: Message, state: FSMContext):
    """Тип объекта"""
    
    if message.text == BTN_HOME:
        await go_home(message, state)
        return
    if message.text == BTN_BACK_CATALOG:
        await back_to_catalog(message, state)
        return
    
    # Проверяем валидность
    valid = any(o["name"] in message.text for o in OBJECTS.values())
    if not valid:
        await message.answer("Выбери тип объекта 👇", reply_markup=objects_keyboard())
        return
    
    logger.info(f"OBJECT: {message.from_user.id} -> {message.text}")
    
    await state.update_data(object_type=message.text)
    await state.set_state(Form.area)
    
    await message.answer(
        "👍 Отлично!\n\n"
        "Какая примерная площадь?",
        reply_markup=areas_keyboard()
    )


# === ПЛОЩАДЬ ===

@dp.message(Form.area)
async def process_area(message: Message, state: FSMContext):
    """Площадь"""
    
    if message.text == BTN_HOME:
        await go_home(message, state)
        return
    if message.text == BTN_BACK:
        await state.set_state(Form.object_type)
        await message.answer("Какой тип объекта?", reply_markup=objects_keyboard())
        return
    
    valid = any(a["name"] in message.text for a in AREAS.values())
    if not valid:
        await message.answer("Выбери площадь 👇", reply_markup=areas_keyboard())
        return
    
    logger.info(f"AREA: {message.from_user.id} -> {message.text}")
    
    await state.update_data(area=message.text)
    await state.set_state(Form.timing)
    
    await message.answer(
        "📐 Записал!\n\n"
        "Когда планируете начать?",
        reply_markup=timings_keyboard()
    )


# === СРОКИ ===

@dp.message(Form.timing)
async def process_timing(message: Message, state: FSMContext):
    """Сроки"""
    
    if message.text == BTN_HOME:
        await go_home(message, state)
        return
    if message.text == BTN_BACK:
        await state.set_state(Form.area)
        await message.answer("Какая площадь?", reply_markup=areas_keyboard())
        return
    
    valid = any(t["name"] in message.text for t in TIMINGS.values())
    if not valid:
        await message.answer("Выбери сроки 👇", reply_markup=timings_keyboard())
        return
    
    logger.info(f"TIMING: {message.from_user.id} -> {message.text}")
    
    await state.update_data(timing=message.text)
    await state.set_state(Form.price_check)
    
    data = await state.get_data()
    
    await message.answer(
        f"📋 **Ваш запрос:**\n\n"
        f"{data.get('service_emoji', '🔧')} {data.get('service')}\n"
        f"🏠 {data.get('object_type')}\n"
        f"📐 {data.get('area')}\n"
        f"📅 {data.get('timing')}\n\n"
        f"💰 **Стоимость работ: {data.get('service_price')}**\n\n"
        "Вам подходит? 👇",
        parse_mode="Markdown",
        reply_markup=price_check_keyboard()
    )


# === ПРОВЕРКА ЦЕНЫ ===

@dp.message(Form.price_check)
async def process_price_check(message: Message, state: FSMContext):
    """Подтверждение цены"""
    
    if message.text == BTN_HOME:
        await go_home(message, state)
        return
    
    text = message.text.lower()
    
    if "да" in text or "✅" in text or "подходит" in text:
        # Цена ОК — показываем контакт
        logger.info(f"PRICE OK: {message.from_user.id}")
        
        await state.update_data(price_accepted=True, status="COMPLETED")
        
        data = await state.get_data()
        await save_lead(message.from_user.id, data)
        await send_to_admin(message.from_user.id, data)
        
        await state.set_state(Form.contact)
        
        await message.answer(
            "🎉 **Отлично!**\n\n"
            f"📞 **Телефон мастера:**\n`{MASTER_PHONE}`\n\n"
            "Мастер ответит в течение 30 минут.\n"
            "Можете позвонить или написать в WhatsApp 👇",
            parse_mode="Markdown",
            reply_markup=contact_keyboard()
        )
        
    elif "нет" in text or "❌" in text or "другое" in text:
        # Цена не подошла
        logger.info(f"PRICE NO: {message.from_user.id}")
        
        await state.update_data(price_accepted=False, status="PRICE_REJECTED")
        
        data = await state.get_data()
        await save_lead(message.from_user.id, data)
        
        await message.answer(
            "Понимаю! 🤝\n\n"
            "Это минимальные цены для качественной работы с гарантией.\n\n"
            "Могу показать другие услуги — возможно, что-то подойдёт лучше 👇",
            reply_markup=back_to_services_keyboard()
        )
        
    else:
        await message.answer("Выбери вариант 👇", reply_markup=price_check_keyboard())


@dp.message(F.text == "🔄 Посмотреть другие услуги")
async def other_services(message: Message, state: FSMContext):
    """Другие услуги после отказа"""
    await back_to_catalog(message, state)


@dp.message(F.text == "🔧 Заказать другую услугу")
async def another_service(message: Message, state: FSMContext):
    """Другая услуга после контакта"""
    await back_to_catalog(message, state)


# === КОНТАКТ МАСТЕРА ===

@dp.message(Form.contact)
async def process_contact(message: Message, state: FSMContext):
    """Действия с контактом"""
    
    if message.text == BTN_HOME:
        await go_home(message, state)
        return
    
    if "Позвонить" in message.text:
        await message.answer(
            f"📞 **Номер мастера:**\n\n"
            f"`{MASTER_PHONE}`\n\n"
            "Нажмите на номер, чтобы скопировать ☝️",
            parse_mode="Markdown",
            reply_markup=contact_keyboard()
        )
        
    elif "WhatsApp" in message.text:
        await message.answer(
            f"💬 **WhatsApp мастера:**\n\n"
            f"{MASTER_WHATSAPP}\n\n"
            "Нажмите на ссылку, чтобы открыть чат ☝️",
            reply_markup=contact_keyboard()
        )
        
    elif "другую услугу" in message.text:
        await back_to_catalog(message, state)
        
    else:
        await message.answer(
            f"📞 Номер мастера: `{MASTER_PHONE}`\n\n"
            "Выберите действие 👇",
            parse_mode="Markdown",
            reply_markup=contact_keyboard()
        )


# === FAQ ===

@dp.message(F.text == BTN_FAQ)
async def show_faq(message: Message, state: FSMContext):
    """Показать FAQ"""
    await state.set_state(Form.faq)
    
    await message.answer(
        "❓ **Частые вопросы**\n\n"
        "Выберите тему:",
        parse_mode="Markdown",
        reply_markup=faq_keyboard()
    )


@dp.message(Form.faq)
async def process_faq(message: Message, state: FSMContext):
    """Обработка FAQ"""
    
    if message.text == BTN_HOME:
        await go_home(message, state)
        return
    
    # Ищем вопрос
    for key, faq in FAQ.items():
        if faq["question"] in message.text:
            await message.answer(
                f"**{faq['question']}**\n\n"
                f"{faq['answer']}",
                parse_mode="Markdown",
                reply_markup=faq_keyboard()
            )
            return
    
    await message.answer("Выбери вопрос из списка 👇", reply_markup=faq_keyboard())


# === ОТПРАВКА АДМИНУ ===

async def send_to_admin(user_id: int, data: dict) -> bool:
    """Уведомление админа"""
    
    timing = data.get('timing', '').lower()
    if 'сейчас' in timing or '🔥' in timing:
        status = "🔥 ГОРЯЧИЙ"
    elif 'месяц' in timing:
        status = "✅ ТЁПЛЫЙ"
    else:
        status = "📝 НОВЫЙ"
    
    tg = f"@{data.get('username')}" if data.get('username') else "—"
    
    text = f"""
{'='*30}
📋 НОВАЯ ЗАЯВКА
{'='*30}

{status}

👤 {data.get('name', '—')}
📱 {tg}
🆔 {user_id}

{data.get('service_emoji', '🔧')} {data.get('service', '—')}
💰 {data.get('service_price', '—')}
🏠 {data.get('object_type', '—')}
📐 {data.get('area', '—')}
📅 {data.get('timing', '—')}

✅ Цена ОК: {'Да' if data.get('price_accepted') else 'Нет'}
{'='*30}
"""
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
        logger.info(f"✅ Admin notified")
        return True
    except Exception as e:
        logger.error(f"❌ Admin error: {e}")
        return False


# === ЗАПУСК ===

async def main():
    await init_db()
    logger.info("🚀 BOT STARTING")
    logger.info(f"ADMIN: {ADMIN_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
