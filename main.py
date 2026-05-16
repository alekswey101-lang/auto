import asyncio
import random
import re
import sys
import json
import os
import threading
from flask import Flask
from datetime import datetime, timezone, timedelta
from pyrogram import Client, filters, handlers

# --- ВЕБ-СЕРВЕР ДЛЯ KEEP-ALIVE НА RENDER ---
app_flask = Flask(__name__)
@app_flask.route('/')
def health(): return "Ферма запущена и работает", 200

threading.Thread(
    target=lambda: app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), 
    daemon=True
).start()

# --- КОНФИГУРАЦИЯ ---
try:
    with open("accounts.json", "r", encoding="utf-8") as f:
        accounts_data = json.load(f)
except FileNotFoundError:
    accounts_data = {} # Если файла нет, скрипт не упадет

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

# Собираем до 5 сессий из переменных окружения Render
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

TRADE_BOT = "phonegetcardsbot"
ROULETTE_BOT = "phonegetroulettebot"
MSK = timezone(timedelta(hours=3))

clients = []
account_states = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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
    await asyncio.sleep(random.uniform(a, b))

def allow_action(acc_id, min_delay=2):
    st = account_states[acc_id]
    now_time = asyncio.get_event_loop().time()
    if now_time - st["last_action_time"] < min_delay:
        return False
    st["last_action_time"] = now_time
    return True

# --- БРОНЕБОЙНЫЙ ФИЗИЧЕСКИЙ КЛИКЕР ---
async def click(msg, name):
    if not getattr(msg, "reply_markup", None) or not getattr(msg.reply_markup, "inline_keyboard", None):
        return False
    
    for row_idx, row in enumerate(msg.reply_markup.inline_keyboard):
        for col_idx, btn in enumerate(row):
            btn_text = getattr(btn, "text", "")
            if btn_text and name.lower() in btn_text.lower():
                try:
                    # Имитируем реальное нажатие по координатам (обходим защиту бота)
                    await msg.click(row_idx, col_idx)
                    await delay(1.0, 2.0)
                    return True
                except Exception as e:
                    print(f"❌ Ошибка клика по кнопке '{btn_text}': {e}", flush=True)
                    return False
    return False

# --- ФОНОВЫЕ ЦИКЛЫ ДЛЯ КАЖДОГО АККАУНТА ---

async def timer_loop(acc_id):
    st = account_states[acc_id]
    while True:
        for k in list(st["timers"]):
            st["timers"][k] -= 1
            if st["timers"][k] <= 0:
                del st["timers"][k]
        await asyncio.sleep(1)

async def tcard_loop(client, acc_id):
    st = account_states[acc_id]
    while True:
        if st["running"] and "tcard" not in st["timers"]:
            st["timers"]["tcard"] = 120
            try: await client.send_message(TRADE_BOT, "ткарточка")
            except: pass
        await asyncio.sleep(15)

async def container_loop(client, acc_id):
    st = account_states[acc_id]
    while True:
        if st["running"] and "containers" not in st["timers"] and not st["locks"]["containers"]:
            st["locks"]["containers"] = True
            st["timers"]["containers"] = 25
            try: await client.send_message(TRADE_BOT, "Магазин контейнеров")
            except: st["locks"]["containers"] = False
        await asyncio.sleep(8)

async def daily_loop(client, acc_id):
    done = False
    while True:
        n = datetime.now(MSK)
        if n.hour == 1 and n.minute == 0 and not done:
            try:
                await client.send_message(TRADE_BOT, "Тмайнинг")
                await delay()
                await client.send_message(TRADE_BOT, "Ежедневная награда")
                await delay()
                await client.send_message(ROULETTE_BOT, "рулетка")
                done = True
                print(f"☀️ [Акк {acc_id}] Собрал ночные награды!", flush=True)
            except: pass
        if n.hour != 1:
            done = False
        await asyncio.sleep(30)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ОТ БОТОВ ---
