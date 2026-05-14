# -*- coding: utf-8 -*-

import os
import asyncio
import json
import threading
import random
from datetime import datetime, timedelta
from flask import Flask
from telethon import TelegramClient, functions
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

async def send_direct_callback(client, message, button):
    """Вариант 1: Отправка Callback-запроса напрямую в API Telegram"""
    try:
        bot_peer = await client.get_input_entity(message.peer_id)
        
        # Формируем прямой низкоуровневый запрос клика
        request = functions.messages.GetBotCallbackAnswerRequest(
            peer=bot_peer,
            msg_id=message.id,
            data=button.data
        )
        
        # Отправляем запрос и перехватываем системный ответ (Alert)
        response = await client(request)
        
        if response and hasattr(response, 'message') and response.message:
            print(f"💬 Системный ответ от бота: {response.message}", flush=True)
        else:
            print(f"✅ Системный клик успешно ушел в API.", flush=True)
        return True
    except Exception as e:
        print(f"⚠️ Ошибка прямого API-клика: {e}", flush=True)
        return False

async def click_farm_buttons(client, bot_username):
    try:
        await asyncio.sleep(random.randint(5, 8)) # Человеческая пауза
        
        # Берем самое последнее сообщение бота
        async for message in client.iter_messages(bot_username, limit=1):
            if message.reply_markup:
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        # Проверяем кнопку «Снять деньги» или индификатор farm_claim
                        if "Снять деньги" in button.text or (hasattr(button, 'data') and button.data.decode() == 'farm_claim'):
                            print(f"🎯 Найдена кнопка [{button.text}]. Применяю прямой API обход...", flush=True)
                            
                            # Пробуем отправить прямой callback
                            await send_direct_callback(client, message, button)
                            await asyncio.sleep(2)
                            return True
    except Exception as e:
        print(f"❌ Ошибка в модуле обхода кнопок: {e}", flush=True)
    return False

async def run_daily_farm(client, acc_id):
    if acc_id == 5:
        print(f"🔇 Акк 5: Сбор фермы отключен.", flush=True)
        return

    while True:
        now = datetime.utcnow()
        # Шымкент 02:10 = UTC 21:10
        target = now.replace(hour=21, minute=10, second=0, microsecond=0)
        if now > target: target += timedelta(days=1)
        
        wait_secs = (target - now).total_seconds()
        print(f"⏳ Акк {acc_id}: Ожидание фермы до 02:10 (осталось {int(wait_secs/60)} мин)", flush=True)
        await asyncio.sleep(wait_secs)
        
        try:
            # Задержка между аккаунтами, чтобы запросы не шли одновременно
            await asyncio.sleep(acc_id * 8)
            
            print(f"🚜 Акк {acc_id}: Запрашиваю меню /tfarm...", flush=True)
            await client.send_message("@phonegetcardsbot", "/tfarm")
            
            if await click_farm_buttons(client, "@phonegetcardsbot"):
                print(f"✅ Акк {acc_id}: API-запрос на снятие отправлен.", flush=True)
            else:
                print(f"⚠️ Акк {acc_id}: Кнопка для сбора не найдена.", flush=True)
                
        except Exception as e:
            print(f"❌ Ошибка фермы на акк {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(600)

async def run_account(session, tasks, acc_id):
    await asyncio.sleep(acc_id * 3)
    
    # Вариант 2: Подменяем параметры сессии под реальный Android-смартфон
    client = TelegramClient(
        StringSession(session), 
        API_ID, 
        API_HASH,
        device_model="Samsung SM-G998B",  # Маскировка под Samsung S21 Ultra
        system_version="Android 13",       # Маскировка ОС
        app_version="10.3.1"               # Маскировка версии Telegram
    )
    
    async with client:
        me = await client.get_me()
        print(f"✅ Аккаунт {acc_id} (@{me.username}) успешно запущен с Android-параметрами!", flush=True)
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
                        print(f"❌ Ошибка отправки {acc_id}: {e}", flush=True)
            await asyncio.sleep(30)

async def main():
    await asyncio.gather(*[run_account(SESSIONS[i], ALL_TASKS[i], i + 1) for i in range(len(SESSIONS))])

if __name__ == "__main__":
    asyncio.run(main())
