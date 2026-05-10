# -*- coding: utf-8 -*-

import os
import asyncio
import json
import threading
from datetime import datetime, timedelta
from flask import Flask
from telethon import TelegramClient
from telethon.sessions import StringSession

# --- FLASK SERVER (RENDER HEALTH CHECK) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask запущен на порту {port}", flush=True)
    app.run(host='0.0.0.0', port=port)

# Запуск веб-сервера в отдельном потоке
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
    """Ищет кнопку по внутреннему ID (farm_claim) или по тексту"""
    try:
        await asyncio.sleep(5) 
        async for message in client.iter_messages(bot_username, limit=3):
            if message.reply_markup:
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        # Проверка технического ID (data)
                        current_data = ""
                        if hasattr(button, 'data') and button.data:
                            current_data = button.data.decode('utf-8')
                        
                        if current_data == target_data or button_text in button.text:
                            print(f"🎯 Нашел кнопку! Нажимаю... (Data: {current_data})", flush=True)
                            await message.click(button)
                            return True
    except Exception as e:
        print(f"❌ Ошибка при клике: {e}", flush=True)
    return False

async def run_daily_farm(client, acc_id):
    """Специальная задача для сбора фермы (кроме 5-го акка)"""
    if acc_id == 5:
        print(f"🔇 Акк 5: Сбор фермы полностью проигнорирован.", flush=True)
        return

    print(f"📡 Акк {acc_id}: Фоновая задача 'Ферма' запущена успешно.", flush=True)

    while True:
        now = datetime.utcnow()
        # Шымкент 02:05 = UTC 21:05
        target = now.replace(hour=21, minute=5, second=0, microsecond=0)
        if now > target: target += timedelta(days=1)
        
        wait_secs = (target - now).total_seconds()
        print(f"⏳ Акк {acc_id}: До сбора фермы осталось {int(wait_secs/3600)}ч {int((wait_secs%3600)/60)}м", flush=True)
        
        await asyncio.sleep(wait_secs)
        
        try:
            print(f"🚜 Акк {acc_id}: Время пришло. Отправляю /tfarm...", flush=True)
            await client.send_message("@phonegetcardsbot", "/tfarm")
            success = await click_inline_button(client, "@phonegetcardsbot", "Снять деньги")
            if success:
                print(f"✅ Акк {acc_id}: Ферма собрана успешно!", flush=True)
            else:
                print(f"⚠️ Акк {acc_id}: Не нашел кнопку для сбора.", flush=True)
        except Exception as e:
            print(f"❌ Ошибка в процессе фермы {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(120)

async def run_account(session, tasks, acc_id):
    """Основной цикл для каждого аккаунта"""
    await asyncio.sleep(acc_id * 3) # Плавный вход
    try:
        async with TelegramClient(StringSession(session), API_ID, API_HASH) as client:
            me = await client.get_me()
            print(f"✅ Аккаунт {acc_id} (@{me.username}) успешно подключен!", flush=True)
            
            # Запускаем сбор фермы в фоне
            asyncio.create_task(run_daily_farm(client, acc_id))

            while True:
                schedule = load_schedule()
                for i, task in enumerate(tasks):
                    key = f"acc{acc_id}_task{i}"
                    now = datetime.now()
                    next_send_str = schedule.get(key)
                    
                    next_send = datetime.fromisoformat(next_send_str) if next_send_str else now

                    if now >= next_send:
                        try:
                            print(f"➡️ Акк {acc_id} -> {task['bot']}: {task['message']}", flush=True)
                            await client.send_message(task["bot"], task["message"])
                            schedule[key] = (now + timedelta(minutes=task["minutes"])).isoformat()
                            save_schedule(schedule)
                        except Exception as e:
                            print(f"❌ Ошибка отправки акк {acc_id}: {e}", flush=True)
                
                await asyncio.sleep(30)
    except Exception as e:
        print(f"💥 Критическая ошибка аккаунта {acc_id}: {e}", flush=True)

async def main():
    print("🚀 Инициализация системы для 5 аккаунтов...", flush=True)
    
    # Собираем список задач
    coros = [run_account(SESSIONS[i], ALL_TASKS[i], i + 1) for i in range(len(SESSIONS))]
    
    print(f"📡 Запускаю {len(coros)} параллельных процессов...", flush=True)
    await asyncio.gather(*coros)

if __name__ == "__main__":
    print("🎬 Скрипт запущен. Ожидание сессий...", flush=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Скрипт остановлен вручную.", flush=True)
    except Exception as e:
        print(f"💥 Общий сбой системы: {e}", flush=True)
