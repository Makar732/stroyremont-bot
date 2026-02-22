import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, get_conversation, save_conversation, save_lead, is_lead_sent, reset_user
from ai_handler import get_ai_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Убрали sent_leads = set() — теперь проверяем через БД!

REQUIRED_FIELDS = ["телефон", "работы", "площадь", "бюджет", "сроки", "тип_объекта", "адрес"]

def check_required_fields(data: dict) -> tuple:
    """Проверяет заполнены ли ключевые поля"""
    filled = [f for f in REQUIRED_FIELDS if data.get(f)]
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    return filled, missing


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    
    # Сбрасываем пользователя при /start
    await reset_user(user_id)
    await save_conversation(user_id, username, first_name, "[]", "{}")
    
    await message.answer(
        f"Здравствуйте, {first_name}! 👋\n\n"
        "Я помощник компании **СтройРемонтНН**.\n\n"
        "Делаем комплексные ремонты в Нижнем Новгороде:\n"
        "• Демонтаж, электрика, сантехника\n"
        "• Перегородки, потолки, плитка\n"
        "• Декоративная отделка\n\n"
        "Расскажите, что хотите сделать? 🏠",
        parse_mode="Markdown"
    )


@dp.message(F.text)
async def message_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    user_text = message.text
    
    conv = await get_conversation(user_id)
    
    if conv:
        messages = json.loads(conv[0])
        collected_data = json.loads(conv[1])
    else:
        messages = []
        collected_data = {}
    
    if not collected_data.get("имя") and first_name != "Клиент":
        collected_data["имя"] = first_name
    
    messages.append({"role": "user", "content": user_text})
    
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        ai_response = await get_ai_response(messages, collected_data)
        
        reply = ai_response.get("reply", "Расскажите подробнее 🙂")
        new_data = ai_response.get("collected_data", {})
        lead_status = ai_response.get("lead_status", "под_вопросом")
        status_reason = ai_response.get("status_reason", "")
        
        logger.info(f"AI new_data: {new_data}")
        
        # Обновляем данные
        if new_data:
            collected_data.update(new_data)
        
        messages.append({"role": "assistant", "content": reply})
        
        await save_conversation(
            user_id, username, first_name, 
            json.dumps(messages[-16:], ensure_ascii=False), 
            json.dumps(collected_data, ensure_ascii=False)
        )
        
        await message.answer(reply)
        
        # Проверяем поля
        filled, missing = check_required_fields(collected_data)
        
        logger.info(f"User {user_id}: filled={filled}, missing={missing}")
        
        # Проверяем через БД, а не через set()
        already_sent = await is_lead_sent(user_id)
        
        if len(missing) == 0 and not already_sent:
            logger.info(f">>> SENDING LEAD for {user_id}")
            await send_lead_to_admin(
                user_id, username, first_name, 
                collected_data, lead_status, status_reason
            )
        elif len(missing) > 0:
            logger.info(f"Missing: {missing}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await message.answer("Что-то пошло не так, попробуйте ещё раз 🙏")


async def send_lead_to_admin(user_id, username, first_name, collected_data, lead_status, status_reason):
    
    status_emoji = {
        "целевой": "✅ ЦЕЛЕВОЙ",
        "под_вопросом": "⚠️ ПОД ВОПРОСОМ",
        "нецелевой": "❌ НЕЦЕЛЕВОЙ"
    }.get(lead_status, "⚠️ ПОД ВОПРОСОМ")
    
    tg_contact = f"@{username}" if username else "нет"
    
    lead_text = f"""
{'='*30}
📋 НОВАЯ ЗАЯВКА
{'='*30}

{status_emoji}
💬 {status_reason or 'Автооценка'}

👤 Имя: {collected_data.get('имя', first_name)}
📞 Телефон: {collected_data.get('телефон', 'не указан')}
📱 Telegram: {tg_contact}
🆔 ID: {user_id}

🏠 Объект: {collected_data.get('тип_объекта', '—')}
📍 Адрес: {collected_data.get('адрес', '—')}
📐 Площадь: {collected_data.get('площадь', '—')}
🔧 Работы: {collected_data.get('работы', '—')}
💰 Бюджет: {collected_data.get('бюджет', '—')}
📅 Сроки: {collected_data.get('сроки', '—')}
{'='*30}
"""
    
    try:
        await bot.send_message(ADMIN_ID, lead_text)
        await save_lead(user_id, json.dumps(collected_data, ensure_ascii=False), lead_status, status_reason)
        logger.info(f"✅ LEAD SENT to admin")
    except Exception as e:
        logger.error(f"❌ Failed to send lead: {e}")


async def main():
    await init_db()
    logger.info("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
