# -*- coding: utf-8 -*-
import os
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask
from pyrogram import Client, handlers, filters
from pyrogram import raw

# --- СЕРВЕР ДЛЯ RENDER (KEEP-ALIVE) ---
app_flask = Flask(__name__)
@app_flask.route('/')
def health(): 
    return "Ready and Running", 200

threading.Thread(
    target=lambda: app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), 
    daemon=True
).start()

# --- CONFIG ФЕРМЫ ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

TRADE_BOT = "phonegetcardsbot"
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

# --- ЖЕЛЕЗОБЕТОННЫЙ КЛИКЕР С ПОВТОРАМИ ПРИ ЛАГАХ ---
async def persistent_click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                btn_text = btn.text.lower()
                btn_data = (btn.callback_data or "").lower()
                if keyword.lower() in btn_text or keyword.lower() in btn_data:
                    for attempt in range(3):
                        try:
                            await client.request_callback_answer(
                                chat_id=message.chat.id, 
                                message_id=message.id, 
                                callback_data=btn.callback_data,
                                timeout=4
                            )
                            return True
                        except Exception:
                            await asyncio.sleep(0.2)
                    return True
    except:
        pass
    return False

# --- ПОЗИЦИОННЫЙ ВЫБОР БЕЗ ПРИВЯЗКИ К ТЕКСТУ КНОПОК ---
async def click_first_valid_button(client, message) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
            
        # Жёсткий чёрный список для фильтрации навигационного мусора бота
        forbidden_text = [
            "назад", "back", "отмена", "cancel", "вернуться", "главное", "меню",
            "⬅️", "🔙", "❌", "✖️", "выход", "exit", "close", "return"
        ]
        
        forbidden_data = [
            "back", "return", "cancel", "close", "exit", "trade_refresh", "menu", "home"
        ]

        # Идём строго сверху вниз. Ищем ПЕРВУЮ кнопку, которая не в чёрном списке
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                text_lower = btn.text.lower().strip()
                data_lower = (btn.callback_data or "").lower().strip()
                
                if any(x in text_lower for x in forbidden_text):
                    continue
                if any(x in data_lower for x in forbidden_data):
                    continue
                
                # Кнопка чистая — кликаем по её callback_data
                for attempt in range(3):
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=4)
                        return True
                    except:
                        await asyncio.sleep(0.15)
                return True
    except:
        pass
    return False

# --- ПОШАГОВЫЙ ЛИНЕЙНЫЙ ДВИЖОК СБОРКИ ПРЕДМЕТОВ ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Трейд принят! Запуск позиционного кликера...", flush=True)
    is_collecting[acc_id] = True  
    added_count = 0  
    
    await asyncio.sleep(1.5) # Пауза на прогрузку стартового экрана
    
    for step in range(80):
        if added_count >= 10:
            break

        msg = None
        try:
            async for last_msg in client.get_chat_history(TRADE_BOT, limit=1):
                msg = last_msg
                break
        except:
            await asyncio.sleep(0.4)
            continue

        if not msg or not msg.reply_markup:
            await asyncio.sleep(0.4)
            continue

        text_lower = msg.text.lower() if msg.text else ""
        
        # Защита от переполнения
        if "10/10" in text_lower and "слот" in text_lower:
            print(f"📥 [Акк {acc_id}] Слот заполнен (10/10) по тексту бота.")
            break

        all_callbacks = []
        all_texts = []
        for row in msg.reply_markup.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())
                if btn.callback_data:
                    all_callbacks.append(btn.callback_data.lower())

        # ШАГ 1: Главный экран трейда. Ищем "Добавить телефон"
        if (any("trade_add_phone" in cb for cb in all_callbacks) or any("добавить телефон" in tx for tx in all_texts)) and not any("trade_refresh" in cb for cb in all_callbacks):
            print(f"📱 [Акк {acc_id}] Шаг 1: Нажимаю 'Добавить телефон'...", flush=True)
            if await persistent_click(client, msg, "trade_add_phone") or await persistent_click(client, msg, "добавить телефон"):
                await asyncio.sleep(1.0) 

        # ШАГ 2: Финальное подтверждение "Добавить 1 шт."
        elif any("trade_add_single" in cb for cb in all_callbacks) or any("добавить 1 шт." in tx for tx in all_texts):
            print(f"📦 [Acc {acc_id}] Шаг ФИНАЛ: Нажимаю 'Добавить 1 шт.'...", flush=True)
            if await persistent_click(client, msg, "trade_add_single") or await persistent_click(client, msg, "добавить 1 шт."):
                added_count += 1
                print(f"➕ [Акк {acc_id}] Телефон №{added_count} успешно добавлен!", flush=True)
                await asyncio.sleep(1.2) # Ощутимая пауза, чтобы бот вернулся на главный экран трейда

        # ШАГ 3: Промежуточные окна (Состояние [Рабочий/Сломанный] -> Редкость -> Модель)
        else:
            print(f"🎯 [Акк {acc_id}] Промежуточный шаг. Прожимаю первую рабочую опцию...", flush=True)
            if await click_first_valid_button(client, msg):
                # Держим стабильный темп в 1.0 секунду, чтобы Telegram успевал обновлять инлайн-состояния
                await asyncio.sleep(1.0)

    is_collecting[acc_id] = False
    print(f"⚖️ [Акк {acc_id}] Сборка окончена ({added_count}/10). Закрываю сделку...", flush=True)
    
    # Прожимаем кнопку "ГОТОВ"
    for _ in range(12):
        async for msg in client.get_chat_history(TRADE_BOT, limit=1):
            if await persistent_click(client, msg, "готов"): break
        await asyncio.sleep(0.5)

    await asyncio.sleep(1.2)

    # Прожимаем кнопку "ПОДТВЕРДИТЬ"
    for _ in range(12):
        async for msg in client.get_chat_history(TRADE_BOT, limit=1):
            if await persistent_click(client, msg, "подтвердить"): break
        await asyncio.sleep(0.5)


