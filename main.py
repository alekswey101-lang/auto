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

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

# --- НАДЕЖНЫЙ КЛИКЕР ---
async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False

        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                t_low = btn.text.lower()
                d_low = (btn.callback_data or "").lower()
                if keyword.lower() in t_low or keyword.lower() in d_low:
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
            t_low = btn.text.lower()
            d_low = (btn.callback_data or "").lower()
            if keyword.lower() in t_low or keyword.lower() in d_low:
                return True
    return False

# --- ДВИЖОК СБОРА ПРЕДМЕТОВ ---
async def execute_menu_step(client, acc_id, step_name, keywords, pick_best, last_fp):
    await asyncio.sleep(0.1)

    forbidden = [
        "назад", "back", "отмена", "cancel", "вернуться", "главное", "меню",
        "быстрый выбор", "быстрый", "⬅️", "🔙", "trade_refresh", "trade_fast_mode"
    ]

    for attempt in range(30):
        try:
            # Прямо берем последнее сообщение из истории, чтобы не зависеть от кэша
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break

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
                    if not btn.callback_data: continue
                    t_low = btn.text.lower().strip()
                    d_low = btn.callback_data.lower().strip()

                    if any(x in t_low or x in d_low for x in forbidden): continue
                    if "подтвердить" in t_low or "trade_confirm" in d_low: continue
                    if "готов" in t_low or "trade_ready" in d_low: continue
                    if "изменить" in t_low or "trade_change" in d_low: continue

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
                        if target_btn: break

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

# --- ЖЕЛЕЗОБЕТОННЫЙ ЦИКЛ ОЖИДАНИЯ ГОТОВНОСТИ ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Начинаю авто-набор телефонов...", flush=True)

    added_count = 0
    current_fp = ""

    # Набираем 10 штук
    for loop_index in range(1, 30):
        if added_count >= 10: break

        msg = None
        async for m in client.get_chat_history(bot_chat, limit=1):
            msg = m
            break

        if msg and msg.text:
            if "10/10" in msg.text.lower() and "слот" in msg.text.lower(): break

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
            print(f"➕ [Акк {acc_id}] Добавлен телефон {added_count}/10", flush=True)

    print(f"⚖️ [Акк {acc_id}] Телефоны собраны. Вхожу в режим жесткого ожидания твоей готовности...", flush=True)

    # Вот он — бескомпромиссный цикл ожидания через прямой пулинг истории
    while True:
        try:
            active_msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                active_msg = m
                break

            if not active_msg or not active_msg.text:
                await asyncio.sleep(0.15)
                continue

            text = active_msg.text.lower()

            # Сделка завершена или отменена
            if "обмен завершен" in text or "отменен" in text or "сделка завершена" in text:
                print(f"🎉 [Акк {acc_id}] Сделка успешно закрылась!", flush=True)
                return

            # Твинк видит галочку основы и жмет «Готов» у себя
            if "✅" in text and (has_button(active_msg, "готов") or has_button(active_msg, "trade_ready")):
                print(f"✍️ [Акк {acc_id}] Замечена готовность основы! Прожимаю 'Готов'...", flush=True)
                await click(client, active_msg, "trade_ready")
                await click(client, active_msg, "готов")
                await asyncio.sleep(0.3)
                continue

            # Появилась финальная кнопка подтверждения
            if has_button(active_msg, "подтвердить") or has_button(active_msg, "trade_confirm"):
                print(f"🔗 [Акк {acc_id}] Прожимаю финальное 'Подтвердить'...", flush=True)
                await click(client, active_msg, "trade_confirm")
                await click(client, active_msg, "подтвердить")
                await asyncio.sleep(0.3)
                continue

        except Exception as e:
            print(f"⚠️ Ошибка в цикле ожидания трейда: {e}", flush=True)
        
        await asyncio.sleep(0.15)

# --- ГЛАВНЫЙ ОБРАБОТЧИК ВХОДЯЩИХ СООБЩЕНИЙ БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return

    # Автосбор ТМайнинга
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                if "собрать деньги" in btn.text.lower() or "farm_claim" in btn.callback_data.lower():
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        print(f"💰 [Акк {acc_id}] Собрал прибыль с майнинга.", flush=True)
                        return
                    except: pass

    if not message.text: return
    text = message.text.lower()

    # Перехват и принятие предложения обмена
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text: return

        if await click(client, message, "trade_accept") or await click(client, message, "принять"):
            print(f"✅ [Акк {acc_id}] Входящий трейд принят. Запускаю сборщик предметов...", flush=True)
            # Отдаем управление сборщику и его внутреннему циклу
            asyncio.create_task(receiver_trade_logic(client, acc_id))

# --- ХЕНДЛЕР ТВОИХ ТЕКСТОВЫХ КОМАНД ---
async def handle_my_messages(client, message):
    if not message.text: return
    
    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    # Вычисляем точный ID аккаунта
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

# --- ФОН ЗАДАЧИ ---
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
                if msk_now.hour == 0 and msk_now.minute == 11: claimed_today = False

            if acc_id in [1, 2]:
                iris_timer += 1
                if iris_timer >= 240:
                    try: await client.send_message(iris_bot_chat, "фарма")
                    except: pass
                    iris_timer = 0

            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                await client.send_message(bot_chat, "ткарточка")
        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Запуск полностью изолированной и стабильной версии...", flush=True)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue
        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )

        # Подключаем обработчик твоих личных команд (.t) стандартным методом
        c.add_handler(handlers.MessageHandler(handle_my_messages, filters.me))

        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id

            async for _ in c.get_dialogs(limit=5): pass
            print(f"✅ Аккаунт {i+1} запущен: @{me.username}", flush=True)
            
            acc_id = i + 1

            # Подключаем перехват сообщений от игрового бота
            c.add_handler(handlers.MessageHandler(
                lambda client, message, a_id=acc_id: process_bot_logic(client, message, a_id),
                filters.chat(bot_chat)
            ))
            
            asyncio.create_task(bg_tasks(c, acc_id))
        except Exception as e:
            print(f"⚠️ Ошибка аккаунта {i+1}: {e}", flush=True)

    print("🚀 Скрипт запущен. Проверяй работу команд и кликера!", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
