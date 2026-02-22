import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, get_conversation, save_conversation, save_lead
from ai_handler import get_ai_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    
    welcome_messages = []
    await save_conversation(user_id, username, first_name, json.dumps(welcome_messages), "{}")
    
    await message.answer(
        f"Здравствуйте, {first_name}! 👋\n\n"
        "Я виртуальный помощник компании **СтройРемонтНН**.\n\n"
        "Подскажу по нашим услугам:\n"
        "🔧 Демонтаж\n"
        "⚡ Электромонтаж\n"
        "🚿 Сантехника\n"
        "🧱 Перегородки и потолки\n"
        "🔲 Плиточные работы\n"
        "🎨 Декоративная отделка\n\n"
        "Расскажите, что вас интересует?",
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
    
    messages.append({"role": "user", "content": user_text})
    
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        ai_response = await get_ai_response(messages, collected_data)
        
        reply = ai_response.get("reply", "Извините, произошла ошибка.")
        new_data = ai_response.get("collected_data", {})
        ready_for_lead = ai_response.get("ready_for_lead", False)
        lead_score = ai_response.get("lead_score")
        score_reason = ai_response.get("score_reason")
        
        # Обновляем собранные данные
        if new_data:
            for key, value in new_data.items():
                if value and value not in ["...", "", "неизвестно", None]:
                    collected_data[key] = value
        
        logger.info(f"User {user_id}: ready_for_lead={ready_for_lead}, collected_data={collected_data}")
        
        messages.append({"role": "assistant", "content": reply})
        
        await save_conversation(
            user_id, username, first_name, 
            json.dumps(messages[-20:], ensure_ascii=False), 
            json.dumps(collected_data, ensure_ascii=False)
        )
        
        # Отправляем ТОЛЬКО reply клиенту
        await message.answer(reply)
        
        # Проверяем нужно ли отправлять лид
        has_phone = collected_data.get("телефон") or collected_data.get("phone")
        
        logger.info(f"Checking lead: ready={ready_for_lead}, has_phone={has_phone}")
        
        if ready_for_lead and has_phone:
            logger.info(f"Sending lead to admin for user {user_id}")
            await send_lead_to_admin(user_id, username, first_name, collected_data, lead_score, score_reason)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("Произошла ошибка. Попробуйте ещё раз.")

async def send_lead_to_admin(user_id, username, first_name, collected_data, lead_score, score_reason):
    score_emoji = {
        "горячий": "🔥🔥🔥 ГОРЯЧИЙ",
        "тёплый": "🟡 ТЁПЛЫЙ", 
        "теплый": "🟡 ТЁПЛЫЙ",
        "холодный": "🟢 ХОЛОДНЫЙ"
    }.get((lead_score or "").lower(), "⚪ НЕ ОЦЕНЁН")
    
    lead_text = f"""
{'='*30}
📋 НОВАЯ ЗАЯВКА
{'='*30}

Оценка: {score_emoji}
Причина: {score_reason or 'не указана'}

👤 Клиент:
• Имя: {collected_data.get('имя', first_name)}
• Username: @{username if username else 'нет'}
• Telegram ID: {user_id}

📞 Телефон: {collected_data.get('телефон', '❌ не указан')}

🏠 Объект:
• Тип: {collected_data.get('тип_объекта', 'не указан')}
• Площадь: {collected_data.get('площадь', 'не указана')} кв.м
• Адрес: {collected_data.get('адрес', 'не указан')}

🔧 Работы: {collected_data.get('работы', 'не указаны')}

📐 Чертежи: {collected_data.get('чертежи', 'не указано')}
💰 Бюджет: {collected_data.get('бюджет', 'не указан')}
📅 Сроки: {collected_data.get('сроки_начала', 'не указаны')}
{'='*30}
"""
    
    try:
        await bot.send_message(ADMIN_ID, lead_text)
        await save_lead(user_id, json.dumps(collected_data, ensure_ascii=False), lead_score or "", score_reason or "")
        logger.info(f"Lead sent successfully to {ADMIN_ID}")
    except Exception as e:
        logger.error(f"Failed to send lead: {e}")

async def main():
    await init_db()
    logger.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