# --- ГЛАВНЫЙ ЦИКЛ НАБЛЮДЕНИЯ ЗА ЧАТОМ (ПУЛИНГ) ---
async def poll_bot_messages(client, acc_id):
    while True:
        try:
            async for msg in client.get_chat_history(TRADE_BOT, limit=1):
                if not msg or not msg.text:
                    continue

                text = msg.text.lower()

                if ("предложение обмена" in text or "пришло предложение" in text) and not is_collecting.get(acc_id, False):
                    if "ваше предложение обмена отправлено" not in text:
                        if msg.reply_markup and any("принять" in b.text.lower() for r in msg.reply_markup.inline_keyboard for b in r):
                            if await persistent_click(client, msg, "принять"):
                                is_collecting[acc_id] = True
                                asyncio.create_task(receiver_trade_logic(client, acc_id))

                if "подтвердите обмен" in text or "подтвердите" in text:
                    await persistent_click(client, msg, "подтвердить")
                
                if "готовность:" in text and text.count("✅") >= 1:
                    if current_bot_msg.get(acc_id) == "sender_waiting":
                        if await persistent_click(client, msg, "готов"):
                            current_bot_msg[acc_id] = "sender_confirmed"
                            await asyncio.sleep(0.8)
                            await persistent_click(client, msg, "подтвердить")
                break
        except:
            pass
        await asyncio.sleep(0.3)


# --- ОБРАБОТКА МАКРОСОВ В ЧАТЕ (.Т) ---
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
        try: await message.edit("🚀 **Ферма онлайн! Позиционный обход активен.**")
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
        await client.send_message(TRADE_BOT, bot_cmd)


# --- ТКАРТОЧКА: ЦИКЛ КАЖДЫЕ 2 ЧАСА ---
async def loop_cards_task(client, acc_id):
    try: await client.send_message(TRADE_BOT, "ткарточка")
    except: pass
    
    while True:
        await asyncio.sleep(121 * 60)
        try:
            await client.send_message(TRADE_BOT, "ткарточка")
            print(f"🃏 [Акк {acc_id}] Запрос 'ткарточка' отправлен по таймеру.", flush=True)
        except:
            pass


# --- ТМАЙНИНГ: СБОР ПРИБЫЛИ СТРОГО В 00:10 ПО МСК ---
async def bg_tasks(client, acc_id):
    tz_moscow = timezone(timedelta(hours=3))
    already_done_today = False

    while True:
        try:
            now_msk = datetime.now(tz_moscow)
            
            if now_msk.hour == 0 and now_msk.minute == 10:
                if not already_done_today:
                    print(f"💰 [Акк {acc_id}] Наступило 00:10 МСК. Забираю баланс фермы...", flush=True)
                    await client.send_message(TRADE_BOT, "тмайнинг")
                    await asyncio.sleep(2.5) 
                    
                    async for msg in client.get_chat_history(TRADE_BOT, limit=1):
                        if msg.reply_markup:
                            if await persistent_click(client, msg, "farm_claim"):
                                print(f"✅ [Акк {acc_id}] Деньги с майнинг-фермы успешно сняты!", flush=True)
                    
                    already_done_today = True 
            else:
                already_done_today = False
                
        except Exception as e:
            print(f"⚠️ Ошибка ночного сбора на акке {acc_id}: {e}", flush=True)
            
        await asyncio.sleep(30)


# --- ЗАПУСК ВСЕХ КЛИЕНТОВ ---
async def start_bot():
    global clients
    print("🛠 Запуск фермы в позиционном режиме без текстовых привязок...", flush=True)

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
            print(f"✅ Аккаунт {i+1} успешно запущен: @{me.username}", flush=True)
            
            is_collecting[i+1] = False
            asyncio.create_task(bg_tasks(c, i+1))
            asyncio.create_task(loop_cards_task(c, i+1))
            asyncio.create_task(poll_bot_messages(c, i+1))
        except Exception as e:
            print(f"⚠️ Ошибка инициализации аккаунта {i+1}: {e}", flush=True)

    print("🚀 Ферма запущена. Теперь скрипт идёт напролом по первому пункту меню.", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
