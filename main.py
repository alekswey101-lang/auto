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
            await asyncio.sleep(4)
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if msg.reply_markup:
                    res, txt = await smart_click(client, bot_chat, msg.id, step.get("v", []), step.get("pick", False))
                    if res:
                        print(f"📦 [Акк {acc_id}] Успешный шаг [{step['n']}]: {txt}", flush=True)
                        break
    except Exception as e:
        print(f"❌ Ошибка в процессе трейда на акке {acc_id}: {e}", flush=True)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
async def handle_messages(client, message):
    if not message.text: return
    text = message.text.lower().strip()
    
    # --- КУСОК КОМАНДЫ ПИНГ ---
    if text.startswith(".ping"):
        try:
            await message.edit("🚀 **Pyrofork юзербот полностью активен!**")
            print("🔔 Команда .ping успешно сработала", flush=True)
        except Exception as e:
            print(f"❌ Ошибка изменения сообщения: {e}", flush=True)
        return

    # --- УНИВЕРСАЛЬНЫЙ ТРЕЙД (.trade, .t, .т) ---
    if text.startswith(".trade") or text.startswith(".t") or text.startswith(".т"):
        target = None
        parts = message.text.split()
        
        # Вариант 1: Трейд через Reply (ответ на сообщение)
        if message.reply_to_message:
            reply_user = message.reply_to_message.from_user
            if reply_user and reply_user.username:
                target = reply_user.username
            else:
                # Если у юзера нет юзернейма, пишем ошибку в лог и выходим
                print("⚠️ Не удается запустить трейд через реплей: у пользователя нет @username", flush=True)
                return

        # Вариант 2: Трейд по вписанному юзернейму (например, .t @asd123)
        elif len(parts) >= 2:
            target = parts[1].replace("@", "")

        # Если цель определена — запускаем
        if target:
            try:
                await message.delete() # Удаляем наше триггер-сообщение
            except: 
                pass
            
            try:
                acc_id = clients.index(client) + 1
            except:
                acc_id = 1
                
            asyncio.create_task(trade_logic(client, target, acc_id))

# --- ФОНОВЫЕ ЗАДАЧИ ---
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
    global clients
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
        c.add_handler(handlers.MessageHandler(handle_messages, filters.me))
        raw_clients.append((i+1, c))

    for acc_num, c in raw_clients:
        try:
            await c.start()
            clients.append(c)
            print(f"✅ Аккаунт {acc_num} успешно авторизован!", flush=True)
            asyncio.create_task(bg_tasks(c, acc_num))
        except Exception as e:
            print(f"⚠️ [Ошибка] Аккаунт {acc_num} НЕ запущен! Причина: {e}", flush=True)

    print(f"💎 Запуск завершен. Работает аккаунтов: {len(clients)} из {len(raw_clients)}", flush=True)
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
