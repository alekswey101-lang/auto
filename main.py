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
    accounts_data = {}

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

TRADE_BOT = "phonegetcardsbot"
ROULETTE_BOT = "phonegetroulettebot"
MAIN_ACC_ID = "7476331360"  # ID твоей основы для слива телефонов
MSK = timezone(timedelta(hours=3))

clients = []
account_states = {}

# Глобальная очередь и флаг занятости для поочередных трейдов
trade_queue = asyncio.Queue()
queue_lock = asyncio.Lock()

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
                    await msg.click(row_idx, col_idx)
                    await delay(1.0, 2.0)
                    return True
                except Exception as e:
                    print(f"❌ Ошибка клика по кнопке '{btn_text}': {e}", flush=True)
                    return False
    return False

# --- БЕЗОПАСНЫЙ ВОРКЕР ОЧЕРЕДИ С БЛОКИРОВКОЙ ---
async def trade_queue_worker():
    while True:
        client, acc_id, count = await trade_queue.get()
        
        # Захватываем лок, чтобы никто другой не мог отправить команду параллельно
        async with queue_lock:
            print(f"⏳ [Очередь] Наступил черед Аккаунта {acc_id}. Отправляю трейд...", flush=True)
            try:
                await client.send_message(TRADE_BOT, f"/trade {MAIN_ACC_ID}")
                print(f"🚀 [Акк {acc_id}] Трейд отправлен основе! Начинаю паузу 2 минуты...", flush=True)
                # Ждем строго 2 минуты БУФЕРА перед тем, как отпустить лок для следующего аккаунта
                await asyncio.sleep(120)
            except Exception as e:
                print(f"❌ [Акк {acc_id}] Ошибка вызова трейда: {e}", flush=True)
                await asyncio.sleep(5) # Короткая пауза при ошибке
                
        trade_queue.task_done()

# --- ФОНОВЫЕ ЦИКЛЫ ---
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
            st["timers"]["tcard"] = 7200
            try: 
                print(f"🃏 [Акк {acc_id}] Отправляю команду 'ткарточка'", flush=True)
                await client.send_message(TRADE_BOT, "ткарточка")
                await delay(2.0, 4.0)
                
                print(f"📊 [Акк {acc_id}] Отправляю команду 'такк' для проверки коллекции", flush=True)
                await client.send_message(TRADE_BOT, "такк")
            except Exception as e: 
                print(f"⚠️ [Акк {acc_id}] Ошибка отправки ткарточки/такк: {e}", flush=True)
                st["timers"]["tcard"] = 60
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

# --- ОБЩАЯ ЛОГИКА ОБРАБОТКИ СООБЩЕНИЙ (И ДЛЯ НОВЫХ, И ДЛЯ ИЗМЕНЕННЫХ) ---
async def process_message_logic(client, msg):
    if msg.from_user and msg.from_user.id == getattr(client, "me_id", 0):
        return

    try: acc_id = clients.index(client) + 1
    except: return

    st = account_states[acc_id]
    text = (msg.text or msg.caption or "").lower()
    
    # 1. Проверка количества телефонов
    if msg.photo and text and "телефонов в коллекции:" in text:
        match = re.search(r"телефонов в коллекции:\s*(\d+)", text)
        if match:
            count = int(match.group(1))
            print(f"📱 [Акк {acc_id}] Телефонов в коллекции: {count}", flush=True)
            if count >= 50:
                print(f"📥 [Акк {acc_id}] Инвентарь забит ({count} шт)! Встаю в очередь на обмен...", flush=True)
                await trade_queue.put((client, acc_id, count))

    # 2. Кулдаун ткарточки
    if "вам выпал" in text or "карта" in text:
        st["timers"]["tcard"] = 7200
    elif "через" in text and hasattr(msg, "reply_to_message") and msg.reply_to_message:
        if "ткарточка" in (msg.reply_to_message.text or "").lower():
            sec = parse_time(text)
            st["timers"]["tcard"] = sec if sec > 0 else 300

    # 3. Контейнеры
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

    # 4. Трейды (триггерятся и при изменении сообщения ботом!)
    if "предложение обмена" in text or "вам пришло предложение" in text:
        print(f"📩 [Акк {acc_id}] Обнаружен входящий трейд! Пробую принять...", flush=True)
        await delay(1.0, 2.0)
        for name_variant in ["принять", "✅ принять"]:
            if await click(msg, name_variant):
                print(f"🤝 [Акк {acc_id}] Трейд успешно ПРИНЯТ!", flush=True)
                return
        return
            
    # Жмет ГОТОВ если слоты забились до 10/10 или основа уже готова
    elif "занято слотов: 10/10" in text or ("готовность: ❌" in text and "✅" in text):
        print(f"⚡ [Акк {acc_id}] Условия выполнены (Слоты 10/10 или основа готова). Нажимаю ГОТОВ...", flush=True)
        await delay(1.0, 2.5)
        if await click(msg, "готов"):
            print(f"👍 [Акк {acc_id}] Успешно нажал кнопку ГОТОВ!", flush=True)
        
    elif "подтвердите обмен" in text or "подтвердите" in text:
        await delay(1.0, 2.0)
        for confirm_variant in ["подтвердить", "подтвержаю"]:
            if await click(msg, confirm_variant):
                print(f"🎉 [Акк {acc_id}] Трейд полностью ПОДТВЕРЖДЕН!", flush=True)
                return

# Перенаправляем новые сообщения в общую логику
async def handle_new_messages(client, msg):
    await process_message_logic(client, msg)

# Перенаправляем отредактированные сообщения в общую логику
async def handle_edited_messages(client, msg):
    await process_message_logic(client, msg)

# --- ГЛАВНЫЙ ЗАПУСК СИСТЕМЫ ---
async def main():
    global clients
    print("🛠 Запуск обновленной фермы (Старт-чек инвентаря + Фикс кнопок)...", flush=True)
    
    # Запускаем независимый воркер очереди
    asyncio.create_task(trade_queue_worker())
    
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
        
        # Перехват новых сообщений
        c.add_handler(handlers.MessageHandler(
            handle_new_messages, 
            filters.chat([TRADE_BOT, ROULETTE_BOT])
        ))
        
        # Перехват обновлений (редактирования) сообщений
        c.add_handler(handlers.EditedMessageHandler(
            handle_edited_messages,
            filters.chat([TRADE_BOT, ROULETTE_BOT])
        ))
        
        raw_clients.append((i+1, c))

    for acc_num, c in raw_clients:
        try:
            await asyncio.sleep(3.0) # Защита от FloodWait при старте сессий
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
            
            # --- ПРИНУДИТЕЛЬНЫЙ СТАРТ-ЧЕК ИНВЕНТАРЯ ---
            try:
                print(f"⚡ [Акк {acc_num}] Проверка инвентаря на старте...", flush=True)
                await c.send_message(TRADE_BOT, "такк")
                await asyncio.sleep(2.0)
            except:
                pass
            
            # Включаем параллельные фоновые циклы задач
            asyncio.create_task(timer_loop(acc_num))
            asyncio.create_task(tcard_loop(c, acc_num))
            asyncio.create_task(container_loop(c, acc_num))
            asyncio.create_task(daily_loop(c, acc_num))
            
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {acc_num}: {e}", flush=True)

    print("💎 Все доступные аккаунты фермы инициализированы и проверены!", flush=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    
