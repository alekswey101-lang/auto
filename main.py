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

# Базовый список доверенных юзернеймов фермы (в нижнем регистре и без @)
TRUSTED_NAMES = ["boymorale", "tintedwindow", "cutemald", "dennyom", "ivannomor"]

# Макросы для быстрого трейда по номерам аккаунтов
ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

# --- ХЕЛПЕРЫ ---
async def delay(min_s: float, max_s: float):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def click(client, message, keyword: str) -> bool:
    """Ищет кнопку по ключевому слову, перечитывает свежее сообщение и нажимает."""
    try:
        fresh_msg = None
        async for m in client.get_chat_history(bot_chat, limit=5):
            if m.reply_markup:
                for row in m.reply_markup.inline_keyboard:
                    for btn in row:
                        if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                            fresh_msg = m
                            break
                if fresh_msg:
                    break

        if not fresh_msg:
            print(f"[DEBUG click] ❌ Кнопка с '{keyword}' не найдена в последних сообщениях.", flush=True)
            return False

        for row in fresh_msg.reply_markup.inline_keyboard:
            for btn in row:
                if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                    print(f"[DEBUG click] кнопка: '{btn.text}' | data: '{btn.callback_data}'", flush=True)
                    await client.request_callback_answer(fresh_msg.chat.id, fresh_msg.id, btn.callback_data)
                    print(f"[DEBUG click] ✅ Нажата кнопка: '{btn.text}'", flush=True)
                    return True
    except Exception as e:
        print(f"❌ click() ошибка: {e}", flush=True)
    return False

# --- УЛЬТРА-НАДЁЖНЫЙ ДВИЖОК ПОШАГОВЫХ КЛИКОВ (ФИНАЛЬНАЯ ВЕРСИЯ) ---
async def execute_menu_step(client, step_name, keywords, pick_first, last_fp):
    print(f"🔍 [{step_name}] Начинаю поиск кнопок... Ищу ключевые слова: {keywords}", flush=True)
    
    for attempt in range(15):  # 15 попыток с интервалом в 2 секунды
        await asyncio.sleep(2)
        try:
            # Читаем строго ПОСЛЕДНЕЕ сообщение, чтобы не собирать мусор из кэша истории
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if not msg.reply_markup:
                    continue

                # Генерируем уникальный отпечаток текущего меню кнопок
                fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
                
                # Если бот ещё не обновил меню (кнопки те же, что на прошлом шаге) — ждем
                if last_fp and fp == last_fp:
                    continue

                # Перебираем инлайн-кнопки
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        text_lower = btn.text.lower().strip()
                        data_lower = (btn.callback_data or "").lower().strip()

                        # Режим 1: Авто-выбор первой доступной кнопки (для выбора редкости, состояния и т.д.)
                        if pick_first:
                            if "назад" not in text_lower and "back" not in data_lower and "изменить" not in text_lower:
                                print(f"🎯 [{step_name}] Попытка нажать авто-кнопку: [{btn.text}] (data: {btn.callback_data})", flush=True)
                                try:
                                    await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                                    print(f"✅ [{step_name}] Успешно нажата авто-кнопка: [{btn.text}]", flush=True)
                                    return True, fp
                                except Exception as click_err:
                                    print(f"❌ [{step_name}] Ошибка клика по авто-кнопке: {click_err}", flush=True)

                        # Режим 2: Поиск конкретной кнопки по ключевым словам
                        else:
                            for kw in keywords:
                                kw_l = kw.lower().strip()
                                # Мягкая проверка через 'in' обходит любые динамические ID в callback_data
                                if kw_l in text_lower or kw_l in data_lower:
                                    print(f"🎯 [{step_name}] Найдено совпадение! Кнопка: [{btn.text}] | Данные: {btn.callback_data}", flush=True)
                                    try:
                                        await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                                        print(f"✅ [{step_name}] Успешный клик по кнопке: [{btn.text}]", flush=True)
                                        return True, fp
                                    except Exception as click_err:
                                        print(f"❌ [{step_name}] Telegram заблокировал клик по кнопке '{btn.text}': {click_err}", flush=True)
                                        
            # Раз в 3 попытки выводим в консоль, что сейчас видит юзербот на экране
            if attempt % 3 == 0:
                current_fp = fp if 'fp' in locals() else 'Кнопок нет/Чат пуст'
                print(f"⏳ [{step_name}] Попытка {attempt+1}/15. Нужной кнопки пока нет. Вижу на экране: [{current_fp}]", flush=True)
                
        except Exception as e:
            print(f"❌ Системная ошибка на шаге {step_name}: {e}", flush=True)
            
    print(f"🛑 [{step_name}] Скрипт сдался после 15 попыток. Шаг не выполнен.", flush=True)
    return False, last_fp

