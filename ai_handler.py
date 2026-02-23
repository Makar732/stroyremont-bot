import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO, REQUIRED_FIELDS, FIELD_QUESTIONS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты менеджер СтройРемонтНН (Нижний Новгород). Ремонт любой сложности.

{COMPANY_INFO}

ПРАВИЛА:
- Короткие ответы (1-2 предложения)
- Дружелюбно, 1-2 эмодзи
- Один вопрос за раз
- Не повторяй сказанное клиентом
- Отвечай на вопросы о ценах по прайсу выше
"""


async def call_ai(messages: list, temperature: float = 0.7, max_tokens: int = 100) -> str | None:
    """Вызов OpenRouter API"""
    
    if not OPENROUTER_API_KEY or len(OPENROUTER_API_KEY) < 20:
        logger.error("❌ Invalid API key")
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status != 200:
                    logger.error(f"❌ API {response.status}")
                    return None
                
                result = await response.json()
                
                if "choices" not in result or not result["choices"]:
                    return None
                
                reply = result["choices"][0]["message"]["content"].strip()
                logger.info(f"✅ AI: {reply[:50]}...")
                return reply
                
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return None


def extract_field_from_text(text: str, field: str) -> str | None:
    """Извлекает конкретное поле из текста"""
    
    text_lower = text.lower().strip()
    original = text.strip()
    
    if field == "object_type":
        if "квартир" in text_lower:
            return "Квартира"
        elif "дом" in text_lower or "коттедж" in text_lower or "частн" in text_lower:
            return "Дом"
        elif "офис" in text_lower or "магазин" in text_lower or "коммерч" in text_lower:
            return "Коммерция"
        # Если просто ответ на вопрос
        if text_lower in ["квартира", "дом", "коммерция", "офис"]:
            return original.capitalize()
    
    elif field == "area":
        # Ищем число с м2
        match = re.search(r'(\d+)\s*(м²|м2|кв\.?\s*м\.?|метр|квадрат)?', text_lower)
        if match:
            return f"{match.group(1)} м²"
    
    elif field == "budget":
        # Любое упоминание денег
        if re.search(r'\d+\s*(тыс|т\.?р|руб|млн|миллион|\d{5,})', text_lower) or re.search(r'\d+', text_lower):
            return original
    
    elif field == "timing":
        # Любое упоминание времени
        timing_words = ['сейчас', 'срочно', 'недел', 'месяц', 'скоро', 'весн', 'лет', 'осен', 'зим', 
                       'январ', 'феврал', 'март', 'апрел', 'май', 'июн', 'июл', 'август', 
                       'сентябр', 'октябр', 'ноябр', 'декабр', 'через', 'готов', 'можно']
        if any(word in text_lower for word in timing_words) or re.search(r'\d', text_lower):
            return original
    
    elif field == "address":
        # Любой адрес или район
        address_words = ['район', 'улица', 'ул\.', 'проспект', 'пр\.', 'автозавод', 'сормов', 
                        'канавин', 'нижегородск', 'ленинск', 'советск', 'московск', 'приокск', 
                        'центр', 'мещер', 'печер', 'кузнечих', 'бурнаков']
        if any(word in text_lower for word in address_words):
            return original
        # Если это просто ответ на вопрос об адресе - принимаем любой текст
        if len(original) > 2:
            return original
    
    elif field == "work":
        # Любое описание работ
        work_words = ['ремонт', 'плитк', 'электр', 'сантехник', 'штукатур', 'потолок', 
                     'стен', 'пол', 'демонтаж', 'отделк', 'покраск', 'обои', 'ламинат', 
                     'стяжк', 'ванн', 'кухн', 'комнат', 'туалет', 'санузел', 'под ключ']
        if any(word in text_lower for word in work_words):
            return original
        # Если это первый ответ - принимаем как описание работ
        if len(original) > 3:
            return original
    
    return None


def get_next_missing_field(collected: dict) -> str | None:
    """Возвращает следующее незаполненное поле"""
    for field in REQUIRED_FIELDS:
        if not collected.get(field):
            return field
    return None


def is_all_collected(collected: dict) -> bool:
    """Проверяет, все ли поля собраны"""
    for field in REQUIRED_FIELDS:
        if not collected.get(field):
            return False
    return True


async def generate_reply(dialog_history: list, collected_data: dict, current_field: str | None) -> tuple[str, dict, str | None, bool]:
    """
    Генерирует ответ
    
    Returns:
        reply: текст ответа
        updated_data: обновлённые данные
        next_field: следующее поле для заполнения
        all_collected: все ли данные собраны
    """
    
    updated_data = collected_data.copy()
    
    # Если есть текущее поле и последнее сообщение от пользователя - пробуем извлечь данные
    if current_field and dialog_history:
        last_user_msg = None
        for msg in reversed(dialog_history):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
        
        if last_user_msg:
            extracted = extract_field_from_text(last_user_msg, current_field)
            if extracted:
                updated_data[current_field] = extracted
                logger.info(f"✅ Extracted {current_field}: {extracted}")
    
    # Определяем следующее поле
    next_field = get_next_missing_field(updated_data)
    all_collected = next_field is None
    
    logger.info(f"📊 Data: {updated_data}")
    logger.info(f"📋 Next field: {next_field}")
    logger.info(f"✅ All collected: {all_collected}")
    
    # Генерируем ответ
    if all_collected:
        # Все данные собраны - не генерируем ответ, это сделает bot.py
        return "", updated_data, None, True
    
    # Нужно задать вопрос
    # Сначала пробуем через AI
    if dialog_history:
        recent = dialog_history[-4:] if len(dialog_history) > 4 else dialog_history
        
        context = f"Уже известно: {json.dumps(updated_data, ensure_ascii=False)}" if updated_data else ""
        task = f"Кратко отреагируй на ответ клиента и спроси: {FIELD_QUESTIONS[next_field]}"
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\n\n{context}\n\nЗАДАЧА: {task}"}]
        messages.extend([{"role": m["role"], "content": m["content"]} for m in recent])
        
        reply = await call_ai(messages, max_tokens=80)
        
        if reply:
            return reply, updated_data, next_field, False
    
    # Fallback
    return FIELD_QUESTIONS[next_field], updated_data, next_field, False


async def check_phone_number(text: str) -> bool:
    """Проверяет наличие телефона"""
    clean = re.sub(r'[\s\-\(\)\+]', '', text)
    return bool(re.search(r'\d{10,11}', clean))


async def generate_farewell(client_name: str) -> str:
    """Генерирует прощание"""
    
    reply = await call_ai([
        {"role": "system", "content": "Коротко поблагодари за заявку (1-2 предложения). Скажи что мастер скоро свяжется."},
        {"role": "user", "content": f"Клиент: {client_name}"}
    ], max_tokens=50)
    
    return reply or f"Спасибо, {client_name}! ✅ Мастер свяжется с вами в ближайшее время!"


async def generate_questions_response(question: str) -> str:
    """Отвечает на вопросы клиента"""
    
    reply = await call_ai([
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nОтветь на вопрос клиента о ценах/услугах. Кратко, по делу."},
        {"role": "user", "content": question}
    ], max_tokens=100)
    
    return reply or "Точную стоимость мастер рассчитает после осмотра объекта."
