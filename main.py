# -*- coding: utf-8 -*-
import asyncio
import random
import re
import sys
import json
import os
from datetime import datetime, timezone, timedelta
from pyrogram import Client, filters
from pyrogram.errors import FloodWait

# =====================================================================
# 🛠️ НАСТРОЙКА АККАУНТА (Впиши свои данные вместо примеров ниже)
# =====================================================================
API_ID = 12345678  # Твой API ID (цифрами, без кавычек)
API_HASH = "твой_api_hash_сюда"  # Твой API Hash (в кавычек)
SESSION_STRING = "твоя_длинная_строка_сессии_telethon_или_pyrogram"  # Строка сессии
# =====================================================================

BOT_NAME = sys.argv[1] if len(sys.argv) > 1 else "main"

# Автоматически генерируем конфиг, чтобы не требовать файл accounts.json
cfg = {
    "api_id": API_ID,
    "api_hash": API_HASH,
    "session": SESSION_STRING
}

SESSION_NAME = cfg["session"]
TRADE_BOT = "phonegetcardsbot"
ROULETTE_BOT = "phonegetroulettebot"
MSK = timezone(timedelta(hours=3))

state = {
    "timers": {},
    "running": True,
    "locks": {"containers": False},
    "last_action_time": 0
}

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

def now():
    return asyncio.get_event_loop().time()

def parse_time(text):
    text = text.replace("\n", " ").lower()
    d = h = m = s = 0
    for value, unit in re.findall(r"(\d+)\s*(дн|ч|мин|сек)", text):
        val = int(value)
        if "дн" in unit: d = val
        elif "ч" in unit: h = val
        elif "мин" in unit: m = val
        elif "сек" in unit: s = val
    return d*86400 + h*3600 + m*60 + s

async def delay(a=0.8, b=2.2):
    await asyncio.sleep(random.uniform(a,b))

def allow_action(min_delay=2):
    if now() - state["last_action_time"] < min_delay:
        return False
    state["last_action_time"] = now()
    return True

async def click(msg, name):
    if not getattr(msg, "reply_markup", None) or not getattr(msg.reply_markup, "inline_keyboard", None):
        return False
    
    target = name.lower().strip()
    for row in msg.reply_markup.inline_keyboard:
        for btn in row:
            if getattr(btn, "text", "") and getattr(btn, "callback_data", None):
                clean_btn_text = re.sub(r'[^\w\s]', '', btn.text).lower().strip()
                
                if target in clean_btn_text or target in btn.text.lower():
                    try:
                        await app.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                        print(f"✅ Успешно нажата кнопка: [{btn.text}]", flush=True)
                        await delay()
                        return True
                    except Exception as e:
                        print(f"❌ Ошибка клика по кнопке [{btn.text}]: {e}", flush=True)
                        return False
    return False

async def tcard_loop():
    while True:
        if state["running"] and "tcard" not in state["timers"]:
            state["timers"]["tcard"] = 120
            try: await app.send_message(TRADE_BOT, "ткарточка")
            except: pass
        await asyncio.sleep(15)

async def daily_loop():
    done = False
    while True:
        n = datetime.now(MSK)
        if n.hour == 1 and n.minute == 0 and not done:
            try:
                await app.send_message(TRADE_BOT, "Тмайнинг")
                await delay()
                await app.send_message(TRADE_BOT, "Ежедневная награда")
                await delay()
                await app.send_message(ROULETTE_BOT, "рулетка")
                done = True
            except: pass
        if n.hour != 1:
            done = False
        await asyncio.sleep(30)

async def container_loop():
    while True:
        if state["running"] and "containers" not in state["timers"] and not state["locks"]["containers"]:
            state["locks"]["containers"] = True
            state["timers"]["containers"] = 25
            try: await app.send_message(TRADE_BOT, "Магазин контейнеров")
            except: state["locks"]["containers"] = False
        await asyncio.sleep(8)

async def timer_loop():
    while True:
        for k in list(state["timers"]):
            state["timers"][k] -= 1
            if state["timers"][k] <= 0:
                del state["timers"][k]
        await asyncio.sleep(1)

async def process_bot_logic(msg):
    text = (msg.text or msg.caption or "").lower()
    
    if "вам выпал" in text or "карта" in text:
        state["timers"]["tcard"] = 7200
    elif "через" in text and hasattr(msg, "reply_to_message") and msg.reply_to_message:
        if "ткарточка" in (msg.reply_to_message.text or "").lower():
            sec = parse_time(text)
            state["timers"]["tcard"] = sec if sec > 0 else 300

    if "раскуплены" in text and "контейнер" in text:
        sec = parse_time(text)
        state["timers"]["containers"] = sec if sec > 0 else 600
        state["locks"]["containers"] = False
    elif "донат" in text and allow_action(2.0):
        if await click(msg, "купить"):
            await click(msg, "оптом")
            await click(msg, "2")
            await click(msg, "подтвердить")
            state["timers"]["containers"] = 30
        state["locks"]["containers"] = False
    elif "контейнер" in text and state["locks"]["containers"]:
        if not await click(msg, "обновить"):
            state["locks"]["containers"] = False
            state["timers"]["containers"] = 15

    if "предложение обмена" in text or "пришло предложение" in text:
        print("🤝 Обнаружен трейд, нажимаю Принять...", flush=True)
        await delay(1.0, 2.0)
        await click(msg, "принять")
        
    elif "готовность:" in text or "занято слотов:" in text:
        print("⏳ Проверяю доступность кнопки Готов...", flush=True)
        await delay(1.5, 2.5)
        await click(msg, "готов")
        
    elif "подтвердите обмен" in text or "подтвердите" in text:
        print("🎉 Финальный этап трейда, нажимаю Подтвердить...", flush=True)
        await delay(1.0, 2.0)
        await click(msg, "подтвердить")

@app.on_message(filters.chat([TRADE_BOT, ROULETTE_BOT]))
async def handle_new_messages(client, msg):
    await process_bot_logic(msg)

@app.on_edited_message(filters.chat([TRADE_BOT, ROULETTE_BOT]))
async def handle_edited_messages(client, msg):
    await process_bot_logic(msg)

@app.on_message(filters.me & filters.command(["t", "trade", "т"], prefixes=["."]))
async def handle_my_trade_commands(client, msg):
    parts = msg.text.split()
    target = None

    if len(parts) == 2 and parts[1] in ACC_MACROS:
        target = ACC_MACROS[parts[1]]
    elif msg.reply_to_message and msg.reply_to_message.from_user:
        user = msg.reply_to_message.from_user
        target = user.username or str(user.id)
    elif len(parts) >= 2:
        target = parts[1].replace("@", "").strip()

    if not target:
        return

    try: await msg.delete()
    except: pass

    bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
    await client.send_message(TRADE_BOT, bot_cmd)

async def console():
    while True:
        try:
            cmd = await asyncio.to_thread(sys.stdin.readline)
            cmd = cmd.strip().lower()
            if cmd == "stop":
                state["running"] = False
                print("Пауза", flush=True)
            elif cmd == "start":
                state["running"] = True
                print("Старт", flush=True)
        except:
            await asyncio.sleep(5)

async def main():
    await app.start()
    print(f"🚀 Сессия '{BOT_NAME}' успешно запущенна! Автопринятие и команды активны.", flush=True)
    asyncio.create_task(timer_loop())
    asyncio.create_task(container_loop())
    asyncio.create_task(tcard_loop())
    asyncio.create_task(daily_loop())
    asyncio.create_task(console())
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
