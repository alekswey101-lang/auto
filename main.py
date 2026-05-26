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

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

twink_finished_event = asyncio.Event()

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
                                timeout=2
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

# --- ТЕХНИЧЕСКИЙ АВТОСБОР ТВИНКА (ФИКС ОШИБКИ ОТКАТА МЕНЮ) ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Фоновый автосбор запущен.", flush=True)
    working_phones_depleted = False 
    failed_work_attempts = 0  # Счетчик неудачных заходов в "Рабочие"
    failed_broken_attempts = 0 # Счетчик неудачных заходов в "Сломанные"

    if not hasattr(client, "dynamic_limit"):
        client.dynamic_limit = 10 

    for tick in range(80):
        try:
            if not hasattr(client, "trade_counter"):
                client.trade_counter = 0

            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.5)
                continue

            text = msg.text.lower() if msg.text else ""

            # Проверка лимитов слотов обмена
            if client.trade_counter >= client.dynamic_limit or "занято слотов" in text:
                if has_button(msg, "вернуться назад") or has_button(msg, "назад"):
                    await click(client, msg, "назад")
                    await asyncio.sleep(1.0)
                    continue

                if has_button(msg, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Трейд заполнен ({client.trade_counter}). Нажимаю Готов!", flush=True)
                    await click(client, msg, "готов")
                    twink_finished_event.set()
                    client.collecting = False 
                    return 

                if "готовность: ✅" in text or "✅" in text:
                    twink_finished_event.set()
                    client.collecting = False
                    return
                continue

            # Собираем все инлайн-кнопки текущего меню
            all_buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        all_buttons.append(btn)

            # 1. Финал: кнопка добавления ("1 шт")
            single_btn = next((b for b in all_buttons if "1 шт" in b.text.lower() or "single" in b.callback_data.lower()), None)
            if single_btn:
                client.trade_counter += 1
                failed_work_attempts = 0   # Сбрасываем ошибки, раз дошли до добавления
                failed_broken_attempts = 0
                print(f"📦 [Твинк {acc_id}] Добавляю телефон в обмен [{client.trade_counter}/{client.dynamic_limit}]", flush=True)
                await client.request_callback_answer(msg.chat.id, msg.id, single_btn.callback_data, timeout=2)
                await asyncio.sleep(1.5)
                continue

            # 2. Старт: Кнопка "Добавить телефон" в главном меню трейда
            add_btn = next((b for b in all_buttons if "добавить телефон" in b.text.lower() or "add_phone" in b.callback_data.lower()), None)
            if add_btn:
                print(f"➕ [Твинк {acc_id}] Нажимаю 'Добавить телефон'", flush=True)
                await client.request_callback_answer(msg.chat.id, msg.id, add_btn.callback_data, timeout=2)
                await asyncio.sleep(1.2)
                continue

            # 3. Шаг 1: Выбор состояния (Рабочий / Сломанный)
            work_btn = next((b for b in all_buttons if "рабоч" in b.text.lower()), None)
            broken_btn = next((b for b in all_buttons if "сломан" in b.text.lower()), None)

            if work_btn or broken_btn:
                # Если обе категории недоступны/пусты — выходим из цикла добавления
                if failed_work_attempts >= 2 and failed_broken_attempts >= 2:
                    print(f"❌ [Твинк {acc_id}] Похоже, телефонов вообще нет в инвентаре. Завершаю обмен.", flush=True)
                    if has_button(msg, "вернуться назад") or has_button(msg, "назад"):
                        await click(client, msg, "назад")
                    else:
                        twink_finished_event.set()
                        client.collecting = False
                        return
                    await asyncio.sleep(1.0)
                    continue

                # Выбираем целевую кнопку на основе флага или прошлых неудач
                if (working_phones_depleted or failed_work_attempts >= 2) and broken_btn:
                    target_btn = broken_btn
                    client.dynamic_limit = 5
                    failed_broken_attempts += 1
                elif work_btn:
                    target_btn = work_btn
                    client.dynamic_limit = 10
                    failed_work_attempts += 1
                else:
                    target_btn = broken_btn or work_btn

                print(f"📱 [Твинк {acc_id}] Выбираю состояние: '{target_btn.text}' (Попытка W:{failed_work_attempts}/B:{failed_broken_attempts})", flush=True)
                try:
                    res = await client.request_callback_answer(msg.chat.id, msg.id, target_btn.callback_data, timeout=2)
                    if res and hasattr(res, 'message') and any(x in res.message.lower() for x in ["нет", "доступных", "отсутствуют", "пусто"]):
                        if target_btn == work_btn:
                            working_phones_depleted = True
                except:
                    pass

                await asyncio.sleep(1.5)  # Увеличенная пауза, чтобы бот успел перерисовать (или вернуть) меню
                continue

            # 4. Шаг 2: Меню выбора РЕДКОСТИ
            if "выберите редкость" in text or "редкость телефона" in text:
                valid_items = [b for b in all_buttons if not any(x in b.text.lower() or x in b.callback_data.lower() for x in ["назад", "back", "меню", "отмена"])]
                if valid_items:
                    target_item = next((b for b in valid_items if any(x in b.text.lower() for x in ["мистич", "редк", "легенд"])), valid_items[0])
                    print(f"🔮 [Твинк {acc_id}] Выбираю редкость: [{target_item.text}]", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target_item.callback_data, timeout=2)
                    await asyncio.sleep(1.2)
                continue

            # 5. Шаг 3: Меню выбора КОНКРЕТНОЙ МОДЕЛИ
            if "выберите модель" in text or "модель телефона" in text or "модель" in text:
                valid_models = [b for b in all_buttons if not any(x in b.text.lower() or x in b.callback_data.lower() for x in ["назад", "back", "меню", "отмена"])]
                if valid_models:
                    target_model = valid_models[0]
                    print(f"💎 [Твинк {acc_id}] Выбираю модель телефона: [{target_model.text}]", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target_model.callback_data, timeout=2)
                    await asyncio.sleep(1.2)
                continue

        except Exception as e:
            print(f"⚠️ Ошибка автосбора твинка {acc_id}: {e}", flush=True)
        await asyncio.sleep(0.5)

    client.collecting = False

# --- ФОНОВАЯ ЗАДАЧА СИНХРОНИЗАЦИИ ДЛЯ ОСНОВЫ ---
async def basis_sync_loop(basis_client):
    while True:
        await twink_finished_event.wait()
        print("🔗 [СИНХРОНИЗАЦИЯ] Твинк закончил сбор. Основа прожимает готовность...", flush=True)
        
        for _ in range(5):
            try:
                msg = None
                async for m in basis_client.get_chat_history(bot_chat, limit=1):
                    msg = m
                    break
                
                if msg:
                    if has_button(msg, "готов"):
                        await click(basis_client, msg, "готов")
                        break
                    else:
                        for row in msg.reply_markup.inline_keyboard if msg.reply_markup else []:
                            for btn in row:
                                if "назад" in btn.text.lower() or "вернуться" in btn.text.lower():
                                    await basis_client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                                    break
            except: pass
            await asyncio.sleep(0.5)
            
        twink_finished_event.clear()

# --- ГЛАВНЫЙ ОБРАБОТЧИК БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return
    if not hasattr(client, "collecting"): client.collecting = False

    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                if any(x in btn.text.lower() for x in ["собрать деньги", "собрать прибыль", "забрать", "забрать✅"]) or "farm_claim" in btn.callback_data.lower():
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        return
                    except: pass

    if not message.text: return
    text = message.text.lower()

    if "вы сможете выбить карту еще раз через" in text:
        hours_match = re.search(r'(\d+)\s*ч', text)
        minutes_match = re.search(r'(\d+)\s*мин', text)
        seconds_match = re.search(r'(\d+)\s*сек', text)

        hours = int(hours_match.group(1)) if hours_match else 0
        minutes = int(minutes_match.group(1)) if minutes_match else 0
        seconds = int(seconds_match.group(1)) if seconds_match else 0

        total_sleep_seconds = (hours * 3600) + (minutes * 60) + seconds + 60 
        if total_sleep_seconds < 180: total_sleep_seconds = 180

        client.card_timer_override = total_sleep_seconds
        return

    if "вам пришел запрос на ремонт" in text or "запрос на ремонт" in text:
        if has_button(message, "принять заказ"):
            await click(client, message, "принять заказ")
            return

    if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
        await click(client, message, "trade_confirm")
        await click(client, message, "подтвердить")
        return

    if "подтвердите обмен" in text or "подтвердите" in text:
        if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
            await click(client, message, "trade_confirm")
            await click(client, message, "подтвердить")
            return

    if acc_id != 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                if client.collecting: return
                print(f"✅ [Твинк {acc_id}] Трейд принят. Запуск автосбора.", flush=True)
                twink_finished_event.clear() 
                client.collecting = True
                asyncio.create_task(twink_collect_logic(client, acc_id))
            return

    if acc_id == 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                twink_finished_event.clear()
            return

# --- ХЕНДЛЕР КОМАНД ЮЗЕРА ---
async def handle_my_messages(client, message):
    if not message.text: return
    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

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

# --- ИЗОЛИРОВАННЫЙ ТАЙМЕР КАРТОЧЕК ---
async def card_timer_loop(client, acc_id):
    await asyncio.sleep(5)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass

    while True:
        try:
            if client.card_timer_override is not None and client.card_timer_override > 0:
                await asyncio.sleep(client.card_timer_override)
                client.card_timer_override = None
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
                continue

            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)
            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
        except: pass
        await asyncio.sleep(30)