async def handle_messages(client, msg):
    # Защита от обработки собственных сообщений юзербота
    if msg.from_user and msg.from_user.id == getattr(client, "me_id", 0):
        return

    try: acc_id = clients.index(client) + 1
    except: return

    st = account_states[acc_id]
    text = (msg.text or msg.caption or "").lower()
    
    # Обработка таймеров ткарточки
    if "вам выпал" in text or "карта" in text:
        st["timers"]["tcard"] = 7200
    elif "через" in text and hasattr(msg, "reply_to_message") and msg.reply_to_message:
        if "ткарточка" in (msg.reply_to_message.text or "").lower():
            sec = parse_time(text)
            st["timers"]["tcard"] = sec if sec > 0 else 300

    # Авто-скупка контейнеров
    if "раскуплены" in text and "контейнер" in text:
        sec = parse_time(text)
        st["timers"]["containers"] = sec if sec > 0 else 600
        st["locks"]["containers"] = False
    elif "донат" in text and allow_action(acc_id, 2.0):
        if await click(msg, "купить"):
            await click(msg, "оптом")
            await click(msg, "2")
            await click(msg, "подтвердить")
            st["timers"]["containers"] = 30
        st["locks"]["containers"] = False
    elif "контейнер" in text and st["locks"]["containers"]:
        if not await click(msg, "обновить"):
            st["locks"]["containers"] = False
            st["timers"]["containers"] = 15

    # --- БРОНЕБОЙНОЕ АВТО-ПРИНЯТИЕ ТРЕЙДА (БЕЗ АВИТО) ---
    if "предложение обмена" in text or "вам пришло предложение" in text:
        print(f"📩 [Акк {acc_id}] Обнаружен входящий трейд! Пробую принять...", flush=True)
        await delay(1.0, 2.0)
        for name_variant in ["принять", "✅ принять"]:
            if await click(msg, name_variant):
                print(f"🤝 [Акк {acc_id}] Трейд успешно ПРИНЯТ!", flush=True)
                return
        return
            
    elif "готовность: ❌" in text and "✅" in text:
        await delay(1.5, 3.0)
        if await click(msg, "готов"):
            print(f"👍 [Акк {acc_id}] Нажал кнопку ГОТОВ!", flush=True)
        
    elif "подтвердите обмен" in text or "подтвердите" in text:
        await delay(1.0, 2.0)
        for confirm_variant in ["подтвердить", "подтверждаю"]:
            if await click(msg, confirm_variant):
                print(f"🎉 [Акк {acc_id}] Трейд полностью ПОДТВЕРЖДЕН!", flush=True)
                return

# --- КОНСОЛЬ УПРАВЛЕНИЯ ФЕРМОЙ ---
async def console():
    while True:
        try:
            cmd = await asyncio.to_thread(sys.stdin.readline)
            cmd = cmd.strip().lower()
            if cmd == "stop":
                for acc_id in account_states:
                    account_states[acc_id]["running"] = False
                print("⏸ Вся ферма поставлена на паузу.", flush=True)
            elif cmd == "start":
                for acc_id in account_states:
                    account_states[acc_id]["running"] = True
                print("▶️ Вся ферма успешно запущена!", flush=True)
        except:
            await asyncio.sleep(5)

# --- ГЛАВНЫЙ ЗАПУСК СИСТЕМЫ ---
async def main():
    global clients
    print("🛠 Запуск фермы из 5 аккаунтов (Авито отключено)...", flush=True)
    
    raw_clients = []
    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": 
            continue
        
        c = Client(
            name=f"farm_session_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True
        )
        
        # Регистрируем обработчик сообщений для каждого аккаунта
        c.add_handler(handlers.MessageHandler(
            handle_messages, 
            filters.chat([TRADE_BOT, ROULETTE_BOT])
        ))
        raw_clients.append((i+1, c))

    for acc_num, c in raw_clients:
        try:
            await asyncio.sleep(3.0)  # Защита от флудвейта при массовом старте
            await c.start()
            clients.append(c)
            
            me = await c.get_me()
            c.me_id = me.id 
                
            account_states[acc_num] = {
                "timers": {},
                "running": True,
                "locks": {"containers": False},
                "last_action_time": 0
            }
            
            print(f"✅ Аккаунт {acc_num} успешно запущен: @{me.username or 'NoUsername'}", flush=True)
            
            # Включаем независимые циклы для каждого аккаунта
            asyncio.create_task(timer_loop(acc_num))
            asyncio.create_task(tcard_loop(c, acc_num))
            asyncio.create_task(container_loop(c, acc_num))
            asyncio.create_task(daily_loop(c, acc_num))
            
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {acc_num}: {e}", flush=True)

    print("💎 Все доступные аккаунты фермы инициализированы!", flush=True)
    asyncio.create_task(console())
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
