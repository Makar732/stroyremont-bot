import aiohttp
import json
import logging
from config import OPENROUTER_API_KEY, COMPANY_INFO, DATA_TO_COLLECT

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""Ты — виртуальный помощник компании СтройРемонтНН. Твоя задача:

1. Отвечать на вопросы клиентов о компании и услугах
2. Естественно в ходе диалога собирать информацию о клиенте и его проекте
3. Быть вежливым, профессиональным, но не занудным
4. НЕ называть точных цен — говори что нужно понять объём работ

{COMPANY_INFO}

{DATA_TO_COLLECT}

ПРАВИЛА ПОВЕДЕНИЯ:
- Отвечай кратко, по делу, дружелюбно
- Не задавай все вопросы сразу — веди естественный диалог
- Если клиент сам даёт информацию — запоминай и не переспрашивай
- Когда собрал достаточно данных — предложи что менеджер свяжется
- Если клиент просит цену — объясни что нужна оценка объекта или подробности

ФОРМАТ ОТВЕТА:
Отвечай ТОЛЬКО в JSON формате без markdown:
{{
    "reply": "твой ответ клиенту",
    "collected_data": {{
        "имя": "...",
        "телефон": "...",
        "тип_объекта": "...",
        "площадь": "...",
        "работы": "...",
        "чертежи": "...",
        "бюджет": "...",
        "сроки_начала": "...",
        "адрес": "..."
    }},
    "ready_for_lead": false,
    "lead_score": "холодный",
    "score_reason": "пока мало данных"
}}

В collected_data заполняй только то что узнал (остальные поля не включай). 
ready_for_lead = true когда есть минимум: телефон + понимание что нужно сделать.

ОЦЕНКА КЛИЕНТА:
🔥 ГОРЯЧИЙ: есть телефон, знает что хочет, готов начать скоро (до месяца), не торгуется, адекватен
🟡 ТЁПЛЫЙ: есть контакт, но сроки неопределённые или 1-3 месяца, ещё думает
🟢 ХОЛОДНЫЙ: "просто узнать", нет конкретики, торгуется сразу, далёкие сроки
"""

async def get_ai_response(messages: list, collected_data: dict) -> dict:
    context_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        context_messages.append({
            "role": "system", 
            "content": f"Уже собранные данные о клиенте: {json.dumps(collected_data, ensure_ascii=False)}"
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
                
                # Логируем ответ для отладки
                logger.info(f"OpenRouter response status: {response.status}")
                logger.info(f"OpenRouter response: {result}")
                
                # Проверяем на ошибки API
                if "error" in result:
                    logger.error(f"OpenRouter API error: {result['error']}")
                    return {
                        "reply": "Извините, сейчас возникли технические сложности. Напишите ваш вопрос ещё раз или оставьте телефон — мы перезвоним!",
                        "collected_data": {},
                        "ready_for_lead": False,
                        "lead_score": None,
                        "score_reason": None
                    }
                
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI raw content: {content}")
                
                # Убираем markdown обёртки
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                parsed = json.loads(content)
                return parsed
                
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}, content was: {content}")
        # Если не JSON — возвращаем как обычный текст
        return {
            "reply": content if 'content' in dir() else "Произошла ошибка обработки. Попробуйте ещё раз.",
            "collected_data": {},
            "ready_for_lead": False,
            "lead_score": None,
            "score_reason": None
        }
    except KeyError as e:
        logger.error(f"KeyError: {e}, result was: {result}")
        return {
            "reply": "Произошла ошибка. Попробуйте написать ещё раз.",
            "collected_data": {},
            "ready_for_lead": False,
            "lead_score": None,
            "score_reason": None
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_ai_response: {type(e).__name__}: {e}")
        return {
            "reply": "Произошла техническая ошибка. Попробуйте позже или оставьте телефон — мы свяжемся!",
            "collected_data": {},
            "ready_for_lead": False,
            "lead_score": None,
            "score_reason": None
        }
