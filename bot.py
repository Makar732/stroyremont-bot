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

sent_leads = set()

def check_required_fields(data: dict) -> tuple:
    """Проверяет заполнены ли ключевые поля"""
    
    # Проверяем разные варианты написания
    has_phone = bool(data.get("телефон") or data.get("phone") or data.get("тел"))
    has_work = bool(data.get("работы") or data.get("работа") or data.get("work"))
    has_area = bool(data.get("площадь") or data.get("area") or data.get("метраж"))
    has_budget = bool(data.get("бюджет") or data.get("budget"))
    has_timing = bool(data.get("сроки") or data.get("сроки_начала") or data.get("когда") or data.get("timing"))
    has_type = bool(data.get("тип_объекта") or data.get("тип") or data.get("объект") or data.get("type"))
    has_address = bool(data.get("адрес") or data.get("address") or data.get("район"))
    
    filled = []
    missing = []
    
    checks = [
        ("телефон", has_phone),
        ("работы", has_work),
        ("площадь", has_area),
        ("бюджет", has_budget),
        ("сроки", has_timing),
        ("тип_объекта", has_type),
        ("адрес", has_address),
    ]
    
    for name, ok in checks:
        if ok:
            filled.append(name)
        else:
            missing.append(name)
    
    return filled, missing

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Клиент"
    
    await save_conversation(user_id, username, first_name, "[]", "{}")
    
    if user_id in sent_leads:
        sent_leads.remove(user_id)
    
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
        
        reply = ai_response.get("reply", "Ошибка.")
        new_data = ai_response.get("collected_data", {})
        lead_status = ai_response.get("lead_status", "под_вопросом")
        status_reason = ai_response.get("status_reason", "")
        
        # Логируем что пришло от AI
        logger.info(f"AI returned new_data: {new_data}")
        
        # Обновляем данные
        if new_data:
            for key, value in new_data.items():
                if value and value not in ["...", "", "неизвестно", None, "не указано"]:
                    collected_data[key] = value
                    logger.info(f"Saved: {key} = {value}")
        
        messages.append({"role": "assistant", "content": reply})
        
        await save_conversation(
            user_id, username, first_name, 
            json.dumps(messages[-16:], ensure_ascii=False), 
            json.dumps(collected_data, ensure_ascii=False)
        )
        
        await message.answer(reply)
        
        # Проверяем поля
        filled, missing = check_required_fields(collected_data)
        
        logger.info(f"=== User {user_id} ===")
        logger.info(f"Collected data: {collected_data}")
        logger.info(f"Filled: {filled}")
        logger.info(f"Missing: {missing}")
        logger.info(f"Already sent: {user_id in sent_leads}")
        
        # Отправляем когда ВСЕ собрано
        if len(missing) == 0 and user_id not in sent_leads:
            logger.info(f">>> SENDING LEAD for {user_id}")
            await send_lead_to_admin(
                user_id, username, first_name, 
                collected_data, lead_status, status_reason
            )
            sent_leads.add(user_id)
        elif len(missing) > 0:
            logger.info(f"Not sending yet, missing: {missing}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await message.answer("Что-то пошло не так, попробуйте ещё раз 🙏")

async def send_lead_to_admin(user_id, username, first_name, collected_data, lead_status, status_reason):
    
    status_emoji = {
        "целевой": "✅ ЦЕЛЕВОЙ",
        "под_вопросом": "⚠️ ПОД ВОПРОСОМ",
        "нецелевой": "❌ НЕЦЕЛЕВОЙ"
    }.get(lead_status, "⚠️ ПОД ВОПРОСОМ")
    
    # Достаём данные с учётом разных ключей
    phone = collected_data.get('телефон') or collected_data.get('phone') or 'не указан'
    work = collected_data.get('работы') or collected_data.get('работа') or '—'
    obj_type = collected_data.get('тип_объекта') or collected_data.get('тип') or collected_data.get('объект') or '—'
    area = collected_data.get('площадь') or collected_data.get('метраж') or '—'
    address = collected_data.get('адрес') or collected_data.get('район') or '—'
    budget = collected_data.get('бюджет') or '—'
    timing = collected_data.get('сроки') or collected_data.get('сроки_начала') or collected_data.get('когда') or '—'
    
    tg_contact = f"@{username}" if username else "нет"
    
    lead_text = f"""
{'='*30}
📋 НОВАЯ ЗАЯВКА
{'='*30}

{status_emoji}
💬 {status_reason if status_reason else 'Автооценка'}

👤 Имя: {collected_data.get('имя', first_name)}
📞 Телефон: {phone}
📱 Telegram: {tg_contact}
🆔 ID: {user_id}

🏠 Объект: {obj_type}
📍 Адрес: {address}
📐 Площадь: {area}
🔧 Работы: {work}
💰 Бюджет: {budget}
📅 Сроки: {timing}
{'='*30}
"""
    
    try:
        await bot.send_message(ADMIN_ID, lead_text)
        await save_lead(user_id, json.dumps(collected_data, ensure_ascii=False), lead_status, status_reason)
        logger.info(f"✅ LEAD SENT to {ADMIN_ID}")
    except Exception as e:
        logger.error(f"❌ Failed to send lead: {e}")

async def main():
    await init_db()
    logger.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
