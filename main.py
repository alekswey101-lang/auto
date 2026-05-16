# -*- coding: utf-8 -*-
import os, asyncio, random, datetime, threading
from flask import Flask
from pyrogram import Client, handlers

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
my_usernames = set()  # Список юзернеймов и ID твоих аккаунтов

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
        async_for msg in client.get_chat_history(bot_chat, limit=1):
            if msg.reply_markup:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "подтвердить" in btn.text.lower() or (btn.callback_data and "trade_confirm" in btn.callback_data.lower()):
                            await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                            print(f"✅ [Акк {acc_id} - Отправитель] Трейд зафиксирован и подтвержден!", flush=True)
                            return
    except Exception as e:
        print(f"❌ Ошибка подтверждения у отправителя {acc_id}: {e}", flush=True)

# --- ЛОГИКА РУЧНОГО СБОРА С ФЕРМЫ ---
async def manual_farm_logic(client, acc_id):
    try:
        print(f"🚜 [Акк {acc_id}] Собираю прибыль...", flush=True)
        await client.send_message(bot_chat, "/tfarm")
        await asyncio.sleep(4)
        async_for msg in client.get_chat_history(bot_chat, limit=1):
            if msg.reply_markup:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "снять деньги" in btn.text.lower() or (btn.callback_data and "farm_claim" in btn.callback_data.lower()):
                            await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                            print(f"💰 [Акк {acc_id}] Деньги успешно переведены на баланс!", flush=True)
                            return
    except Exception as e:
        print(f"❌ Ошибка сбора на акке {acc_id}: {e}", flush=True)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ИГРОВОГО БОТА ---
async def handle_bot_messages(client, message):
    # Железный фильтр чата: приводим к нижнему регистру во избежание PhoneGetCardsBot != phonegetcardsbot
    if not message.chat or not message.chat.username or message.chat.username.lower() != bot_chat.lower():
        return

    # Защита от обработки собственных сообщений
    if message.from_user and message.from_user.id == getattr(client, "me_id", 0):
        return
        
    if not message.text: return
    text = message.text.lower()
    
    # Проверяем, что это уведомление о входящем обмене
    if "предложение обмена" in text or "пришло предложение" in text:
        # Проверяем, есть ли упоминание любого аккаунта нашей фермы внутри текста сообщения
        is_from_farm = False
        for uname in my_usernames:
            if uname in text:
                is_from_farm = True
                break

        if is_from_farm:
            try: acc_id = clients.index(client) + 1
            except: acc_id = "Х"
                
            print(f"🤝 [Акк {acc_id}] Обнаружен внутренний обмен! Нажимаю Принять...", flush=True)
            await asyncio.sleep(2) 
            
            try:
                if message.reply_markup:
                    for row in message.reply_markup.inline_keyboard:
                        for btn in row:
                            text_btn = btn.text.lower()
                            data_btn = (btn.callback_data or "").lower()
                            
                            if "принять" in text_btn or "accept" in data_btn or "trade_accept" in data_btn:
                                await client.request_callback_answer(message.chat.id, message.id, btn.callback_data)
                                print(f"✅ [Акк {acc_id}] Входящий трейд успешно принят! Запускаю заполнение...", flush=True)
                                asyncio.create_task(receiver_trade_logic(client, acc_id))
                                return
            except Exception as e:
                print(f"❌ Не удалось нажать Принять на акке {acc_id}: {e}", flush=True)

