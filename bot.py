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
from database import init_db, save_lead, save_conversation, get_conversation, reset_user
from ai_handler import generate_reply, check_phone_number, generate_farewell

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class ConversationState(StatesGroup):
    """Состояния диалога"""
    collecting = State()      # Сбор информации
    waiting_phone = State()   # Ждём телефон
    chatting = State()        # Свободное общение после заявки


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    
    user = message.from_user
    name = user.first_name or "Клиент"
    
    logger.info(f"New conversation: user_id={user.id}, name={name}")
    
    # Инициализируем данные сессии
    await state.update_data(
        name=name,
        username=user.username or "",
        dialog_history=[],
        collected_data={},
        messages_count=0
    )
    
    await state.set_state(ConversationState.collecting)
    
    # Приветствие
    greeting = (
        f"Здравствуйте, {name}! 👋\n\n"
        "Я — помощник компании **СтройРемонтНН**.\n\n"
        "Мы делаем комплексные ремонты в Нижнем Новгороде:\n"
        "🔨 Демонтаж, электрика, сантехника\n"
        "🏗 Перегородки, потолки, плитка\n"
        "✨ Декоративная отделка\n\n"
        "Расскажите, что хотите сделать? 🏠"
    )
    
    await message.answer(greeting, parse_mode="Markdown")


