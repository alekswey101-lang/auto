# -*- coding: utf-8 -*-
import os
import asyncio
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
    target=lambda: app.run(
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 10000))
    ),
    daemon=True
).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

bot_chat = "phonegetcardsbot"
iris_bot_chat = "iris_moon_bot"

clients = []

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "ivannomor"
}

# --- НАДЕЖНЫЙ КЛИКЕР ---
async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False

        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                t_low = btn.text.lower()
                d_low = (btn.callback_data or "").lower()
                if keyword.lower() in t_low or keyword.lower() in d_low:
                    if btn.callback_data:
                        try:
                            await client.request_callback_answer(
                                message.chat.id,
                                message.id,
                                btn.callback_data,
                                timeout=1
                            )
                            return True
                        except:
                            return True
    except:
        pass
    return False

def has_button(message, keyword: str) -> bool:
    if not message or not message.reply_markup:
        return False
    for row in message.reply_markup.inline_keyboard:
        for btn in row:
            t_low = btn.text.lower()
            d_low = (btn.callback_data or "").lower()
            if keyword.lower() in t_low or keyword.lower() in d_low:
                return True
    return False

# --- ИДЕАЛЬНЫЙ АВТОСБОР ПО ИНТЕРФЕЙСУ БОТА ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Запуск точного автосбора предметов...", flush=True)
    
    last_clicked_callback = ""

    for tick in range(150):
        try:
            # Запрашиваем актуальное состояние чата
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.2)
                continue

            text = msg.text.lower() if msg.text else ""

            # ЕСЛИ НАБРАЛИ 10/10 — Срочно выходим в главное меню трейда к кнопке "Готов"
            if "10/10" in text or ("слот" in text and "0/" not in text and "1/" not in text and "2/" not in text and "3/" not in text):
                if has_button(msg, "вернуться назад"):
                    print(f"⚖️ [Твинк {acc_id}] Слоты забиты (10/10)! Выхожу в меню...", flush=True)
                    await click(client, msg, "вернуться назад")
                    await asyncio.sleep(0.5)
                elif has_button(msg, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Вижу главное меню. Нажимаю 'Готов'!", flush=True)
                    await click(client, msg, "готов")
                    break
                continue

            # Разбираем доступные кнопки на экране
            buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        buttons.append(btn)

            # Распределяем строго по их текстовому назначению на скриншотах
            add_buttons = [b for b in buttons if "добавить телефон" in b.text.lower()]
            cond_buttons = [b for b in buttons if "рабочий телефон" in b.text.lower()]
            single_buttons = [b for b in buttons if "1 шт" in b.text.lower() or "add_single" in b.callback_data.lower()]
            
            # Предметы (модели или редкости) — это кнопки, которые не являются системными (назад, обновить, отмена, готов)
            item_buttons = []
            for b in buttons:
                t_b = b.text.lower()
                if any(x in t_b for x in ["добавить телефон", "добавить предмет", "рабочий телефон", "сломанный телефон", "вернуться назад", "обновить", "отменить трейд", "готов", "убрать предмет"]): 
                    continue
                item_buttons.append(b)

            # --- ВЫПОЛНЕНИЕ СТРОГИХ ШАГОВ КЛИКА ---

            # Шаг 1: Финальное подтверждение количества (1 шт)
            if single_buttons:
                target = single_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    print(f"📦 [Твинк {acc_id}] Нажимаю 'Добавить 1 шт.'", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.5)
                continue

            # Шаг 2: Главное меню обмена — нажимаем «Добавить телефон»
            if add_buttons:
                target = add_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    print(f"➕ [Твинк {acc_id}] Нажимаю 'Добавить телефон'", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.4)
                continue

            # Шаг 3: Меню категории — выбираем строго «Рабочий телефон»
            if cond_buttons:
                target = cond_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    print(f"📱 [Твинк {acc_id}] Выбираю 'Рабочий телефон'", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.4)
                continue

            # Шаг 4: Выбор редкости или конкретной модели
            if item_buttons:
                target = item_buttons[0]
                # Умный приоритет для редких/мистических категорий
                for b in item_buttons:
                    if "мистич" in b.text.lower() or "редк" in b.text.lower():
                        target = b
                        break
                
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    print(f"💎 [Твинк {acc_id}] Выбираю элемент: {target.text}", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.4)
                continue

        except Exception as e:
            print(f"⚠️ Ошибка автосбора твинка {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(0.2)

    print(f"⚖️ [Твинк {acc_id}] Сбор успешно завершен.", flush=True)

# --- ГЛАВНЫЙ ОБРАБОТЧИК БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return

    # Автосбор прибыли с ТМайнинга для всей фермы
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                if "собрать деньги" in btn.text.lower() or "farm_claim" in btn.callback_data.lower():
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        print(f"💰 [Акк {acc_id}] Собрал прибыль с майнинга.", flush=True)
                        return
                    except: pass

    if not message.text: return
    text = message.text.lower()

    # --- ЛОГИКА ДЛЯ ТВИНКОВ (АКК 1, 3, 4, 5) ---
    if acc_id != 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                print(f"✅ [Твинк {acc_id}] Трейд принят. Запускаю точный сборщик...", flush=True)
                asyncio.create_task(twink_collect_logic(client, acc_id))
            return

        # Страховочный чек на случай, если твинк вышел в меню, но цикл прервался
        if "10/10" in text and has_button(message, "готов"):
            print(f"⚡ [Твинк {acc_id}] Страховка: Нажимаю 'Готов' в меню.", flush=True)
            await click(client, message, "готов")
        return

    # --- ЛОГИКА ДЛЯ ОСНОВЫ (АКК №2 STRICT) ---
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text: return
        if await click(client, message, "trade_accept") or await click(client, message, "принять"):
            print(f"✅ [ОСНОВА - Акк 2] Приняла трейд. Ожидаю готовности твинка...", flush=True)
        return

    if "❌" in text or "✅" in text:
        # Если твинк нажал готов (появилась галочка ✅), а у Основы доступна кнопка
        if "✅" in text and has_button(message, "готов"):
            print(f"⚡ [ОСНОВА - Акк 2] Твинк готов! Нажимаю 'Готов' на основе...", flush=True)
            await click(client, message, "готов")
            return

        # Финальное подтверждение сделки
        if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
            print(f"🔗 [ОСНОВА - Акк 2] Нажимаю финальное 'Подтвердить'!", flush=True)
            await click(client, message, "trade_confirm")
            await click(client, message, "подтвердить")
            return

    if "подтвердите обмен" in text or "подтвердите" in text:
        if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
            await click(client, message, "trade_confirm")
            await click(client, message, "подтвердить")

# --- ХЕНДЛЕР ТЕКСТОВЫХ КОМАНД (.t и .ping) ---
async def handle_my_messages(client, message):
    if not message.text: return
    
    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    if cmd == ".ping":
        try: await message.edit("🚀 Юзербот активен!")
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

# --- ФОН ЗАДАЧИ ---
async def bg_tasks(client, acc_id):
    await asyncio.sleep(5)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass

    if acc_id in [1, 2]:
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass

    claimed_today = False
    iris_timer = 0

    while True:
        try:
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)

            if msk_now.hour == 0 and msk_now.minute == 10:
                if not claimed_today:
                    await client.send_message(bot_chat, "тмайнинг")
                    claimed_today = True
            else:
                if msk_now.hour == 0 and msk_now.minute == 11: claimed_today = False

            if acc_id in [1, 2]:
                iris_timer += 1
                if iris_timer >= 240:
                    try: await client.send_message(iris_bot_chat, "фарма")
                    except: pass
                    iris_timer = 0

            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                await client.send_message(bot_chat, "ткарточка")
        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Запуск полностью синхронизированной фермы. Аккаунт 2 — ОСНОВА.", flush=True)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue
        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )

        c.add_handler(handlers.MessageHandler(handle_my_messages, filters.me))

        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id

            async for _ in c.get_dialogs(limit=5): pass
            
            acc_id = i + 1
            if acc_id == 2:
                print(f"👑 ГЛАВНАЯ ОСНОВА (Аккаунт 2) запущена: @{me.username}", flush=True)
            else:
                print(f"✅ Твинк-аккаунт {acc_id} запущен: @{me.username}", flush=True)

            c.add_handler(handlers.MessageHandler(
                lambda client, message, a_id=acc_id: process_bot_logic(client, message, a_id),
                filters.chat(bot_chat)
            ), group=0)

            c.add_handler(handlers.EditedMessageHandler(
                lambda client, message, a_id=acc_id: process_bot_logic(client, message, a_id),
                filters.chat(bot_chat)
            ), group=0)
            
            asyncio.create_task(bg_tasks(c, acc_id))
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {i+1}: {e}", flush=True)

    print("🚀 Скрипт запущен! Логика полностью синхронизирована с кнопками на скриншотах.", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
