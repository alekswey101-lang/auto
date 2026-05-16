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

# --- ЛОГИКА ТРЕЙДА ---
async def trade_logic(client, target_user, acc_id):
    print(f"🔄 [Акк {acc_id}] Начинаю трейд на {target_user}...", flush=True)
    try:
        await client.send_message(bot_chat, f"/trade @{target_user}")
        
        steps = [
            {"n": "Добавить", "v": ["Добавить телефон", "trade_add_phone_start"]},
            {"n": "Тип", "v": ["Рабочий", "Сломанный", "trd_wrk", "trd_brk"]},
            {"n": "Редкость", "v": ["Ширпотреб", "trade_add_rarity"]},
            {"n": "Модель", "v": [], "pick": True}, 
            {"n": "Кол-во", "v": ["Добавить 1 шт.", "trade_add_single"]},
            {"n": "Финал", "v": ["Подтвердить", "trade_confirm"]}
        ]

        for step in steps:
            await asyncio.sleep(4) # Пауза между шагами, чтобы бот успел обновить кнопки
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if msg.reply_markup:
                    res, txt = await smart_click(client, bot_chat, msg.id, step.get("v", []), step.get("pick", False))
                    if res:
                        print(f"📦 [Акк {acc_id}] Успешный шаг [{step['n']}]: {txt}", flush=True)
                        break # Выходим из внутреннего перебора сообщения, идем к следующему шагу step
    except Exception as e:
        print(f"❌ Ошибка в процессе трейда на акке {acc_id}: {e}", flush=True)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
async def handle_messages(client, message):
    if not message.text: return
    
    # ПИНГ
    if message.text.startswith(".ping"):
        try:
            await message.edit("🚀 **Pyrofork юзербот полностью активен!**")
            print("🔔 Команда .ping успешно сработала", flush=True)
        except Exception as e:
            print(f"❌ Ошибка изменения сообщения: {e}", flush=True)

    # ТРЕЙД
    elif message.text.startswith(".trade"):
        parts = message.text.split()
        if len(parts) < 2: return
        target = parts[1].replace("@", "")
        try:
            await message.delete()
        except: pass
        
        try:
            acc_id = clients.index(client) + 1
        except:
            acc_id = 1
            
        asyncio.create_task(trade_logic(client, target, acc_id))

# --- ФОНОВЫЕ ЗАДАЧИ ---
async def bg_tasks(client, acc_id):
    # МГНОВЕННЫЙ СТАРТ ПРИ ЗАПУСКЕ
    print(f"🟢 [Акк {acc_id}] Фоновые задачи запущены! Отправляю первую карточку...", flush=True)
    try:
        await client.send_message(bot_chat, "ткарточка")
    except Exception as e:
        print(f"❌ Не удалось отправить стартовую карточку на акке {acc_id}: {e}", flush=True)

    while True:
        await asyncio.sleep(121 * 60) # Ждем 2 часа перед следующим кругом
        try:
            print(f"🃏 [Акк {acc_id}] Повторный круг: Отправляю 'ткарточка'...", flush=True)
            await client.send_message(bot_chat, "ткарточка")
            
            # Авто-сбор фермы в 21:10 UTC (02:10 по Шымкенту)
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
    global clients
    print("🛠 Инициализация Pyrofork клиентов...", flush=True)
    
    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": 
            continue
        
        # Запускаем сессии в памяти (без создания файлов базы данных)
        c = Client(
            name=f"memory_session_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True
        )
        
        c.add_handler(handlers.MessageHandler(handle_messages, filters.me))
        clients.append(c)

    # Запуск всех клиентов параллельно
    for i, c in enumerate(clients):
        await c.start()
        acc_id = i + 1
        print(f"✅ Аккаунт {acc_id} успешно авторизован!", flush=True)
        # Запускаем фоновые задачи без искусственных задержек
        asyncio.create_task(bg_tasks(c, acc_id))

    print("💎 Все аккаунты онлайн, карточки отправлены. Ожидаю команд.", flush=True)
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
                        
