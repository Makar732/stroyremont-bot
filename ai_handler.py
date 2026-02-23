import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO, REQUIRED_FIELDS

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


async def check_api_status() -> dict:
    """Проверяет статус OpenRouter API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return {"status": "ok", "data": await response.json()}
                return {"status": "error", "code": response.status}
    except Exception as e:
        return {"status": "exception", "error": str(e)}


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
                    error_text = await response.text()
                    logger.error(f"❌ API {response.status}: {error_text[:200]}")
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


def extract_data_from_message(text: str, existing: dict) -> dict:
    """Извлекает данные из ОДНОГО сообщения"""
    
    data = existing.copy()
    text_lower = text.lower()
    original_text = text.strip()
    
    # Тип объекта
    if not data.get("object_type"):
        if "квартир" in text_lower:
            data["object_type"] = "квартира"
        elif "дом" in text_lower or "коттедж" in text_lower or "частн" in text_lower:
            data["object_type"] = "дом"
        elif "офис" in text_lower or "магазин" in text_lower or "коммерч" in text_lower:
            data["object_type"] = "коммерция"
    
    # Площадь - ищем число с м2/метров/квадратов
    if not data.get("area"):
        area_patterns = [
            r'(\d+)\s*(м²|м2|кв\.?\s*м\.?|метр|квадрат)',
            r'(\d+)\s*квадрат',
            r'площад\w*\s*(\d+)',
            r'(\d+)\s*м\b',
        ]
        for pattern in area_patterns:
            match = re.search(pattern, text_lower)
            if match:
                num = match.group(1) if match.group(1).isdigit() else match.group(2) if len(match.groups()) > 1 else None
                if num:
                    data["area"] = f"{num} м²"
                    break
    
    # Бюджет
    if not data.get("budget"):
        # Проверяем различные форматы бюджета
        budget_found = False
        
        # 100 тыс, 100тыс, 100 т.р.
        match = re.search(r'(\d+)\s*(тыс|т\.?\s*р)', text_lower)
        if match:
            data["budget"] = original_text
            budget_found = True
        
        # 1 млн, 1млн, 1 миллион
        if not budget_found:
            match = re.search(r'(\d+)\s*(млн|миллион)', text_lower)
            if match:
                data["budget"] = original_text
                budget_found = True
        
        # 100000, 1000000 (большие числа)
        if not budget_found:
            match = re.search(r'\b(\d{5,})\b', text_lower)
            if match:
                data["budget"] = original_text
                budget_found = True
        
        # "бюджет 100"
        if not budget_found:
            match = re.search(r'бюджет\w*\s*[\:\-]?\s*(\d+)', text_lower)
            if match:
                data["budget"] = original_text
    
    # Сроки
    if not data.get("timing"):
        timing_words = [
            'сейчас', 'срочно', 'неделю', 'недели', 'месяц', 'месяца', 
            'скоро', 'быстр', 'весн', 'лет', 'осен', 'зим',
            'январ', 'феврал', 'март', 'апрел', 'мая', 'май', 'июн', 
            'июл', 'август', 'сентябр', 'октябр', 'ноябр', 'декабр',
            'через', 'начать', 'старт', 'приступ', 'готов'
        ]
        if any(word in text_lower for word in timing_words):
            data["timing"] = original_text
    
    # Адрес/район
    if not data.get("address"):
        address_words = [
            'район', 'улица', 'ул.', 'проспект', 'пр.', 'переулок',
            'автозавод', 'сормов', 'канавин', 'нижегородск', 'ленинск', 
            'советск', 'московск', 'приокск', 'центр', 'мещер', 
            'верхние печёры', 'печер', 'кузнечих', 'бурнаков', 'карповк'
        ]
        if any(word in text_lower for word in address_words):
            data["address"] = original_text
    
    # Работы
    if not data.get("work"):
        work_words = [
            'ремонт', 'плитк', 'электр', 'сантехник', 'штукатур', 
            'потолок', 'потолки', 'стен', 'стены', 'пол', 'полы',
            'демонтаж', 'отделк', 'покраск', 'обои', 'ламинат', 
            'стяжк', 'ванн', 'кухн', 'комнат', 'туалет', 'санузел',
            'косметич', 'капитальн', 'под ключ', 'евроремонт'
        ]
        if any(word in text_lower for word in work_words):
            data["work"] = original_text
    
    return data


def extract_all_data(dialog_history: list, existing: dict) -> dict:
    """Извлекает данные из ВСЕЙ истории диалога"""
    
    data = existing.copy()
    
    for msg in dialog_history:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            data = extract_data_from_message(content, data)
    
    return data


def get_missing_fields(collected: dict) -> list:
    """Возвращает список недостающих полей в правильном порядке"""
    
    # Порядок вопросов
    order = ["work", "object_type", "area", "address", "timing", "budget"]
    
    missing = []
    for field in order:
        if field in REQUIRED_FIELDS and not collected.get(field):
            missing.append(field)
    
    return missing


async def generate_reply(dialog_history: list, collected_data: dict) -> tuple[str, dict, bool]:
    """Генерирует ответ"""
    
    # Извлекаем данные из ВСЕЙ истории
    updated_data = extract_all_data(dialog_history, collected_data)
    
    # Получаем недостающие поля
    missing = get_missing_fields(updated_data)
    
    # Проверяем готовность - ВСЕ поля должны быть заполнены
    ready_for_lead = len(missing) == 0
    
    logger.info(f"📊 Collected: {updated_data}")
    logger.info(f"📋 Missing: {missing}")
    logger.info(f"✅ Ready: {ready_for_lead}")
    
    # Формируем задачу для AI
    if ready_for_lead:
        task = "Вся информация собрана! Поблагодари и спроси, есть ли вопросы по ценам или услугам."
    else:
        next_field = missing[0]
        hints = {
            "work": "Спроси какие работы нужны (ремонт, плитка, электрика и т.д.)",
            "object_type": "Спроси тип объекта: квартира, дом или коммерция?",
            "area": "Спроси примерную площадь в метрах",
            "address": "Спроси в каком районе находится объект",
            "timing": "Спроси когда планируют начать работы",
            "budget": "Спроси примерный бюджет на работы"
        }
        task = hints.get(next_field, "Продолжи разговор")
    
    # Контекст собранных данных
    context = ""
    if updated_data:
        context = f"\n\nУже известно: {json.dumps(updated_data, ensure_ascii=False)}"
        context += f"\nОсталось узнать: {', '.join(missing)}" if missing else "\nВсё собрано!"
    
    # Берём последние сообщения для AI
    recent = dialog_history[-6:] if len(dialog_history) > 6 else dialog_history
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT + context + f"\n\nТВОЯ ЗАДАЧА: {task}"}]
    messages.extend([{"role": m["role"], "content": m["content"]} for m in recent])
    
    # Вызываем AI
    reply = await call_ai(messages, max_tokens=80)
    
    # Fallback если AI не ответил
    if not reply:
        if ready_for_lead:
            reply = "Отлично, всё записал! 📝 Есть вопросы по ценам или услугам?"
        else:
            fallbacks = {
                "work": "Расскажите, какие работы вас интересуют? 🔨",
                "object_type": "Это квартира, дом или коммерческое помещение? 🏠",
                "area": "Какая примерно площадь объекта в метрах? 📐",
                "address": "В каком районе находится объект? 📍",
                "timing": "Когда планируете начать работы? 📅",
                "budget": "Какой примерный бюджет закладываете? 💰"
            }
            reply = fallbacks.get(missing[0], "Расскажите подробнее?")
    
    return reply, updated_data, ready_for_lead


async def check_phone_number(text: str) -> bool:
    """Проверяет наличие телефона"""
    clean = re.sub(r'[\s\-\(\)\+]', '', text)
    # Ищем 10-11 цифр
    return bool(re.search(r'\d{10,11}', clean))


async def generate_farewell(client_name: str) -> str:
    """Генерирует прощание"""
    
    reply = await call_ai([
        {"role": "system", "content": "Коротко поблагодари за заявку (1-2 предложения). Скажи что мастер свяжется."},
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