# --- ЖЕЛЕЗНЫЙ ОБРАБОТЧИК ТВОИХ СЛОВЕСНЫХ КОМАНД ---
async def handle_my_messages(client, message):
    if not message.text: return
    
    my_id = getattr(client, "me_id", 0)
    if not message.from_user or message.from_user.id != my_id:
        return
        
    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()
    
    try: acc_id = clients.index(client) + 1
    except: acc_id = 1

    if cmd == ".ping":
        try: await message.edit("🚀 **Pyrofork юзербот полностью активен!**")
        except: pass
        return

    if cmd == ".farmn":
        try: await message.delete()
        except: pass
        for i, cl in enumerate(clients):
            asyncio.create_task(manual_farm_logic(cl, i + 1))
        return

    if cmd in [".trade", ".t", ".т"] or cmd.startswith(".t@") or cmd.startswith(".т@"):
        print(f"⚡ [Акк {acc_id}] Поймал команду трейда: '{message.text}'", flush=True)
        target = None
        
        if message.reply_to_message and message.reply_to_message.from_user:
            user = message.reply_to_message.from_user
            target = user.username or str(user.id)
        elif "@" in parts[0]:
            target = parts[0].split("@", 1)[1].strip()
        elif len(parts) >= 2:
            target = parts[1].replace("@", "").strip()

        if not target:
            print(f"⚠️ [Акк {acc_id}] Ошибка: не указан юзернейм и нет реплая!", flush=True)
            try: await message.edit("❌ **Ошибка:** Напишите `.t @username` или ответьте командой `.t` на сообщение игрока.")
            except: pass
            return

        try: await message.delete()
        except: pass
            
        print(f"📣 [Акк {acc_id} - Отправитель] Инициирую трейд на {target}...", flush=True)
        
        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        await client.send_message(bot_chat, bot_cmd)
        
        if target.lower() in my_usernames or target in my_usernames:
            asyncio.create_task(sender_confirm_logic(client, acc_id))

# --- ФОНОВЫЕ ЗАДАЧИ ПО ТАЙМЕРУ ---
async def bg_tasks(client, acc_id):
    print(f"🟢 [Акк {acc_id}] Цикл отправки карточек запущен!", flush=True)
    try:
        await client.send_message(bot_chat, "ткарточка")
    except Exception as e:
        print(f"❌ Стартовая карточка не ушла на акке {acc_id}: {e}", flush=True)

    while True:
        await asyncio.sleep(121 * 60)
        try:
            print(f"🃏 [Акк {acc_id}] Время пришло: отправляю 'ткарточка'...", flush=True)
            await client.send_message(bot_chat, "ткарточка")
            
            if acc_id != 5:
                now = datetime.datetime.utcnow()
                if now.hour == 21 and now.minute <= 25:
                    await client.send_message(bot_chat, "/tfarm")
                    await asyncio.sleep(10)
                    async_for msg in client.get_chat_history(bot_chat, limit=1):
                        if msg.reply_markup:
                            for row in msg.reply_markup.inline_keyboard:
                                for btn in row:
                                    if "снять деньги" in btn.text.lower() or (btn.callback_data and "farm_claim" in btn.callback_data.lower()):
                                        await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
        except Exception as e:
            print(f"❌ Ошибка в таймере аккаунта {acc_id}: {e}", flush=True)

# --- ЗАПУСК КЛИЕНТОВ ---
async def start_bot():
    global clients, my_usernames
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
            in_memory=True
        )
        
        c.add_handler(handlers.MessageHandler(handle_my_messages))
        c.add_handler(handlers.MessageHandler(handle_bot_messages))
        raw_clients.append((i+1, c))

    for acc_num, c in raw_clients:
        try:
            await c.start()
            clients.append(c)
            
            me = await c.get_me()
            c.me_id = me.id  
            
            if me.username:
                my_usernames.add(me.username.lower())
            my_usernames.add(str(me.id)) 
                
            print(f"✅ Аккаунт {acc_num} успешно авторизован! (@{me.username} | ID: {me.id})", flush=True)
            asyncio.create_task(bg_tasks(c, acc_num))
        except Exception as e:
            print(f"⚠️ [Ошибка] Аккаунт {acc_num} не запущен: {e}", flush=True)

    print(f"💎 База своих аккаунтов для авто-трейда: {my_usernames}", flush=True)
    print(f"💎 Юзербот запущен. Активных сессий: {len(clients)} из {len(raw_clients)}", flush=True)
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
