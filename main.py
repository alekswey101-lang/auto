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

# --- НАДЕЖНЫЙ КЛИКЕР С ОБРАБОТКОЙ АЛЕРТОВ ---
async def click(client, message, keyword: str, acc_id="Твинк") -> bool:
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
                            res = await client.request_callback_answer(
                                message.chat.id,
                                message.id,
                                btn.callback_data,
                                timeout=2
                            )
                            if res and hasattr(res, "message") and "нет доступных" in res.message.lower():
                                print(f"⚠️ [{acc_id}] Бот выдал алерт: '{res.message}'. Переключаюсь на сломанные!", flush=True)
                                if "рабоч" in t_low:
                                    client.working_phones_empty = True
                                    client.category_selected = False
                            return True
                        except Exception as e:
                            if "BUTTON_DATA_INVALID" in str(e):
                                return False
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

# --- ТЕХНИЧЕСКИЙ АВТОСБОР ТВИНКА ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Фоновый автосбор успешно запущен.", flush=True)
    last_clicked_callback = "" 
    
    client.working_phones_empty = False
    client.category_selected = False
    
    # Счетчик стагнации (увеличен запас по времени)
    stuck_counter = 0
    prev_trade_counter = 0

    for tick in range(150):
        try:
            if not hasattr(client, "trade_counter"):
                client.trade_counter = 0

            # Анти-зависание: сбрасываем флаг только если реально долго стоим на месте (3.5 секунды)
            if client.trade_counter == prev_trade_counter:
                stuck_counter += 1
                if stuck_counter > 15: 
                    print(f"🔄 [Твинк {acc_id}] Долгий простой в меню. Мягкий сброс флага категории.", flush=True)
                    client.category_selected = False
                    stuck_counter = 0
            else:
                stuck_counter = 0
                prev_trade_counter = client.trade_counter

            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.2)
                continue

            text = msg.text.lower() if msg.text else ""

            # СТРОГИЙ КОНТРОЛЬ ЛИМИТА: Твинк останавливается ТОЛЬКО если набрал 10 штук
            if client.trade_counter >= 10:
                back_button_found = False
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if any(x in btn.text.lower() for x in ["вернуться назад", "назад", "корень", "главное"]):
                            print(f"⚖️ [Твинк {acc_id}] Цель 10/10 достигнута! Выхожу в главное меню...", flush=True)
                            await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                            back_button_found = True
                            break
                    if back_button_found: break
                
                if back_button_found:
                    await asyncio.sleep(0.5)
                    continue

                if has_button(msg, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Финализирую трейд. Нажимаю кнопку 'Готов'!", flush=True)
                    await click(client, msg, "готов", acc_id)
                    return 
                
                continue

            # СБОР ПРЕДМЕТОВ И СОРТИРОВКА КНОПОК
            buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        buttons.append(btn)

            add_buttons = []       
            cond_buttons = []      
            single_buttons = []    
            item_buttons = []      

            for btn in buttons:
                c_data = btn.callback_data.lower()
                b_text = btn.text.lower()

                # Полностью игнорируем системную навигацию страниц
                if any(x in c_data or x in b_text for x in ["назад", "back", "cancel", "отмена", "главное", "меню", "⬅️", "🔙", "далее", "вперед", "➡️"]): 
                    continue
                if any(x in c_data for x in ["trade_confirm", "trade_ready", "trade_change", "trade_refresh"]): 
                    continue

                if "add_phone" in c_data or "добавить телефон" in b_text:
                    add_buttons.append(btn)
                elif "single" in c_data or "1 шт" in b_text or "add_single" in c_data:
                    single_buttons.append(btn)
                elif "cond" in c_data or "рабоч" in b_text or "сломан" in b_text:
                    cond_buttons.append(btn)
                else:
                    item_buttons.append(btn)

            # 1. Добавление количества (1 шт)
            if single_buttons:
                target = single_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    client.trade_counter += 1
                    client.category_selected = False  # Сброс для следующего телефона
                    print(f"📦 [Твинк {acc_id}] Нажал '1 шт'. В трейде уже предметов: {client.trade_counter}/10", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.4) 
                continue

            # 2. Главная кнопка "Добавить телефон" (Именно тут он застревал, теперь этот блок отработает на 100%)
            if add_buttons:
                target = add_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    client.category_selected = False
                    print(f"➕ [Твинк {acc_id}] Нажимаю главную кнопку 'Добавить телефон' в меню трейда.", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.3)
                continue

            # 3. Выбор Состояния (Рабочий/Сломанный)
            if cond_buttons and not client.category_selected:
                target = None
                if client.working_phones_empty:
                    for btn in cond_buttons:
                        if "сломан" in btn.text.lower(): target = btn; break
                else:
                    for btn in cond_buttons:
                        if "рабоч" in btn.text.lower(): target = btn; break
                    if not target:
                        for btn in cond_buttons:
                            if "сломан" in btn.text.lower(): target = btn; client.working_phones_empty = True; break

                if target:
                    last_clicked_callback = target.callback_data
                    client.category_selected = True
                    print(f"📂 [Твинк {acc_id}] Перехожу в подкатегорию: {target.text}", flush=True)
                    await click(client, msg, target.text, f"Твинк {acc_id}")
                    await asyncio.sleep(0.4)
                continue

            # 4. Выбор конкретной модели телефона из списка
            if item_buttons:
                target = item_buttons[0]
                for btn in item_buttons:
                    if any(x in btn.text.lower() for x in ["мистич", "редк", "эпич"]):
                        target = btn
                        break
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    print(f"📱 [Твинк {acc_id}] Выбираю доступную модель: {target.text}", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.4) 
                continue

        except Exception as e:
            print(f"⚠️ Ошибка автосбора твинка {acc_id}: {e}", flush=True)
        await asyncio.sleep(0.2) # Оптимальная задержка между шагами цикла

# --- ГИБРИДНЫЙ ТАЙМЕР ОЖИДАНИЯ ДЛЯ ОСНОВЫ ---
async def smart_basis_wait_loop(client):
    print("⏳ [ОСНОВА] Запущен гибридный чекер (макс. 25 секунд)...", flush=True)
    
    for second in range(25):
        await asyncio.sleep(1.0)
        try:
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break
            
            if not msg: continue
            text = msg.text.lower() if msg.text else ""

            # Основа прожимает готовность, только если видит, что твинк набил 10 слотов
            if "занято слотов: 10/10" in text or "10/10" in text:
                if has_button(msg, "готов"):
                    print(f"🎯 [ОСНОВА] Твинк забил 10/10 предметов. Нажимаю 'Готов'.", flush=True)
                    await click(client, msg, "готов", "Основа")
                    return

        except Exception as e:
            print(f"⚠️ Ошибка чекера основы: {e}", flush=True)

    try:
        async for m in client.get_chat_history(bot_chat, limit=1):
            if m and has_button(m, "готов"):
                print("⏰ [ОСНОВА] Время ожидания вышло. Силовой клик по кнопке 'Готов'.", flush=True)
                await click(client, m, "готов", "Основа")
    except: pass

# --- ГЛАВНЫЙ ОБРАБОТЧИК БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return
    if not message.text: return
    text = message.text.lower()

    if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
        print(f"🔗 [Аккаунт {acc_id}] Нажимаю 'Подтвердить обмен'!", flush=True)
        await click(client, message, "trade_confirm", acc_id)
        await click(client, message, "подтвердить", acc_id)
        return

    if "подтвердите обмен" in text or "подтвердите" in text:
        if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
            await click(client, message, "trade_confirm", acc_id)
            await click(client, message, "подтвердить", acc_id)
            return

    if acc_id != 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept", acc_id) or await click(client, message, "принять", acc_id):
                print(f"✅ [Твинк {acc_id}] Трейд принят. Начинаю непрерывное заполнение до 10 шт...", flush=True)
                client.trade_counter = 0
                asyncio.create_task(twink_collect_logic(client, acc_id))
            return

        if "10/10" in text and has_button(message, "готов"):
            await click(client, message, "готов", acc_id)
        return

    if acc_id == 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept", "Основа") or await click(client, message, "принять", "Основа"):
                print(f"✅ [ОСНОВА] Трейд принят. Запускаю таймер контроля...", flush=True)
                asyncio.create_task(smart_basis_wait_loop(client))
            return

# --- ХЕНДЛЕР ТЕКСТОВЫХ КОМАНД ---
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

# --- ФОН ЗАДАЧ И НЕЗАВИСИМЫЕ ТАЙМЕРЫ ---
async def bg_tasks(client, acc_id):
    await asyncio.sleep(5)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass

    if acc_id in [1, 2]:
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass

    claimed_today = False
    iris_timer = 0
    card_timer = 0  

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

            card_timer += 1
            if card_timer >= 121:
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
                card_timer = 0
        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Перезапуск. Ложные остановки твинка полностью заблокированы.", flush=True)

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
        clients.append(c)

    for i, c in enumerate(clients):
        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            me = await c.get_me()
            c.me_id = me.id
            
            acc_id = i + 1
            async for _ in c.get_dialogs(limit=5): pass

            if acc_id == 2:
                print(f"👑 ОСНОВА (Акк 2) в сети.", flush=True)
            else:
                print(f"✅ Твинк {acc_id} в сети.", flush=True)

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

    print("🚀 Всё готово! Ошибка 5-го телефона полностью устранена.", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
