import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, REQUIRED_FIELDS
from database import init_db, save_lead, save_conversation, reset_user
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
    collecting = State()       # Сбор информации
    asking_questions = State() # Вопросы по ценам
    waiting_phone = State()    # Ждём телефон
    chatting = State()         # Свободное общение


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    
    user = message.from_user
    name = user.first_name or "Клиент"
    
    logger.info(f"New conversation: user_id={user.id}, name={name}")
    
    await state.update_data(
        name=name,
        username=user.username or "",
        dialog_history=[],
        collected_data={},
    )
    
    await state.set_state(ConversationState.collecting)
    
    greeting = (
        f"Здравствуйте, {name}! 👋\n\n"
        "Я — помощник компании **СтройРемонтНН**.\n\n"
        "Мы делаем ремонт в Нижнем Новгороде:\n"
        "🔨 Демонтаж, электрика, сантехника\n"
        "🏗 Перегородки, потолки, плитка\n"
        "✨ Декоративная отделка\n\n"
        "Расскажите, что хотите сделать? 🏠"
    )
    
    await message.answer(greeting, parse_mode="Markdown")


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
    
    text = "📋 **Собрано:**\n\n"
    for field, value in collected.items():
        text += f"✅ {field}: {value}\n"
    
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("debug"))
async def cmd_debug(message: Message):
    """Диагностика API"""
    from ai_handler import check_api_status, call_ai
    
    await message.answer("🔍 Проверяю API...")
    
    status = await check_api_status()
    await message.answer(f"```\n{json.dumps(status, indent=2)}\n```", parse_mode="Markdown")
    
    test = await call_ai([{"role": "user", "content": "Скажи ОК"}], max_tokens=10)
    await message.answer(f"✅ AI: {test}" if test else "❌ AI не ответил")


@dp.message(ConversationState.collecting)
async def handle_collecting(message: Message, state: FSMContext):
    """Сбор информации"""
    
    data = await state.get_data()
    dialog_history = data.get("dialog_history", [])
    collected_data = data.get("collected_data", {})
    
    dialog_history.append({"role": "user", "content": message.text})
    
    reply, updated_data, ready_for_lead = await generate_reply(dialog_history, collected_data)
    
    dialog_history.append({"role": "assistant", "content": reply})
    
    await state.update_data(
        dialog_history=dialog_history,
        collected_data=updated_data,
    )
    
    await save_conversation(
        user_id=message.from_user.id,
        username=data.get("username", ""),
        first_name=data.get("name", ""),
        messages=json.dumps(dialog_history[-20:], ensure_ascii=False),
        collected_data=json.dumps(updated_data, ensure_ascii=False)
    )
    
    await message.answer(reply)
    
    # Если всё собрано - спрашиваем про вопросы
    if ready_for_lead:
        await state.set_state(ConversationState.asking_questions)
        logger.info(f"Data collected for {message.from_user.id}, asking about questions")


@dp.message(ConversationState.asking_questions)
async def handle_questions(message: Message, state: FSMContext):
    """Обработка вопросов по ценам"""
    
    text = message.text.lower()
    
    # Проверяем, есть ли вопросы или клиент готов
    no_questions = ['нет', 'всё понятно', 'все понятно', 'понятно', 'ок', 'хорошо', 'давайте', 'готов', 'жду', 'нету']
    
    if any(phrase in text for phrase in no_questions):
        # Нет вопросов - переходим к телефону
        await state.set_state(ConversationState.waiting_phone)
        
        phone_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Отлично! Нажмите кнопку, чтобы оставить номер — мастер свяжется с вами 👇",
            reply_markup=phone_keyboard
        )
    else:
        # Есть вопрос - отвечаем
        data = await state.get_data()
        dialog_history = data.get("dialog_history", [])
        
        dialog_history.append({"role": "user", "content": message.text})
        
        reply = await generate_questions_response(message.text)
        
        dialog_history.append({"role": "assistant", "content": reply})
        
        await state.update_data(dialog_history=dialog_history)
        
        await message.answer(reply)
        await message.answer("Есть ещё вопросы? Или готовы оставить заявку? 😊")


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
    
    success = await send_lead_to_admin(
        user_id=message.from_user.id,
        data={**collected_data, "name": data.get("name", ""), "username": data.get("username", "")}
    )
    
    farewell = await generate_farewell(data.get("name", ""))
    await message.answer(farewell)
    
    await state.set_state(ConversationState.chatting)
    logger.info(f"Lead sent: {success}")


@dp.message(ConversationState.waiting_phone, F.text)
async def handle_phone_text(message: Message, state: FSMContext):
    """Телефон текстом"""
    
    if await check_phone_number(message.text):
        data = await state.get_data()
        
        collected_data = data.get("collected_data", {})
        collected_data["phone"] = message.text.strip()
        
        await message.answer("✅ Номер получен!", reply_markup=ReplyKeyboardRemove())
        
        await send_lead_to_admin(
            user_id=message.from_user.id,
            data={**collected_data, "name": data.get("name", ""), "username": data.get("username", "")}
        )
        
        farewell = await generate_farewell(data.get("name", ""))
        await message.answer(farewell)
        
        await state.set_state(ConversationState.chatting)
    else:
        phone_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("Нажмите кнопку ниже 👇", reply_markup=phone_keyboard)


@dp.message(ConversationState.chatting)
async def handle_chatting(message: Message, state: FSMContext):
    """Свободное общение после заявки"""
    
    data = await state.get_data()
    dialog_history = data.get("dialog_history", [])
    
    dialog_history.append({"role": "user", "content": message.text})
    
    reply, _, _ = await generate_reply(dialog_history, data.get("collected_data", {}))
    
    dialog_history.append({"role": "assistant", "content": reply})
    
    await state.update_data(dialog_history=dialog_history)
    await message.answer(reply)


async def send_lead_to_admin(user_id: int, data: dict) -> bool:
    """Отправляет заявку админу"""
    
    logger.info(f"Sending lead to {ADMIN_ID}")
    
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
        logger.info("✅ Lead sent!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        return False


def evaluate_lead(data: dict) -> tuple[str, str]:
    """Оценка заявки (упрощённая)"""
    
    timing = data.get('timing', '').lower()
    budget = data.get('budget', '').lower()
    
    # Срочные
    if any(w in timing for w in ['сейчас', 'срочно', 'завтра', 'на этой неделе']):
        return "🔥 ГОРЯЧИЙ", "Готов начать срочно"
    
    # Скоро
    if any(w in timing for w in ['месяц', 'скоро', 'через неделю']):
        return "✅ ЦЕЛЕВОЙ", "Готов начать скоро"
    
    # Хороший бюджет
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
