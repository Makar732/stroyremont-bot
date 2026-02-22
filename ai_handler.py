import aiohttp
import json
import logging
from config import OPENROUTER_API_KEY, COMPANY_INFO, REQUIRED_FIELDS

logger = logging.getLogger(__name__)

# Системный промпт для AI
SYSTEM_PROMPT = f"""Ты — дружелюбный менеджер компании СтройРемонтНН (Нижний Новгород).

{COMPANY_INFO}

ТВОЯ ЗАДАЧА:
1. Вести естественный, тёплый диалог с клиентом
2. Собрать информацию о проекте (но НЕ как анкету, а в разговоре)
3. Отвечать на вопросы о ценах и услугах
4. Если клиент спрашивает о мелких работах (один кран, одна розетка) — вежливо объясни, что мы делаем комплексные ремонты от 100 000 руб

СТИЛЬ ОБЩЕНИЯ:
- Короткие ответы (1-3 предложения)
- Дружелюбно, но профессионально
- Используй эмодзи умеренно (1-2 на сообщение)
- Задавай только ОДИН вопрос за раз
- Не повторяй то, что клиент уже сказал

ВАЖНО:
- НЕ выдумывай цены — используй только указанные выше
- НЕ обещай точные сроки — говори "мастер уточнит"
- Если что-то непонятно — переспроси
"""

EXTRACT_PROMPT = """Извлеки информацию из диалога. Верни JSON с полями:
- work: какие работы нужны (null если не сказано)
- object_type: квартира/дом/коммерция (null если не сказано)
- area: площадь в м² или текстом (null если не сказано)
- address: район/адрес (null если не сказано)  
- timing: когда начать (null если не сказано)
- budget: бюджет (null если не сказано)

Отвечай ТОЛЬКО валидным JSON, без пояснений.

Диалог:
{dialog}

JSON:"""


async def call_ai(messages: list, temperature: float = 0.7, max_tokens: int = 200) -> str | None:
    """Базовый вызов OpenRouter API"""
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
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"AI API error {response.status}: {error_text}")
                    return None
                
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"AI error: {result['error']}")
                    return None
                
                if "choices" not in result or len(result["choices"]) == 0:
                    logger.error("No choices in AI response")
                    return None
                
                return result["choices"][0]["message"]["content"].strip()
                
    except aiohttp.ClientTimeout:
        logger.error("AI request timeout")
        return None
    except Exception as e:
        logger.error(f"AI Error: {type(e).__name__}: {e}")
        return None


async def extract_data(dialog_history: list) -> dict:
    """Извлекает структурированные данные из истории диалога"""
    
    # Форматируем диалог для анализа
    dialog_text = "\n".join([
        f"{'Клиент' if msg['role'] == 'user' else 'Менеджер'}: {msg['content']}"
        for msg in dialog_history
    ])
    
    messages = [
        {"role": "user", "content": EXTRACT_PROMPT.format(dialog=dialog_text)}
    ]
    
    response = await call_ai(messages, temperature=0.1, max_tokens=300)
    
    if not response:
        return {}
    
    try:
        # Пробуем найти JSON в ответе
        # Иногда модель оборачивает в ```json ... ```
        if "```" in response:
            start = response.find("{")
            end = response.rfind("}") + 1
            response = response[start:end]
        
        data = json.loads(response)
        
        # Фильтруем null значения
        return {k: v for k, v in data.items() if v is not None and v != "null" and v != ""}
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI JSON: {e}\nResponse: {response}")
        return {}


def get_missing_fields(collected: dict) -> list:
    """Возвращает список полей, которые ещё не собраны"""
    missing = []
    for field, description in REQUIRED_FIELDS.items():
        if field not in collected or not collected[field]:
            missing.append(field)
    return missing


