import aiohttp
import logging
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

async def make_reply(context: str, task: str) -> str:
    """Генерирует живой ответ."""
    
    prompt = f"""Ты помощник СтройРемонтНН. Отвечай по-русски, дружелюбно, кратко (1-2 предложения).

{COMPANY_INFO}

Контекст: {context}
Задача: {task}

Ответь только текстом, без JSON."""

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
                    "max_tokens": 100
                }
            ) as response:
                result = await response.json()
                
                logger.info(f"AI response status: {response.status}")
                
                if "error" in result:
                    logger.error(f"API error: {result['error']}")
                    # Возвращаем запасной текст
                    if "спроси:" in task:
                        return task.split("спроси:")[-1].strip()
                    elif "попроси" in task:
                        return task.split("попроси")[-1].strip()
                    else:
                        return "Продолжим? Расскажите подробнее."
                
                reply = result["choices"][0]["message"]["content"].strip()
                logger.info(f"AI reply: {reply[:50]}...")
                return reply
                
    except Exception as e:
        logger.error(f"AI Error: {type(e).__name__}: {e}")
        # Возвращаем запасной текст
        if "спроси:" in task:
            return task.split("спроси:")[-1].strip()
        elif "попроси" in task:
            return task.split("попроси")[-1].strip()
        else:
            return "Продолжим? Расскажите подробнее."
