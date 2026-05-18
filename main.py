# -*- coding: utf-8 -*-
import os
import re
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
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=1)
                        return True
                    except:
                        return True
    except:
        pass
    return False

# --- УМНЫЙ ДВИЖОК С ЖЕСТКОЙ СЕПАРАЦИЕЙ КНОПОК МОДЕЛЕЙ ---
async def execute_menu_step(client, acc_id, step_name, keywords, pick_best, last_fp):
    await asyncio.sleep(0.16)
    
    # Запрещенный ТЕКСТ на кнопках
    forbidden_text = ["назад", "back", "отмена", "cancel", "вернуться", "главное", "меню", "быстрый выбор", "быстрый", "⬅️", "🔙"]
    # Точные совпадения для дата-коллабеков навигации
    forbidden_data_exact = ["trade_refresh", "back", "cancel", "menu_main", "to_main", "trade_fast_mode"]

    for attempt in range(25):
        try:
            msg = current_bot_msg.get(acc_id)
            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.06)
                continue

            fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
            
            # Контроль зависания на одном и том же меню
            if "Добавить телефон" not in step_name:
                if last_fp and fp == last_fp:
                    if attempt > 0 and attempt % 6 == 0:
                        last_fp = "" 
                    await asyncio.sleep(0.06)
                    continue

            valid_buttons = []

            # Фильтруем и собираем только чистые кнопки характеристик/моделей
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    text_lower = btn.text.lower().strip()
                    data_lower = (btn.callback_data or "").lower().strip()

                    if any(root in text_lower for root in forbidden_text):
                        continue
                    if any(x == data_lower for x in forbidden_data_exact):
                        continue
                    if any(x in text_lower or x in data_lower for x in ["изменить", "подтвердить", "готов"]):
                        continue

                    valid_buttons.append(btn)

            if not valid_buttons:
                await asyncio.sleep(0.06)
                continue

            # Если активирован выбор лучшего/автовыбор
            if pick_best:
                target_btn = None
                
                # НАСТРОЙКА ДЛЯ МОДЕЛЕЙ: Ищем кнопку, которая реально является телефоном (содержит "(x")
                if step_name == "Выбор Модели":
                    for btn in valid_buttons:
                        if "(x" in btn.text.lower():
                            target_btn = btn
                            break
                
                # НАСТРОЙКА ДЛЯ РЕДКОСТЕЙ: Ищем категорию с максимальным количеством штук в скобках
                elif step_name == "Выбор Редкости":
                    max_count = -1
                    for btn in valid_buttons:
                        match = re.search(r'\((\d+)\)', btn.text)
                        if match:
                            count = int(match.group(1))
                            if count > max_count:
                                max_count = count
                                target_btn = btn

                # Если под спец-фильтры ничего не подошло или это выбор Состояния — берем самую первую чистую кнопку
                if not target_btn:
                    target_btn = valid_buttons[0]

                try: 
                    await client.request_callback_answer(msg.chat.id, msg.id, target_btn.callback_data, timeout=1)
                except: 
                    pass
                return True, fp

            else:
                # Обычный точечный клик (Добавить телефон / Добавить 1 шт)
                for btn in valid_buttons:
                    text_lower = btn.text.lower().strip()
                    data_lower = (btn.callback_data or "").lower().strip()
                    
                    for kw in keywords:
                        kw_l = kw.lower().strip()
                        if kw_l in text_lower or kw_l in data_lower:
                            try: 
                                await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                            except: 
                                pass
                            return True, fp
        except:
            pass
        await asyncio.sleep(0.06)
            
    return False, last_fp

# --- СБОРЩИК ПРЕДМЕТОВ Х10 ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Начинаю умный сбор предметов...", flush=True)
    is_collecting[acc_id] = True  
    added_count = 0  
    
    for loop_index in range(1, 30):
        if added_count >= 10:
            break

        msg = current_bot_msg.get(acc_id)
        if msg and msg.text:
            msg_text = msg.text.lower()
            if "10/10" in msg_text and "слот" in msg_text:
                break

        last_fp = ""
        # 1. Клик: Добавить телефон
        res, last_fp = await execute_menu_step(client, acc_id, "Добавить телефон", ["добавить телефон", "trade_add_phone"], False, last_fp)
        if not res: break

        last_fp = ""
        # 2. Клик: Состояние
        res, last_fp = await execute_menu_step(client, acc_id, "Выбор Состояния", [], True, last_fp)
        if not res: continue

        last_fp = ""
        # 3. Клик: Редкость (Выбирает ту, где больше всего карт)
        res, last_fp = await execute_menu_step(client, acc_id, "Выбор Редкости", [], True, last_fp)
        if not res: continue

        last_fp = ""
        # 4. Клик: Модель (Жестко зафильтровано на нажатие по названию телефона)
        res, last_fp = await execute_menu_step(client, acc_id, "Выбор Модели", [], True, last_fp)
        if not res: continue

        last_fp = ""
        # 5. Клик: Добавить 1 шт
        res, last_fp = await execute_menu_step(client, acc_id, "Количество 1шт", ["добавить 1 шт.", "trade_add_single"], False, last_fp)
        if res:
            added_count += 1  
            print(f"➕ [Акк {acc_id}] Успешно добавлен телефон №{added_count}", flush=True)
        else:
            continue

    is_collecting[acc_id] = False

    # Финал сделки
    print(f"⚖️ [Акк {acc_id}] Лимит собран. Перехожу к фиксации...", flush=True)
    for _ in range(10):
        msg = current_bot_msg.get(acc_id)
        if await click(client, msg, "готов"):
            break
        await asyncio.sleep(0.2)

    await asyncio.sleep(0.8)

    for _ in range(10):
        msg = current_bot_msg.get(acc_id)
        if await click(client, msg, "подтвердить"):
            break
        await asyncio.sleep(0.2)

# --- МГНОВЕННЫЙ ОБРАБОТЧИК СОБЫТИЙ ---
async def process_bot_logic(client, message, acc_id):
    if not message or not message.text:
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
                            print(f"✅ [Акк {acc_id}] Входящий трейд принят моментально!", flush=True)
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
        await asyncio.sleep(0.18) 

# --- ОСНОВА ---
async def sender_confirm_logic(client, acc_id):
    print(f"⏳ [Акк {acc_id} - Основа] Ожидаю завершения сборки предметов твинком...", flush=True)
    
    for _ in range(120):
        await asyncio.sleep(0.4)
        try:
            msg = current_bot_msg.get(acc_id)
            if not msg or not msg.text:
                continue
                
            text = msg.text.lower()
            
            if "готовность:" in text and text.count("✅") >= 1:
                print(f"✍️ [Акк {acc_id} - Основа] Твинк зафиксировал инвентарь. Закрываю сделку...", flush=True)
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
        try: await message.edit("🚀 **Юзербот активен! Наведение на модели телефонов зафиксировано.**")
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

async def bg_tasks(client, acc_id):
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    while True:
        await asyncio.sleep(121 * 60)
        try: await client.send_message(bot_chat, "ткарточка")
        except: pass

async def start_bot():
    global clients
    print("🛠 Старт фермы с жесткой фильтрацией сервисных кнопок моделей...", flush=True)

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

    print("🚀 Полная боевая готовность! Проверяй добавление моделей.", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
