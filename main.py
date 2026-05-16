# -*- coding: utf-8 -*-
import os, asyncio, random, datetime, threading
from flask import Flask
from pyrogram import Client, filters, handlers

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
my_usernames = set()  # Список юзернеймов твоих аккаунтов фермы

# --- ФУНКЦИЯ КЛИКА ---
async def smart_click(client, chat_id, message_id, variants, pick_first=False):
    try:
        async for message in client.get_chat_history(chat_id, limit=1):
            if message.id == message_id and message.reply_markup:
                for row in message.reply_markup.inline_keyboard:
                    for btn in row:
                        data = btn.callback_data or ""
                        if pick_first:
                            if "назад" not in btn.text.lower() and "back" not in data.lower():
                                await client.request_callback_answer(chat_id, message.id, data)
                                return True, btn.text
                        elif any(v in btn.text or data.startswith(v) for v in variants):
                            await client.request_callback_answer(chat_id, message.id, data)
                            return True, btn.text
    except Exception as e:
        print(f"❌ Ошибка клика: {e}", flush=True)
    return False, None

# --- ЛОГИКА ДЛЯ ОТПРАВИТЕЛЯ (ТОЛЬКО ПОДТВЕРЖДЕНИЕ В КОНЦЕ) ---
async def sender_confirm_logic(client, acc_id):
    # Ждем 25 секунд, пока принимающий аккаунт спокойно добавляет свои телефоны
    await asyncio.sleep(25)
    print(f"✍️ [Акк {acc_id} - Отправитель] Время вышло. Подтверждаю трейд со своей стороны...", flush=True)
    try:
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if msg.reply_markup:
                res, txt = await smart_click(client, bot_chat, msg.id, ["Подтвердить", "trade_confirm"])
                if res:
                    print(f"✅ [Акк {acc_id} - Отправитель] Успешно подтвердил чистый трейд!", flush=True)
    except Exception as e:
        print(f"❌ Ошибка подтверждения на стороне отправителя {acc_id}: {e}", flush=True)

# --- ЛОГИКА ДЛЯ ПОЛУЧАТЕЛЯ (ПОЛНЫЙ СБОР И НАПОЛНЕНИЕ ТРЕЙДА) ---
async def receiver_trade_logic(client, acc_id):
    print(f"📦 [Акк {acc_id} - Получатель] Начинаю процесс добавления телефонов в обмен...", flush=True)
    
    # Сверхнадежные шаги: тип, редкость и модель кликаются по первой кнопке без привязки к тексту
    steps = [
        {"n": "Добавить", "v": ["Добавить телефон", "trade_add_phone_start"]},
        {"n": "Тип", "v": [], "pick": True},       # Кликает первую кнопку состояния (Рабочие/Сломанные)
        {"n": "Редкость", "v": [], "pick": True},   # Кликает первую кнопку редкости (Ширпотреб) — ТЕПЕРЬ НЕ ЗАВИСАЕТ!
        {"n": "Модель", "v": [], "pick": True},     # Кликает первую доступную модель
        {"n": "Кол-во", "v": ["Добавить 1 шт.", "trade_add_single"]},
        {"n": "Финал", "v": ["Подтвердить", "trade_confirm"]}
    ]

    for step in steps:
        await asyncio.sleep(4)
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if msg.reply_markup:
                    res, txt = await smart_click(client, bot_chat, msg.id, step.get("v", []), step.get("pick", False))
                    if res:
                        print(f"⚡ [Акк {acc_id} - Получатель] Шаг [{step['n']}] пройден: {txt}", flush=True)
                        break
        except Exception as e:
            print(f"❌ Ошибка на шаге {step['n']} у получателя {acc_id}: {e}", flush=True)

# --- ЛОГИКА РУЧНОГО СБОРА С ФЕРМЫ ---
async def manual_farm_logic(client, acc_id):
    try:
        print(f"🚜 [Акк {acc_id}] Ручной сбор фермы по команде .farmn", flush=True)
        await client.send_message(bot_chat, "/tfarm")
        await asyncio.sleep(5)
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if msg.reply_markup:
                res, txt = await smart_click(client, bot_chat, msg.id, ["Снять деньги", "farm_claim"])
                if res:
                    print(f"💰 [Акк {acc_id}] Деньги с фермы успешно сняты вручную!", flush=True)
    except Exception as e:
        print(f"❌ Ошибка ручного сбора на акке {acc_id}: {e}", flush=True)

