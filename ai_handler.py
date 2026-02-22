import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — дружелюбный помощник компании СтройРемонтНН. Общайся как живой человек.

{COMPANY_INFO}

СТИЛЬ:
- Дружелюбно и профессионально
- 2-3 предложения максимум
- Реагируй на слова клиента, не игнорируй
- Эмодзи умеренно

ЦЕЛЬ — собрать ВСЕ данные:
1. Что нужно сделать (работы)
2. Тип объекта (квартира/дом/коммерция)
3. Площадь (кв.м)
4. Адрес или район
5. Сроки начала
6. Бюджет
7. Телефон

Спрашивай естественно, по ходу разговора. Не все сразу.

ВАЖНО:
- Цены называй как ориентир

ОТВЕТ СТРОГО JSON:
{{"reply":"ответ","collected_data":{{"телефон":"","работы":"","тип_объекта":"","площадь":"","адрес":"","сроки":"","бюджет":""}},"lead_status":"none","status_reason":""}}

lead_status:
- "целевой" — бюджет от 100к, крупная работа, адекватные сроки
- "под_вопросом" — потенциал есть, но что-то смущает
- "нецелевой" — мелочь, бюджет <100к, торгуется, "просто узнать"
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
    recent_messages = messages[-8:] if len(messages) > 8 else messages
    
    context = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        data_summary = ", ".join([f"{k}: {v}" for k, v in collected_data.items() if v and v not in ["", "...", None]])
        if data_summary:
            context.append({
                "role": "system", 
                "content": f"Уже знаешь: {data_summary}. Не спрашивай это повторно!"
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
                    "temperature": 0.8,
                    "max_tokens": 300
                }
            ) as response:
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"API error: {result['error']}")
                    return {"reply": "Секунду, что-то пошло не так. Напишите ещё раз 🙏", "collected_data": {}, "lead_status": "none", "status_reason": ""}
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI: {content[:150]}...")
                
                parsed = extract_json(content)
                
                if parsed and "reply" in parsed:
                    return parsed
                else:
                    clean_reply = content.split("{")[0].strip() if "{" in content else content
                    return {
                        "reply": clean_reply,
                        "collected_data": {},
                        "lead_status": "none",
                        "status_reason": ""
                    }
                
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"reply": "Упс, технический сбой. Попробуйте ещё раз!", "collected_data": {}, "lead_status": "none", "status_reason": ""}
