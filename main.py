# -*- coding: utf-8 -*-
import os, asyncio, json, threading, random, datetime
from flask import Flask
from telethon import TelegramClient, functions, types, events
from telethon.sessions import StringSession

# --- SERVER ---
app = Flask(__name__)
@app.route('/')
def health_check(): return "Userbot is Active!", 200
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ[f"SESSION_{i}"] for i in range(1, 6)]

DEVICES = [
    {"model": "Samsung SM-S918B", "sys": "Android 13"},
    {"model": "Pixel 8 Pro", "sys": "Android 14"},
    {"model": "Xiaomi 13 Ultra", "sys": "Android 13"},
    {"model": "Samsung SM-G998B", "sys": "Android 12"},
    {"model": "Pixel 7a", "sys": "Android 13"}
]

async def smart_click(client, message, button):
    """Клик с чтением ответа (Alert)"""
    try:
        await client(functions.messages.ReadHistoryRequest(peer=message.peer_id, max_id=message.id))
        await asyncio.sleep(random.randint(2, 4))
        result = await client(functions.messages.GetBotCallbackAnswerRequest(
            peer=message.peer_id, msg_id=message.id, data=button.data
        ))
        return result.message if result and result.message else "Клик ок"
    except Exception as e: return f"Ошибка: {e}"

# --- КАРТОЧКИ ---
async def card_task(client, acc_id):
    bot_username = "@phonegetcardsbot"
    while True:
        try:
            print(f"🃏 [Акк {acc_id}] Ткарточка...", flush=True)
            await client.send_message(bot_username, "ткарточка")
        except: pass
        await asyncio.sleep(121 * 60)

# --- ФЕРМА ---
async def daily_farm_task(client, acc_id):
    if acc_id == 5: return 
    while True:
        now = datetime.datetime.utcnow()
        target = now.replace(hour=21, minute=10, second=0, microsecond=0)
        if now > target: target += datetime.timedelta(days=1)
        wait_secs = (target - now).total_seconds()
        print(f"📡 [Акк {acc_id}] Жду сбор {int(wait_secs/60)} мин", flush=True)
        await asyncio.sleep(wait_secs)
        await asyncio.sleep((acc_id - 1) * random.randint(60, 150))
        try:
            await client.send_message("@phonegetcardsbot", "/tfarm")
            await asyncio.sleep(10)
            async for msg in client.iter_messages("@phonegetcardsbot", limit=1):
                if msg.reply_markup:
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            if "Снять деньги" in btn.text or (hasattr(btn, 'data') and btn.data.decode().startswith('farm_claim')):
                                await smart_click(client, msg, btn)
        except: pass
        await asyncio.sleep(600)

# --- ЗАПУСК ---
async def run_account(session_str, acc_id):
    device = DEVICES[acc_id-1]
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH,
                            device_model=device["model"], system_version=device["sys"])

    @client.on(events.NewMessage(pattern=r'^\.ping', outgoing=True))
    async def ping(event): await event.edit("🚀 **Работаю!**")

    @client.on(events.NewMessage(pattern=r'^\.farm_now', outgoing=True))
    async def farm_now(event):
        await event.edit("🚜 Сбор...")
        await client.send_message("@phonegetcardsbot", "/tfarm")
        await asyncio.sleep(5)
        async for msg in client.iter_messages("@phonegetcardsbot", limit=1):
            if msg.reply_markup:
                for row in msg.reply_markup.rows:
                    for btn in row.buttons:
                        if "Снять деньги" in btn.text or (hasattr(btn, 'data') and btn.data.decode().startswith('farm_claim')):
                            ans = await smart_click(client, msg, btn)
                            await event.edit(f"🔔 **Бот:** {ans}"); return
        await event.edit("❌ Кнопка не найдена.")

    # ОБНОВЛЕННЫЙ ТРЕЙД
    @client.on(events.NewMessage(pattern=r'^\.trade @?(\w+)', outgoing=True))
    async def trade_cmd(event):
        target = event.pattern_match.group(1)
        await event.delete()
        bot = "@phonegetcardsbot"
        await client.send_message(bot, f"/trade @{target}")
        
        # Список шагов: текст кнопки ИЛИ начало callback_data
        steps = [
            ("Добавить телефон", "trade_add_phone_start"),
            ("Рабочий телефон", "trd_wrk_start"),
            ("Ширпотреб", "trade_add_rarity"),
            ("10", "trade_add_amount"), # На всякий случай добавил и сюда код
            ("Подтвердить", "trade_confirm")
        ]
        
        for text_tag, data_tag in steps:
            await asyncio.sleep(6)
            async for msg in client.iter_messages(bot, limit=1):
                if msg.reply_markup:
                    found = False
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            c_data = btn.data.decode() if btn.data else ""
                            # Ищем совпадение либо по тексту, либо по началу кода
                            if text_tag in btn.text or c_data.startswith(data_tag):
                                await msg.click(btn)
                                found = True; break
                        if found: break

    async with client:
        me = await client.get_me()
        print(f"✅ Акк {acc_id} (@{me.username}) онлайн!", flush=True)
        asyncio.create_task(card_task(client, acc_id))
        asyncio.create_task(daily_farm_task(client, acc_id))
        await client.run_until_disconnected()

async def main():
    await asyncio.gather(*[run_account(SESSIONS[i], i+1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    asyncio.run(main())
