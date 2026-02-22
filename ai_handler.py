import aiohttp
import json
import logging
import re
from config import OPENROUTER_API_KEY, COMPANY_INFO, DATA_TO_COLLECT

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — виртуальный помощник компании СтройРемонтНН. Твоя задача:

1. Отвечать на вопросы клиентов о компании и услугах
2. Естественно в ходе диалога собирать информацию о клиенте и его проекте
3. Быть вежливым, профессиональным, но не занудным
4. НЕ называть точных цен — говори что нужно понять объём работ

{COMPANY_INFO}

{DATA_TO_COLLECT}

ПРАВИЛА:
- Отвечай кратко, по делу, дружелюбно
- Не задавай все вопросы сразу — веди естественный диалог
- Когда собрал достаточно данных — предложи что менеджер свяжется

ВАЖНО! Отвечай ТОЛЬКО JSON без лишнего текста:
{{"reply": "твой ответ клиенту", "collected_data": {{"имя": "...", "телефон": "...", "тип_объекта": "...", "площадь": "...", "работы": "...", "чертежи": "...", "бюджет": "...", "сроки_начала": "...", "адрес": "..."}}, "ready_for_lead": false, "lead_score": "холодный", "score_reason": "причина"}}

ready_for_lead = true когда есть: телефон + что нужно сделать.
Оценка: горячий (готов начать скоро) / тёплый (думает 1-3 мес) / холодный (просто узнать)
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
