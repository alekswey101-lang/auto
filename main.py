# -*- coding: utf-8 -*-

import os
import asyncio
import json
import threading
from datetime import datetime, timedelta
from flask import Flask
from telethon import TelegramClient
from telethon.sessions import StringSession

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route('/')
def health_check(): return "Bot is alive!", 200
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

# --- CONFIG ---
API_ID   = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

SESSIONS = [os.environ[f"SESSION_{i}"] for i in range(1, 6)]

ALL_TASKS = [
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}, {"bot": "@iris_moon_bot", "message": "фарма", "minutes": 240}],
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}],
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}],
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}],
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}],
]

CONFIG_FILE = "schedule.json"

def load_schedule():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f: return json.load(f)
        except: return {}
    return {}

def save_schedule(schedule):
    with open(CONFIG_FILE, "w") as f: json.dump(schedule, f, indent=2)

async def click_farm_buttons(client, bot_username):
    """Ищет и нажимает ВСЕ кнопки для сбора фермы"""
    try:
        await asyncio.sleep(5) # Ждем прогрузки сообщения
        async for message in client.iter_messages(bot_username, limit=3):
            if message.reply_markup:
                clicked = False
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        # Проверяем техническую дату кнопки
                        data = button.data.decode('utf-8') if hasattr(button, 'data') and button.data else ""
                        
                        if data == "farm_claim" or "Снять" in button.text:
                            print(f"🎯 Акк: Нашел кнопку '{button.text}' (data: {data}). Кликаю...", flush=True)
                            try:
                                await message.click(button)
                                clicked = True
                                await asyncio.sleep(2) # Пауза между кликами, если кнопок много
                            except Exception as e:
                                print(f"⚠️ Ошибка при клике на кнопку: {e}", flush=True)
                
                if clicked:
                    return True
    except Exception as e:
        print(f"❌ Ошибка в поиске кнопок: {e}", flush=True)
    return False

async def run_daily_farm(client, acc_id):
    if acc_id == 5:
        print(f"🔇 Акк 5: Сбор фермы отключен", flush=True)
        return

    while True:
        now = datetime.utcnow()
        # Цель: 02:10 по Шымкенту (21:10 UTC)
        target = now.replace(hour=21, minute=10, second=0, microsecond=0)
        if now > target: target += timedelta(days=1)
        
        wait_secs = (target - now).total_seconds()
        print(f"⏳ Акк {acc_id}: Жду 02:10 для сбора (осталось {int(wait_secs/60)} мин)", flush=True)
        await asyncio.sleep(wait_secs)
        
        try:
            print(f"🚜 Акк {acc_id}: Запрашиваю /tfarm...", flush=True)
            await client.send_message("@phonegetcardsbot", "/tfarm")
            
            # Запускаем поиск и клик
            if await click_farm_buttons(client, "@phonegetcardsbot"):
                print(f"✅ Акк {acc_id}: Процесс кликов завершен", flush=True)
            else:
                print(f"⚠️ Акк {acc_id}: Кнопки не найдены", flush=True)
                
        except Exception as e:
            print(f"❌ Ошибка фермы {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(600) # Спим 10 минут, чтобы не сработало повторно

async def run_account(session, tasks, acc_id):
    await asyncio.sleep(acc_id * 3)
    async with TelegramClient(StringSession(session), API_ID, API_HASH) as client:
        print(f"✅ Аккаунт {acc_id} в сети", flush=True)
        asyncio.create_task(run_daily_farm(client, acc_id))

        while True:
            schedule = load_schedule()
            for i, task in enumerate(tasks):
                key = f"acc{acc_id}_task{i}"
                now = datetime.now()
                next_send = datetime.fromisoformat(schedule.get(key, now.isoformat()))
                if now >= next_send:
                    try:
                        await client.send_message(task["bot"], task["message"])
                        schedule[key] = (now + timedelta(minutes=task["minutes"])).isoformat()
                        save_schedule(schedule)
                        print(f"✅ Акк {acc_id}: {task['message']} отправлено", flush=True)
                    except Exception as e: print(f"❌ Ошибка {acc_id}: {e}", flush=True)
            await asyncio.sleep(30)

async def main():
    await asyncio.gather(*[run_account(SESSIONS[i], ALL_TASKS[i], i + 1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    asyncio.run(main())
