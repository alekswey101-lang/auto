# -*- coding: utf-8 -*-
import os
import asyncio
import datetime
import threading
from flask import Flask
from pyrogram import Client, handlers, filters
from pyrogram import raw

# --- СЕРВЕР ДЛЯ RENDER (KEEP-ALIVE) ---
app = Flask(__name__)
@app.route('/')
def health(): 
    return "Ready and Running", 200

threading.Thread(
    target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), 
    daemon=True
).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

bot_chat = "phonegetcardsbot"
iris_bot_chat = "iris_moon_bot"  # Юзернейм бота Iris Moon
clients = []
current_bot_msg = {}  
is_collecting = {}    

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

# --- ИДЕАЛЬНЫЙ СКОРОСТНОЙ КЛИКЕР ---
async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                    if btn.callback_data:
                        try:
                            await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=1)
                            return True
                        except:
                            return True
    except:
        pass
    return False

# --- АНТИ-РАССИНХРОННЫЙ ДВИЖОК КЛИКОВ ---
async def execute_menu_step(client, acc_id, step_name, keywords, pick_best, last_fp):
    await asyncio.sleep(0.15)
    
    forbidden = ["назад", "back", "отмена", "cancel", "вернуться", "главное", "меню", "быстрый выбор", "быстрый", "⬅️", "🔙", "trade_refresh", "trade_fast_mode"]

    for attempt in range(40):
        try:
            msg = current_bot_msg.get(acc_id)
            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.05)
                continue

            current_fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
            
            if last_fp and current_fp == last_fp:
                await asyncio.sleep(0.05)
                continue

            valid_buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if not btn.callback_data: 
                        continue
                        
                    t_low = btn.text.lower().strip()
                    d_low = btn.callback_data.lower().strip()
                    
                    if any(x in t_low or x in d_low for x in forbidden):
                        continue
                    if any(x in t_low or x in d_low for x in ["изменить", "подтвердить", "готов"]):
                        continue
                        
                    valid_buttons.append(btn)

            if not valid_buttons:
                await asyncio.sleep(0.05)
                continue

            if pick_best:
                target_btn = None
                
                if step_name == "Выбор Редкости":
                    for priority_keyword in ["мистические", "редкие", "хроматические", "необычные", "арканы", "ширпотреб"]:
                        for btn in valid_buttons:
                            if priority_keyword in btn.text.lower():
                                target_btn = btn
                                break
                        if target_btn:
                            break
                
                if not target_btn:
                    target_btn = valid_buttons[0]

                try: 
                    await client.request_callback_answer(msg.chat.id, msg.id, target_btn.callback_data, timeout=1)
                    return True, current_fp
                except:
                    await asyncio.sleep(0.05)
                    continue

            else:
                for btn in valid_buttons:
                    t_low = btn.text.lower().strip()
                    d_low = btn.callback_data.lower().strip()
                    
                    for kw in keywords:
                        if kw.lower().strip() in t_low or kw.lower().strip() in d_low:
                            try:
                                await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                                return True, current_fp
                            except:
                                await asyncio.sleep(0.05)
                                continue
        except:
            pass
        await asyncio.sleep(0.05)
            
    return False, last_fp

# --- СБОРЩИК ПРЕДМЕТОВ Х10 ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Запуск полностью синхронизированного кликера...", flush=True)
    is_collecting[acc_id] = True  
    added_count = 0  
    
    current_fp = ""
    msg = current_bot_msg.get(acc_id)
    if msg and msg.reply_markup:
        current_fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
    
    for loop_index in range(1, 30):
        if added_count >= 10:
            break

        msg = current_bot_msg.get(acc_id)
        if msg and msg.text:
            msg_text = msg.text.lower()
            if "10/10" in msg_text and "слот" in msg_text:
                break

        res, current_fp = await execute_menu_step(client, acc_id, "Добавить телефон", ["добавить телефон", "trade_add_phone"], False, current_fp)
        if not res: break

        res, current_fp = await execute_menu_step(client, acc_id, "Выбор Состояния", [], True, current_fp)
        if not res: continue

        res, current_fp = await execute_menu_step(client, acc_id, "Выбор Редкости", [], True, current_fp)
        if not res: continue

        res, current_fp = await execute_menu_step(client, acc_id, "Выбор Модели", [], True, current_fp)
        if not res: continue

        res, current_fp = await execute_menu_step(client, acc_id, "Количество 1шт", ["добавить 1 шт.", "trade_add_single"], False, current_fp)
        if res:
            added_count += 1  
            print(f"➕ [Акк {acc_id}] Телефон №{added_count} успешно добавлен.", flush=True)
        else:
            continue

    is_collecting[acc_id] = False

    print(f"⚖️ [Акк {acc_id}] Набор завершен. Фиксирую сделку...", flush=True)
    for _ in range(10):
        msg = current_bot_msg.get(acc_id)
        if await click(client, msg, "готов"):
            break
        await asyncio.sleep(0.3)

    await asyncio.sleep(0.8)

    for _ in range(10):
        msg = current_bot_msg.get(acc_id)
        if await click(client, msg, "подтвердить"):
            break
        await asyncio.sleep(0.3)

# --- МГНОВЕННЫЙ ОБРАБОТЧИК СОБЫТИЙ ---
async def process_bot_logic(client, message, acc_id):
    if not message:
        return

    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                t_low = btn.text.lower()
                d_low = btn.callback_data.lower()
                if "собрать деньги" in t_low or "farm_claim" in d_low:
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        print(f"💰 [Акк {acc_id}] Деньги с ТМайнинга успешно собраны!", flush=True)
                        return
                    except:
                        pass

    if not message.text:
        return

    text = message.text.lower()

    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return

        for _ in range(10):
            try:
                async for fresh_msg in client.get_chat_history(bot_chat, limit=1):
                    if fresh_msg.reply_markup:
                        if await click(client, fresh_msg, "принять"):
                            print(f"✅ [Акк {acc_id}] Входящий трейд принят!", flush=True)
                            await asyncio.sleep(0.2)
                            asyncio.create_task(receiver_trade_logic(client, acc_id))
                            return
            except:
                pass
            await asyncio.sleep(0.06)
        return

    if "подтвердите обмен" in text or "подтвердите" in text:
        await click(client, message, "подтвердить")
        return

