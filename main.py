# -*- coding: utf-8 -*-
import os, asyncio, json, threading, random, datetime
from flask import Flask
from telethon import TelegramClient, functions, types, events
from telethon.sessions import StringSession

# --- СЕРВЕР ДЛЯ ПОДДЕРЖКИ РАБОТЫ ---
app = Flask(__name__)
@app.route('/')
def health_check(): return "Userbot is running!", 200
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()

# --- КОНФИГУРАЦИЯ ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ[f"SESSION_{i}"] for i in range(1, 6)]

# Модели устройств для маскировки
DEVICES = [
    {"model": "Samsung SM-S918B", "sys": "Android 13"},
    {"model": "Pixel 7 Pro", "sys": "Android 14"},
    {"model": "Xiaomi 13 Ultra", "sys": "Android 13"},
    {"model": "Samsung SM-G998B", "sys": "Android 12"},
    {"model": "Pixel 6a", "sys": "Android 13"}
]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def smart_click(client, message, button):
    """Имитация человеческого клика с чтением истории"""
    try:
        await client(functions.messages.ReadHistoryRequest(peer=message.peer_id, max_id=message.id))
        await asyncio.sleep(random.randint(2, 4))
        await client(functions.messages.GetBotCallbackAnswerRequest(
            peer=message.peer_id, msg_id=message.id, data=button.data
        ))
        return True
    except: return False

# --- ЛОГИКА ФЕРМЫ ---
async def daily_farm_task(client, acc_id):
    if acc_id == 5: return
    while True:
        now = datetime.datetime.utcnow()
        # 02:10 Шымкент = 21:10 UTC
        target = now.replace(hour=21, minute=10, second=0, microsecond=0)
        if now > target: target += datetime.timedelta(days=1)
        
        print(f"📡 [Акк {acc_id}] Сбор через {int((target-now).total_seconds()/60)} мин", flush=True)
        await asyncio.sleep((target - now).total_seconds())
        
        # Разброс между аккаунтами 1-3 минуты
        await asyncio.sleep((acc_id - 1) * random.randint(60, 150))
        
        try:
            await client.send_message("@phonegetcardsbot", "/tfarm")
            await asyncio.sleep(random.randint(5, 10))
            async for msg in client.iter_messages("@phonegetcardsbot", limit=1):
                if msg.reply_markup:
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            if "Снять деньги" in btn.text:
                                await smart_click(client, msg, btn)
                                print(f"💰 [Акк {acc_id}] Ферма собрана!", flush=True)
        except Exception as e: print(f"❌ [Акк {acc_id}] Ошибка фермы: {e}", flush=True)
        await asyncio.sleep(600)

# --- ЗАПУСК АККАУНТА ---
async def run_account(session_str, acc_id):
    device = DEVICES[acc_id-1]
    client = TelegramClient(
        StringSession(session_str), API_ID, API_HASH,
        device_model=device["model"], system_version=device["sys"], app_version="10.5.0"
    )

    # КОМАНДА: .trade @username
    @client.on(events.NewMessage(pattern=r'\.trade @(\w+)', outgoing=True))
    async def trade_cmd(event):
        target = event.pattern_match.group(1)
        await event.delete()
        bot = "@phonegetcardsbot"
        await client.send_message(bot, f"/trade @{target}")
        
        steps = ["Добавить телефон", "Ширпотреб", "10", "Подтвердить"]
        for step in steps:
            await asyncio.sleep(random.randint(4, 6))
            async for msg in client.iter_messages(bot, limit=1):
                if msg.reply_markup:
                    found = False
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            if step in btn.text:
                                await msg.click(btn)
                                print(f"🔹 [Акк {acc_id}] {step} - OK", flush=True)
                                found = True; break
                        if found: break

    # КОМАНДА: .farm_now (принудительный сбор)
    @client.on(events.NewMessage(pattern=r'\.farm_now', outgoing=True))
    async def farm_now_cmd(event):
        await event.edit("🚜 Сбор запускается...")
        await client.send_message("@phonegetcardsbot", "/tfarm")
        await asyncio.sleep(5)
        async for msg in client.iter_messages("@phonegetcardsbot", limit=1):
            if msg.reply_markup:
                for row in msg.reply_markup.rows:
                    for btn in row.buttons:
                        if "Снять деньги" in btn.text:
                            await smart_click(client, msg, btn)
                            await event.edit("✅ Ферма собрана!")
                            return
        await event.edit("❌ Кнопка не найдена.")

    async with client:
        print(f"🚀 Юзербот {acc_id} онлайн!", flush=True)
        asyncio.create_task(daily_farm_task(client, acc_id))
        
        # Цикл карточек (пример для Акка 1)
        while True:
            # Тут можно добавить логику "ткарточка" как в прошлых версиях
            await asyncio.sleep(120 * 60)
            if acc_id == 1:
                await client.send_message("@phonegetcardsbot", "ткарточка")

async def main():
    await asyncio.gather(*[run_account(SESSIONS[i], i+1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    asyncio.run(main())
