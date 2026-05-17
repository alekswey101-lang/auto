# -*- coding: utf-8 -*-
import os
import asyncio
import threading
from flask import Flask
from pyrogram import Client, handlers, filters
from pyrogram.types import Message
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
is_collecting = {}    
added_count = {}

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

# --- МГНОВЕННЫЙ КЛИКЕР (БЕЗ ОЖИДАНИЯ ОТВЕТА СЕТИ) ---
def fast_click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                    asyncio.create_task(client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=1))
                    return True
    except:
        pass
    return False

# --- МОМЕНТАЛЬНЫЙ КЛИК ПО ПЕРВОЙ ДОСТУПНОЙ КНОПКЕ ---
def fast_click_first(client, message) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                text_lower = btn.text.lower().strip()
                data_lower = (btn.callback_data or "").lower().strip()
                
                if any(x in text_lower or x in data_lower for x in ["назад", "back", "изменить", "отмена", "подтвердить", "главное", "готов"]):
                    continue
                asyncio.create_task(client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=1))
                return True
    except:
        pass
    return False

# --- ОБРАБОТЧИК ДЛЯ ТВИНКА (ПРИЕМ И СБОРКА НА СВЕРХСКОРОСТИ) ---
async def handle_bot_updates(client, message: Message):
    if not message.from_user or message.from_user.username != bot_chat:
        return

    try:
        acc_id = clients.index(client) + 1
    except:
        return

    text = message.text.lower() if message.text else ""

    # 1. ИСПРАВЛЕННЫЙ ФОРСИРОВАННЫЙ ПРИЕМ ТРЕЙДА (ПРОБИВАЕТ ЛАГ ПОЯВЛЕНИЯ КНОПКИ)
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return
            
        print(f"🤝 [Акк {acc_id}] Замечен входящий трейд! Ловлю кнопку принять...", flush=True)
        # В течение 1.5 секунд активно перепроверяем историю чата, ожидая появления кнопки от бота
        for _ in range(15):
            try:
                async for fresh_msg in client.get_chat_history(bot_chat, limit=1):
                    if fresh_msg.reply_markup:
                        if fast_click(client, fresh_msg, "принять"):
                            print(f"🚀 [Акк {acc_id}] Трейд успешно принят!", flush=True)
                            is_collecting[acc_id] = True
                            added_count[acc_id] = 0
                            return
            except:
                pass
            await asyncio.sleep(0.1) # Микро-шаг ожидания генерации кнопки кнопко-ботом
        return

    # 2. ЛОГИКА СБОРКИ НА ЖИВЫХ ХЭНДЛЕРАХ
    if is_collecting.get(acc_id, False):
        if "10/10" in text and "слот" in text:
            is_collecting[acc_id] = False
            print(f"🏁 [Акк {acc_id}] Слоты забиты 10/10. Нажимаю ГОТОВ...", flush=True)
            fast_click(client, message, "готов")
            return

        if added_count.get(acc_id, 0) >= 10:
            is_collecting[acc_id] = False
            print(f"🏁 [Акк {acc_id}] Счетчик достиг 10 тел. Нажимаю ГОТОВ...", flush=True)
            fast_click(client, message, "готов")
            return

        # Шаг 1: Если мы в главном меню обмена и видим "Добавить телефон"
        if message.reply_markup and any("добавить телефон" in btn.text.lower() for row in message.reply_markup.inline_keyboard for btn in row):
            fast_click(client, message, "добавить телефон")
            return

        # Шаг 5: Если дошли до выбора количества
        if message.reply_markup and any("добавить 1 шт." in btn.text.lower() for row in message.reply_markup.inline_keyboard for btn in row):
            if fast_click(client, message, "добавить 1 шт."):
                added_count[acc_id] = added_count.get(acc_id, 0) + 1
            return

        # Шаги 2, 3, 4: Выбор Состояния -> Редкости -> Модели
        if message.reply_markup:
            fast_click_first(client, message)
            return

    # 3. Финальный апрув сделки твинком
    if "подтвердите обмен" in text or "подтвердите" in text:
        fast_click(client, message, "подтвердить")
        return

# --- ОБРАБОТЧИК ДЛЯ ОСНОВЫ (ЖДЕТ ТВИНКА И ЗАКРЫВАЕТ СДЕЛКУ) ---
async def handle_sender_updates(client, message: Message):
    if not message.from_user or message.from_user.username != bot_chat:
        return

    text = message.text.lower() if message.text else ""
    
    if "готовность:" in text and text.count("✅") >= 1:
        if fast_click(client, message, "готов"):
            await asyncio.sleep(0.5)
            fast_click(client, message, "подтвердить")

# --- ОТПРАВКА КОМАНДЫ .TRADE / .T ---
async def handle_my_messages(client, message):
    if not message.text: return
    my_id = getattr(client, "me_id", 0)
    if not message.from_user or message.from_user.id != my_id: return

    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    if cmd == ".ping":
        try: await message.edit("🚀 **Сверхзвуковой Юзербот онлайн!**")
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

async def bg_tasks(client, acc_id):
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    while True:
        await asyncio.sleep(121 * 60)
        try: await client.send_message(bot_chat, "ткарточка")
        except: pass

async def start_bot():
    global clients
    print("🛠 Старт новой архитектуры на чистых хэндлерах событий...", flush=True)

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
        c.add_handler(handlers.MessageHandler(handle_bot_updates))
        c.add_handler(handlers.MessageHandler(handle_sender_updates))
        
        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            async for _ in c.get_dialogs(limit=5): pass
            print(f"✅ Аккаунт {i+1} запущен: @{me.username}", flush=True)
            
            is_collecting[i+1] = False
            added_count[i+1] = 0
            asyncio.create_task(bg_tasks(c, i+1))
        except Exception as e:
            print(f"⚠️ Ошибка аккаунта {i+1}: {e}", flush=True)

    print("🚀 Исправленная ультра-скоростная версия запущена!", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
