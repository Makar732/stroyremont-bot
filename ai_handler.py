import aiohttp
import logging
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

# Запасные ответы если AI не работает
FALLBACK_REPLIES = {
    "object_type": "Отлично! А это квартира, дом или коммерция?",
    "area": "Понял вас! Какая примерно площадь объекта?",
    "address": "Хорошо! В каком районе находится объект?",
    "timing": "Отлично! Когда планируете начать работы?",
    "budget": "Понял! Какой примерный бюджет закладываете?",
    "phone": "Супер! Оставьте телефон — мастер свяжется с вами 📞",
    "default": "Понял вас! Расскажите подробнее."
}

def get_fallback(task: str) -> str:
    """Возвращает запасной ответ"""
    task_lower = task.lower()
    
    if "квартира" in task_lower or "дом" in task_lower or "object" in task_lower:
        return FALLBACK_REPLIES["object_type"]
    elif "площадь" in task_lower or "area" in task_lower:
        return FALLBACK_REPLIES["area"]
    elif "район" in task_lower or "адрес" in task_lower or "address" in task_lower:
        return FALLBACK_REPLIES["address"]
    elif "когда" in task_lower or "срок" in task_lower or "timing" in task_lower:
        return FALLBACK_REPLIES["timing"]
    elif "бюджет" in task_lower or "budget" in task_lower:
        return FALLBACK_REPLIES["budget"]
    elif "телефон" in task_lower or "phone" in task_lower:
        return FALLBACK_REPLIES["phone"]
    else:
        return FALLBACK_REPLIES["default"]

async def make_reply(context: str, task: str) -> str:
    """Генерирует живой ответ."""
    
    prompt = f"""Ты менеджер СтройРемонтНН. Ответь коротко и тепло (1-2 предложения).

Контекст: {context}
Задача: {task}

Пример хорошего ответа: "Отлично, понял вас! А какая площадь объекта?"

Твой ответ:"""

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
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8,
                    "max_tokens": 60
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status != 200:
                    logger.error(f"AI status: {response.status}")
                    return get_fallback(task)
                
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"API error: {result['error']}")
                    return get_fallback(task)
                
                if "choices" not in result or len(result["choices"]) == 0:
                    logger.error(f"No choices in result")
                    return get_fallback(task)
                
                reply = result["choices"][0]["message"]["content"].strip()
                
                if not reply:
                    return get_fallback(task)
                
                logger.info(f"AI: {reply[:50]}...")
                return reply
                
    except aiohttp.ClientTimeout:
        logger.error("AI timeout")
        return get_fallback(task)
    except Exception as e:
        logger.error(f"AI Error: {type(e).__name__}: {e}")
        return get_fallback(task)
