# -*- coding: utf-8 -*-

import os
import asyncio
import json
import threading
from datetime import datetime, timedelta
from flask import Flask
from telethon import TelegramClient, events
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

async def click_inline_button(client, bot_username, button_text, target_data="farm_claim"):
    try:
        await asyncio.sleep(5) 
        async for message in client.iter_messages(bot_username, limit=3):
            if message.reply_markup:
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        current_data = ""
                        if hasattr(button, 'data') and button.data:
                            current_data = button.data.decode('utf-8')
                        
                        if current_data == target_data or button_text in button.text:
                            print(f"🎯 Нашел кнопку! (Data: {current_data})", flush=True)
                            await message.click(button)
                            return True
    except Exception as e:
        print(f"❌ Ошибка кнопки: {e}", flush=True)
    return False

async def run_daily_farm(client, acc_id):
    if acc_id == 5:
        print(f"🔇 Акк 5: Сбор фермы отключен", flush=True)
        return

    while True:
        now = datetime.utcnow()
        # Шымкент 02:10 = UTC 21:10
        target = now.replace(hour=21, minute=10, second=0, microsecond=0)
        
        if now > target: target += timedelta(days=1)
        
        wait_secs = (target - now).total_seconds()
        print(f"⏳ Акк {acc_id}: Ожидание фермы до 02:10 (еще {int(wait_secs/3600)}ч {int((wait_secs%3600)/60)}м)", flush=True)
        await asyncio.sleep(wait_secs)
        
        try:
            print(f"🚜 Акк {acc_id}: Сбор по кнопке farm_claim...", flush=True)
            await client.send_message("@phonegetcardsbot", "/tfarm")
            if await click_inline_button(client, "@phonegetcardsbot", "Снять деньги"):
                print(f"✅ Акк {acc_id}: Деньги сняты", flush=True)
        except Exception as e:
            print(f"❌ Ошибка фермы акк {acc_id}: {e}", flush=True)
        await asyncio.sleep(120)

async def run_account(session, tasks, acc_id):
    await asyncio.sleep(acc_id * 3)
    async with TelegramClient(StringSession(session), API_ID, API_HASH) as client:
        print(f"✅ Аккаунт {acc_id} запущен", flush=True)
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
                    except Exception as e: print(f"❌ Ошибка отправки {acc_id}: {e}", flush=True)
            await asyncio.sleep(30)

async def main():
    await asyncio.gather(*[run_account(SESSIONS[i], ALL_TASKS[i], i + 1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    asyncio.run(main())
