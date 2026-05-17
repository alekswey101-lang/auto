# -*- coding: utf-8 -*-
import asyncio
import random
import re
import sys
import os
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask

# Настройка веб-сервера для Render
app_flask = Flask(__name__)
@app_flask.route('/')
def health(): return "OK", 200

try:
    threading.Thread(
        target=lambda: app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), 
        daemon=True
    ).start()
except Exception as e:
    print(f"⚠️ Предупреждение Flask: {e}", flush=True)

# Глобальный перехват ошибок импорта Pyrogram
try:
    from pyrogram import Client, filters
    from pyrogram.errors import FloodWait
except Exception as e:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА PYROGRAM: {e}", flush=True)
    sys.exit(1)

# --- БЛОК ИНИЦИАЛИЗАЦИИ И ПРОВЕРКИ ПЕРЕМЕННЫХ ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")

SESSION_STRING = (
    os.environ.get("SESSION") or 
    os.environ.get("SESSION_1") or 
    os.environ.get("SESSION_2") or 
    os.environ.get("SESSION_3") or 
    os.environ.get("SESSION_4") or 
    os.environ.get("SESSION_5")
)

if not all([API_ID, API_HASH, SESSION_STRING]):
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют переменные окружения на Render!", flush=True)
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: API_ID должен состоять только из цифр!", flush=True)
    sys.exit(1)

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

app = Client(
    name="render_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

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
                        print(f"✅ Нажата кнопка: [{btn.text}]", flush=True)
                        await delay()
                        return True
                    except Exception as e:
                        print(f"❌ Ошибка клика по кнопке [{btn.text}]: {e}", flush=True)
                        return False
    return False

# --- АСИНХРОННЫЕ ЦИКЛЫ АВТОМАТИЗАЦИИ ---
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
        print("🤝 Обнаружен трейд, принимаю...", flush=True)
        await delay(1.0, 2.0)
        await click(msg, "принять")
    elif "готовность:" in text or "занято слотов:" in text:
        await delay(1.5, 2.5)
        await click(msg, "готов")
    elif "подтвердите обмен" in text or "подтвердите" in text:
        await delay(1.0, 2.0)
        await click(msg, "подтвердить")

@app.on_message(filters.chat([TRADE_BOT, ROULETTE_BOT]))
async def handle_new_messages(client, msg):
    await process_bot_logic(msg)

@app.on_edited_message(filters.chat([TRADE_BOT, ROULETTE_BOT]))
async def handle_edited_messages(client, msg):
    await process_bot_logic(msg)

# --- ФИКСИРОВАННЫЙ БЛОК КОМАНДЫ .t (РАБОТАЕТ ВЕЗДЕ) ---
@app.on_message(filters.me & filters.command(["t", "trade", "т"], prefixes=["."]))
async def handle_my_trade_commands(client, msg):
    parts = msg.text.split()
    target = None

    # 1. Макросы .t 1, .t 2 и т.д.
    if len(parts) == 2 and parts[1] in ACC_MACROS:
        target = ACC_MACROS[parts[1]]
    # 2. Репли (ответ на сообщение)
    elif msg.reply_to_message and msg.reply_to_message.from_user:
        user = msg.reply_to_message.from_user
        target = user.username or str(user.id)
    # 3. Прямой юзернейм типа .t @username
    elif len(parts) >= 2:
        target = parts[1].replace("@", "").strip()

    if not target:
        return

    try: await msg.delete()
    except: pass

    bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
    
    # Отправляем команду СТРОГО в чат к TRADE_BOT, даже если написали её в другом месте
    await client.send_message(TRADE_BOT, bot_cmd)

async def main():
    try:
        await app.start()
        print("🚀 Бот успешно авторизовался в Telegram на базе Pyrogram!", flush=True)
        asyncio.create_task(timer_loop())
        asyncio.create_task(container_loop())
        asyncio.create_task(tcard_loop())
        asyncio.create_task(daily_loop())
        await asyncio.Event().wait()
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ СТАРТЕ АСИНХРОННОГО ЦИКЛА: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        app.run(main())
    except Exception as main_err:
        print(f"❌ КРИТИЧЕСКИЙ СБОЙ В МЕТОДЕ RUN: {main_err}", flush=True)
        sys.exit(1)