@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Сброс диалога (для тестирования)"""
    await state.clear()
    await reset_user(message.from_user.id)
    await message.answer("♻️ Диалог сброшен. Напишите /start чтобы начать заново.", reply_markup=ReplyKeyboardRemove())


@dp.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext):
    """Показать собранные данные (для отладки)"""
    data = await state.get_data()
    collected = data.get("collected_data", {})
    
    if not collected:
        await message.answer("📋 Пока ничего не собрано.")
        return
    
    status_text = "📋 **Собранная информация:**\n\n"
    for field, value in collected.items():
        emoji = "✅" if value else "❌"
        field_name = REQUIRED_FIELDS.get(field, field)
        status_text += f"{emoji} {field_name}: {value or '—'}\n"
    
    missing = [f for f in REQUIRED_FIELDS if f not in collected]
    if missing:
        status_text += f"\n⏳ Осталось узнать: {len(missing)} пунктов"
    else:
        status_text += "\n✅ Вся информация собрана!"
    
    await message.answer(status_text, parse_mode="Markdown")


@dp.message(Command("debug"))
async def cmd_debug(message: Message):
    """Диагностика API"""
    from ai_handler import check_api_status, call_ai
    
    await message.answer("🔍 Проверяю OpenRouter API...")
    
    # Проверяем статус
    status = await check_api_status()
    
    status_text = f"**API Status:**\n```\n{json.dumps(status, indent=2, ensure_ascii=False)}\n```"
    await message.answer(status_text, parse_mode="Markdown")
    
    # Пробуем простой запрос
    await message.answer("🧪 Тестовый запрос к AI...")
    
    test_reply = await call_ai([
        {"role": "user", "content": "Скажи 'Привет, я работаю!'"}
    ], max_tokens=20)
    
    if test_reply:
        await message.answer(f"✅ AI ответил: {test_reply}")
    else:
        await message.answer("❌ AI не ответил! Смотрите логи.")


@dp.message(ConversationState.collecting)
async def handle_collecting(message: Message, state: FSMContext):
    """Основной обработчик - сбор информации"""
    
    data = await state.get_data()
    dialog_history = data.get("dialog_history", [])
    collected_data = data.get("collected_data", {})
    messages_count = data.get("messages_count", 0)
    
    # Добавляем сообщение клиента в историю
    dialog_history.append({
        "role": "user",
        "content": message.text
    })
    
    # Генерируем ответ через AI
    reply, updated_data, ready_for_lead = await generate_reply(dialog_history, collected_data)
    
    # Добавляем ответ в историю
    dialog_history.append({
        "role": "assistant",
        "content": reply
    })
    
    # Обновляем состояние
    await state.update_data(
        dialog_history=dialog_history,
        collected_data=updated_data,
        messages_count=messages_count + 1
    )
    
    # Сохраняем в БД
    await save_conversation(
        user_id=message.from_user.id,
        username=data.get("username", ""),
        first_name=data.get("name", ""),
        messages=json.dumps(dialog_history, ensure_ascii=False),
        collected_data=json.dumps(updated_data, ensure_ascii=False)
    )
    
    # Если вся информация собрана - переходим к ожиданию телефона
    if ready_for_lead:
        await state.set_state(ConversationState.waiting_phone)
        logger.info(f"All data collected for user {message.from_user.id}, waiting for phone")
        
        # Сначала отправляем ответ AI
        await message.answer(reply)
        
        # Затем отправляем кнопку для номера телефона
        phone_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Нажмите кнопку ниже, чтобы поделиться номером 👇",
            reply_markup=phone_keyboard
        )
    else:
        await message.answer(reply)


@dp.message(ConversationState.waiting_phone, F.contact)
async def handle_phone_contact(message: Message, state: FSMContext):
    """Обработка номера телефона через кнопку (контакт)"""
    
    data = await state.get_data()
    
    # Получаем телефон из контакта
    phone = message.contact.phone_number
    
    # Добавляем + если нет
    if not phone.startswith("+"):
        phone = "+" + phone
    
    logger.info(f"📞 Received phone via contact: {phone}")
    
    # Сохраняем телефон
    collected_data = data.get("collected_data", {})
    collected_data["phone"] = phone
    
    # Убираем клавиатуру
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
    
    # Генерируем прощание
    farewell = await generate_farewell(data.get("name", ""))
    await message.answer(farewell)
    
    # Переходим в режим свободного чата
    await state.set_state(ConversationState.chatting)
    
    logger.info(f"Lead sent for user {message.from_user.id}, success={success}")


@dp.message(ConversationState.waiting_phone, F.text)
async def handle_phone_text(message: Message, state: FSMContext):
    """Если написали текстом вместо кнопки - проверяем на телефон"""
    
    data = await state.get_data()
    
    # Проверяем, есть ли в сообщении телефон
    has_phone = await check_phone_number(message.text)
    
    if has_phone:
        # Телефон найден в тексте
        phone = message.text.strip()
        
        logger.info(f"📞 Received phone via text: {phone}")
        
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
        
        farewell = await generate_farewell(data.get("name", ""))
        await message.answer(farewell)
        
        await state.set_state(ConversationState.chatting)
        
    else:
        # Напоминаем про кнопку
        phone_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Нажмите кнопку ниже, чтобы поделиться номером 👇",
            reply_markup=phone_keyboard
        )


@dp.message(ConversationState.chatting)
async def handle_chatting(message: Message, state: FSMContext):
    """Свободное общение после отправки заявки"""
    
    data = await state.get_data()
    dialog_history = data.get("dialog_history", [])
    
    # Добавляем сообщение в историю
    dialog_history.append({
        "role": "user",
        "content": message.text
    })
    
    # Генерируем ответ (без сбора данных)
    reply, _, _ = await generate_reply(dialog_history, data.get("collected_data", {}))
    
    dialog_history.append({
        "role": "assistant",
        "content": reply
    })
    
    await state.update_data(dialog_history=dialog_history)
    await message.answer(reply)


async def send_lead_to_admin(user_id: int, data: dict) -> bool:
    """Отправляет заявку админу"""
    
    logger.info(f"Sending lead to admin {ADMIN_ID}")
    
    # Оценка качества заявки
    status, reason = evaluate_lead(data)
    
    # Форматируем username
    tg_link = f"@{data.get('username')}" if data.get('username') else "нет"
    
    # Формируем текст заявки
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
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=lead_text,
            parse_mode="Markdown"
        )
        
        # Сохраняем в БД
        await save_lead(
            user_id=user_id,
            data=json.dumps(data, ensure_ascii=False),
            score=status,
            score_reason=reason
        )
        
        logger.info(f"✅ Lead sent successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send lead: {e}")
        return False


def evaluate_lead(data: dict) -> tuple[str, str]:
    """Оценивает качество заявки"""
    
    budget = data.get('budget', '').lower()
    timing = data.get('timing', '').lower()
    work = data.get('work', '').lower()
    
    # Проверка на мелкие работы
    small_works = ['кран', 'смеситель', 'розетк', 'выключатель', 'лампочк', 'замок']
    if any(word in work for word in small_works) and 'ремонт' not in work:
        return "⚠️ ПОД ВОПРОСОМ", "Возможно мелкая работа"
    
    # Проверка бюджета
    low_budget_markers = ['10 тыс', '20 тыс', '30 тыс', '50 тыс', '10000', '20000', '30000', '50000']
    if any(marker in budget for marker in low_budget_markers):
        return "❌ НЕЦЕЛЕВОЙ", "Бюджет ниже минимального (100к)"
    
    # Проверка сроков
    urgent_markers = ['сейчас', 'срочно', 'на этой неделе', 'завтра', 'сегодня']
    soon_markers = ['в этом месяце', 'скоро', 'через неделю', 'через 2 недели']
    
    if any(marker in timing for marker in urgent_markers):
        return "🔥 ГОРЯЧИЙ", "Готов начать срочно!"
    
    if any(marker in timing for marker in soon_markers):
        return "✅ ЦЕЛЕВОЙ", "Готов начать в ближайшее время"
    
    # Проверка на хороший бюджет
    good_budget_markers = ['100', '150', '200', '300', '400', '500', 'миллион', 'млн']
    if any(marker in budget for marker in good_budget_markers):
        return "✅ ЦЕЛЕВОЙ", "Хороший бюджет"
    
    return "⚠️ ПОД ВОПРОСОМ", "Требует уточнения"


async def main():
    """Запуск бота"""
    await init_db()
    
    logger.info("="*50)
    logger.info("🚀 BOT STARTING...")
    logger.info(f"📋 ADMIN_ID: {ADMIN_ID}")
    logger.info("="*50)
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
