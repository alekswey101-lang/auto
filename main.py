# -*- coding: utf-8 -*-
import os
import asyncio
import threading
from datetime import datetime, timedelta, timezone
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

# --- СТАБИЛЬНЫЙ КЛИКЕР ---
async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                btn_text = btn.text.lower()
                btn_data = (btn.callback_data or "").lower()
                if keyword.lower() in btn_text or keyword.lower() in btn_data:
                    await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                    return True
    except:
        pass
    return False

# --- АВТО-ВЫБОР ХАРАКТЕРИСТИК ---
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

# --- ДВИЖОК СБОРКИ ПРЕДМЕТОВ В ТРЕЙДЕ ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Начался пошаговый сбор инвентаря...", flush=True)
    is_collecting[acc_id] = True  
    added_count = 0  
    last_fp = ""
    
    await asyncio.sleep(0.5)
    
    for step in range(60):
        if added_count >= 10:
            break

        msg = None
        try:
            async for last_msg in client.get_chat_history(bot_chat, limit=1):
                msg = last_msg
                break
        except:
            await asyncio.sleep(0.2)
            continue

        if not msg or not msg.reply_markup:
            await asyncio.sleep(0.2)
            continue

        text_lower = msg.text.lower() if msg.text else ""
        if "10/10" in text_lower and "слот" in text_lower:
            print(f"📥 [Акк {acc_id}] Достигнут лимит 10/10 в меню бота.")
            break

        all_callbacks = []
        all_texts = []
        for row in msg.reply_markup.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())
                if btn.callback_data:
                    all_callbacks.append(btn.callback_data.lower())

        current_fp = "|".join(all_texts)

        # 1. ПРОВЕРКА: Главный экран трейда
        if any("trade_add_phone" in cb for cb in all_callbacks) or any("добавить телефон" in tx for tx in all_texts):
            if await click(client, msg, "trade_add_phone") or await click(client, msg, "добавить телефон"):
                await asyncio.sleep(0.25 if current_fp == last_fp else 0.18)
            last_fp = current_fp

        # 2. ПРОВЕРКА: Экран выбора количества 1 шт
        elif any("trade_add_single" in cb for cb in all_callbacks) or any("добавить 1 шт." in tx for tx in all_texts):
            if await click(client, msg, "trade_add_single") or await click(client, msg, "добавить 1 шт."):
                added_count += 1
                print(f"➕ [Акк {acc_id}] Добавлен телефон №{added_count}", flush=True)
                await asyncio.sleep(0.25 if current_fp == last_fp else 0.18)
            last_fp = current_fp

        # 3. ПРОВЕРКА: Выбор характеристик
        else:
            if await click_first(client, msg):
                await asyncio.sleep(0.22 if current_fp == last_fp else 0.15)
            last_fp = current_fp

    is_collecting[acc_id] = False
    print(f"⚖️ [Акк {acc_id}] Сборка завершена ({added_count}/10). Закрываю сделку...", flush=True)
    
    for _ in range(10):
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if await click(client, msg, "готов"): break
        await asyncio.sleep(0.3)

    await asyncio.sleep(0.8)

    for _ in range(10):
        async for msg in client.get_chat_history(bot_chat, limit=1):
            if await click(client, msg, "подтвердить"): break
        await asyncio.sleep(0.3)


# --- ГЛАВНЫЙ ЦИКЛ НАБЛЮДЕНИЯ (ПРИЕМ ТРЕЙДОВ) ---
async def poll_bot_messages(client, acc_id):
    while True:
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if not msg or not msg.text:
                    continue

                text = msg.text.lower()

                if ("предложение обмена" in text or "пришло предложение" in text) and not is_collecting.get(acc_id, False):
                    if "ваше предложение обмена отправлено" not in text:
                        if msg.reply_markup and any("принять" in b.text.lower() for r in msg.reply_markup.inline_keyboard for b in r):
                            if await click(client, msg, "принять"):
                                is_collecting[acc_id] = True
                                asyncio.create_task(receiver_trade_logic(client, acc_id))

                if "подтвердите обмен" in text or "подтвердите" in text:
                    await click(client, msg, "подтвердить")
                
                if "готовность:" in text and text.count("✅") >= 1:
                    if current_bot_msg.get(acc_id) == "sender_waiting":
                        if await click(client, msg, "готов"):
                            current_bot_msg[acc_id] = "sender_confirmed"
                            await asyncio.sleep(0.8)
                            await click(client, msg, "подтвердить")
                break
        except:
            pass
        await asyncio.sleep(0.3)


# --- ОБРАБОТКА КОМАНДЫ ЮЗЕРБОТА (.Т) ---
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
        try: await message.edit("🚀 **Юзербот активен и готов к обменам!**")
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
        current_bot_msg[acc_id] = "sender_waiting" 
        await client.send_message(bot_chat, bot_cmd)


# --- ДОПОЛНИТЕЛЬНЫЙ ЦИКЛ: КАРТОЧКА КАЖДЫЕ 2 ЧАСА ---
async def loop_cards_task(client, acc_id):
    # Отправляем один раз при запуске скрипта
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    
    while True:
        await asyncio.sleep(121 * 60) # Ровно 2 часа и 1 минута
        try:
            await client.send_message(bot_chat, "ткарточка")
            print(f"🃏 [Акк {acc_id}] Авто-запрос 'ткарточка' отправлен.", flush=True)
        except:
            pass


# --- ФОНОВЫЕ ЗАДАЧИ: СБОР МАЙНИНГА СТРОГО В 00:10 ПО МСК ---
async def bg_tasks(client, acc_id):
    print(f"⏰ [Акк {acc_id}] Таймер сбора майнинга запущен. Ожидание 00:10 по МСК...", flush=True)
    
    tz_moscow = timezone(timedelta(hours=3))
    already_done_today = False

    while True:
        try:
            now_msk = datetime.now(tz_moscow)
            
            if now_msk.hour == 0 and now_msk.minute == 10:
                if not already_done_today:
                    print(f"💰 [Акк {acc_id}] Время 00:10 МСК! Отправляю тмайнинг...", flush=True)
                    
                    await client.send_message(bot_chat, "тмайнинг")
                    await asyncio.sleep(2.5) 
                    
                    async for msg in client.get_chat_history(bot_chat, limit=1):
                        if msg.reply_markup:
                            if await click(client, msg, "farm_claim"):
                                print(f"✅ [Акк {acc_id}] Деньги с фермы успешно сняты!", flush=True)
                    
                    already_done_today = True 
            else:
                already_done_today = False
                
        except Exception as e:
            print(f"⚠️ Ошибка выполнения ночного сбора на акке {acc_id}: {e}", flush=True)
            
        await asyncio.sleep(30)


async def start_bot():
    global clients
    print("🛠 Запуск полностью исправленной версии...", flush=True)

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
            asyncio.create_task(loop_cards_task(c, i+1)) # Запускаем параллельный цикл для карточек
            asyncio.create_task(poll_bot_messages(c, i+1))
        except Exception as e:
            print(f"⚠️ Ошибка аккаунта {i+1}: {e}", flush=True)

    print("🚀 Ферма готова. Тмайнинг: 00:10 МСК. Ткарточка: каждые 2 часа.", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