# --- ЛОГИКА ДЛЯ ПОЛУЧАТЕЛЯ ---
async def receiver_trade_logic(client, acc_id):
    print(f"📦 [Акк {acc_id} - Получатель] Запуск умного сборщика телефонов в трейд...", flush=True)

    # 1. Жмем Добавить телефон (ищет по вхождению "trade_add_phone")
    res, last_fp = await execute_menu_step(client, "Кнопка Добавить", ["добавить телефон", "trade_add_phone"], False, "")
    if not res: return

    # 2. Выбираем состояние (первая кнопка)
    res, last_fp = await execute_menu_step(client, "Выбор Состояния", [], True, last_fp)
    if not res: return

    # 3. Выбираем редкость (первая кнопка)
    res, last_fp = await execute_menu_step(client, "Выбор Редкости", [], True, last_fp)
    if not res: return

    # 4. Выбираем модель (первая кнопка)
    res, last_fp = await execute_menu_step(client, "Выбор Модели", [], True, last_fp)
    if not res: return

    # 5. Выбираем количество 1 шт.
    res, last_fp = await execute_menu_step(client, "Количество 1шт", ["добавить 1 шт.", "trade_add_single"], False, last_fp)
    if not res: return

    # 6. Финальное подтверждение со стороны получателя
    res, last_fp = await execute_menu_step(client, "Финал Получателя", ["подтвердить", "trade_confirm"], False, last_fp)
    if res:
        print(f"🎉 [Акк {acc_id} - Получатель] Все этапы пройдены! Трейд укомплектован.", flush=True)

# --- ЛОГИКА ДЛЯ ОТПРАВИТЕЛЯ ---
async def sender_confirm_logic(client, acc_id):
    print(f"⏳ [Акк {acc_id} - Отправитель] Засыпаю на 32 секунды, даю получателю собрать предметы...", flush=True)
    await asyncio.sleep(32)
    print(f"✍️ [Акк {acc_id} - Отправитель] Время вышло. Подтверждаю обмен...", flush=True)
    try:
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if msg.reply_markup:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "подтвердить" in btn.text.lower() or (btn.callback_data and "trade_confirm" in btn.callback_data.lower()):
                            await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                            print(f"✅ [Акк {acc_id} - Отправитель] Трейд зафиксирован и подтвержден!", flush=True)
                            return
    except Exception as e:
        print(f"❌ Ошибка подтверждения у отправителя {acc_id}: {e}", flush=True)

# --- ЛОГИКА РУЧНОГО И АВТОМАТИЧЕСКОГО СБОРА С ФЕРМЫ ---
async def manual_farm_logic(client, acc_id, mode="Ручной"):
    try:
        print(f"🚜 [Акк {acc_id}] Выполняется {mode} сбор прибыли...", flush=True)
        await client.send_message(bot_chat, "/tfarm")
        await asyncio.sleep(4)
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if msg.reply_markup:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "снять деньги" in btn.text.lower() or (btn.callback_data and "farm_claim" in btn.callback_data.lower()):
                            await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                            print(f"💰 [Акк {acc_id}] {mode} сбор успешен! Деньги сняты.", flush=True)
                            return
        print(f"⚠️ [Акк {acc_id}] Кнопка снятия денег не найдена в меню.", flush=True)
    except Exception as e:
        print(f"❌ Ошибка сбора на акке {acc_id}: {e}", flush=True)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ИГРОВОГО БОТА ---
async def process_bot_logic(client, message):
    try:
        acc_id = clients.index(client) + 1
    except:
        acc_id = "Х"

    if not message or not message.chat or not message.text:
        return

    chat_username = (getattr(message.chat, 'username', None) or '').lower()
    sender_username = (getattr(message.from_user, 'username', None) or '').lower() if message.from_user else ''

    is_our_bot = (chat_username == bot_chat.lower()) or (sender_username == bot_chat.lower())

    if not is_our_bot:
        return
    if message.from_user and message.from_user.id == getattr(client, "me_id", 0):
        return

    text = message.text.lower()

    # 1. ВХОДЯЩИЙ ТРЕЙД
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return

        is_trusted = any(name in text for name in TRUSTED_NAMES)
        
        if not is_trusted:
            print(f"🤷‍♂️ [Акк {acc_id}] Фильтр отклонил трейд. Имя отправителя чужое.", flush=True)
            return

        print(f"🤝 [Акк {acc_id}] Трейд от своей фермы! Принимаю...", flush=True)
        await delay(1.0, 2.0)
        
        if await click(client, message, "принять"):
            print(f"✅ [Акк {acc_id}] Принято! Запускаю receiver_trade_logic...", flush=True)
            asyncio.create_task(receiver_trade_logic(client, acc_id))
        else:
            print(f"⚠️ [Акк {acc_id}] Кнопка 'Принять' не найдена!", flush=True)
        return

    # 2. АВТОГОТОВНОСТЬ
    if ("готовность:" in text and "❌" in text and "✅" in text) or "занято слотов: 10/10" in text:
        await delay(1.5, 3.0)
        if await click(client, message, "готов"):
            print(f"✅ [Акк {acc_id}] Нажал ГОТОВ.", flush=True)
        return

    # 3. АВТОПОДТВЕРЖДЕНИЕ
    if "подтвердите обмен" in text or "подтвердите" in text:
        await delay(1.0, 2.0)
        if await click(client, message, "подтвердить"):
            print(f"🎉 [Акк {acc_id}] Обмен подтверждён!", flush=True)
        return

