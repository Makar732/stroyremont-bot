import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO, REQUIRED_FIELDS

logger = logging.getLogger(__name__)

# Короткий системный промпт (экономия токенов)
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
    """Вызов OpenRouter API (оптимизированный)"""
    
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


def extract_data_simple(text: str, existing: dict) -> dict:
    """Простое извлечение данных БЕЗ AI (экономия токенов)"""
    
    data = existing.copy()
    text_lower = text.lower()
    
    # Тип объекта
    if not data.get("object_type"):
        if "квартир" in text_lower:
            data["object_type"] = "квартира"
        elif "дом" in text_lower or "коттедж" in text_lower:
            data["object_type"] = "дом"
        elif "офис" in text_lower or "магазин" in text_lower or "коммерч" in text_lower:
            data["object_type"] = "коммерция"
    
    # Площадь
    if not data.get("area"):
        area_match = re.search(r'(\d+)\s*(м²|м2|кв\.?м?|метр|квадрат)', text_lower)
        if area_match:
            data["area"] = f"{area_match.group(1)} м²"
    
    # Бюджет
    if not data.get("budget"):
        budget_patterns = [
            r'(\d+)\s*(тыс|т\.р|тр)',
            r'(\d+)\s*(млн|миллион)',
            r'(\d{6,})',
            r'бюджет[:\s]*(\d+)',
        ]
        for pattern in budget_patterns:
            match = re.search(pattern, text_lower)
            if match:
                data["budget"] = text
                break
    
    # Сроки
    if not data.get("timing"):
        timing_words = ['сейчас', 'срочно', 'неделю', 'месяц', 'скоро', 'весн', 'лет', 'осен', 'зим', 'январ', 'феврал', 'март', 'апрел', 'май', 'июн', 'июл', 'август', 'сентябр', 'октябр', 'ноябр', 'декабр']
        if any(word in text_lower for word in timing_words):
            data["timing"] = text
    
    # Адрес/район
    if not data.get("address"):
        address_words = ['район', 'улица', 'ул.', 'проспект', 'пр.', 'автозавод', 'сормово', 'канавино', 'нижегородск', 'ленинск', 'советск', 'московск', 'приокск', 'центр']
        if any(word in text_lower for word in address_words):
            data["address"] = text
    
    # Работы
    if not data.get("work"):
        work_words = ['ремонт', 'плитк', 'электр', 'сантехник', 'штукатур', 'потолок', 'стен', 'пол', 'демонтаж', 'отделк', 'покраск', 'обои', 'ламинат', 'стяжк', 'ванн', 'кухн', 'комнат', 'туалет', 'санузел']
        if any(word in text_lower for word in work_words):
            data["work"] = text
    
    return data


def get_missing_fields(collected: dict) -> list:
    """Возвращает список недостающих полей"""
    return [f for f in REQUIRED_FIELDS if not collected.get(f)]


async def generate_reply(dialog_history: list, collected_data: dict) -> tuple[str, dict, bool]:
    """Генерирует ответ (оптимизированная версия)"""
    
    # Извлекаем данные из ВСЕХ сообщений пользователя
    updated_data = collected_data.copy()
    for msg in dialog_history:
        if msg.get("role") == "user":
            updated_data = extract_data_simple(msg.get("content", ""), updated_data)
    
    missing = get_missing_fields(updated_data)
    ready_for_lead = len(missing) == 0
    
    logger.info(f"📊 Collected: {updated_data}, Missing: {missing}")
    
    # Формируем подсказку для AI
    if ready_for_lead:
        task = "Вся информация собрана. Спроси, есть ли вопросы по ценам или услугам, прежде чем передать заявку мастеру."
    else:
        hints = {
            "work": "Спроси какие работы нужны",
            "object_type": "Спроси: квартира, дом или коммерция?",
            "area": "Спроси примерную площадь",
            "address": "Спроси район или адрес объекта",
            "timing": "Спроси когда планируют начать",
            "budget": "Спроси примерный бюджет"
        }
        task = hints.get(missing[0], "Продолжи разговор")
    
    # Формируем контекст из собранных данных
    context = ""
    if updated_data:
        context = f"\n\nУже известно о клиенте: {json.dumps(updated_data, ensure_ascii=False)}"
    
    # Берём последние 6 сообщений для AI (экономия + контекст)
    recent = dialog_history[-6:] if len(dialog_history) > 6 else dialog_history
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT + context + f"\n\nЗАДАЧА: {task}"}]
    messages.extend([{"role": m["role"], "content": m["content"]} for m in recent])
    
    # Вызываем AI
    reply = await call_ai(messages, max_tokens=80)
    
    # Fallback если AI не ответил
    if not reply:
        if ready_for_lead:
            reply = "Отлично, всё записал! Есть вопросы по ценам или услугам? 🤔"
        else:
            fallbacks = {
                "work": "Какие работы вас интересуют? 🔨",
                "object_type": "Это квартира, дом или коммерческое помещение?",
                "area": "Какая примерно площадь объекта?",
                "address": "В каком районе находится объект?",
                "timing": "Когда планируете начать работы?",
                "budget": "Какой примерный бюджет?"
            }
            reply = fallbacks.get(missing[0], "Расскажите подробнее?")
    
    return reply, updated_data, ready_for_lead


async def check_phone_number(text: str) -> bool:
    """Проверяет наличие телефона в тексте"""
    clean = re.sub(r'[\s\-\(\)]', '', text)
    return bool(re.search(r'(\+7|8)\d{10}', clean) or re.search(r'\d{10,11}', clean))


async def generate_farewell(client_name: str) -> str:
    """Генерирует прощание"""
    
    reply = await call_ai([
        {"role": "system", "content": "Коротко поблагодари за заявку (1-2 предложения). Скажи что мастер свяжется."},
        {"role": "user", "content": f"Клиент: {client_name}"}
    ], max_tokens=50)
    
    return reply or f"Спасибо, {client_name}! ✅ Мастер свяжется с вами в ближайшее время!"


async def generate_questions_response(question: str) -> str:
    """Отвечает на вопросы клиента о ценах/услугах"""
    
    reply = await call_ai([
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nОтветь на вопрос клиента о ценах/услугах. Кратко, по делу."},
        {"role": "user", "content": question}
    ], max_tokens=100)
    
    return reply or "Точную стоимость мастер рассчитает после осмотра объекта."
