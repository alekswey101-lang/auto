# -*- coding: utf-8 -*-
import os, asyncio, random, datetime, threading
from flask import Flask
from pyrogram import Client, handlers, filters
from pyrogram import raw

# --- СЕРВЕР ДЛЯ RENDER (KEEP-ALIVE) ---
app = Flask(__name__)
@app.route('/')
def health(): return "Ready and Running", 200

threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()

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
    """Ищет кнопку по ключевому слову и нажимает её."""
    if not message.reply_markup:
        print(f"[DEBUG click] ❌ НЕТ reply_markup у сообщения!", flush=True)
        return False
    try:
        print(f"[DEBUG click] Ищу кнопку по слову: '{keyword}'", flush=True)
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                text_l = btn.text.lower()
                data_l = (btn.callback_data or "").lower()
                print(f"[DEBUG click] кнопка: '{btn.text}' | data: '{btn.callback_data}'", flush=True)
                if keyword.lower() in text_l or keyword.lower() in data_l:
                    await client.request_callback_answer(message.chat.id, message.id, btn.callback_data)
                    print(f"[DEBUG click] ✅ Нажата кнопка: '{btn.text}'", flush=True)
                    return True
        print(f"[DEBUG click] ❌ Кнопка с '{keyword}' не найдена среди кнопок выше.", flush=True)
    except Exception as e:
        print(f"❌ click() ошибка: {e}", flush=True)
    return False

# --- СВЕРХНАДЕЖНЫЙ ДВИЖОК ПОШАГОВЫХ КЛИКОВ ---
async def execute_menu_step(client, step_name, keywords, pick_first, last_fp):
    for attempt in range(12):
        await asyncio.sleep(2)
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if not msg.reply_markup:
                    continue

                fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
                if last_fp and fp == last_fp:
                    continue

                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        text_lower = btn.text.lower().strip()
                        data_lower = (btn.callback_data or "").lower().strip()

                        if pick_first:
                            if "назад" not in text_lower and "back" not in data_lower and "изменить" not in text_lower:
                                await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                                print(f"✅ [{step_name}] Авто-выбор первой кнопки: [{btn.text}]", flush=True)
                                return True, fp
                        else:
                            for kw in keywords:
                                kw_l = kw.lower().strip()
                                if kw_l in text_lower or data_lower.startswith(kw_l):
                                    await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                                    print(f"✅ [{step_name}] Успешно нажата кнопка: [{btn.text}]", flush=True)
                                    return True, fp
        except Exception as e:
            print(f"❌ Ошибка выполнения шага {step_name}: {e}", flush=True)
    return False, last_fp

