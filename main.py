# -*- coding: utf-8 -*-

import os
import asyncio
import json
import threading
from datetime import datetime, timedelta
from flask import Flask
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# --- ВЕБ-СЕРВЕР ДЛЯ ПОДДЕРЖКИ ЖИЗНИ (RENDER + CRON-JOB) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- НАСТРОЙКИ API ---
API_ID   = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

# 5 рабочих сессий
SESSIONS = [
    os.environ["SESSION_1"],
    os.environ["SESSION_2"],
    os.environ["SESSION_3"],
    os.environ["SESSION_4"],
    os.environ["SESSION_5"],
]

# Стандартные цикличные задачи
ALL_TASKS = [
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}, {"bot": "@iris_moon_bot", "message": "фарма", "minutes": 240}], # Акк 1
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}], # Акк 2
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}], # Акк 3
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}], # Акк 4
    [{"bot": "@phonegetcardsbot", "message": "ткарточка", "minutes": 121}], # Акк 5
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

async def click_inline_button(client, bot_username, button_text):
    """Логика поиска и нажатия кнопки"""
    try:
        await asyncio.sleep(5) 
        async for message in client.iter_messages(bot_username, limit=3):
            if message.reply_markup:
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        if button_text in button.text:
                            await message.click(button)
                            return True
    except Exception as e:
        print(f"❌ Ошибка кнопки: {e}")
    return False

async def run_daily_farm(client, acc_id):
    """Сбор с фермы в 02:05 по Шымкенту (21:05 UTC)"""
    if acc_id == 5: # Пятый аккаунт отдыхает
        return

    while True:
        now = datetime.utcnow()
        # Ставим цель на 21:05 UTC (это 02:05 в Шымкенте)
        target = now.replace(hour=21, minute=5, second=0, microsecond=0)
        
        if now > target:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        print(f"⏳ Акк {acc_id}: сбор фермы через {int(wait_seconds/3600)}ч")
        
        await asyncio.sleep(wait_seconds)
        
        try:
            print(f"🚜 Акк {acc_id}: Снимаю деньги...")
            await client.send_message("@phonegetcardsbot", "/tfarm")
            success = await click_inline_button(client, "@phonegetcardsbot", "Снять деньги с фермы")
            if success:
                print(f"✅ Акк {acc_id}: Деньги сняты")
        except Exception as e:
            print(f"❌ Ошибка фермы акк {acc_id}: {e}")
        
        await asyncio.sleep(60)

async def run_account(session, tasks, acc_id):
    """Запуск одного аккаунта"""
    await asyncio.sleep(acc_id * 5) # Плавный запуск
    async with TelegramClient(StringSession(session), API_ID, API_HASH) as client:
        print(f"✅ Аккаунт {acc_id} в сети")
        
        # Фоновая задача на ежедневный сбор
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
                        print(f"[{now.strftime('%H:%M')}] ✅ Сообщение от Акк {acc_id}")
                    except Exception as e:
                        print(f"❌ Ошибка отправки: {e}")
            
            await asyncio.sleep(30)

async def main():
    print(f"🚀 Старт системы на {len(SESSIONS)} аккаунтов...")
    await asyncio.gather(*[run_account(SESSIONS[i], ALL_TASKS[i], i + 1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
