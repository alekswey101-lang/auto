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

# --- ВЕБ-СЕРВЕР ДЛЯ ПОДДЕРЖКИ ЖИЗНИ ---
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

# Стандартные задачи
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
        print(f"❌ Ошибка кнопки: {e}", flush=True)
    return False

async def run_daily_farm(client, acc_id):
    """Сбор с фермы в 02:05 по Шымкенту (21:05 UTC)"""
    if acc_id == 5: 
        print(f"🔇 Акк 5: Пропускаю задачу фермы (согласно настройкам)", flush=True)
        return

    print(f"📡 Акк {acc_id}: Задача 'Ферма' запущена в фоне", flush=True)

    while True:
        now = datetime.utcnow()
        # Цель: 21:05 UTC (это 02:05 Шымкент)
        target = now.replace(hour=21, minute=5, second=0, microsecond=0)
        
        if now > target:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        
        print(f"⏳ Акк {acc_id}: До сбора фермы осталось {int(wait_seconds/3600)}ч {int((wait_seconds%3600)/60)}м", flush=True)
        
        await asyncio.sleep(wait_seconds)
        
        try:
            print(f"🚜 Акк {acc_id}: Начинаю сбор фермы (/tfarm)...", flush=True)
            await client.send_message("@phonegetcardsbot", "/tfarm")
            success = await click_inline_button(client, "@phonegetcardsbot", "Снять деньги с фермы")
            if success:
                print(f"✅ Акк {acc_id}: Кнопка 'Снять деньги' нажата!", flush=True)
            else:
                print(f"⚠️ Акк {acc_id}: Кнопка не найдена в ответе бота", flush=True)
        except Exception as e:
            print(f"❌ Ошибка фермы акк {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(120) # Пауза 2 минуты, чтобы исключить повтор

async def run_account(session, tasks, acc_id):
    """Запуск одного аккаунта"""
    await asyncio.sleep(acc_id * 3) # Небольшая задержка при старте
    async with TelegramClient(StringSession(session), API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"✅ Аккаунт {acc_id} (@{me.username}) в сети", flush=True)
        
        # Запускаем сбор фермы для этого аккаунта
        asyncio.create_task(run_daily_farm(client, acc_id))

        while True:
            schedule = load_schedule()
            for i, task in enumerate(tasks):
                key = f"acc{acc_id}_task{i}"
                now = datetime.now()
                next_send_str = schedule.get(key)
                
                if next_send_str:
                    next_send = datetime.fromisoformat(next_send_str)
                else:
                    next_send = now

                if now >= next_send:
                    try:
                        print(f"➡️ Акк {acc_id} отправляет {task['message']} в {task['bot']}", flush=True)
                        await client.send_message(task["bot"], task["message"])
                        
                        new_next = now + timedelta(minutes=task["minutes"])
                        schedule[key] = new_next.isoformat()
                        save_schedule(schedule)
                        print(f"✅ Акк {acc_id}: Успешно. След. отправка через {task['minutes']} мин", flush=True)
                    except Exception as e:
                        print(f"❌ Ошибка отправки акк {acc_id}: {e}", flush=True)
            
            await asyncio.sleep(30)

async def main():
    print(f"🚀 СТАРТ СИСТЕМЫ: {len(SESSIONS)} аккаунтов", flush=True)
    await asyncio.gather(*[run_account(SESSIONS[i], ALL_TASKS[i], i + 1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