# --- СТАБИЛЬНЫЙ ПУЛИНГ ---
async def poll_bot_messages(client, acc_id):
    last_msg_id = 0
    last_buttons_fp = ""
    
    while True:
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                buttons_fp = ""
                if msg.reply_markup:
                    buttons_fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
                
                current_bot_msg[acc_id] = msg
                
                if msg.id != last_msg_id or buttons_fp != last_buttons_fp:
                    last_msg_id = msg.id
                    last_buttons_fp = buttons_fp
                    await process_bot_logic(client, msg, acc_id)
                break
        except:
            pass
        await asyncio.sleep(0.15) 

# --- ОСНОВА ---
async def sender_confirm_logic(client, acc_id):
    print(f"⏳ [Акк {acc_id} - Основа] Ожидаю фиксации предметов твинком...", flush=True)
    for _ in range(120):
        await asyncio.sleep(0.4)
        try:
            msg = current_bot_msg.get(acc_id)
            if not msg or not msg.text:
                continue
            text = msg.text.lower()
            if "готовность:" in text and text.count("✅") >= 1:
                print(f"✍️ [Акк {acc_id} - Основа] Твинк готов. Завершаю трейд...", flush=True)
                await click(client, msg, "готов")
                await asyncio.sleep(0.8)
                await click(client, msg, "подтвердить")
                break
        except:
            pass

async def handle_my_messages(client, message):
    if not message.text: return
    my_id = getattr(client, "me_id", 0)
    if not message.from_user or message.from_user.id != my_id: return

    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    try: acc_id = clients.index(client) + 1
    except: acc_id = 1

    if cmd == ".ping":
        try: await message.edit("🚀 **Юзербот запущен! Защита от рассинхрона и фарм Iris активны.**")
        except: pass
        return

    if cmd in [".trade", ".t", ".т"]:
        target = None
        if len(parts) == 2 and parts[1] in ACC_MACROS:
            target = ACC_MACROS[parts[1]]
        elif message.reply_to_message and message.reply_to_message.from_user:
            user = message.reply_to_message.from_user
            target = user.username or str(user.id)
        elif len(parts) >= 2:
            target = parts[1].replace("@", "").strip()

        if not target: return
        try: await message.delete()
        except: pass

        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        await client.send_message(bot_chat, bot_cmd)
        asyncio.create_task(sender_confirm_logic(client, acc_id))

# --- УМНЫЙ ПЛАНИРОВЩИК ЗАДАЧ, ТМАЙНИНГА И ИРИС ФАРМЫ ---
async def bg_tasks(client, acc_id):
    # Первичные отправки при старте
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    
    if acc_id == 1:
        try: 
            print("🌙 [Акк 1] Стартовый запуск фармы в Iris Moon...", flush=True)
            await client.send_message(iris_bot_chat, "фарма")
        except: pass

    claimed_today = False
    iris_timer = 0  # Счётчик минут для Iris Moon (4 часа = 240 минут)
    
    while True:
        try:
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)
            
            # --- 1. ЛОГИКА ТМАЙНИНГА (00:10 МСК) ---
            if msk_now.hour == 0 and msk_now.minute == 10:
                if not claimed_today:
                    print(f"⏰ [Акк {acc_id}] Наступило 00:10 по МСК! Отправляю команду на сбор майнинг-фермы...", flush=True)
                    await client.send_message(bot_chat, "тмайнинг")
                    claimed_today = True
            else:
                if msk_now.hour == 0 and msk_now.minute == 11:
                    claimed_today = False
            
            # --- 2. ЛОГИКА АВТОФАРМЫ IRIS (Каждые 4 часа только для Акк 1) ---
            if acc_id == 1:
                iris_timer += 1
                if iris_timer >= 240:  # Прошло 240 минут (4 часа)
                    print("🌙 [Акк 1] Прошло 4 часа! Отправляю 'фарма' в Iris Moon bot...", flush=True)
                    await client.send_message(iris_bot_chat, "фарма")
                    iris_timer = 0  # Сбрасываем таймер
                    
            # --- 3. ПОДДЕРЖАНИЕ АКТИВНОСТИ ---
            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                await client.send_message(bot_chat, "ткарточка")
                
        except Exception as e:
            print(f"⚠️ [bg_tasks Ошибка на Акк {acc_id}]: {e}", flush=True)
            
        # Цикл bg_tasks проверяет условия строго РАЗ В МИНУТУ (60 секунд)
        await asyncio.sleep(60)

async def start_bot():
    global clients
    print("🛠 Старт фермы с интегрированной автофармой Iris Moon...", flush=True)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue
            
        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )
        
        c.add_handler(handlers.MessageHandler(handle_my_messages))
        
        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            async for _ in c.get_dialogs(limit=5): pass
            print(f"✅ Аккаунт {i+1} запущен: @{me.username}", flush=True)
            
            is_collecting[i+1] = False
            asyncio.create_task(bg_tasks(c, i+1))
            asyncio.create_task(poll_bot_messages(c, i+1))
        except Exception as e:
            print(f"⚠️ Ошибка аккаунта {i+1}: {e}", flush=True)

    print("🚀 Все модули автоматизации успешно запущены!", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
