import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — бот компании СтройРемонтНН. Веди диалог коротко.

{COMPANY_INFO}

ЦЕЛЬ: получить телефон, понять объём работ, отсеять мелочь.

ПРАВИЛА:
- 1-2 предложения максимум
- Один вопрос за раз
- Без воды и вступлений
- На вопрос о цене — называй цифры как ориентир
- Мелкие работы или бюджет <100к — вежливо отказывай

ПОРЯДОК:
1. Что нужно сделать?
2. Какой объём/площадь?
3. Когда планируете начать?
4. Какой бюджет?
5. Телефон для связи?

Если нет телефона — попроси ещё раз вежливо.

ОТВЕТ СТРОГО JSON:
{{"reply":"ответ","collected_data":{{"имя":"","телефон":"","тип_объекта":"","площадь":"","работы":"","бюджет":"","сроки":""}},"ready_for_lead":false,"lead_status":"none","status_reason":""}}

lead_status:
- "целевой" — бюджет ок, работа крупная, готов начать
- "под_вопросом" — что-то не ясно, но потенциал есть
- "нецелевой" — мелочь, бюджет <100к, торгуется

ready_for_lead=true когда есть телефон ИЛИ отказ/нецелевой.
"""

def extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return None

async def get_ai_response(messages: list, collected_data: dict) -> dict:
    recent_messages = messages[-4:] if len(messages) > 4 else messages
    
    context = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        context.append({
            "role": "system", 
            "content": f"Известно: {json.dumps(collected_data, ensure_ascii=False)}"
        })
    
    context.extend(recent_messages)
    
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
                    "messages": context,
                    "temperature": 0.7,
                    "max_tokens": 200
                }
            ) as response:
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"API error: {result['error']}")
                    return {"reply": "Ошибка. Напишите ещё раз.", "collected_data": {}, "ready_for_lead": False, "lead_status": "none", "status_reason": ""}
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI: {content[:100]}...")
                
                parsed = extract_json(content)
                
                if parsed and "reply" in parsed:
                    return parsed
                else:
                    return {
                        "reply": content.split("{")[0].strip() if "{" in content else content,
                        "collected_data": {},
                        "ready_for_lead": False,
                        "lead_status": "none",
                        "status_reason": ""
                    }
                
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"reply": "Ошибка. Попробуйте снова.", "collected_data": {}, "ready_for_lead": False, "lead_status": "none", "status_reason": ""}