# --- ГЛАВНЫЕ ФОНОВЫЕ ЗАДАЧИ ---
async def bg_tasks(client, acc_id):
    asyncio.create_task(card_timer_loop(client, acc_id))

    await asyncio.sleep(8)
    try: await client.send_message(bot_chat, "тмайнинг")
    except: pass

    if acc_id in [1, 2]:
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass

    claimed_today = False
    reward_claimed_today = False
    iris_timer = 0

    while True:
        try:
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)

            if msk_now.hour == 1 and msk_now.minute == 0:
                if not reward_claimed_today:
                    await client.send_message(bot_chat, "ежедневная награда")
                    reward_claimed_today = True
            else:
                if msk_now.hour == 1 and msk_now.minute == 2:
                    reward_claimed_today = False

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
        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Перезапуск фермы. Реализован обход блокировок пустых категорий.", flush=True)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue
        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )

        c.add_handler(handlers.MessageHandler(handle_my_messages, filters.me))

        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            c.card_timer_override = None

            async for _ in c.get_dialogs(limit=5): pass
            
            acc_id = i + 1
            if acc_id == 2:
                print(f"👑 ГЛАВНАЯ ОСНОВА (Аккаунт 2) запущена: @{me.username}", flush=True)
                asyncio.create_task(basis_sync_loop(c))
            else:
                print(f"✅ Твинк-аккаунт {acc_id} запущен: @{me.username}", flush=True)

            c.add_handler(handlers.MessageHandler(
                lambda client, message, a_id=acc_id: process_bot_logic(client, message, a_id),
                filters.chat(bot_chat)
            ), group=0)

            c.add_handler(handlers.EditedMessageHandler(
                lambda client, message, a_id=acc_id: process_bot_logic(client, message, a_id),
                filters.chat(bot_chat)
            ), group=0)
            
            asyncio.create_task(bg_tasks(c, acc_id))
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {i+1}: {e}", flush=True)

    print("🚀 Скрипт запущен! Проблема с откатом категорий исправлена.", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
