# -*- coding: utf-8 -*-
import os
import asyncio
import datetime
import threading
from flask import Flask
from pyrogram import Client, handlers
from pyrogram import raw

# --- СЕРВЕР ДЛЯ RENDER (KEEP-ALIVE) ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Ready and Running", 200

threading.Thread(
    target=lambda: app.run(
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 10000))
    ),
    daemon=True
).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

bot_chat = "phonegetcardsbot"
iris_bot_chat = "iris_moon_bot"

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
                            await client.request_callback_answer(
                                message.chat.id,
                                message.id,
                                btn.callback_data,
                                timeout=1
                            )
                            return True
                        except:
                            return True
    except:
        pass

    return False

def has_button(message, keyword: str) -> bool:
    if not message or not message.reply_markup:
        return False
    for row in message.reply_markup.inline_keyboard:
        for btn in row:
            if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                return True
    return False

# --- АНТИ-РАССИНХРОННЫЙ ДВИЖОК КЛИКОВ ---
async def execute_menu_step(client, acc_id, step_name, keywords, pick_best, last_fp):
    await asyncio.sleep(0.15)

    forbidden = [
        "назад", "back", "отмена", "cancel",
        "вернуться", "главное", "меню",
        "быстрый выбор", "быстрый",
        "⬅️", "🔙",
        "trade_refresh",
        "trade_fast_mode"
    ]

    for attempt in range(40):
        try:
            msg = current_bot_msg.get(acc_id)

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.05)
                continue

            current_fp = "|".join([
                btn.text
                for row in msg.reply_markup.inline_keyboard
                for btn in row
            ])

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
                    for priority_keyword in [
                        "мистические",
                        "редкие",
                        "хроматические",
                        "необычные",
                        "арканы",
                        "ширпотреб"
                    ]:
                        for btn in valid_buttons:
                            if priority_keyword in btn.text.lower():
                                target_btn = btn
                                break

                        if target_btn:
                            break

                if not target_btn:
                    target_btn = valid_buttons[0]

                try:
                    await client.request_callback_answer(
                        msg.chat.id,
                        msg.id,
                        target_btn.callback_data,
                        timeout=1
                    )
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
                                await client.request_callback_answer(
                                    msg.chat.id,
                                    msg.id,
                                    btn.callback_data,
                                    timeout=1
                                )
                                return True, current_fp
                            except:
                                await asyncio.sleep(0.05)
                                continue
        except:
            pass

        await asyncio.sleep(0.05)

    return False, last_fp

# --- СБОРЩИК ПРЕДМЕТОВ Х10 + ИНТЕЛЛЕКТУАЛЬНОЕ ПОДТВЕРЖДЕНИЕ ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Запуск сбора предметов...", flush=True)

    is_collecting[acc_id] = True
    added_count = 0
    current_fp = ""

    msg = current_bot_msg.get(acc_id)
    if msg and msg.reply_markup:
        current_fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])

    # Цикл добавления 10 телефонов
    for loop_index in range(1, 30):
        if added_count >= 10:
            break

        msg = current_bot_msg.get(acc_id)
        if msg and msg.text:
            if "10/10" in msg.text.lower() and "слот" in msg.text.lower():
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
            print(f"➕ [Акк {acc_id}] Телефон №{added_count} добавлен.", flush=True)

    is_collecting[acc_id] = False
    print(f"⚖️ [Акк {acc_id}] Набор завершен. Ожидаю готовности основы...", flush=True)

    # --- ЦИКЛ ОЖИДАНИЯ ГОТОВНОСТИ ОСНОВЫ И АВТО-ПРОЖАТИЯ ---
    # Твинк будет висеть в этом цикле до победного конца, обновляя сообщение
    for _ in range(60): 
        msg = current_bot_msg.get(acc_id)
        if not msg or not msg.text:
            await asyncio.sleep(0.5)
            continue
            
        text = msg.text.lower()
        
        # Если сделка уже завершена или отменена
        if "обмен завершен" in text or "отменен" in text:
            print(f"🎉 [Акк {acc_id}] Трейд успешно закрыт!", flush=True)
            return

        # Шаг 1: Ждем пока основа нажмет Готов (появится хотя бы один ✅) и жмем Готов у себя
        if "✅" in text and has_button(msg, "готов"):
            print(f"✍️ [Акк {acc_id}] Основа готова! Нажимаю кнопку 'Готов'...", flush=True)
            await click(client, msg, "готов")
            await asyncio.sleep(1.0)
            continue

        # Шаг 2: Если кнопка "Подтвердить" доступна — кликаем её сразу
        if has_button(msg, "подтвердить"):
            print(f"🔗 [Акк {acc_id}] Нажимаю финальное 'Подтвердить'...", flush=True)
            await click(client, msg, "подтвердить")
            await asyncio.sleep(1.0)
            continue
            
        await asyncio.sleep(0.4)

# --- ОБРАБОТЧИК СОБЫТИЙ СЕТИ ---
async def process_bot_logic(client, message, acc_id):
    if not message:
        return

    # 1. Автосбор ТМайнинга
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                if "собрать деньги" in btn.text.lower() or "farm_claim" in btn.callback_data.lower():
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        print(f"💰 [Акк {acc_id}] Деньги с ТМайнинга собраны!", flush=True)
                        return
                    except: pass

    if not message.text:
        return

    text = message.text.lower()

    # 2. РАБОЧЕЕ АВТОПРИНЯТИЕ ВХОДЯЩЕГО ТРЕЙДА
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return

        if await click(client, message, "принять"):
            print(f"✅ [Акк {acc_id}] Входящий трейд принят!", flush=True)
            await asyncio.sleep(0.5)
            # Запускаем монолитную логику сбора и ожидания галочек
            asyncio.create_task(receiver_trade_logic(client, acc_id))
        return

    # Подстраховка на случай, если бот прислал отдельное текстовое сообщение с требованием подтверждения
    if "подтвердите обмен" in text or "подтвердите" in text:
        if has_button(message, "подтвердить"):
            await click(client, message, "подтвердить")

# --- ПУЛИНГ ---
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
    print(f"⏳ [Акк {acc_id} - Инициатор] Трейд запущен.", flush=True)

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
        try: await message.edit("🚀 Юзербот активен!")
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

# --- ФОН ЗАДАЧ ---
async def bg_tasks(client, acc_id):
    await asyncio.sleep(5)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass

    if acc_id in [1, 2]:
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass

    claimed_today = False
    iris_timer = 0

    while True:
        try:
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)

            if msk_now.hour == 0 and msk_now.minute == 10:
                if not claimed_today:
                    await client.send_message(bot_chat, "тмайнинг")
                    claimed_today = True
            else:
                if msk_now.hour == 0 and msk_now.minute == 11:
                    claimed_today = False

            if acc_id in [1, 2]:
                iris_timer += 1
                if iris_timer >= 240:
                    try: await client.send_message(iris_bot_chat, "фарма")
                    except: pass
                    iris_timer = 0

            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                await client.send_message(bot_chat, "ткарточка")
        except:
            pass
        await asyncio.sleep(60)

# --- ЗАПУСК ---
async def start_bot():
    global clients
    print("🛠 Старт фермы...", flush=True)

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
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
