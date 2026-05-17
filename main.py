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

# --- НАДЕЖНЫЙ СКОРОСТНОЙ КЛИКЕР ---
async def async_click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                    await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=1)
                    return True
    except:
        pass
    return False

# --- КЛИК ПО ПЕРВОЙ КНОПКЕ (ДЛЯ ВЫБОРА ХАРАКТЕРИСТИК) ---
async def async_click_first(client, message) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                text_lower = btn.text.lower().strip()
                data_lower = (btn.callback_data or "").lower().strip()
                if any(x in text_lower or x in data_lower for x in ["назад", "back", "изменить", "отмена", "подтвердить", "главное", "готов"]):
                    continue
                await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=1)
                return True
    except:
        pass
    return False

# --- ИЗОЛИРОВАННАЯ ЛОГИКА СБОРКИ (ПИПЕЛАЙН) ---
async def run_turbo_collection(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Запуск турбо-движка сборки 10 предметов...", flush=True)
    added_count[acc_id] = 0
    
    # Даем боту 0.3 сек прийти в себя после открытия трейда
    await asyncio.sleep(0.3)
    
    for _ in range(40): # Максимум 40 шагов-кликов на всю сессию, чтобы не зациклилось
        if not is_collecting.get(acc_id, False) or added_count.get(acc_id, 0) >= 10:
            break
            
        try:
            # Всегда берем самое актуальное состояние чата напрямую
            async for msg in client.get_chat_history(bot_chat, limit=1):
                text = msg.text.lower() if msg.text else ""
                
                if "10/10" in text and "слот" in text:
                    is_collecting[acc_id] = False
                    break

                if msg.reply_markup:
                    # Проверяем, какой экран перед нами
                    fp_buttons = [btn.text.lower() for row in msg.reply_markup.inline_keyboard for btn in row]
                    
                    # Шаг 1: Главное меню трейда
                    if any("добавить телефон" in b for b in fp_buttons):
                        await async_click(client, msg, "добавить телефон")
                        await asyncio.sleep(0.16)
                        
                    # Шаг 5: Выбор количества
                    elif any("добавить 1 шт." in b for b in fp_buttons):
                        if await async_click(client, msg, "добавить 1 шт."):
                            added_count[acc_id] = added_count.get(acc_id, 0) + 1
                        await asyncio.sleep(0.16)
                        
                    # Шаги 2, 3, 4: Промежуточные меню (качество, редкость, модель)
                    else:
                        await async_click_first(client, msg)
                        await asyncio.sleep(0.16)
        except Exception as e:
            await asyncio.sleep(0.1)
            
    # Финал сборки
    is_collecting[acc_id] = False
    print(f"⚖️ [Акк {acc_id}] Сборка завершена ({added_count.get(acc_id)}/10). Фиксирую...", flush=True)
    
    for _ in range(5):
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if await async_click(client, msg, "готов"):
                break
        await asyncio.sleep(0.25)
        
    await asyncio.sleep(0.8)
    
    for _ in range(5):
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if await async_click(client, msg, "подтвердить"):
                break
        await asyncio.sleep(0.25)

# --- ГЛАВНЫЙ ВХОДНОЙ ХЭНДЛЕР (ЛОВИТ ТОЛЬКО НОВЫЕ ТЕКСТОВЫЕ СООБЩЕНИЯ) ---
async def handle_incoming_bot_messages(client, message: Message):
    if not message.from_user or message.from_user.username != bot_chat:
        return
    if not message.text:
        return

    try: acc_id = clients.index(client) + 1
    except: return

    text = message.text.lower()

    # ТОЧНЫЙ ХИТ: Ловим предложение обмена
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return
            
        if is_collecting.get(acc_id, False): 
            return # Защита от повторного входа, если хэндлер вызван дважды

        print(f"🤝 [Акк {acc_id}] Обнаружен трейд! Начинаю фазу принятия...", flush=True)
        
        # Цикл долбёжки кнопки "Принять", пока бот её генерирует
        for _ in range(15):
            try:
                async for fresh_msg in client.get_chat_history(bot_chat, limit=1):
                    if fresh_msg.reply_markup and any("принять" in btn.text.lower() for row in fresh_msg.reply_markup.inline_keyboard for btn in row):
                        if await async_click(client, fresh_msg, "принять"):
                            print(f"✅ [Акк {acc_id}] Трейд успешно ПРИНЯТ!", flush=True)
                            is_collecting[acc_id] = True
                            # Передаем управление изолированному потоку сборки, освобождая хэндлер
                            asyncio.create_task(run_turbo_collection(client, acc_id))
                            return
            except:
                pass
            await asyncio.sleep(0.1)
        return

    # Подтверждение финала со стороны твинка
    if "подтвердите обмен" in text or "подтвердите" in text:
        await async_click(client, message, "подтвердить")
        return

# --- ХЭНДЛЕР ДЛЯ ОСНОВЫ (ЗАКРЫТИЕ СДЕЛКИ) ---
async def handle_sender_updates(client, message: Message):
    if not message.from_user or message.from_user.username != bot_chat:
        return
    if not message.text:
        return

    text = message.text.lower()
    if "готовность:" in text and text.count("✅") >= 1:
        if await async_click(client, message, "готов"):
            await asyncio.sleep(0.6)
            await async_click(client, message, "подтвердить")

# --- МАКРОСЫ .TRADE / .T ---
async def handle_my_messages(client, message):
    if not message.text: return
    my_id = getattr(client, "me_id", 0)
    if not message.from_user or message.from_user.id != my_id: return

    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    if cmd == ".ping":
        try: await message.edit("🚀 **Юзербот активен и исправен!**")
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
    print("🛠 Запуск исправленной архитектуры юзербота...", flush=True)

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
        c.add_handler(handlers.MessageHandler(handle_incoming_bot_messages, filters.incoming & filters.text))
        c.add_handler(handlers.MessageHandler(handle_sender_updates, filters.incoming & filters.text))
        
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
        except Exception as e:
            print(f"⚠️ Ошибка аккаунта {i+1}: {e}", flush=True)

    print("🚀 Стабильная скоростная ферма запущена. Делай тесты!", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