def build_context_prompt(collected: dict, missing: list) -> str:
    """Создаёт подсказку для AI о том, что нужно узнать"""
    
    if not missing:
        return "\n\nВся информация собрана! Поблагодари клиента и попроси номер телефона для связи мастера."
    
    # Берём первое недостающее поле
    next_field = missing[0]
    field_desc = REQUIRED_FIELDS[next_field]
    
    hints = {
        "work": "Уточни, какие именно работы нужны клиенту",
        "object_type": "Спроси, это квартира, дом или коммерческое помещение",
        "area": "Поинтересуйся примерной площадью объекта",
        "address": "Узнай, в каком районе или по какому адресу объект",
        "timing": "Спроси, когда планируют начать ремонт",
        "budget": "Уточни примерный бюджет на работы"
    }
    
    prompt = f"\n\n[ВНУТРЕННЯЯ ЗАДАЧА - не показывай клиенту]\n"
    prompt += f"Уже известно: {json.dumps(collected, ensure_ascii=False) if collected else 'пока ничего'}\n"
    prompt += f"Нужно узнать: {hints.get(next_field, field_desc)}\n"
    prompt += "Спроси об этом естественно, в контексте разговора."
    
    return prompt


async def generate_reply(dialog_history: list, collected_data: dict) -> tuple[str, dict, bool]:
    """
    Генерирует ответ менеджера.
    
    Returns:
        tuple: (ответ, обновлённые_данные, готов_к_заявке)
    """
    
    # Извлекаем данные из всего диалога
    extracted = await extract_data(dialog_history)
    
    # Объединяем с уже собранными
    updated_data = {**collected_data, **extracted}
    
    # Проверяем, что ещё нужно узнать
    missing = get_missing_fields(updated_data)
    
    # Проверяем, готовы ли к заявке (всё собрано)
    ready_for_lead = len(missing) == 0
    
    # Формируем контекст для AI
    context_hint = build_context_prompt(updated_data, missing)
    
    # Собираем сообщения для AI
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + context_hint}
    ]
    
    # Добавляем историю диалога (последние 10 сообщений)
    for msg in dialog_history[-10:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Генерируем ответ
    reply = await call_ai(messages, temperature=0.7, max_tokens=150)
    
    if not reply:
        # Fallback если AI не ответил
        if ready_for_lead:
            reply = "Отлично, у меня есть вся информация! Оставьте номер телефона — мастер свяжется с вами для обсуждения деталей 📞"
        elif missing:
            fallbacks = {
                "work": "Расскажите, какие работы вам нужны?",
                "object_type": "А это квартира, дом или коммерческое помещение?",
                "area": "Какая примерно площадь объекта?",
                "address": "В каком районе находится объект?",
                "timing": "Когда планируете начать ремонт?",
                "budget": "Какой примерный бюджет закладываете?"
            }
            reply = fallbacks.get(missing[0], "Расскажите подробнее о вашем проекте?")
    
    logger.info(f"Collected: {updated_data}, Missing: {missing}, Ready: {ready_for_lead}")
    
    return reply, updated_data, ready_for_lead


async def check_phone_number(text: str) -> bool:
    """Проверяет, содержит ли текст номер телефона"""
    import re
    # Ищем паттерны телефонов
    patterns = [
        r'\+7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',  # +7 999 123 45 67
        r'8\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',    # 8 999 123 45 67
        r'\d{10,11}',                              # 89991234567
    ]
    
    for pattern in patterns:
        if re.search(pattern, text.replace("-", "").replace("(", "").replace(")", "")):
            return True
    return False


async def generate_farewell(client_name: str) -> str:
    """Генерирует прощальное сообщение после получения телефона"""
    
    messages = [
        {"role": "system", "content": "Ты менеджер СтройРемонтНН. Напиши короткое (2-3 предложения) прощальное сообщение. Поблагодари за заявку, скажи что мастер скоро свяжется. Дружелюбно, с эмодзи."},
        {"role": "user", "content": f"Клиент {client_name} оставил телефон. Попрощайся."}
    ]
    
    reply = await call_ai(messages, temperature=0.8, max_tokens=100)
    
    return reply or f"Спасибо, {client_name}! ✅ Мастер свяжется с вами в ближайшее время. Если будут вопросы — пишите!"
