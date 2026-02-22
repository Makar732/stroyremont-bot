import aiohttp
import logging
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

async def make_reply(context: str, task: str) -> str:
    """Генерирует живой ответ. Минимум токенов."""
    
    prompt = f"""Ты — дружелюбный помощник компании СтройРемонтНН. Общайся как живой человек. {COMPANY_INFO} СТИЛЬ: - Дружелюбно и профессионально - 2-3 предложения максимум - Реагируй на слова клиента, не игнорируй - Эмодзи умеренно ЦЕЛЬ — собрать ВСЕ данные: 1. Что нужно сделать (работы) 2. Тип объекта (квартира/дом/коммерция) 3. Площадь (кв.м) 4. Адрес или район 5. Сроки начала 6. Бюджет 7. Телефон Спрашивай естественно, по ходу разговора. Не все сразу. ВАЖНО: - Цены называй как ориентир ОТВЕТ СТРОГО JSON: {{"reply":"ответ","collected_data":{{"телефон":"","работы":"","тип_объекта":"","площадь":"","адрес":"","сроки":"","бюджет":""}},"lead_status":"none","status_reason":""}} lead_status: - "целевой" — бюджет от 100к, крупная работа, адекватные сроки - "под_вопросом" — потенциал есть, но что-то смущает - "нецелевой" — мелочь, бюджет <100к, торгуется, "просто узнать"
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
                    "max_tokens": 100  # Минимум токенов!
                }
            ) as response:
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"API error: {result['error']}")
                    return task.split("спроси:")[-1].strip() if "спроси:" in task else "Продолжим?"
                
                reply = result["choices"][0]["message"]["content"].strip()
                logger.info(f"AI reply: {reply}")
                return reply
                
    except Exception as e:
        logger.error(f"Error: {e}")
        return task.split("спроси:")[-1].strip() if "спроси:" in task else "Продолжим?"