# --- ЛОГИКА ДЛЯ ПОЛУЧАТЕЛЯ ---
async def receiver_trade_logic(client, acc_id):
    print(f"📦 [Акк {acc_id} - Получатель] Запуск умного сборщика телефонов в трейд...", flush=True)

    res, last_fp = await execute_menu_step(client, "Кнопка Добавить", ["добавить телефон", "trade_add_phone_start"], False, "")
    if not res: return

    res, last_fp = await execute_menu_step(client, "Выбор Состояния", [], True, last_fp)
    if not res: return

    res, last_fp = await execute_menu_step(client, "Выбор Редкости", [], True, last_fp)
    if not res: return

    res, last_fp = await execute_menu_step(client, "Выбор Модели", [], True, last_fp)
    if not res: return

    res, last_fp = await execute_menu_step(client, "Количество 1шт", ["добавить 1 шт.", "trade_add_single"], False, last_fp)
    if not res: return

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

    # ДЕБАГ — ВСЕ входящие сообщения без исключения
    chat_info = f"{getattr(message.chat, 'username', None)} | id={getattr(message.chat, 'id', None)}"
    print(f"[ALL MSG] Акк {acc_id} | чат: {chat_info} | текст: '{(message.text or '')[:80]}'", flush=True)

    if not message.chat:
        return

    # Проверяем и по username чата и по username отправителя
    chat_username = (getattr(message.chat, 'username', None) or '').lower()
    sender_username = (getattr(message.from_user, 'username', None) or '').lower() if message.from_user else ''

    is_our_bot = (chat_username == bot_chat.lower()) or (sender_username == bot_chat.lower())

    if not is_our_bot:
        return
    if message.from_user and message.from_user.id == getattr(client, "me_id", 0):
        return
    if not message.text:
        return

    text = message.text.lower()

    # ДЕБАГ — каждое сообщение от бота
    print(f"[DEBUG] Акк {acc_id} | markup: {bool(message.reply_markup)} | текст: '{message.text[:120]}'", flush=True)

    # 1. ВХОДЯЩИЙ ТРЕЙД
    if "предложение обмена" in text or "пришло предложение" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер трейда сработал!", flush=True)
        print(f"[DEBUG] Акк {acc_id} | TRUSTED_NAMES: {TRUSTED_NAMES}", flush=True)

        is_trusted = any(name in text for name in TRUSTED_NAMES)
        print(f"[DEBUG] Акк {acc_id} | is_trusted: {is_trusted}", flush=True)

        if not is_trusted:
            print(f"🙅 [Акк {acc_id}] Фильтр отклонил трейд. Полный текст: '{message.text}'", flush=True)
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
    if "готовность:" in text and "❌" in text and "✅" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер ГОТОВНОСТИ сработал!", flush=True)
        await delay(1.5, 3.0)
        if await click(client, message, "готов"):
            print(f"✅ [Акк {acc_id}] Нажал ГОТОВ.", flush=True)
        else:
            print(f"⚠️ [Акк {acc_id}] Кнопка 'Готов' не найдена!", flush=True)
        return

    # 3. АВТОПОДТВЕРЖДЕНИЕ
    if "подтвердите обмен" in text or "подтвердите" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер ПОДТВЕРЖДЕНИЯ сработал!", flush=True)
        await delay(1.0, 2.0)
        if await click(client, message, "подтвердить"):
            print(f"🎉 [Акк {acc_id}] Обмен подтверждён!", flush=True)
        else:
            print(f"⚠️ [Акк {acc_id}] Кнопка 'Подтвердить' не найдена!", flush=True)
        return
        
    # 2. АВТОГОТОВНОСТЬ
    if "готовность:" in text and "❌" in text and "✅" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер ГОТОВНОСТИ сработал!", flush=True)
        await delay(1.5, 3.0)
        if await click(client, message, "готов"):
            print(f"✅ [Акк {acc_id}] Нажал ГОТОВ.", flush=True)
        else:
            print(f"⚠️ [Акк {acc_id}] Кнопка 'Готов' не найдена!", flush=True)
        return

    # 3. АВТОПОДТВЕРЖДЕНИЕ
    if "подтвердите обмен" in text or "подтвердите" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер ПОДТВЕРЖДЕНИЯ сработал!", flush=True)
        await delay(1.0, 2.0)
        if await click(client, message, "подтвердить"):
            print(f"🎉 [Акк {acc_id}] Обмен подтверждён!", flush=True)
        else:
            print(f"⚠️ [Акк {acc_id}] Кнопка 'Подтвердить' не найдена!", flush=True)
        return

    # === ДЕБАГ: каждое сообщение от бота ===
    print(f"[DEBUG] Акк {acc_id} | markup: {bool(message.reply_markup)} | текст: '{message.text[:120]}'", flush=True)

    # 1. ВХОДЯЩИЙ ТРЕЙД — проверка белого списка + принятие
    if "предложение обмена" in text or "пришло предложение" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер трейда сработал!", flush=True)
        print(f"[DEBUG] Акк {acc_id} | TRUSTED_NAMES: {TRUSTED_NAMES}", flush=True)

        is_trusted = any(name in text for name in TRUSTED_NAMES)
        print(f"[DEBUG] Акк {acc_id} | is_trusted: {is_trusted}", flush=True)

        if not is_trusted:
            print(f"🙅 [Акк {acc_id}] Фильтр отклонил трейд. Полный текст: '{message.text}'", flush=True)
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
    if "готовность:" in text and "❌" in text and "✅" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер ГОТОВНОСТИ сработал!", flush=True)
        await delay(1.5, 3.0)
        if await click(client, message, "готов"):
            print(f"✅ [Акк {acc_id}] Нажал ГОТОВ.", flush=True)
        else:
            print(f"⚠️ [Акк {acc_id}] Кнопка 'Готов' не найдена!", flush=True)
        return

    # 3. АВТОПОДТВЕРЖДЕНИЕ
    if "подтвердите обмен" in text or "подтвердите" in text:
        print(f"[DEBUG] Акк {acc_id} | Триггер ПОДТВЕРЖДЕНИЯ сработал!", flush=True)
        await delay(1.0, 2.0)
        if await click(client, message, "подтвердить"):
            print(f"🎉 [Акк {acc_id}] Обмен подтверждён!", flush=True)
        else:
            print(f"⚠️ [Акк {acc_id}] Кнопка 'Подтвердить' не найдена!", flush=True)
        return

# Слушаем и новые, и отредактированные сообщения от бота
async def handle_bot_messages(client, message):
    await process_bot_logic(client, message)

async def handle_bot_edited_messages(client, message):
    await process_bot_logic(client, message)

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
        try: await message.edit("🚀 **Pyrofork юзербот полностью активен!**")
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
        print(f"⚡ [Акк {acc_id}] Поймал команду трейда: '{message.text}'", flush=True)
        target = None

        if len(parts) == 2 and parts[1] in ACC_MACROS:
            target = ACC_MACROS[parts[1]]
        elif message.reply_to_message and message.reply_to_message.from_user:
            user = message.reply_to_message.from_user
            target = user.username or str(user.id)
        elif len(parts) >= 2:
            target = parts[1].replace("@", "").strip()

        if not target:
            print(f"⚠️ [Акк {acc_id}] Ошибка: не удалось определить цель для обмена!", flush=True)
            return

        try: await message.delete()
        except: pass

        print(f"📣 [Акк {acc_id} - Отправитель] Инициирую трейд на {target}...", flush=True)
        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        await client.send_message(bot_chat, bot_cmd)

        if target.lower() in TRUSTED_NAMES:
            asyncio.create_task(sender_confirm_logic(client, acc_id))

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
        
        c.add_handler(handlers.MessageHandler(handle_my_messages))
        c.add_handler(handlers.MessageHandler(handle_bot_messages, filters.incoming))
        c.add_handler(handlers.MessageHandler(handle_bot_messages, filters.private & filters.incoming))
        c.add_handler(handlers.EditedMessageHandler(handle_bot_edited_messages))
        
        raw_clients.append((i + 1, c))
        
    for acc_num, c in raw_clients:
        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            # Принудительная синхронизация апдейтов
            async for _ in c.get_dialogs(limit=5):
                pass
            if me.first_name:
                TRUSTED_NAMES.append(me.first_name.lower())
            TRUSTED_NAMES.append(str(me.id))
            print(f"✅ Аккаунт {acc_num} успешно авторизован! (@{me.username} | Имя: {me.first_name})", flush=True)
            asyncio.create_task(bg_tasks(c, acc_num))
        except Exception as e:
            print(f"⚠️ [Ошибка] Аккаунт {acc_num} не запущен: {e}", flush=True)

    TRUSTED_NAMES = list(set(TRUSTED_NAMES))
    print(f"💎 Белый список имен для распознавания трейдов: {TRUSTED_NAMES}", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
