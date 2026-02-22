import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — дружелюбный помощник компании СтройРемонтНН.

{COMPANY_INFO}

СТИЛЬ: Дружелюбно, 2-3 предложения, эмодзи умеренно.

СОБЕРИ ДАННЫЕ (спрашивай постепенно):
- работы (что делать)
- тип_объекта (квартира/дом/коммерция)  
- площадь (кв.м)
- адрес
- сроки
- бюджет
- телефон

ОТВЕЧАЙ ТОЛЬКО ЧИСТЫМ JSON (без ```):
{{"reply":"ответ клиенту","collected_data":{{"телефон":"","работы":"","тип_объекта":"","площадь":"","адрес":"","сроки":"","бюджет":""}},"lead_status":"none","status_reason":""}}

lead_status: "целевой"/"под_вопросом"/"нецелевой"/"none"
В collected_data пиши ТОЛЬКО новые данные из ЭТОГО сообщения клиента."""


def normalize_keys(data: dict) -> dict:
    mapping = {
        "phone": "телефон", "тел": "телефон",
        "работа": "работы", "work": "работы",
        "area": "площадь", "метраж": "площадь",
        "budget": "бюджет",
        "timing": "сроки", "когда": "сроки", "сроки_начала": "сроки",
        "type": "тип_объекта", "тип": "тип_объекта", "объект": "тип_объекта",
        "address": "адрес", "район": "адрес",
    }
    
    normalized = {}
    for key, value in data.items():
        if not value or value in ["...", "", "неизвестно", "не указано"]:
            continue
        new_key = mapping.get(key.lower(), key.lower())
        normalized[new_key] = value
    
    return normalized


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            data = json.loads(match.group())
            # Нормализуем ключи сразу
            if "collected_data" in data:
                data["collected_data"] = normalize_keys(data["collected_data"])
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
    return None


async def get_ai_response(messages: list, collected_data: dict) -> dict:
    recent = messages[-8:]
    
    context = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        known = ", ".join(f"{k}: {v}" for k, v in collected_data.items() if v)
        if known:
            context.append({
                "role": "system",
                "content": f"УЖЕ ЗНАЕМ: {known}. Не спрашивай повторно!"
            })
    
    context.extend(recent)
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": context,
                    "temperature": 0.7,
                    "max_tokens": 300
                }
            ) as response:
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"API error: {result['error']}")
                    return default_response("Секунду, попробуйте ещё раз 🙏")
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI raw: {content[:200]}")
                
                parsed = extract_json(content)
                
                if parsed and "reply" in parsed:
                    return parsed
                
                # Fallback
                clean = content.split("{")[0].strip() if "{" in content else content
                return default_response(clean or "Расскажите подробнее 🙂")
                
    except asyncio.TimeoutError:
        logger.error("API timeout")
        return default_response("Сервер думает долго, попробуйте ещё раз")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return default_response("Технический сбой, попробуйте ещё раз!")


def default_response(text: str) -> dict:
    return {
        "reply": text,
        "collected_data": {},
        "lead_status": "none",
        "status_reason": ""
    }
