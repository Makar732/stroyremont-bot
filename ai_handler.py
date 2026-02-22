import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — дружелюбный помощник компании СтройРемонтНН. Общайся как живой человек, не как робот.

{COMPANY_INFO}

ТВОЙ СТИЛЬ:
- Дружелюбно, но профессионально
- Короткие ответы (2-3 предложения)
- Можно использовать эмодзи, но умеренно
- Отвечай на вопросы клиента, потом задавай свой
- Проявляй интерес к проекту клиента

ТВОЯ ЦЕЛЬ:
Узнать: что нужно сделать → объём → сроки → бюджет → телефон

НО! Не делай допрос. Веди живой разговор. Если клиент что-то рассказывает — реагируй на это.

ВАЖНО:
- Мелкие работы (замена крана, одна розетка) — вежливо говори что работаем с более крупными проектами
- Если бюджет меньше 100к — мягко уточни, может клиент имел в виду что-то другое
- Цены называй как ориентир, точную стоимость скажет мастер после осмотра

ОТВЕТ JSON:
{{"reply":"твой живой ответ","collected_data":{{"имя":"","телефон":"","тип_объекта":"","площадь":"","работы":"","бюджет":"","сроки":""}},"ready_for_lead":false,"lead_status":"none","status_reason":""}}

lead_status: "целевой" / "под_вопросом" / "нецелевой"
ready_for_lead=true когда получил телефон ИЛИ понял что клиент нецелевой
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
    # Берём последние 8 сообщений для баланса памяти и токенов
    recent_messages = messages[-8:] if len(messages) > 8 else messages
    
    context = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Передаём собранные данные чтобы не забывал
    if collected_data:
        data_summary = ", ".join([f"{k}: {v}" for k, v in collected_data.items() if v and v not in ["", "..."]])
        if data_summary:
            context.append({
                "role": "system", 
                "content": f"Уже знаешь о клиенте: {data_summary}"
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
                    return {"reply": "Секунду, что-то пошло не так. Напишите ещё раз 🙏", "collected_data": {}, "ready_for_lead": False, "lead_status": "none", "status_reason": ""}
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI: {content[:150]}...")
                
                parsed = extract_json(content)
                
                if parsed and "reply" in parsed:
                    return parsed
                else:
                    # Если JSON не распарсился, возвращаем текст без JSON части
                    clean_reply = content.split("{")[0].strip() if "{" in content else content
                    return {
                        "reply": clean_reply,
                        "collected_data": {},
                        "ready_for_lead": False,
                        "lead_status": "none",
                        "status_reason": ""
                    }
                
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"reply": "Упс, технический сбой. Попробуйте ещё раз!", "collected_data": {}, "ready_for_lead": False, "lead_status": "none", "status_reason": ""}
