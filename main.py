# -*- coding: utf-8 -*-
import os, asyncio, random, datetime, threading, re, sys
from flask import Flask
from pyrogram import Client, filters, handlers

# --- СЕРВЕР ДЛЯ RENDER (KEEP-ALIVE) ---
app_flask = Flask(__name__)
@app_flask.route('/')
def health(): return "Ready and Running", 200

threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

TRADE_BOT = "phonegetcardsbot"
ROULETTE_BOT = "phonegetroulettebot"
MSK = datetime.timezone(datetime.timedelta(hours=3))

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

# --- ОБНОВЛЕННЫЙ БРОНЕБОЙНОЕ КЛИКЕР ---
async def click(client, msg, name):
    if not getattr(msg, "reply_markup", None) or not getattr(msg.reply_markup, "inline_keyboard", None):
        return False
    
    for row_idx, row in enumerate(msg.reply_markup.inline_keyboard):
        for col_idx, btn in enumerate(row):
            btn_text = getattr(btn, "text", "")
            
            if btn_text and name.lower() in btn_text.lower():
                try:
                    # Нажатие теперь ПОЛНОСТЬЮ АКТИВНО (решетки убраны)
                    await msg.click(row_idx, col_idx)
                    await delay(1.0, 2.0)
                    return True
                except Exception as e:
                    print(f"❌ Ошибка физического клика по '{btn_text}': {e}", flush=True)
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
        n = datetime.datetime.now(MSK)
        if n.hour == 1 and n.minute == 0 and not done:
            try:
                await client.send_message(TRADE_BOT, "Тмайнинг")
                await delay()
                await client.send_message(TRADE_BOT, "Ежедневная награда")
                await delay()
                await client.send_message(ROULETTE_BOT, "рулетка")
                await delay()
                done = True
                print(f"☀️ [Акк {acc_id}] Собрал ночные награды!", flush=True)
            except: pass
        if n.hour != 1:
            done = False
        await asyncio.sleep(30)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ОТ БОТОВ ---
async def handle_bot_messages(client, msg):
    if msg.from_user and msg.from_user.id == getattr(client, "me_id", 0):
        return

    try: acc_id = clients.index(client) + 1
    except: return

    st = account_states[acc_id]
    text = (msg.text or msg.caption or "").lower()

    # Таймеры карточек
    if "вам выпал" in text or "карта" in text:
        st["timers"]["tcard"] = 7200  
    elif "через" in text and hasattr(msg, "reply_to_message") and msg.reply_to_message:
        if "ткарточка" in (msg.reply_to_message.text or "").lower():
            sec = parse_time(text)
            st["timers"]["tcard"] = sec if sec > 0 else 300

    # Авто-скупка Контейнеров
    if "раскуплены" in text and "контейнер" in text:
        sec = parse_time(text)
        st["timers"]["containers"] = sec if sec > 0 else 600
        st["locks"]["containers"] = False
    elif "донат" in text and allow_action(acc_id, 2.0):
        if await click(client, msg, "купить"):
            await click(client, msg, "оптом")
            await click(client, msg, "2")
            await click(client, msg, "подтвердить")
            st["timers"]["containers"] = 30
        st["locks"]["containers"] = False
    elif "контейнер" in text and st["locks"]["containers"]:
        if not await click(client, msg, "обновить"):
            st["locks"]["containers"] = False
            st["timers"]["containers"] = 15

    # --- БРОНЕБОЙНОЕ АВТО-ПРИНЯТИЕ ТРЕЙДА ---
    if "предложение обмена" in text or "вам пришло предложение" in text:
        print(f"📩 [Акк {acc_id}] Обнаружено уведомление о трейде! Пробую принять...", flush=True)
        await delay(1.0, 2.0)
        
        # Ищем кнопку по тексту "принять", включая вариант с эмодзи
        for name_variant in ["принять", "✅ принять"]:
            if await click(client, msg, name_variant):
                print(f"🤝 [Акк {acc_id}] Успешно нажал кнопку ПРИНЯТЬ!", flush=True)
                return
        print(f"⚠️ [Акк {acc_id}] Кнопка принять не была нажата.", flush=True)
        return
            
    elif "готовность: ❌" in text and "✅" in text:
        await delay(1.5, 3.0)
        if await click(client, msg, "готов"):
            print(f"👍 [Акк {acc_id}] Нажал кнопку ГОТОВ!", flush=True)
        
    elif "подтвердите обмен" in text or "подтвердите" in text:
        await delay(1.0, 2.0)
        for confirm_variant in ["подтвердить", "подтверждаю"]:
            if await click(client, msg, confirm_variant):
                print(f"🎉 [Акк {acc_id}] Трейд успешно завершен автоматикой!", flush=True)
                return

# --- ТЕКСТОВЫЕ КОМАНДЫ ДЛЯ ТЕБЯ ---
async def handle_my_messages(client, msg):
    if not msg.text: return
    if not msg.from_user or msg.from_user.id != getattr(client, "me_id", 0):
        return

    text = msg.text.lower().strip()
    try: acc_id = clients.index(client) + 1
    except: acc_id = 1
    st = account_states[acc_id]

    if text == ".stop":
        st["running"] = False
        try: await msg.edit(f"⏸ **[Акк {acc_id}] Автоматика поставлена на паузу.**")
        except: pass
        return

    if text == ".start":
        st["running"] = True
        try: await msg.edit(f"▶️ **[Акк {acc_id}] Автоматика успешно запущена!**")
        except: pass
        return

# --- ОДНОВРЕМЕННЫЙ ЗАПУСК ВСЕХ 5 СЕССИЙ ---
async def start_bot():
    global clients
    print("🛠 Инициализация клиентов фермы...", flush=True)
    
    raw_clients = []
    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": 
            continue
        
        c = Client(
            name=f"memory_session_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True
        )
        
        c.add_handler(handlers.MessageHandler(handle_my_messages))
        c.add_handler(handlers.MessageHandler(handle_bot_messages, filters.chat([TRADE_BOT, ROULETTE_BOT])))
        raw_clients.append((i+1, c))

    for acc_num, c in raw_clients:
        try:
            await asyncio.sleep(3.5) # Пауза защиты против краша сессий
            
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
            
            print(f"✅ Аккаунт {acc_num} запущен! (@{me.username or 'NoUsername'} | ID: {me.id})", flush=True)
            
            # Фоновые циклы (Авито полностью удалено отсюда)
            asyncio.create_task(timer_loop(acc_num))
            asyncio.create_task(tcard_loop(c, acc_num))
            asyncio.create_task(container_loop(c, acc_num))
            asyncio.create_task(daily_loop(c, acc_num))
            
        except Exception as e:
            print(f"⚠️ [Ошибка] Сессия {acc_num} не запустилась: {e}", flush=True)

    print(f"💎 Все доступные аккаунты фермы в сети!", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
