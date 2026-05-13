# -*- coding: utf-8 -*-

import os
import asyncio
import json
import threading
import random
from datetime import datetime, timedelta
from flask import Flask
from telethon import TelegramClient
from telethon.sessions import StringSession

# --- FLASK SERVER (Для работы на Render) ---
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

# Задачи для каждого аккаунта
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
    """Специальная логика для клика по кнопке снятия (как на image_2055cf.png)"""
    try:
        # Случайная пауза 4-7 сек, чтобы бот 'прогрузил' кнопки
        await asyncio.sleep(random.randint(4, 7))
        
        async for message in client.iter_messages(bot_username, limit=3):
            if message.reply_markup:
                clicked = False
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        btn_text = button.text
                        # Ищем кнопку по тексту, который виден на image_2055cf.png
                        if "Снять деньги" in btn_text:
                            print(f"🎯 Нашел кнопку '{btn_text}'. Кликаю...", flush=True)
                            
                            # Нажимаем на кнопку
                            await message.click(button)
                            clicked = True
                            
                            # Небольшая пауза после клика для регистрации на сервере
                            await asyncio.sleep(3)
                
                if clicked:
                    return True
    except Exception as e:
        print(f"❌ Ошибка при клике на ферме: {e}", flush=True)
    return False

async def run_daily_farm(client, acc_id):
    """Сбор с фермы в 02:10 по Шымкенту (21:10 UTC)"""
    if acc_id == 5:
        print(f"🔇 Акк 5: Сбор фермы отключен по настройкам", flush=True)
        return

    while True:
        now = datetime.utcnow()
        # 02:10 Шымкент = 21:10 UTC
        target = now.replace(hour=21, minute=10, second=0, microsecond=0)
        
        if now > target:
            target += timedelta(days=1)
        
        wait_secs = (target - now).total_seconds()
        print(f"⏳ Акк {acc_id}: Жду до 02:10 (осталось {int(wait_secs/60)} мин)", flush=True)
        
        await asyncio.sleep(wait_secs)
        
        try:
            # Разносим аккаунты по времени, чтобы не кликали в одну секунду
            await asyncio.sleep(acc_id * 10)
            
            print(f"🚜 Акк {acc_id}: Отправляю /tfarm...", flush=True)
            await client.send_message("@phonegetcardsbot", "/tfarm")
            
            if await click_farm_buttons(client, "@phonegetcardsbot"):
                print(f"✅ Акк {acc_id}: Кнопка нажата успешно!", flush=True)
            else:
                print(f"⚠️ Акк {acc_id}: Кнопка 'Снять деньги' не найдена в сообщении", flush=True)
                
        except Exception as e:
            print(f"❌ Ошибка в задаче фермы акк {acc_id}: {e}", flush=True)
        
        # Спим 10 минут, чтобы избежать случайного повторного срабатывания в ту же минуту
        await asyncio.sleep(600)

async def run_account(session, tasks, acc_id):
    """Запуск работы одного аккаунта"""
    await asyncio.sleep(acc_id * 3) # Плавный старт аккаунтов
    async with TelegramClient(StringSession(session), API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"✅ Аккаунт {acc_id} (@{me.username}) успешно запущен", flush=True)
        
        # Запускаем фоновую задачу фермы
        asyncio.create_task(run_daily_farm(client, acc_id))

        while True:
            schedule = load_schedule()
            for i, task in enumerate(tasks):
                key = f"acc{acc_id}_task{i}"
                now = datetime.now()
                
                # Загружаем время следующей отправки
                next_send_str = schedule.get(key)
                if next_send_str:
                    next_send = datetime.fromisoformat(next_send_str)
                else:
                    next_send = now

                if now >= next_send:
                    try:
                        print(f"➡️ Акк {acc_id} шлет '{task['message']}' в {task['bot']}", flush=True)
                        await client.send_message(task["bot"], task["message"])
                        
                        # Сохраняем время следующей задачи
                        new_next = now + timedelta(minutes=task["minutes"])
                        schedule[key] = new_next.isoformat()
                        save_schedule(schedule)
                    except Exception as e:
                        print(f"❌ Ошибка отправки акк {acc_id}: {e}", flush=True)
            
            # Проверяем задачи каждые 30 секунд
            await asyncio.sleep(30)

async def main():
    print(f"🚀 СТАРТ СИСТЕМЫ: {len(SESSIONS)} аккаунтов", flush=True)
    # Запускаем все аккаунты параллельно
    await asyncio.gather(*[run_account(SESSIONS[i], ALL_TASKS[i], i + 1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен.")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}", flush=True)
