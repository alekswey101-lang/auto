# -*- coding: utf-8 -*-
import os
import asyncio
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
current_bot_msg = {}  
is_collecting = {}    

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

# --- ПРЯМОЙ И НАДЕЖНЫЙ КЛИКЕР ---
async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                    # Обычный await запрос — медленнее на 5мс, зато работает безотказно
                    await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                    return True
    except:
        pass
    return False

# --- КЛИК ПО ПЕРВОЙ КНОПКЕ ХАРАКТЕРИСТИК ---
async def click_first(client, message) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                text_lower = btn.text.lower().strip()
                data_lower = (btn.callback_data or "").lower().strip()
                if any(x in text_lower or x in data_lower for x in ["назад", "back", "изменить", "отмена", "подтвердить", "главное", "готов"]):
                    continue
                await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                return True
    except:
        pass
    return False

# --- ЛИНЕЙНЫЙ ТРАДИЦИОННЫЙ СБОРЩИК ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Трейд принят. Начинаю сборку предметов...", flush=True)
    is_collecting[acc_id] = True  
    added_count = 0  
    
    for loop_index in range(1, 35):
        if added_count >= 10:
            break

        # Проверяем текст прямо в процессе
        try:
            async for current_msg in client.get_chat_history(bot_chat, limit=1):
                if current_msg and current_msg.text:
                    msg_text = current_msg.text.lower()
                    if "10/10" in msg_text and "слот" in msg_text:
                        added_count = 10
                        break
        except:
            pass

        if added_count >= 10:
            break

        # Шаг 1: Жмем "Добавить телефон"
        success = False
        for _ in range(10):
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if msg.reply_markup and any("добавить телефон" in b.text.lower() for r in msg.reply_markup.inline_keyboard for b in r):
                    if await click(client, msg, "добавить телефон"):
                        success = True
                        break
            await asyncio.sleep(0.1)
        if not success: 
            continue

        await asyncio.sleep(0.15) # Микро-пауза на прогрузку меню бота

        # Шаг 2: Состояние (первая кнопка)
        for _ in range(10):
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if await click_first(client, msg): break
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.15)

        # Шаг 3: Редкость (первая кнопка)
        for _ in range(10):
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if await click_first(client, msg): break
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.15)

        # Шаг 4: Модель (первая кнопка)
        for _ in range(10):
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if await click_first(client, msg): break
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.15)

        # Шаг 5: Жмем "Добавить 1 шт."
        success_add = False
        for _ in range(10):
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if msg.reply_markup and any("добавить 1 шт." in b.text.lower() for r in msg.reply_markup.inline_keyboard for b in r):
                    if await click(client, msg, "добавить 1 шт."):
                        success_add = True
                        break
            await asyncio.sleep(0.1)
        
        if success_add:
            added_count += 1
        await asyncio.sleep(0.15)

    is_collecting[acc_id] = False

    # Завершение сделки твинком
    print(f"⚖️ [Акк {acc_id}] Сборка завершена. Жму готов и подтвердить...", flush=True)
    for _ in range(10):
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if await click(client, msg, "готов"): break
        await asyncio.sleep(0.2)

    await asyncio.sleep(1.0)

    for _ in range(10):
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if await click(client, msg, "подтвердить"): break
        await asyncio.sleep(0.2)

# --- ПРОСТОЙ И НАДЕЖНЫЙ ЦИКЛ ПУЛИНГА ИСТОРИИ ЧАТА ---
async def poll_bot_messages(client, acc_id):
    last_msg_id = 0
    last_buttons_fp = ""
    
    while True:
        try:
            # Скрипт не зависит от хэндлеров, он просто проверяет последнее сообщение в чате
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if not msg or not msg.text:
                    continue

                text = msg.text.lower()

                # Если это входящий трейд и мы сейчас ничего не собираем
                if ("предложение обмена" in text or "пришло предложение" in text) and not is_collecting.get(acc_id, False):
                    if "ваше предложение обмена отправлено" not in text:
                        if msg.reply_markup and any("принять" in b.text.lower() for r in msg.reply_markup.inline_keyboard for b in r):
                            if await click(client, msg, "принять"):
                                is_collecting[acc_id] = True
                                asyncio.create_task(receiver_trade_logic(client, acc_id))

                # Если это финал
                if "подтвердите обмен" in text or "подтвердите" in text:
                    await click(client, msg, "подтвердить")
                
                # Синхронизация основы
                if "готовность:" in text and text.count("✅") >= 1:
                    # Проверяем, что этот аккаунт — основа, отправившая трейд
                    if current_bot_msg.get(acc_id) == "sender_waiting":
                        if await click(client, msg, "готов"):
                            current_bot_msg[acc_id] = "sender_confirmed"
                            await asyncio.sleep(0.8)
                            await click(client, msg, "подтвердить")
                break
        except Exception as e:
            pass
        await asyncio.sleep(0.25) # Безопасный тайм-аут пулинга, чтобы Telegram не выдавал FloodWait

# --- МАКРОСЫ ДЛЯ ОТПРАВКИ ТРЕЙДА (.Т) ---
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
        try: await message.edit("🚀 **Юзербот активен!**")
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
        current_bot_msg[acc_id] = "sender_waiting" # Помечаем, что этот акк — основа в данной сделке
        await client.send_message(bot_chat, bot_cmd)

async def bg_tasks(client, acc_id):
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    while True:
        await asyncio.sleep(121 * 60)
        try: await client.send_message(bot_chat, "ткарточка")
        except: pass

async def start_bot():
    global clients
    print("🛠 Перезапуск фермы в классическом режиме пулинга...", flush=True)

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

    print("🚀 Старый добрый рабочий режим запущен. Проверяй!", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
