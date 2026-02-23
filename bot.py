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
from ai_handler import generate_reply, check_phone_number, generate_farewell, generate_questions_response

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class ConversationState(StatesGroup):
    collecting = State()        # Сбор информации
    confirming = State()        # Подтверждение данных
    asking_questions = State()  # Вопросы по ценам
    waiting_phone = State()     # Ждём телефон
    chatting = State()          # Свободное общение


def get_phone_keyboard():
    """Клавиатура с кнопкой телефона"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_confirm_keyboard():
    """Клавиатура подтверждения"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Всё верно")],
            [KeyboardButton(text="❌ Изменить данные")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def format_collected_data(data: dict) -> str:
    """Форматирует собранные данные для показа клиенту"""
    text = "📋 **Проверьте данные:**\n\n"
    
    for field in REQUIRED_FIELDS:
        value = data.get(field, "—")
        name = FIELD_NAMES.get(field, field)
        text += f"▫️ **{name}:** {value}\n"
    
    text += "\nВсё верно? ✅"
    return text


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    
    user = message.from_user
    name = user.first_name or "Клиент"
    
    logger.info(f"New conversation: user_id={user.id}, name={name}")
    
    # Пробуем загрузить предыдущую историю
    existing = await get_conversation(user.id)
    
    old_messages = []
    old_data = {}
    
    if existing:
        try:
            old_messages = json.loads(existing[0]) if existing[0] else []
            old_data = json.loads(existing[1]) if existing[1] else {}
            logger.info(f"Restored {len(old_messages)} messages for user {user.id}")
        except:
            pass
    
    # Определяем первое незаполненное поле
    current_field = None
    for field in REQUIRED_FIELDS:
        if not old_data.get(field):
            current_field = field
            break
    
    await state.update_data(
        name=name,
        username=user.username or "",
        dialog_history=old_messages,
        collected_data=old_data,
        current_field=current_field
    )
    
    await state.set_state(ConversationState.collecting)
    
    if old_messages and old_data:
        # Есть история - спрашиваем продолжить
        greeting = (
            f"С возвращением, {name}! 👋\n\n"
            "Я помню наш разговор. Продолжим?\n"
            "Или напишите /reset чтобы начать заново."
        )
    else:
        greeting = (
            f"Здравствуйте, {name}! 👋\n\n"
            "Я — помощник компании **СтройРемонтНН**.\n\n"
            "Мы делаем ремонт в Нижнем Новгороде:\n"
            "🔨 Демонтаж, электрика, сантехника\n"
            "🏗 Перегородки, потолки, плитка\n"
            "✨ Декоративная отделка\n\n"
            f"{FIELD_QUESTIONS['work']}"
        )
        current_field = "work"
        await state.update_data(current_field=current_field)
    
    await message.answer(greeting, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Сброс диалога"""
    await state.clear()
    await reset_user(message.from_user.id)
    await message.answer("♻️ Диалог сброшен. Напишите /start", reply_markup=ReplyKeyboardRemove())


@dp.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext):
    """Показать собранные данные"""
    data = await state.get_data()
    collected = data.get("collected_data", {})
    
    if not collected:
        await message.answer("📋 Пока ничего не собрано.")
        return
    
    text = "📋 **Собранные данные:**\n\n"
    for field in REQUIRED_FIELDS:
        value = collected.get(field)
        name = FIELD_NAMES.get(field, field)
        emoji = "✅" if value else "❌"
        text += f"{emoji} **{name}:** {value or 'не указано'}\n"
    
    await message.answer(text, parse_mode="Markdown")


@dp.message(ConversationState.collecting)
async def handle_collecting(message: Message, state: FSMContext):
    """Сбор информации по полям"""
    
    data = await state.get_data()
    dialog_history = data.get("dialog_history", [])
    collected_data = data.get("collected_data", {})
    current_field = data.get("current_field")
    
    # Добавляем сообщение в историю
    dialog_history.append({"role": "user", "content": message.text})
    
    # Генерируем ответ и извлекаем данные
    reply, updated_data, next_field, all_collected = await generate_reply(
        dialog_history, collected_data, current_field
    )
    
    if all_collected:
        # Все данные собраны - показываем для подтверждения
        dialog_history.append({"role": "assistant", "content": "Проверка данных..."})
        
        await state.update_data(
            dialog_history=dialog_history,
            collected_data=updated_data,
            current_field=None
        )
        
        # Сохраняем в БД
        await save_conversation(
            user_id=message.from_user.id,
            username=data.get("username", ""),
            first_name=data.get("name", ""),
            messages=json.dumps(dialog_history, ensure_ascii=False),
            collected_data=json.dumps(updated_data, ensure_ascii=False)
        )
        
        # Показываем собранные данные
        summary = format_collected_data(updated_data)
        await message.answer(summary, parse_mode="Markdown", reply_markup=get_confirm_keyboard())
        
        await state.set_state(ConversationState.confirming)
        logger.info(f"✅ All data collected for {message.from_user.id}, waiting confirmation")
        
    else:
        # Продолжаем сбор
        dialog_history.append({"role": "assistant", "content": reply})
        
        await state.update_data(
            dialog_history=dialog_history,
            collected_data=updated_data,
            current_field=next_field
        )
        
        # Сохраняем в БД
        await save_conversation(
            user_id=message.from_user.id,
            username=data.get("username", ""),
            first_name=data.get("name", ""),
            messages=json.dumps(dialog_history, ensure_ascii=False),
            collected_data=json.dumps(updated_data, ensure_ascii=False)
        )
        
        await message.answer(reply)


@dp.message(ConversationState.confirming)
async def handle_confirming(message: Message, state: FSMContext):
    """Подтверждение данных"""
    
    text = message.text.lower().strip()
    
    if "верно" in text or "да" in text or "✅" in text or "ок" in text or "подтверж" in text:
        # Данные подтверждены - спрашиваем про вопросы
        await state.set_state(ConversationState.asking_questions)
        
        await message.answer(
            "Отлично! 👍 Есть вопросы по ценам или услугам?",
            reply_markup=ReplyKeyboardRemove()
        )
        
    elif "изменить" in text or "нет" in text or "❌" in text or "исправ" in text:
        # Хотят изменить - сбрасываем и начинаем заново
        await state.update_data(
            collected_data={},
            current_field="work"
        )
        await state.set_state(ConversationState.collecting)
        
        await message.answer(
            "Хорошо, давайте заново! 📝\n\n" + FIELD_QUESTIONS["work"],
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # Непонятный ответ
        await message.answer(
            "Пожалуйста, подтвердите данные или нажмите 'Изменить' 👇",
            reply_markup=get_confirm_keyboard()
        )


@dp.message(ConversationState.asking_questions)
async def handle_questions(message: Message, state: FSMContext):
    """Обработка вопросов по ценам"""
    
    data = await state.get_data()
    dialog_history = data.get("dialog_history", [])
    
    dialog_history.append({"role": "user", "content": message.text})
    
    text = message.text.lower().strip()
    
    # Проверяем, есть ли вопросы
    no_questions = ['нет', 'нету', 'не', 'всё понятно', 'все понятно', 'понятно', 
                   'ок', 'хорошо', 'давайте', 'готов', 'жду', 'нет вопросов',
                   'всё ясно', 'все ясно', 'ясно', 'норм', 'окей', 'да', 'давай', 'го']
    
    is_no_questions = any(text == phrase or text.startswith(phrase + " ") for phrase in no_questions)
    
    if is_no_questions or len(text) < 3:
        # Нет вопросов - просим телефон
        await state.set_state(ConversationState.waiting_phone)
        await state.update_data(dialog_history=dialog_history)
        
        logger.info(f"📞 Requesting phone from {message.from_user.id}")
        
        await message.answer(
            "Отлично! 📱 Нажмите кнопку ниже, чтобы оставить номер телефона.\n"
            "Мастер свяжется с вами для уточнения деталей:",
            reply_markup=get_phone_keyboard()
        )
    else:
        # Есть вопрос - отвечаем
        reply = await generate_questions_response(message.text)
        
        dialog_history.append({"role": "assistant", "content": reply})
        await state.update_data(dialog_history=dialog_history)
        
        await save_conversation(
            user_id=message.from_user.id,
            username=data.get("username", ""),
            first_name=data.get("name", ""),
            messages=json.dumps(dialog_history, ensure_ascii=False),
            collected_data=json.dumps(data.get("collected_data", {}), ensure_ascii=False)
        )
        
        await message.answer(reply)
        await message.answer("Ещё вопросы? Или готовы оставить заявку? 😊")


@dp.message(ConversationState.waiting_phone, F.contact)
async def handle_phone_contact(message: Message, state: FSMContext):
    """Телефон через кнопку"""
    
    data = await state.get_data()
    phone = message.contact.phone_number
    
    if not phone.startswith("+"):
        phone = "+" + phone
    
    logger.info(f"📞 Phone received: {phone}")
    
    collected_data = data.get("collected_data", {})
    collected_data["phone"] = phone
    
    await message.answer("✅ Номер получен!", reply_markup=ReplyKeyboardRemove())
    
    # Отправляем заявку админу
    success = await send_lead_to_admin(
        user_id=message.from_user.id,
        data={
            **collected_data,
            "name": data.get("name", ""),
            "username": data.get("username", "")
        }
    )
    
    if success:
        logger.info(f"✅ Lead sent to admin for user {message.from_user.id}")
        farewell = await generate_farewell(data.get("name", ""))
        await message.answer(farewell)
    else:
        logger.error(f"❌ Failed to send lead for user {message.from_user.id}")
        await message.answer("Заявка принята! Мастер свяжется с вами в ближайшее время. 👍")
    
    await state.set_state(ConversationState.chatting)


@dp.message(ConversationState.waiting_phone, F.text)
async def handle_phone_text(message: Message, state: FSMContext):
    """Телефон текстом"""
    
    if await check_phone_number(message.text):
        data = await state.get_data()
        phone = message.text.strip()
        
        logger.info(f"📞 Phone received via text: {phone}")
        
        collected_data = data.get("collected_data", {})
        collected_data["phone"] = phone
        
        await message.answer("✅ Номер получен!", reply_markup=ReplyKeyboardRemove())
        
        success = await send_lead_to_admin(
            user_id=message.from_user.id,
            data={
                **collected_data,
                "name": data.get("name", ""),
                "username": data.get("username", "")
            }
        )
        
        if success:
            farewell = await generate_farewell(data.get("name", ""))
            await message.answer(farewell)
        else:
            await message.answer("Заявка принята! Мастер свяжется с вами. 👍")
        
        await state.set_state(ConversationState.chatting)
    else:
        await message.answer(
            "📱 Нажмите кнопку ниже, чтобы поделиться номером:",
            reply_markup=get_phone_keyboard()
        )


@dp.message(ConversationState.chatting)
async def handle_chatting(message: Message, state: FSMContext):
    """Свободное общение после заявки"""
    
    data = await state.get_data()
    dialog_history = data.get("dialog_history", [])
    
    dialog_history.append({"role": "user", "content": message.text})
    
    reply, _, _, _ = await generate_reply(dialog_history, data.get("collected_data", {}), None)
    
    if not reply:
        reply = "Спасибо за сообщение! Если будут вопросы — пишите. 😊"
    
    dialog_history.append({"role": "assistant", "content": reply})
    await state.update_data(dialog_history=dialog_history)
    
    await save_conversation(
        user_id=message.from_user.id,
        username=data.get("username", ""),
        first_name=data.get("name", ""),
        messages=json.dumps(dialog_history, ensure_ascii=False),
        collected_data=json.dumps(data.get("collected_data", {}), ensure_ascii=False)
    )
    
    await message.answer(reply)


async def send_lead_to_admin(user_id: int, data: dict) -> bool:
    """Отправляет заявку админу"""
    
    logger.info(f"📤 Sending lead to admin {ADMIN_ID}")
    logger.info(f"📊 Data: {data}")
    
    status, reason = evaluate_lead(data)
    tg_link = f"@{data.get('username')}" if data.get('username') else "нет"
    
    lead_text = f"""
{'='*35}
📋 **НОВАЯ ЗАЯВКА**
{'='*35}

{status}
💬 _{reason}_

👤 **Имя:** {data.get('name', '—')}
📞 **Телефон:** {data.get('phone', '—')}
📱 **Telegram:** {tg_link}
🆔 **ID:** `{user_id}`

🔧 **Работы:** {data.get('work', '—')}
🏠 **Объект:** {data.get('object_type', '—')}
📐 **Площадь:** {data.get('area', '—')}
📍 **Адрес:** {data.get('address', '—')}
📅 **Сроки:** {data.get('timing', '—')}
💰 **Бюджет:** {data.get('budget', '—')}
{'='*35}
"""
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=lead_text, parse_mode="Markdown")
        await save_lead(user_id, json.dumps(data, ensure_ascii=False), status, reason)
        logger.info("✅ Lead sent successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send lead: {e}")
        return False


def evaluate_lead(data: dict) -> tuple[str, str]:
    """Оценка заявки"""
    
    timing = data.get('timing', '').lower()
    budget = data.get('budget', '').lower()
    
    if any(w in timing for w in ['сейчас', 'срочно', 'завтра', 'на этой неделе']):
        return "🔥 ГОРЯЧИЙ", "Готов начать срочно"
    
    if any(w in timing for w in ['месяц', 'скоро', 'через неделю']):
        return "✅ ЦЕЛЕВОЙ", "Готов начать скоро"
    
    if any(w in budget for w in ['200', '300', '400', '500', 'млн', 'миллион']):
        return "✅ ЦЕЛЕВОЙ", "Хороший бюджет"
    
    return "📝 НОВАЯ", "Требует обработки"


async def main():
    await init_db()
    logger.info("=" * 50)
    logger.info("🚀 BOT STARTING...")
    logger.info(f"📋 ADMIN_ID: {ADMIN_ID}")
    logger.info("=" * 50)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