# --- ОБРАБОТЧИК ВХОДЯЩИХ СООБЩЕНИЙ ОТ ИГРОВОГО БОТА ---
async def handle_bot_messages(client, message):
    if not message.text: return
    text = message.text.lower()
    
    if "вам пришло предложение обмена от" in text:
        try:
            sender_username = text.split("от @")[1].split()[0].strip().replace(",", "").replace(".", "")
        except:
            sender_username = ""

        # Если трейд пришел от нашего же круга аккаунтов фермы
        if sender_username in my_usernames:
            try:
                acc_id = clients.index(client) + 1
            except:
                acc_id = "Х"
                
            print(f"🤝 [Акк {acc_id}] Принял уведомление. Трейд от своего же акка @{sender_username}! Нажимаю Принять...", flush=True)
            await asyncio.sleep(2) 
            
            res, txt = await smart_click(client, bot_chat, message.id, ["Принять", "trade_accept"])
            if res:
                print(f"✅ [Акк {acc_id}] Трейд принят! Перехожу к наполнению предметами...", flush=True)
                # Передаем задачу наполнения ПОЛУЧАТЕЛЮ обмена
                asyncio.create_task(receiver_trade_logic(client, acc_id))

# --- ОБРАБОТЧИК ТВОИХ СЛОВЕСНЫХ КОМАНД (.ping, .farmn, .t, .т) ---
async def handle_my_messages(client, message):
    if not message.text: return
    text = message.text.lower().strip()
    
    # --- КОМАНДА ПИНГ ---
    if text.startswith(".ping"):
        try:
            await message.edit("🚀 **Pyrofork юзербот полностью активен!**")
        except Exception as e:
            print(f"❌ Ошибка изменения сообщения: {e}", flush=True)
        return

    # --- КОМАНДА СБОРА С ФЕРМЫ (.farmn) ---
    if text.startswith(".farmn"):
        try:
            await message.delete()
        except: pass
        
        for i, cl in enumerate(clients):
            asyncio.create_task(manual_farm_logic(cl, i + 1))
        return

    # --- УНИВЕРСАЛЬНЫЙ ТРЕЙД (.trade, .t, .т) ---
    if text.startswith(".trade") or text.startswith(".t") or text.startswith(".т"):
        target = None
        parts = message.text.split()
        
        if message.reply_to_message:
            reply_user = message.reply_to_message.from_user
            if reply_user and reply_user.username:
                target = reply_user.username
        elif len(parts) >= 2:
            target = parts[1].replace("@", "")

        if target:
            try:
                await message.delete() 
            except: pass
            
            try:
                acc_id = clients.index(client) + 1
            except:
                acc_id = 1
                
            print(f"📣 [Акк {acc_id} - Отправитель] Инициирую трейд на @{target}...", flush=True)
            await client.send_message(bot_chat, f"/trade @{target}")
            
            # Если цель обмена — один из наших же ботов, запускаем таймер ожидания подтверждения
            if target.lower() in my_usernames:
                asyncio.create_task(sender_confirm_logic(client, acc_id))

# --- ФОНОВЫЕ ЗАДАЧИ ПО ТАЙМЕРУ (КАРТОЧКИ РАЗ В 2 ЧАСА) ---
async def bg_tasks(client, acc_id):
    print(f"🟢 [Акк {acc_id}] Фоновые задачи запущены! Отправляю первую карточку...", flush=True)
    try:
        await client.send_message(bot_chat, "ткарточка")
    except Exception as e:
        print(f"❌ Не удалось отправить стартовую карточку на акке {acc_id}: {e}", flush=True)

    while True:
        await asyncio.sleep(121 * 60)
        try:
            print(f"🃏 [Акк {acc_id}] Повторный круг: Отправляю 'ткарточка'...", flush=True)
            await client.send_message(bot_chat, "ткарточка")
            
            if acc_id != 5:
                now = datetime.datetime.utcnow()
                if now.hour == 21 and now.minute <= 25:
                    print(f"🚜 [Акк {acc_id}] Время авто-сбора фермы!", flush=True)
                    await client.send_message(bot_chat, "/tfarm")
                    await asyncio.sleep(10)
                    async for msg in client.get_chat_history(bot_chat, limit=1):
                        await smart_click(client, bot_chat, msg.id, ["Снять деньги", "farm_claim"])
        except Exception as e:
            print(f"❌ Ошибка в bg_tasks для аккаунта {acc_id}: {e}", flush=True)

# --- ЗАПУСК ВСЕХ КЛИЕНТОВ ---
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
        
        c.add_handler(handlers.MessageHandler(handle_my_messages, filters.me))
        c.add_handler(handlers.MessageHandler(handle_bot_messages, filters.chat(bot_chat) & ~filters.me))
        raw_clients.append((i+1, c))

    for acc_num, c in raw_clients:
        try:
            await c.start()
            clients.append(c)
            
            me = await c.get_me()
            if me.username:
                my_usernames.add(me.username.lower())
                
            print(f"✅ Аккаунт {acc_num} успешно авторизован! (@{me.username})", flush=True)
            asyncio.create_task(bg_tasks(c, acc_num))
        except Exception as e:
            print(f"⚠️ [Ошибка] Аккаунт {acc_num} НЕ запущен! Причина: {e}", flush=True)

    print(f"💎 Запуск завершен. Наших аккаунтов в базе для авто-принятия: {my_usernames}", flush=True)
    print(f"💎 Всего работает аккаунтов: {len(clients)} из {len(raw_clients)}", flush=True)
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
