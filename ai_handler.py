import aiohttp
import json
from config import OPENROUTER_API_KEY, COMPANY_INFO, DATA_TO_COLLECT

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
Отвечай в JSON формате:
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
    "ready_for_lead": true/false,
    "lead_score": "горячий/тёплый/холодный",
    "score_reason": "почему такая оценка"
}}

В collected_data заполняй только то что узнал. ready_for_lead = true когда есть минимум: телефон + понимание что нужно сделать.

ОЦЕНКА КЛИЕНТА:
🔥 ГОРЯЧИЙ: есть телефон, знает что хочет, готов начать скоро (до месяца), не торгуется на пустом месте, адекватен
🟡 ТЁПЛЫЙ: есть контакт, но сроки неопределённые или 1-3 месяца, ещё думает
🟢 ХОЛОДНЫЙ: "просто узнать", нет конкретики, торгуется сразу без понимания объёма, далёкие сроки
"""

async def get_ai_response(messages: list, collected_data: dict) -> dict:
    """Получить ответ от AI"""
    
    # Формируем контекст с уже собранными данными
    context_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if collected_data:
        context_messages.append({
            "role": "system", 
            "content": f"Уже собранные данные о клиенте: {json.dumps(collected_data, ensure_ascii=False)}"
        })
    
    context_messages.extend(messages)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": context_messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
        ) as response:
            result = await response.json()
            
            try:
                content = result["choices"][0]["message"]["content"]
                # Пробуем распарсить JSON
                # Убираем возможные markdown обёртки
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                
                return json.loads(content.strip())
            except (json.JSONDecodeError, KeyError) as e:
                # Если не JSON — возвращаем как обычный текст
                return {
                    "reply": result.get("choices", [{}])[0].get("message", {}).get("content", "Произошла ошибка, попробуйте ещё раз"),
                    "collected_data": {},
                    "ready_for_lead": False,
                    "lead_score": None,
                    "score_reason": None
                }
