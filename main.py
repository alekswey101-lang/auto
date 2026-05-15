# -*- coding: utf-8 -*-
import os, asyncio, random, datetime, threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup

# --- ХОСТИНГ ПРОВЕРКА ---
app = Flask(__name__)
@app.route('/')
def health(): return "Trade Bot is Active", 200
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()

# --- КОНФИГУРАЦИЯ ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ[f"SESSION_{i}"] for i in range(1, 6)]

clients = []
for i, session_str in enumerate(SESSIONS):
    clients.append(Client(
        name=f"acc_{i+1}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_str
    ))

# --- ФУНКЦИЯ КЛИКА ---
async def smart_click(client, chat_id, message_id, variants, pick_first=False):
    """
    variants: список текстов или префиксов callback_data.
    pick_first: если True, нажмет первую попавшуюся кнопку (кроме 'Назад').
    """
    async for message in client.get_chat_history(chat_id, limit=1):
        if message.id == message_id and message.reply_markup:
            for row in message.reply_markup.inline_keyboard:
                for btn in row:
                    data = btn.callback_data or ""
                    
                    # Режим "просто жми первую кнопку" (для выбора модели телефона)
                    if pick_first:
                        if "назад" not in btn.text.lower() and "back" not in data.lower():
                            await client.request_callback_answer(chat_id, message.id, data)
                            return True, btn.text
                    
                    # Обычный режим поиска по списку
                    elif any(v in btn.text or data.startswith(v) for v in variants):
                        await client.request_callback_answer(chat_id, message.id, data)
                        return True, btn.text
    return False, None

# --- ЛОГИКА ТРЕЙДА ---
async def trade_logic(client, target_user, acc_id):
    bot_chat = "phonegetcardsbot"
    await client.send_message(bot_chat, f"/trade @{target_user}")
    
    # План действий
    # 1. Добавить телефон
    # 2. Выбрать тип (Рабочий/Сломанный)
    # 3. Выбрать редкость (Ширпотреб)
    # 4. Выбрать любую модель (первая кнопка)
    # 5. Нажать "Добавить 1 шт."
    # 6. Подтвердить обмен
    
    steps = [
        {"name": "Начало", "variants": ["Добавить телефон", "trade_add_phone_start"]},
        {"name": "Тип", "variants": ["✅ Рабочий", "❌ Сломанный", "trd_wrk", "trd_brk"]},
        {"name": "Редкость", "variants": ["Ширпотреб", "trade_add_rarity"]},
        {"name": "Модель", "variants": [], "pick_first": True}, # Тут берем любую модель
        {"name": "Кол-во", "variants": ["Добавить 1 шт.", "trade_add_single", "add_1"]},
        {"name": "Финал", "variants": ["Подтвердить", "trade_confirm"]}
    ]

    for step in steps:
        await asyncio.sleep(5)
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if msg.reply_markup:
                success, clicked = await smart_click(
                    client, bot_chat, msg.id, 
                    step.get("variants", []), 
                    step.get("pick_first", False)
                )
                if success:
                    print(f"✅ [Акк {acc_id}] {step['name']}: {clicked}")
                    break

# --- КОМАНДЫ ---

@Client.on_message(filters.me & filters.command("trade", prefixes="."))
async def cmd_trade(client, message):
    if len(message.command) < 2: return
    target = message.command[1].replace("@", "")
    await message.delete()
    await trade_logic(client, target, clients.index(client) + 1)

@Client.on_message(filters.me & filters.command("farm_now", prefixes="."))
async def cmd_farm(client, message):
    await message.edit("🚜 Собираю...")
    bot = "phonegetcardsbot"
    await client.send_message(bot, "/tfarm")
    await asyncio.sleep(5)
    async for msg in client.get_chat_history(bot, limit=1):
        if msg.reply_markup:
            res, _ = await smart_click(client, bot, msg.id, ["Снять деньги", "farm_claim"])
            if res:
                await message.edit("✅ Деньги в мешке!")
                return
    await message.edit("❌ Не нашел кнопку")

# --- ФОН (Карточки и Ферма) ---
async def bg_tasks(client, acc_id):
    while True:
        try:
            # Карточка раз в 2 часа
            await client.send_message("phonegetcardsbot", "ткарточка")
            
            # Ферма (только если не 5-й акк)
            if acc_id != 5:
                now = datetime.datetime.utcnow()
                # 21:10 UTC = 02:10 по Шымкенту
                if now.hour == 21 and now.minute <= 15:
                    await client.send_message("phonegetcardsbot", "/tfarm")
                    await asyncio.sleep(10)
                    async for msg in client.get_chat_history("phonegetcardsbot", limit=1):
                        await smart_click(client, "phonegetcardsbot", msg.id, ["Снять деньги", "farm_claim"])
        except: pass
        await asyncio.sleep(121 * 60)

async def main():
    for i, client in enumerate(clients):
        await client.start()
        asyncio.create_task(bg_tasks(client, i + 1))
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
                        