# --- ОБРАБОТЧИК ТВОИХ КОМАНД (.farmn, .t, .ping) ---
async def handle_my_messages(client, message):
    if not message.text: return

    my_id = getattr(client, "me_id", 0)
    if not message.from_user or message.from_user.id != my_id:
        return

    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    try:
        acc_id = clients.index(client) + 1
    except:
        acc_id = 1

    if cmd == ".ping":
        try: await message.edit("🚀 **Юзербот активен и готов к работе!**")
        except: pass
        return

    if cmd == ".farmn":
        print(f"⚡ [Акк {acc_id}] Получена команда принудительного сбора .farmn!", flush=True)
        try: await message.delete()
        except: pass
        for i, cl in enumerate(clients):
            asyncio.create_task(manual_farm_logic(cl, i + 1, mode="Принудительный ручной"))
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

        if not target:
            return

        try: await message.delete()
        except: pass

        print(f"📣 [Акк {acc_id} - Отправитель] Инициирую трейд на {target}...", flush=True)
        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        await client.send_message(bot_chat, bot_cmd)

        if target.lower() in TRUSTED_NAMES:
            asyncio.create_task(sender_confirm_logic(client, acc_id))

# --- POLLING ЛИЧНЫХ СООБЩЕНИЙ ОТ БОТА ---
async def poll_bot_messages(client, acc_id):
    last_msg_id = 0
    last_msg_text = ""
    print(f"🔄 [Акк {acc_id}] Запущен polling сообщений от бота...", flush=True)
    while True:
        try:
            async for msg in client.get_chat_history(bot_chat, limit=5):
                current_text = (msg.text or "")
                if msg.id != last_msg_id or current_text != last_msg_text:
                    if last_msg_id != 0:
                        await process_bot_logic(client, msg)
                    last_msg_id = msg.id
                    last_msg_text = current_text
                break
        except Exception as e:
            print(f"❌ [Акк {acc_id}] Ошибка polling: {e}", flush=True)
        await asyncio.sleep(5)

# --- ФОНОВЫЕ ЗАДАЧИ ПО ТАЙМЕРУ ---
async def bg_tasks(client, acc_id):
    print(f"🟢 [Акк {acc_id}] Цикл отправки карточек запущен!", flush=True)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass

    while True:
        await asyncio.sleep(121 * 60)
        try:
            print(f"🃏 [Акк {acc_id}] Время пришло: отправляю 'ткарточка'...", flush=True)
            await client.send_message(bot_chat, "ткарточка")

            now = datetime.datetime.utcnow()
            if now.hour == 21 and now.minute <= 25:
                await manual_farm_logic(client, acc_id, mode="Плановый ночной (00:00 МСК)")
        except Exception as e:
            print(f"❌ Ошибка в таймере аккаунта {acc_id}: {e}", flush=True)

# --- ЗАПУСК КЛИЕНТОВ ---
async def start_bot():
    global clients, TRUSTED_NAMES
    print("🛠 Инициализация Pyrofork клиентов...", flush=True)
    
    raw_clients = []
    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "":
            continue
            
        c = Client(
            name=f"memory_session_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )
        
        # Обрабатываем хэндлером исключительно исходящие команды от администратора (.t, .farmn, .ping)
        c.add_handler(handlers.MessageHandler(handle_my_messages))
        raw_clients.append((i + 1, c))
        
    for acc_num, c in raw_clients:
        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            
            try:
                await c.send_message(bot_chat, "/start")
            except Exception as ex:
                print(f"[Акк {acc_num}] Не смог отправить /start: {ex}", flush=True)

            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            async for _ in c.get_dialogs(limit=5):
                pass
            if me.first_name:
                TRUSTED_NAMES.append(me.first_name.lower())
            TRUSTED_NAMES.append(str(me.id))
            print(f"✅ Аккаунт {acc_num} успешно авторизован! (@{me.username})", flush=True)
            asyncio.create_task(bg_tasks(c, acc_num))
            asyncio.create_task(poll_bot_messages(c, acc_num))
            await asyncio.sleep(2)
        except Exception as e:
            print(f"⚠️ [Ошибка] Аккаунт {acc_num} не запущен: {e}", flush=True)

    TRUSTED_NAMES = list(set(TRUSTED_NAMES))
    print(f"💎 Белый список имен для распознавания трейдов: {TRUSTED_NAMES}", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
