import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты менеджер СтройРемонтНН (Нижний Новгород). Ремонт любой сложности.

{COMPANY_INFO}

ПРАВИЛА:
- Короткие ответы (1-2 предложения)
- Дружелюбно, 1-2 эмодзи
- Один вопрос за раз
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
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                
                if response.status != 200:
                    logger.error(f"❌ API {response.status}")
                    return None
                
                result = await response.json()
                
                if "choices" not in result or not result["choices"]:
                    return None
                
                return result["choices"][0]["message"]["content"].strip()
                
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return None


async def generate_ai_response(user_message: str, collected_data: dict, next_question: str) -> str:
    """Генерирует ответ с реакцией на сообщение пользователя"""
    
    context = f"Клиент написал: {user_message}\nУже известно: {json.dumps(collected_data, ensure_ascii=False)}"
    task = f"Кратко отреагируй (1 предложение) и задай вопрос: {next_question}"
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n\nКонтекст: {context}\n\nЗадача: {task}"}
    ]
    
    reply = await call_ai(messages, max_tokens=80)
    return reply


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
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nОтветь на вопрос клиента. Кратко."},
        {"role": "user", "content": question}
    ], max_tokens=100)
    
    return reply or "Точную стоимость мастер рассчитает после осмотра."


def check_phone_number(text: str) -> bool:
    """Проверяет наличие телефона"""
    clean = re.sub(r'[\s\-\(\)\+]', '', text)
    return bool(re.search(r'\d{10,11}', clean))
