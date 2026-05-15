# -*- coding: utf-8 -*-
import os, asyncio, json, threading, random, datetime
from flask import Flask
from telethon import TelegramClient, functions, types, events
from telethon.sessions import StringSession

# --- SERVER FOR RENDER ---
app = Flask(__name__)
@app.route('/')
def health_check(): return "Userbot is Active!", 200
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ[f"SESSION_{i}"] for i in range(1, 6)]

# Маскировка под разные устройства
DEVICES = [
    {"model": "Samsung SM-S918B", "sys": "Android 13"},
    {"model": "Pixel 7 Pro", "sys": "Android 14"},
    {"model": "Xiaomi 13 Ultra", "sys": "Android 13"},
    {"model": "Samsung SM-G998B", "sys": "Android 12"},
    {"model": "Pixel 6a", "sys": "Android 13"}
]

async def smart_click(client, message, button):
    """Эмуляция реального клика"""
    try:
        await client(functions.messages.ReadHistoryRequest(peer=message.peer_id, max_id=message.id))
        await asyncio.sleep(random.randint(2, 4))
        await client(functions.messages.GetBotCallbackAnswerRequest(
            peer=message.peer_id, msg_id=message.id, data=button.data
        ))
        return True
    except: return False

# --- ЗАДАЧА ДЛЯ КАРТОЧЕК ---
async def card_task(client, acc_id):
    """Шлет 'ткарточка' каждые 2 часа"""
    bot_username = "@phonegetcardsbot"
    while True:
        try:
            print(f"🃏 [Акк {acc_id}] Отправляю 'ткарточка'...", flush=True)
            await client.send_message(bot_username, "ткарточка")
        except Exception as e:
            print(f"❌ [Акк {acc_id}] Ошибка карточек: {e}", flush=True)
        
        # Ждем 121 минуту до следующего раза
        await asyncio.sleep(121 * 60)

# --- ЗАДАЧА ДЛЯ ФЕРМЫ ---
async def daily_farm_task(client, acc_id):
    if acc_id == 5: return
    while True:
        now = datetime.datetime.utcnow()
        target = now.replace(hour=21, minute=10, second=0, microsecond=0)
        if now > target: target += datetime.timedelta(days=1)
        
        wait_secs = (target - now).total_seconds()
        print(f"📡 [Акк {acc_id}] Сбор фермы через {int(wait_secs/60)} мин", flush=True)
        await asyncio.sleep(wait_secs)
        
        await asyncio.sleep((acc_id - 1) * random.randint(60, 150)) # Разброс
        
        try:
            await client.send_message("@phonegetcardsbot", "/tfarm")
            await asyncio.sleep(10)
            async for msg in client.iter_messages("@phonegetcardsbot", limit=1):
                if msg.reply_markup:
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            if "Снять деньги" in btn.text:
                                await smart_click(client, msg, btn)
                                print(f"💰 [Акк {acc_id}] Авто-сбор выполнен!", flush=True)
        except: pass
        await asyncio.sleep(600)

# --- ЗАПУСК ЮЗЕРБОТА ---
async def run_account(session_str, acc_id):
    device = DEVICES[acc_id-1]
    client = TelegramClient(
        StringSession(session_str), API_ID, API_HASH,
        device_model=device["model"], system_version=device["sys"], app_version="10.5.0"
    )

    # КОМАНДА .ping
    @client.on(events.NewMessage(pattern=r'^\.ping', outgoing=True))
    async def ping(event):
        await event.edit("🚀 **Юзербот активен!**")

    # КОМАНДА .farm_now
    @client.on(events.NewMessage(pattern=r'^\.farm_now', outgoing=True))
    async def farm_now(event):
        await event.edit("🚜 Пробую снять деньги...")
        await client.send_message("@phonegetcardsbot", "/tfarm")
        await asyncio.sleep(5)
        async for msg in client.iter_messages("@phonegetcardsbot", limit=1):
            if msg.reply_markup:
                for row in msg.reply_markup.rows:
                    for btn in row.buttons:
                        if "Снять деньги" in btn.text:
                            await smart_click(client, msg, btn)
                            await event.edit("✅ Запрос на снятие отправлен!")
                            return
        await event.edit("❌ Кнопка не найдена.")

    # КОМАНДА .trade @user
    @client.on(events.NewMessage(pattern=r'^\.trade @?(\w+)', outgoing=True))
    async def trade_cmd(event):
        target = event.pattern_match.group(1)
        await event.delete()
        bot = "@phonegetcardsbot"
        await client.send_message(bot, f"/trade @{target}")
        
        steps = ["Добавить телефон", "Ширпотреб", "10", "Подтвердить"]
        for step in steps:
            await asyncio.sleep(5)
            async for msg in client.iter_messages(bot, limit=1):
                if msg.reply_markup:
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            if step in btn.text:
                                await msg.click(btn)
                                break

    async with client:
        me = await client.get_me()
        print(f"🚀 Аккаунт {acc_id} (@{me.username}) запущен!", flush=True)
        
        # Запускаем фоновые задачи
        asyncio.create_task(card_task(client, acc_id))
        asyncio.create_task(daily_farm_task(client, acc_id))
        
        await client.run_until_disconnected()

async def main():
    await asyncio.gather(*[run_account(SESSIONS[i], i+1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    asyncio.run(main())
