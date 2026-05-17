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

with open("accounts.json", "r", encoding="utf-8") as f:
    accounts = json.load(f)

BOT_NAME = sys.argv[1] if len(sys.argv) > 1 else "main"
cfg = accounts.get(BOT_NAME, list(accounts.values())[0])

API_ID = cfg["api_id"]
API_HASH = cfg["api_hash"]
SESSION_NAME = cfg["session"]

TRADE_BOT = "phonegetcardsbot"
ROULETTE_BOT = "phonegetroulettebot"
MSK = timezone(timedelta(hours=3))

state = {
    "timers": {},
    "running": True,
    "locks": {"containers": False},
    "limits": {"phantom": 7000000, "artifact": 550000, "platinum": 300000},
    "avito_mode": "phantom",
    "last_action_time": 0
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

def extract_price(text):
    x = re.search(r"Цена:\s*([\d,]+)", text)
    return int(x.group(1).replace(",", "")) if x else None

async def delay(a=0.8, b=2.2):
    await asyncio.sleep(random.uniform(a,b))

def allow_action(min_delay=2):
    if now() - state["last_action_time"] < min_delay:
        return False
    state["last_action_time"] = now()
    return True

# Умный кликер: очищает кнопки от смайликов (крестиков/галочек) перед сравнением текста
async def click(msg, name):
    if not getattr(msg, "reply_markup", None) or not getattr(msg.reply_markup, "inline_keyboard", None):
        return False
    
    target = name.lower().strip()
    for row in msg.reply_markup.inline_keyboard:
        for btn in row:
            if getattr(btn, "text", "") and getattr(btn, "callback_data", None):
                # Убираем любые смайлики и лишние пробелы из текста кнопки
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

async def avito_loop():
    while True:
        if state["running"] and "avito" not in state["timers"]:
            state["timers"]["avito"] = 15
            try: await app.send_message(TRADE_BOT, "Авито")
            except: pass
        await asyncio.sleep(2)

async def timer_loop():
    while True:
        for k in list(state["timers"]):
            state["timers"][k] -= 1
            if state["timers"][k] <= 0:
                del state["timers"][k]
        await asyncio.sleep(1)

# --- ЕДИНЫЙ ПРОЦЕССОР ДЛЯ ЛОГИКИ ИГРОВОГО БОТА ---
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

    price = extract_price(text)
    if price and ("объявление" in text or "авито" in text):
        state["timers"]["avito"] = 10
        if price <= state["limits"][state["avito_mode"]] and allow_action(1.5):
            await click(msg, "купить")
            await click(msg, "подтвердить")
            state["timers"]["avito"] = 15
        elif allow_action(2.5):
            for btn in ["обновить", "далее", "➡️", "след"]:
                if await click(msg, btn): break

    # --- НАДЕЖНЫЙ БЛОК АВТО-ТРЕЙДА ---
    if "предложение обмена" in text or "пришло предложение" in text:
        print("🤝 Обнаружен трейд, нажимаю Принять...", flush=True)
        await delay(1.0, 2.0)
        await click(msg, "принять")
        
    elif "готовность:" in text or "занято слотов:" in text:
        # Реагирует на любое изменение статуса готовности в меню обмена
        print("⏳ Проверяю доступность кнопки Готов...", flush=True)
        await delay(1.5, 2.5)
        await click(msg, "готов")
        
    elif "подтвердите обмен" in text or "подтвердите" in text:
        print("🎉 Финальный этап трейда, нажимаю Подтвердить...", flush=True)
        await delay(1.0, 2.0)
        await click(msg, "подтвердить")

# Ловим новые сообщения от бота
@app.on_message(filters.chat([TRADE_BOT, ROULETTE_BOT]))
async def handle_new_messages(client, msg):
    await process_bot_logic(msg)

# Ловим ОБНОВЛЕНИЯ старых сообщений (важно для кнопок Готов и Подтвердить)
@app.on_edited_message(filters.chat([TRADE_BOT, ROULETTE_BOT]))
async def handle_edited_messages(client, msg):
    await process_bot_logic(msg)

async def console():
    while True:
        try:
            cmd = await asyncio.to_thread(sys.stdin.readline)
            cmd = cmd.strip().lower()
            if cmd == "stop":
                state["running"] = False
                print("Пауза")
            elif cmd == "start":
                state["running"] = True
                print("Старт")
            elif cmd.startswith("change"):
                parts = cmd.split()
                if len(parts) > 1 and parts[1] in state["limits"]:
                    state["avito_mode"] = parts[1]
                    print(f"Режим: {parts[1]}")
        except:
            await asyncio.sleep(5)

async def main():
    await app.start()
    print(f"🚀 Сессия {BOT_NAME} успешно запущена и слушает {TRADE_BOT}!", flush=True)
    asyncio.create_task(timer_loop())
    asyncio.create_task(container_loop())
    asyncio.create_task(avito_loop())
    asyncio.create_task(tcard_loop())
    asyncio.create_task(daily_loop())
    asyncio.create_task(console())
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
