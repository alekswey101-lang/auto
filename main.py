# -*- coding: utf-8 -*-
import os
import asyncio
import random
import datetime
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
    """Ищет кнопку в конкретном сообщении и нажимает её."""
    try:
        if not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                    print(f"[КЛИК] Нажимаю кнопку: '{btn.text}' | data: '{btn.callback_data}'", flush=True)
                    await client.request_callback_answer(message.chat.id, message.id, btn.callback_data)
                    return True
    except Exception as e:
        print(f"❌ Ошибка click(): {e}", flush=True)
    return False

# --- ОБНОВЛЕННЫЙ ПОШАГОВЫЙ ДВИЖОК КЛИКОВ ---
async def execute_menu_step(client, message_id, step_name, keywords, pick_first):
    print(f"🔍 [{step_name}] Ищу ключевые слова {keywords} в сообщении #{message_id}...", flush=True)
    
    for attempt in range(10):
        await asyncio.sleep(1.5)
        try:
            # Запрашиваем строго то самое сообщение, которое обрабатываем
            msg = await client.get_messages(bot_chat, message_id)
            if not msg or not msg.reply_markup:
                continue

            # Выводим в логи текущие кнопки на этом шаге для диагностики
            current_buttons = [btn.text for row in msg.reply_markup.inline_keyboard for btn in row]
            print(f"⏳ [{step_name}] Попытка {attempt+1}/10. Вижу кнопки: {current_buttons}", flush=True)

            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    text_lower = btn.text.lower().strip()
                    data_lower = (btn.callback_data or "").lower().strip()

                    # Режим 1: Клик по первой попавшейся кнопке (состояние, редкость, модель)
                    if pick_first:
                        if "назад" not in text_lower and "back" not in data_lower and "изменить" not in text_lower:
                            print(f"🎯 [{step_name}] Нажимаю авто-кнопку: [{btn.text}]", flush=True)
                            await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                            return True

                    # Режим 2: Поиск конкретной кнопки (Добавить телефон, Количество, Финал)
                    else:
                        for kw in keywords:
                            kw_l = kw.lower().strip()
                            if kw_l in text_lower or kw_l in data_lower:
                                print(f"🎯 [{step_name}] Найдено совпадение! Нажимаю: [{btn.text}]", flush=True)
                                await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data)
                                return True
        except Exception as e:
            print(f"❌ Ошибка выполнения шага {step_name}: {e}", flush=True)
            
    print(f"🛑 [{step_name}] Не удалось выполнить шаг за 10 попыток.", flush=True)
    return False

# --- ПОТОКОВАЯ ЛОГИКА СБОРЩИКА ДЛЯ ПОЛУЧАТЕЛЯ ---
async def receiver_trade_logic(client, message_id, acc_id):
    print(f"📦 [Акк {acc_id}] Начинаю автоматическую сборку предметов в трейд...", flush=True)

    # Шаг 1: Нажатие кнопки "Добавить телефон"
    if not await execute_menu_step(client, message_id, "Добавить телефон", ["добавить телефон", "trade_add_phone"], False): return

    # Шаг 2: Выбор состояния
    if not await execute_menu_step(client, message_id, "Выбор Состояния", [], True): return

    # Шаг 3: Выбор редкости
    if not await execute_menu_step(client, message_id, "Выбор Редкости", [], True): return

    # Шаг 4: Выбор модели
    if not await execute_menu_step(client, message_id, "Выбор Модели", [], True): return

    # Шаг 5: Выбор количества (1 шт)
    if not await execute_menu_step(client, message_id, "Количество 1шт", ["добавить 1 шт.", "trade_add_single"], False): return

    # Шаг 6: Подтверждение получателя
    if await execute_menu_step(client, message_id, "Финал Получателя", ["подтвердить", "trade_confirm"], False):
        print(f"🎉 [Акк {acc_id}] Трейд успешно собран и подтвержден твинком!", flush=True)

# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ БОТА ---
async def handle_bot_messages(client, message):
    try:
        acc_id = clients.index(client) + 1
    except:
        acc_id = "X"

    if not message.text:
        return

    text = message.text.lower()
    
    # ТРИГГЕР ДЕБАГА: Выводим вообще любое изменение/сообщение от бота в консоль
    print(f"📡 [ИНФО - Акк {acc_id}] Получено/изменено сообщение #{message.id}: '{text[:90]}...'", flush=True)

    # 1. ОБРАБОТКА ВХОДЯЩЕГО ТРЕЙДА
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return

        print(f"🤝 [Акк {acc_id}] Вижу предложение обмена! Пробую принять...", flush=True)
        await delay(0.5, 1.5)
        
        if await click(client, message, "принять"):
            print(f"✅ [Акк {acc_id}] Кнопка 'Принять' нажата. Передаю message_id {message.id} в логику сборщика...", flush=True)
            # Передаем ID сообщения, чтобы скрипт мучил именно его
            asyncio.create_task(receiver_trade_logic(client, message.id, acc_id))
        else:
            print(f"⚠️ [Акк {acc_id}] Не нашел кнопку 'Принять' в сообщении.", flush=True)
        return

    # 2. АВТОГОТОВНОСТЬ СЛОТОВ
    if ("готовность:" in text and "❌" in text and "✅" in text) or "занято слотов: 10/10" in text:
        await delay(1.0, 2.0)
        await click(client, message, "готов")
        return

    # 3. АВТОПОДТВЕРЖДЕНИЕ СДЕЛКИ
    if "подтвердите обмен" in text or "подтвердите" in text:
        await delay(0.5, 1.5)
        await click(client, message, "подтвердить")
        return

# --- ОТПРАВИТЕЛЬ: ОЖИДАНИЕ И ФИНАЛЬНЫЙ КЛИК ---
async def sender_confirm_logic(client, acc_id):
    print(f"⏳ [Акк {acc_id} - Отправитель] Жду 30 секунд, пока твинк собирает телефон...", flush=True)
    await asyncio.sleep(30)
    print(f"✍️ [Акк {acc_id} - Отправитель] Время вышло. Подтверждаю трейд со своей стороны...", flush=True)
    try:
        async for msg in client.get_chat_history(bot_chat, limit=1):
            await click(client, msg, "подтвердить")
    except Exception as e:
        print(f"❌ Ошибка отправителя: {e}", flush=True)

# --- АДМИН-КОМАНДЫ ЮЗЕРБОТА (.t, .farmn, .ping) ---
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
        try: await message.edit("🚀 **Юзербот онлайн и слушает чаты!**")
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

        print(f"📣 [Акк {acc_id}] Запускаю трейд на аккаунт: {target}...", flush=True)
        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        await client.send_message(bot_chat, bot_cmd)
        asyncio.create_task(sender_confirm_logic(client, acc_id))

# --- ТАЙМЕРЫ (КАРТОЧКА РАЗ В 2 ЧАСА) ---
async def bg_tasks(client, acc_id):
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    while True:
        await asyncio.sleep(121 * 60)
        try:
            print(f"🃏 [Акк {acc_id}] Авто-отправка: ткарточка", flush=True)
            await client.send_message(bot_chat, "ткарточка")
        except: pass

# --- ЗАПУСК КЛИЕНТОВ ---
async def start_bot():
    global clients
    print("🛠 Запуск Pyrofork клиентов...", flush=True)
    
    bot_filter = filters.chat(bot_chat)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue
            
        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )
        
        # 1. Хэндлер на твои личные текстовые команды
        c.add_handler(handlers.MessageHandler(handle_my_messages))
        
        # 2. Хэндлеры НА СООБЩЕНИЯ БОТА (Ловят и новые сообщения, и ИЗМЕНЕНИЯ старых кнопок)
        c.add_handler(handlers.MessageHandler(handle_bot_messages, bot_filter))
        c.add_handler(handlers.EditedMessageHandler(handle_bot_messages, bot_filter))
        
        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            
            # Прогружаем диалоги, чтобы чат с ботом гарантированно всплыл в памяти сессии
            async for _ in c.get_dialogs(limit=10): pass
            
            print(f"✅ Аккаунт {i+1} успешно запущен как: @{me.username}", flush=True)
            asyncio.create_task(bg_tasks(c, i+1))
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"⚠️ Ошибка старта аккаунта {i+1}: {e}", flush=True)

    print("💎 Все доступные аккаунты запущены. Ожидаю команд...", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
