# -*- coding: utf-8 -*-
import os
import asyncio
import random
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
current_bot_msg = {}  # Глобальное хранилище самых свежих сообщений бота для каждого аккаунта

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

# --- МГНОВЕННЫЙ КЛИКЕР ---
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

# --- БЕЗЗАДЕРЖЕЧНЫЙ ДВИЖОК (РАБОТАЕТ ЧЕРЕЗ ОЗУ) ---
async def execute_menu_step(client, acc_id, step_name, keywords, pick_first, last_fp):
    # Никакого сна на старте. Работаем на опережение.
    for attempt in range(40):
        try:
            msg = current_bot_msg.get(acc_id)
            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.05) # Микро-пауза 50мс если сообщения еще нет
                continue

            fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
            
            if "Добавить телефон" not in step_name:
                if last_fp and fp == last_fp:
                    await asyncio.sleep(0.05) # Ждем смену экрана ботом
                    continue

            # Если бот реально затупил на 15-й микро-попытке, пробуем Назад
            if attempt == 20 and pick_first:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "назад" in btn.text.lower() or "back" in (btn.callback_data or "").lower():
                            try: await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                            except: pass
                            return False, fp

            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    text_lower = btn.text.lower().strip()
                    data_lower = (btn.callback_data or "").lower().strip()

                    if pick_first:
                        if any(x in text_lower or x in data_lower for x in ["назад", "back", "изменить", "отмена", "подтвердить", "главное", "готов"]):
                            continue
                        try: await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                        except: pass
                        return True, fp
                    else:
                        for kw in keywords:
                            kw_l = kw.lower().strip()
                            if kw_l in text_lower or kw_l in data_lower:
                                try: await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                                except: pass
                                return True, fp
        except:
            pass
        await asyncio.sleep(0.05) # Минимальный тик во избежание перегрузки CPU
            
    return False, last_fp

# --- ТУРБО СБОРЩИК Х10 (СНАЧАЛА ГОТОВ -> ПОТОМ ПОДТВЕРДИТЬ) ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Сборка x10 в режиме МАКСИМАЛЬНЫЙ ТУРБО...", flush=True)
    
    for loop_index in range(1, 26):
        slots_full = False
        msg = current_bot_msg.get(acc_id)
        if msg and msg.text:
            msg_text = msg.text.lower()
            if "10/10" in msg_text and "слот" in msg_text:
                print(f"🎯 [Акк {acc_id}] Слоты забиты 10/10!", flush=True)
                slots_full = True
                break
                
        if slots_full:
            break

        last_fp = ""
        # Шаг 1: Добавить телефон
        res, last_fp = await execute_menu_step(client, acc_id, "Добавить телефон", ["добавить телефон", "trade_add_phone"], False, last_fp)
        if not res: break

        # Шаг 2: Выбор состояния
        res, last_fp = await execute_menu_step(client, acc_id, "Выбор Состояния", [], True, last_fp)
        if not res: continue

        # Шаг 3: Выбор редкости
        res, last_fp = await execute_menu_step(client, acc_id, "Выбор Редкости", [], True, last_fp)
        if not res: continue

        # Шаг 4: Выбор модели
        res, last_fp = await execute_menu_step(client, acc_id, "Выбор Модели", [], True, last_fp)
        if not res: continue

        # Шаг 5: Выбор количества (1 шт)
        res, last_fp = await execute_menu_step(client, acc_id, "Количество 1шт", ["добавить 1 шт.", "trade_add_single"], False, last_fp)
        if not res: continue

    # --- ФИНАЛЬНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ КЛИКОВ ---
    print(f"⚖️ [Акк {acc_id}] Предметы собраны. Жму ГОТОВ...", flush=True)
    
    # 1. Сначала прожимаем ГОТОВ
    for _ in range(10):
        msg = current_bot_msg.get(acc_id)
        if await click(client, msg, "готов"):
            break
        await asyncio.sleep(0.2)

    # Даем боту 1 секунду обновиться до статуса готовности
    await asyncio.sleep(1.0)

    # 2. Только ПОСЛЕ этого жмем ПОДТВЕРДИТЬ
    print(f"🚀 [Акк {acc_id}] Статус готов! Прожимаю ПОДТВЕРДИТЬ для закрытия сделки...", flush=True)
    for _ in range(10):
        msg = current_bot_msg.get(acc_id)
        if await click(client, msg, "подтвердить"):
            break
        await asyncio.sleep(0.2)

# --- ЛОГИКА ОБРАБОТКИ СИГНАЛОВ ИЗ ЧАТА ---
async def process_bot_logic(client, message, acc_id):
    if not message or not message.text:
        return

    text = message.text.lower()

    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return

        print(f"🤝 [Акк {acc_id}] Обнаружен трейд! Принимаю...", flush=True)
        await click(client, message, "принять")
        asyncio.create_task(receiver_trade_logic(client, acc_id))
        return

    if ("готовность:" in text and "❌" in text and "✅" in text) or "занято слотов: 10/10" in text:
        await click(client, message, "готов")
        return

    if "подтвердите обмен" in text or "подтвердите" in text:
        await click(client, message, "подтвердить")
        return

# --- УЛЬТРА-СКОРОСТНОЙ ПУЛИНГ (КАЖДЫЕ 0.15 СЕКУНДЫ) ---
async def poll_bot_messages(client, acc_id):
    last_msg_id = 0
    last_buttons_fp = ""
    
    while True:
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                buttons_fp = ""
                if msg.reply_markup:
                    buttons_fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
                
                # Мгновенно пушим актуальное сообщение в ОЗУ для движка
                current_bot_msg[acc_id] = msg
                
                if msg.id != last_msg_id or buttons_fp != last_buttons_fp:
                    last_msg_id = msg.id
                    last_buttons_fp = buttons_fp
                    await process_bot_logic(client, msg, acc_id)
                break
        except:
            pass
        await asyncio.sleep(0.15) # Идеальный баланс скорости без бана от Telegram за спам-запросы

# --- ОТПРАВИТЕЛЬ ---
async def sender_confirm_logic(client, acc_id):
    # Срезали таймер до 20 сек, твинк теперь управляется мгновенно
    await asyncio.sleep(20)
    try:
        async for msg in client.get_chat_history(bot_chat, limit=1):
            await click(client, msg, "готов")
            await asyncio.sleep(1.0)
            await click(client, msg, "подтвердить")
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
        try: await message.edit("🚀 **Турбо-Юзербот онлайн!**")
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
    print("🛠 Запуск СВЕРХЗВУКОВОЙ Pyrofork фермы...", flush=True)

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
            asyncio.create_task(bg_tasks(c, i+1))
            asyncio.create_task(poll_bot_messages(c, i+1))
        except Exception as e:
            print(f"⚠️ Ошибка аккаунта {i+1}: {e}", flush=True)

    print("🚀 Скрипт разогнан до предела возможностей. Запускай .t", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
