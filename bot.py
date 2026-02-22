import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from openai import OpenAI
from aiohttp import web

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_KEY)

# Хранилище диалогов
conversations = {}

# ===== ПРОМПТ КОМПАНИИ =====
SYSTEM_PROMPT = """
Ты — вежливый сотрудник компании СтройРемонтНН.
Компания занимается ремонтом квартир, домов и коттеджей 
в Нижнем Новгороде и области.

Твоя задача:
1. Отвечать на вопросы клиентов о ремонте
2. В процессе разговора ЕСТЕСТВЕННО узнать:
   - Имя клиента
   - Что нужно сделать (какой ремонт)
   - Тип объекта (квартира/дом/коттедж)
   - Площадь в м²
   - Бюджет (сколько готов потратить)
   - Сроки (когда хочет начать)
   - Есть ли проект/чертежи
   - Номер телефона для связи

3. НЕ спрашивай всё сразу — веди диалог плавно
4. Когда собрал информацию — поблагодари 
   и скажи что менеджер свяжется

5. Если не знаешь точную цену — говори 
   "точную стоимость рассчитает мастер после осмотра"
6. НЕ придумывай цены

7. Когда собрал данные клиента, в КОНЦЕ сообщения
   добавь блок:
   
   [ЗАЯВКА]
   Имя: ...
   Телефон: ...
   Объект: ...
   Площадь: ...
   Бюджет: ...
   Сроки: ...
   Чертежи: ...
   Работы: ...
   Горячесть: горячий/тёплый/холодный
   [/ЗАЯВКА]
"""


# ===== ОБРАБОТЧИКИ =====

@dp.message(CommandStart())
async def start(message: types.Message):
    conversations[message.from_user.id] = []
    await message.answer(
        "Здравствуйте! 👋\n\n"
        "Я — виртуальный помощник компании "
        "СтройРемонтНН.\n"
        "Помогу с вопросами по ремонту квартир, "
        "домов и коттеджей в Нижнем Новгороде.\n\n"
        "Расскажите, что вас интересует? 🏠"
    )


@dp.message(F.text)
async def chat(message: types.Message):
    user_id = message.from_user.id

    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({
        "role": "user",
        "content": message.text
    })

    # Лимит истории
    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT}
            ] + conversations[user_id],
            max_tokens=1000,
            temperature=0.7
        )

        answer = response.choices[0].message.content

        conversations[user_id].append({
            "role": "assistant",
            "content": answer
        })

        # Проверяем заявку
        if "[ЗАЯВКА]" in answer and "[/ЗАЯВКА]" in answer:
            start_idx = answer.index("[ЗАЯВКА]")
            end_idx = answer.index("[/ЗАЯВКА]") + len("[/ЗАЯВКА]")
            zayavka = answer[start_idx:end_idx]

            clean_answer = answer[:start_idx].strip()
            await message.answer(clean_answer)

            admin_text = (
                f"📋 НОВАЯ ЗАЯВКА\n\n"
                f"👤 @{message.from_user.username or 'нет'}\n"
                f"🆔 ID: {user_id}\n\n"
                f"{zayavka}\n\n"
                f"💬 Написать: tg://user?id={user_id}"
            )
            await bot.send_message(ADMIN_ID, admin_text)
        else:
            await message.answer(answer)

    except Exception as e:
        await message.answer(
            "Извините, произошёл сбой. "
            "Оставьте номер телефона — "
            "менеджер свяжется с вами!"
        )
        await bot.send_message(
            ADMIN_ID, f"⚠️ Ошибка:\n{str(e)}"
        )


@dp.message(F.photo | F.document)
async def handle_files(message: types.Message):
    await message.answer(
        "Спасибо за файл! 📎\n"
        "Передам специалисту.\n"
        "Расскажите подробнее о проекте?"
    )
    await message.forward(ADMIN_ID)


# ===== ВЕБ-СЕРВЕР (чтобы Render не усыплял) =====

async def health(request):
    return web.Response(text="OK")


async def run_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# ===== ЗАПУСК =====

async def main():
    print("Бот запущен ✅")
    await run_web()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
