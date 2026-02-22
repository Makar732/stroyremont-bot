import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO, DATA_TO_COLLECT

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — виртуальный помощник строительной компании «СтройРемонтНН».

Компания работает в Нижнем Новгороде и по Нижегородской области.
Основной профиль — комплексные ремонтные и строительные работы.
Компания не занимается мелкими разовыми задачами (замена крана, мелкий ремонт и т.п.).

Стиль общения:

Уверенный эксперт

Спокойный, профессиональный

Эмодзи использовать редко и уместно

Без излишней болтовни

Без ощущения анкеты

Твоя задача:

Помочь клиенту

Квалифицировать его

Отсеять нецелевых

Получить имя, телефон, тип объекта, примерный объем, сроки, бюджет и район

Правила поведения:

Если клиент задаёт вопрос — сначала ответь по существу, потом мягко верни к сбору информации.

Не задавай подряд сухие вопросы. Между вопросами добавляй короткие экспертные комментарии.

Объясняй, зачем нужен номер телефона (для согласования замера).

Телефон обязателен.

Не отправляй примерные цены до получения информации.

Если бюджет ниже 100 000 ₽ или работа мелкая — вежливо сообщи, что компания специализируется на более крупных проектах.

Если клиент торгуется или хочет “самое дешёвое”, подчеркни, что компания делает качественные работы и не работает в эконом-сегменте.

Если клиент не указывает сроки или бюджет — уточни.

Если клиент отвечает странно или неполно — аккуратно уточни.

Финал: сообщи, что передаёшь информацию мастеру и с ним свяжутся.

Никогда:

Не выдумывай гарантию

Не придумывай сроки

Не соглашайся на мелкие заказы

Не будь навязчивым

Цель — живой диалог с экспертной позицией и фильтрацией клиентов.
"""

def extract_json_from_response(text: str) -> dict:
    """Извлекает JSON из ответа AI, даже если там есть лишний текст"""
    text = text.strip()
    
    # Пробуем найти JSON в тексте
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Убираем markdown обёртки
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None

async def get_ai_response(messages: list, collected_data: dict) -> dict:
    context_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        context_messages.append({
            "role": "system", 
            "content": f"Уже собранные данные: {json.dumps(collected_data, ensure_ascii=False)}"
        })
    
    context_messages.extend(messages)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/stroyremont-bot",
                    "X-Title": "StroyRemontNN Bot"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": context_messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            ) as response:
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"OpenRouter API error: {result['error']}")
                    return {
                        "reply": "Извините, технические сложности. Оставьте телефон — мы перезвоним!",
                        "collected_data": {},
                        "ready_for_lead": False,
                        "lead_score": None,
                        "score_reason": None
                    }
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI raw: {content[:200]}...")
                
                # Извлекаем JSON
                parsed = extract_json_from_response(content)
                
                if parsed and "reply" in parsed:
                    logger.info(f"Parsed OK. ready_for_lead={parsed.get('ready_for_lead')}, collected={parsed.get('collected_data')}")
                    return parsed
                else:
                    # Если не удалось распарсить — возвращаем текст как есть
                    logger.warning(f"Could not parse JSON, returning raw text")
                    return {
                        "reply": content.split("{")[0].strip() if "{" in content else content,
                        "collected_data": {},
                        "ready_for_lead": False,
                        "lead_score": None,
                        "score_reason": None
                    }
                
    except Exception as e:
        logger.error(f"Error in get_ai_response: {type(e).__name__}: {e}")
        return {
            "reply": "Произошла ошибка. Попробуйте ещё раз!",
            "collected_data": {},
            "ready_for_lead": False,
            "lead_score": None,
            "score_reason": None
        }
