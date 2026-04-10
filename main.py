# -*- coding: utf-8 -*-

import os  # ОС должен быть в самом верху!
import asyncio
import json
import threading
from datetime import datetime, timedelta
from flask import Flask
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# --- БЛОК ДЛЯ RENDER (FLASK) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive!", 200

def run_flask():
    # Берем порт из переменной окружения Render или ставим 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Запускаем сервер в отдельном потоке
threading.Thread(target=run_flask, daemon=True).start()
# ------------------------------

API_ID   = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

# 4 сессии
SESSIONS = [
    os.environ["SESSION_1"],
    os.environ["SESSION_2"],
    os.environ["SESSION_3"],
    os.environ["SESSION_4"],
]

# задачи
ALL_TASKS = [
    # АКК 1
    [
        {"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121},
        {"bot": "@iris_moon_bot",    "message": "фарма",     "minutes": 240},
    ],
    # АКК 2
    [
        {"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121},
    ],
    # АКК 3
    [
        {"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121},
    ],
    # АКК 4
    [
        {"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121},
    ],
]

CONFIG_FILE = "schedule.json"

def load_schedule():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_schedule(schedule):
    with open(CONFIG_FILE, "w") as f:
        json.dump(schedule, f, indent=2)

async def send_task(client, task, key, schedule):
    now = datetime.now()

    if key not in schedule:
        next_send = now
    else:
        next_send = datetime.fromisoformat(schedule[key])

    if now >= next_send:
        try:
            print(f"➡️ Пытаюсь отправить {task['message']} в {task['bot']}")
            await client.send_message(task["bot"], task["message"])
            
            next_send = now + timedelta(minutes=task["minutes"])
            schedule[key] = next_send.isoformat()
            save_schedule(schedule)
            print(f"[{now.strftime('%H:%M:%S')}] ✅ {task['bot']} ← {task['message']}")
        except FloodWaitError as e:
            print(f"⏳ FloodWait {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Ошибка: {e}")

async def run_account(session, tasks, acc_id):
    async with TelegramClient(StringSession(session), API_ID, API_HASH) as client:
        try:
            me = await client.get_me()
            print(f"✅ Аккаунт {acc_id}: @{me.username}")
        except Exception as e:
            print(f"❌ Аккаунт {acc_id} ошибка входа: {e}")
            return

        while True:
            schedule = load_schedule()
            for i, task in enumerate(tasks):
                key = f"acc{acc_id}_task{i}"
                await send_task(client, task, key, schedule)
            await asyncio.sleep(10)

async def main():
    print("🚀 Запуск 4 аккаунтов...")
    await asyncio.gather(*[
        run_account(SESSIONS[i], ALL_TASKS[i], i + 1)
        for i in range(len(SESSIONS))
    ])

if __name__ == "__main__":
    import time
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"⚠️ Ошибка: {e}, рестарт через 30 сек")
            time.sleep(30)
