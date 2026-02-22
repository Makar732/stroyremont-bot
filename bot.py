import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, get_conversation, save_conversation, save_lead
from ai_handler import get_ai_response

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: Message):
    """Обработка команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    
    # Инициализируем новый диалог
    welcome_messages = [{"role": "assistant", "content": f"Здравствуйте! 👋 Я виртуальный помощник компании СтройРемонтНН. Подскажу по нашим услугам и помогу оставить заявку. Чем могу помочь?"}]
    
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
    """Обработка всех текстовых сообщений"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    user_text = message.text
    
    # Получаем историю диалога
    conv = await get_conversation(user_id)
    
    if conv:
        messages = json.loads(conv[0])
        collected_data = json.loads(conv[1])
    else:
        messages = []
        collected_data = {}
    
    # Добавляем сообщение пользователя
    messages.append({"role": "user", "content": user_text})
    
    # Показываем что бот печатает
    await bot.send_chat_action(message.chat.id, "typing")
    
    # Получаем ответ от AI
    try:
        ai_response = await get_ai_response(messages, collected_data)
        
        reply = ai_response.get("reply", "Извините, произошла ошибка. Попробуйте ещё раз.")
        new_data = ai_response.get("collected_data", {})
        ready_for_lead = ai_response.get("ready_for_lead", False)
        lead_score = ai_response.get("lead_score")
        score_reason = ai_response.get("score_reason")
        
        # Обновляем собранные данные
        for key, value in new_data.items():
            if value and value not in ["...", "", None, "неизвестно"]:
                collected_data[key] = value
        
        # Добавляем ответ бота в историю
        messages.append({"role": "assistant", "content": reply})
        
        # Сохраняем диалог (храним последние 20 сообщений)
        await save_conversation(
            user_id, 
            username, 
            first_name, 
            json.dumps(messages[-20:], ensure_ascii=False), 
            json.dumps(collected_data, ensure_ascii=False)
        )
        
        # Отправляем ответ клиенту
        await message.answer(reply)
        
        # Если готовы отправлять лид
        if ready_for_lead and collected_data.get("телефон"):
            await send_lead_to_admin(
                user_id=user_id,
                username=username,
                first_name=first_name,
                collected_data=collected_data,
                lead_score=lead_score,
                score_reason=score_reason,
                messages=messages
            )
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.answer("Произошла техническая ошибка. Попробуйте написать ещё раз.")

async def send_lead_to_admin(user_id: int, username: str, first_name: str, 
                              collected_data: dict, lead_score: str, 
                              score_reason: str, messages: list):
    """Отправляем заявку админу"""
    
    # Определяем эмодзи для оценки
    score_emoji = {
        "горячий": "🔥🔥🔥 ГОРЯЧИЙ",
        "тёплый": "🟡 ТЁПЛЫЙ", 
        "теплый": "🟡 ТЁПЛЫЙ",
        "холодный": "🟢 ХОЛОДНЫЙ"
    }.get(lead_score.lower() if lead_score else "", "⚪ НЕ ОЦЕНЁН")
    
    # Формируем красивое сообщение
    lead_text = f"""
{'='*30}
📋 **НОВАЯ ЗАЯВКА**
{'='*30}

**Оценка: {score_emoji}**
📝 Причина: {score_reason or 'не указана'}

👤 **Клиент:**
• Имя: {collected_data.get('имя', first_name)}
• Username: @{username if username else 'нет'}
• Telegram ID: `{user_id}`

📞 **Контакт:**
• Телефон: {collected_data.get('телефон', '❌ не указан')}

🏠 **Объект:**
• Тип: {collected_data.get('тип_объекта', 'не указан')}
• Площадь: {collected_data.get('площадь', 'не указана')}
• Адрес: {collected_data.get('адрес', 'не указан')}

🔧 **Работы:**
{collected_data.get('работы', 'не указаны')}

📐 **Чертежи/проект:** {collected_data.get('чертежи', 'не указано')}

💰 **Бюджет:** {collected_data.get('бюджет', 'не указан')}

📅 **Сроки начала:** {collected_data.get('сроки_начала', 'не указаны')}

{'='*30}
"""
    
    try:
        await bot.send_message(ADMIN_ID, lead_text, parse_mode="Markdown")
        
        # Сохраняем лид в базу
        await save_lead(
            user_id=user_id,
            data=json.dumps(collected_data, ensure_ascii=False),
            score=lead_score or "не оценён",
            score_reason=score_reason or ""
        )
        
        logger.info(f"Lead sent to admin: {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send lead to admin: {e}")

async def main():
    """Запуск бота"""
    await init_db()
    logger.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
