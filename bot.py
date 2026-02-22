import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from config import BOT_TOKEN, ADMIN_ID
from database import init_db, get_conversation, save_conversation, save_lead, is_lead_sent, reset_user
from ai_handler import get_ai_response

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

REQUIRED_FIELDS = ["телефон", "работы", "площадь", "бюджет", "сроки", "тип_объекта", "адрес"]


def check_fields(data: dict) -> tuple:
    filled = [f for f in REQUIRED_FIELDS if data.get(f)]
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    return filled, missing


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    
    await reset_user(user_id)
    await save_conversation(user_id, username, first_name, "[]", "{}")
    
    await message.answer(
        f"Здравствуйте, {first_name}! 👋\n\n"
        "Я помощник компании **СтройРемонтНН**.\n\n"
        "Делаем ремонты в Нижнем Новгороде:\n"
        "• Демонтаж, электрика, сантехника\n"
        "• Стены, потолки, полы\n"
        "• Под ключ и частично\n\n"
        "Расскажите, что хотите сделать? 🏠",
        parse_mode="Markdown"
    )


@dp.message(Command("test"))
async def test_handler(message: Message):
    """Тест отправки админу"""
    logger.info(f"TEST: ADMIN_ID = {ADMIN_ID}")
    try:
        await bot.send_message(int(ADMIN_ID), f"✅ Тест работает! От: {message.from_user.id}")
        await message.answer("✅ Сообщение отправлено админу!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        logger.error(f"Test failed: {e}")


@dp.message(F.text)
async def message_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    user_text = message.text
    
    # Получаем историю
    conv = await get_conversation(user_id)
    
    if conv:
        messages = json.loads(conv[0])
        collected_data = json.loads(conv[1])
    else:
        messages = []
        collected_data = {}
    
    # Сохраняем имя
    if not collected_data.get("имя") and first_name != "Клиент":
        collected_data["имя"] = first_name
    
    messages.append({"role": "user", "content": user_text})
    
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # Запрос к AI
        ai_response = await get_ai_response(messages, collected_data)
        
        reply = ai_response.get("reply", "Расскажите подробнее 🙂")
        new_data = ai_response.get("collected_data", {})
        lead_status = ai_response.get("lead_status", "под_вопросом")
        status_reason = ai_response.get("status_reason", "")
        
        # Добавляем новые данные
        if new_data:
            for key, value in new_data.items():
                if value:
                    collected_data[key] = value
                    logger.info(f"✅ Collected: {key} = {value}")
        
        messages.append({"role": "assistant", "content": reply})
        
        # Сохраняем
        await save_conversation(
            user_id, username, first_name,
            json.dumps(messages[-16:], ensure_ascii=False),
            json.dumps(collected_data, ensure_ascii=False)
        )
        
        await message.answer(reply)
        
        # Проверяем готовность
        filled, missing = check_fields(collected_data)
        logger.info(f"📊 User {user_id}: filled={len(filled)}/7, missing={missing}")
        logger.info(f"📊 Data: {collected_data}")
        
        # Отправляем если всё собрано
        if len(missing) == 0:
            already_sent = await is_lead_sent(user_id)
            logger.info(f"📊 Already sent: {already_sent}")
            
            if not already_sent:
                logger.info(f"🚀 SENDING LEAD...")
                await send_lead_to_admin(
                    user_id, username, first_name,
                    collected_data, lead_status, status_reason
                )
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await message.answer("Ошибка, попробуйте ещё раз 🙏")


async def send_lead_to_admin(user_id, username, first_name, collected_data, lead_status, status_reason):
    """Отправка заявки админу"""
    
    logger.info(f"📤 send_lead_to_admin called")
    logger.info(f"📤 ADMIN_ID = {ADMIN_ID} (type: {type(ADMIN_ID)})")
    
    status_emoji = {
        "целевой": "✅ ЦЕЛЕВОЙ",
        "под_вопросом": "⚠️ ПОД ВОПРОСОМ", 
        "нецелевой": "❌ НЕЦЕЛЕВОЙ"
    }.get(lead_status, "⚠️ ПОД ВОПРОСОМ")
    
    tg_link = f"@{username}" if username else f"tg://user?id={user_id}"
    
    lead_text = f"""
{'='*30}
📋 НОВАЯ ЗАЯВКА
{'='*30}

{status_emoji}
{status_reason or ''}

👤 Имя: {collected_data.get('имя', first_name)}
📞 Телефон: {collected_data.get('телефон', '—')}
📱 Telegram: {tg_link}

🏠 Объект: {collected_data.get('тип_объекта', '—')}
📍 Адрес: {collected_data.get('адрес', '—')}
📐 Площадь: {collected_data.get('площадь', '—')}
🔧 Работы: {collected_data.get('работы', '—')}
💰 Бюджет: {collected_data.get('бюджет', '—')}
📅 Сроки: {collected_data.get('сроки', '—')}

🆔 ID: {user_id}
{'='*30}
"""
    
    try:
        admin_id = int(ADMIN_ID)
        logger.info(f"📤 Sending to {admin_id}...")
        
        result = await bot.send_message(admin_id, lead_text)
        logger.info(f"✅ SENT! message_id = {result.message_id}")
        
        await save_lead(
            user_id,
            json.dumps(collected_data, ensure_ascii=False),
            lead_status,
            status_reason
        )
        logger.info(f"✅ Saved to DB")
        
    except Exception as e:
        logger.error(f"❌ SEND FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await init_db()
    logger.info("🤖 Bot started!")
    logger.info(f"🤖 ADMIN_ID = {ADMIN_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
