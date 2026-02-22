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

# Храним отправленные лиды чтобы не дублировать
sent_leads = set()

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    
    await save_conversation(user_id, username, first_name, "[]", "{}")
    
    # Убираем из отправленных при новом старте
    if user_id in sent_leads:
        sent_leads.remove(user_id)
    
    await message.answer(
        f"Здравствуйте, {first_name}! 👋\n\n"
        "Я помощник компании **СтройРемонтНН**.\n\n"
        "Наши услуги:\n"
        "🔧 Демонтаж\n"
        "⚡ Электромонтаж\n"
        "🚿 Сантехника\n"
        "🧱 Перегородки и потолки\n"
        "🔲 Плиточные работы\n"
        "🎨 Декоративная отделка\n\n"
        "Какие работы вас интересуют?",
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
        
        reply = ai_response.get("reply", "Ошибка.")
        new_data = ai_response.get("collected_data", {})
        ready_for_lead = ai_response.get("ready_for_lead", False)
        lead_status = ai_response.get("lead_status", "none")
        status_reason = ai_response.get("status_reason", "")
        
        # Обновляем данные
        if new_data:
            for key, value in new_data.items():
                if value and value not in ["...", "", "неизвестно", None]:
                    collected_data[key] = value
        
        messages.append({"role": "assistant", "content": reply})
        
        # Сохраняем (последние 10 сообщений)
        await save_conversation(
            user_id, username, first_name, 
            json.dumps(messages[-10:], ensure_ascii=False), 
            json.dumps(collected_data, ensure_ascii=False)
        )
        
        await message.answer(reply)
        
        # Отправляем лид если готов и ещё не отправляли
        has_contact = collected_data.get("телефон") or username
        
        if ready_for_lead and has_contact and user_id not in sent_leads:
            await send_lead_to_admin(
                user_id, username, first_name, 
                collected_data, lead_status, status_reason
            )
            sent_leads.add(user_id)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("Ошибка. Попробуйте снова.")

async def send_lead_to_admin(user_id, username, first_name, collected_data, lead_status, status_reason):
    
    status_emoji = {
        "целевой": "✅ ЦЕЛЕВОЙ",
        "под_вопросом": "⚠️ ПОД ВОПРОСОМ",
        "нецелевой": "❌ НЕЦЕЛЕВОЙ"
    }.get(lead_status, "❓ НЕ ОПРЕДЕЛЁН")
    
    phone = collected_data.get('телефон', 'не указан')
    contact_info = f"📞 {phone}" if phone != 'не указан' else f"📱 @{username}" if username else "❌ Нет контакта"
    
    lead_text = f"""
{'='*30}
📋 ЗАЯВКА
{'='*30}

{status_emoji}
💬 {status_reason}

👤 {collected_data.get('имя', first_name)}
{contact_info}
🆔 {user_id}

🏠 Объект: {collected_data.get('тип_объекта', '—')}
📐 Площадь: {collected_data.get('площадь', '—')}
🔧 Работы: {collected_data.get('работы', '—')}
💰 Бюджет: {collected_data.get('бюджет', '—')}
📅 Сроки: {collected_data.get('сроки', '—')}
{'='*30}
"""
    
    try:
        await bot.send_message(ADMIN_ID, lead_text)
        await save_lead(user_id, json.dumps(collected_data, ensure_ascii=False), lead_status, status_reason)
        logger.info(f"Lead sent: {user_id} [{lead_status}]")
    except Exception as e:
        logger.error(f"Failed to send lead: {e}")

async def main():
    await init_db()
    logger.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
