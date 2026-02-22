import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — дружелюбный помощник компании СтройРемонтНН.

{COMPANY_INFO}

ТВОЯ ЗАДАЧА — собрать данные через приятный диалог:
- телефон
- работы (что делать)
- тип_объекта (квартира/дом/офис)
- площадь
- адрес
- сроки
- бюджет

Спрашивай по 1-2 вопроса за раз. Будь живым, используй эмодзи.

ОТВЕЧАЙ СТРОГО JSON БЕЗ MARKDOWN:
{{"reply":"твой ответ","collected_data":{{"телефон":"","работы":"","тип_объекта":"","площадь":"","адрес":"","сроки":"","бюджет":""}},"lead_status":"none","status_reason":""}}

В collected_data пиши ТОЛЬКО то, что клиент СЕЙЧАС сказал. Пустые поля не заполняй.
lead_status: "целевой" / "под_вопросом" / "нецелевой" / "none"
"""

def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return None

def normalize_data(data: dict) -> dict:
    if not data:
        return {}
    
    mapping = {
        "phone": "телефон", "тел": "телефон", "номер": "телефон",
        "работа": "работы", "work": "работы", "услуги": "работы",
        "тип": "тип_объекта", "объект": "тип_объекта", "type": "тип_объекта",
        "area": "площадь", "метраж": "площадь", "квадраты": "площадь",
        "address": "адрес", "район": "адрес", "где": "адрес",
        "timing": "сроки", "когда": "сроки", "сроки_начала": "сроки", "начало": "сроки",
        "budget": "бюджет", "деньги": "бюджет", "цена": "бюджет",
    }
    
    result = {}
    for key, value in data.items():
        if not value or value in ["", "...", "неизвестно", "не указано", None]:
            continue
        
        clean_key = mapping.get(key.lower(), key.lower())
        result[clean_key] = str(value).strip()
    
    return result

async def get_ai_response(messages: list, collected_data: dict) -> dict:
    context = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        known = ", ".join(f"{k}: {v}" for k, v in collected_data.items() if v)
        if known:
            context.append({
                "role": "system",
                "content": f"Уже собрано: {known}. НЕ спрашивай это снова!"
            })
    
    context.extend(messages[-8:])
    
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
                    logger.error(f"API error: {result}")
                    return {"reply": "Секунду... Повторите пожалуйста 🙏", "collected_data": {}, "lead_status": "none", "status_reason": ""}
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI raw: {content[:200]}")
                
                parsed = extract_json(content)
                
                if parsed and "reply" in parsed:
                    parsed["collected_data"] = normalize_data(parsed.get("collected_data", {}))
                    return parsed
                
                clean = content.split("{")[0].strip() if "{" in content else content
                return {"reply": clean or "Расскажите подробнее 🙂", "collected_data": {}, "lead_status": "none", "status_reason": ""}
                
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return {"reply": "Ошибка связи, попробуйте ещё раз!", "collected_data": {}, "lead_status": "none", "status_reason": ""}

import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

# Проверка ключа при импорте
logger.info(f"🔑 OpenRouter key: {OPENROUTER_API_KEY[:20] if OPENROUTER_API_KEY else 'NOT SET'}...")

SYSTEM_PROMPT = f"""Ты — дружелюбный помощник компании СтройРемонтНН.

{COMPANY_INFO}

ТВОЯ ЗАДАЧА — собрать данные через приятный диалог:
- телефон
- работы (что делать)
- тип_объекта (квартира/дом/офис)
- площадь
- адрес
- сроки
- бюджет

Спрашивай по 1-2 вопроса за раз. Будь живым, используй эмодзи.

ОТВЕЧАЙ СТРОГО JSON БЕЗ MARKDOWN:
{{"reply":"твой ответ","collected_data":{{"телефон":"","работы":"","тип_объекта":"","площадь":"","адрес":"","сроки":"","бюджет":""}},"lead_status":"none","status_reason":""}}

В collected_data пиши ТОЛЬКО то, что клиент СЕЙЧАС сказал. Пустые поля не заполняй.
"""

def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return None

def normalize_data(data: dict) -> dict:
    if not data:
        return {}
    
    mapping = {
        "phone": "телефон", "тел": "телефон", "номер": "телефон",
        "работа": "работы", "work": "работы",
        "тип": "тип_объекта", "объект": "тип_объекта",
        "area": "площадь", "метраж": "площадь",
        "address": "адрес", "район": "адрес",
        "timing": "сроки", "когда": "сроки",
        "budget": "бюджет",
    }
    
    result = {}
    for key, value in data.items():
        if not value or value in ["", "...", "неизвестно", "не указано", None]:
            continue
        clean_key = mapping.get(key.lower(), key.lower())
        result[clean_key] = str(value).strip()
    
    return result

async def get_ai_response(messages: list, collected_data: dict) -> dict:
    
    # Проверка ключа
    if not OPENROUTER_API_KEY:
        logger.error("❌ OPENROUTER_API_KEY is empty!")
        return {"reply": "Ошибка конфигурации. Напишите позже.", "collected_data": {}, "lead_status": "none", "status_reason": ""}
    
    context = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        known = ", ".join(f"{k}: {v}" for k, v in collected_data.items() if v)
        if known:
            context.append({
                "role": "system",
                "content": f"Уже собрано: {known}. НЕ спрашивай это снова!"
            })
    
    context.extend(messages[-8:])
    
    logger.info(f"📤 Sending to OpenRouter...")
    
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
                
                status = response.status
                logger.info(f"📥 OpenRouter status: {status}")
                
                result = await response.json()
                logger.info(f"📥 OpenRouter response: {json.dumps(result, ensure_ascii=False)[:500]}")
                
                if "error" in result:
                    logger.error(f"❌ API error: {result['error']}")
                    return {
                        "reply": "Проблема с AI сервисом. Попробуйте позже 🙏", 
                        "collected_data": {}, 
                        "lead_status": "none", 
                        "status_reason": ""
                    }
                
                if "choices" not in result:
                    logger.error(f"❌ No choices in response: {result}")
                    return {
                        "reply": "Ошибка ответа AI. Попробуйте ещё раз.", 
                        "collected_data": {}, 
                        "lead_status": "none", 
                        "status_reason": ""
                    }
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"🤖 AI said: {content[:200]}")
                
                parsed = extract_json(content)
                
                if parsed and "reply" in parsed:
                    parsed["collected_data"] = normalize_data(parsed.get("collected_data", {}))
                    return parsed
                
                clean = content.split("{")[0].strip() if "{" in content else content
                return {
                    "reply": clean or "Расскажите подробнее 🙂", 
                    "collected_data": {}, 
                    "lead_status": "none", 
                    "status_reason": ""
                }
                
    except aiohttp.ClientError as e:
        logger.error(f"❌ Network error: {e}")
        return {"reply": "Ошибка сети. Попробуйте ещё раз!", "collected_data": {}, "lead_status": "none", "status_reason": ""}
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {"reply": "Что-то пошло не так 🙏", "collected_data": {}, "lead_status": "none", "status_reason": ""}
