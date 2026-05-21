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

# --- ТЕХНИЧЕСКИЙ АВТОСБОР ТВИНКА ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Фоновый автосбор успешно запущен.", flush=True)
    last_clicked_callback = "" 
    
    client.working_phones_empty = False
    client.failed_working_clicks = 0

    for tick in range(150):
        try:
            if not hasattr(client, "trade_counter"):
                client.trade_counter = 0

            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.2)
                continue

            text = msg.text.lower() if msg.text else ""

            # ЕСЛИ ЛИМИТ ДОСТИГНУТ (10/10)
            if client.trade_counter >= 10 or "занято слотов: 10/10" in text:
                back_button_found = False
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "вернуться назад" in btn.text.lower() or "назад" in btn.text.lower():
                            print(f"⚖️ [Твинк {acc_id}] Лимит 10/10! Жму 'Вернуться назад' для выхода в меню...", flush=True)
                            await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                            back_button_found = True
                            break
                    if back_button_found: break
                
                if back_button_found:
                    await asyncio.sleep(0.5)
                    continue

                if has_button(msg, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Вышли в меню. Нажимаю 'Готов'!", flush=True)
                    await click(client, msg, "готов")
                    client.collecting = False  
                    return 

                if "готовность: ✅" in text or "✅" in text:
                    print(f"✨ [Твинк {acc_id}] Готовность подтверждена ботом. Выхожу из цикла сбора.", flush=True)
                    client.collecting = False  
                    return
                
                continue

            # СБОР ПРЕДМЕТОВ
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

                if any(x in c_data or x in b_text for x in ["назад", "back", "cancel", "отмена", "главное", "меню", "⬅️", "🔙"]): 
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

            if item_buttons or single_buttons:
                client.failed_working_clicks = 0

            # 1. Шаг добавления количества (1 шт)
            if single_buttons:
                target = single_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    client.trade_counter += 1
                    print(f"📦 [Твинк {acc_id}] Клик: 'Добавить 1 шт.' (Загружено: {client.trade_counter}/10)", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.5) 
                continue

            # 2. Шаг открытия меню добавления телефона
            if add_buttons:
                target = add_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    print(f"➕ [Твинк {acc_id}] Клик: 'Добавить телефон'", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.3)
                continue

            # 3. НАДЕЖНЫЙ ВЫБОР СОСТОЯНИЯ
            if cond_buttons:
                target = None
                
                if client.working_phones_empty:
                    for btn in cond_buttons:
                        if "сломан" in btn.text.lower():
                            target = btn
                            break
                else:
                    for btn in cond_buttons:
                        if "рабоч" in btn.text.lower():
                            target = btn
                            break
                    if not target:
                        for btn in cond_buttons:
                            if "сломан" in btn.text.lower():
                                target = btn
                                client.working_phones_empty = True
                                break

                if target:
                    if "рабоч" in target.text.lower():
                        client.failed_working_clicks += 1
                        if client.failed_working_clicks >= 3:
                            print(f"🪛 [Твинк {acc_id}] Рабочие пустые. Переключаюсь на СЛОМАННЫЕ!", flush=True)
                            client.working_phones_empty = True
                            for btn in cond_buttons:
                                if "сломан" in btn.text.lower():
                                    target = btn
                                    break

                    last_clicked_callback = target.callback_data
                    print(f"📱 [Твинк {acc_id}] Клик состояние: [{target.text}]", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.5)
                continue

            # 4. Шаг выбора модели телефона
            if item_buttons:
                target = item_buttons[0]
                for btn in item_buttons:
                    if "мистич" in btn.text.lower() or "редк" in btn.text.lower():
                        target = btn
                        break
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    print(f"💎 [Твинк {acc_id}] Клик: Выбор модели [{target.text}]", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.4) 
                continue

        except Exception as e:
            print(f"⚠️ Ошибка в цикле автосбора твинка {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(0.2)
    
    client.collecting = False

# --- АКТИВНЫЙ ПОТОК ЖЕЛАНИЯ ГОТОВНОСТИ ДЛЯ ОСНОВЫ ---
async def main_account_wait_loop(client):
    global clients
    print("⏳ [ОСНОВА] Запущен активный цикл ожидания завершения сбора твинков...", flush=True)
    
    for _ in range(100): # Максимум 100 секунд ждем
        await asyncio.sleep(1.0)
        
        # Проверяем, занят ли кто-то из твинков сбором прямо сейчас
        any_twink_collecting = False
        for c in clients:
            if hasattr(c, "me_id") and c.me_id != client.me_id:
                if getattr(c, "collecting", False):
                    any_twink_collecting = True
                    break
        
        # Если все твинки закончили сбор (collecting == False)
        if not any_twink_collecting:
            # Берем актуальное сообщение из чата основы
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break
            
            if msg and has_button(msg, "готов"):
                print("⚡ [ОСНОВА] Активный чекер подтвердил: Твинки свободны! Нажимаю 'Готов'.", flush=True)
                await click(client, msg, "готов")
                break


# --- ГЛАВНЫЙ ОБРАБОТЧИК БОТА ---
async def process_bot_logic(client, message, acc_id):
    global clients
    if not message: return

    if not hasattr(client, "collecting"): client.collecting = False
    if not hasattr(client, "trade_counter"): client.trade_counter = 0

    # Автосбор прибыли с ТМайнинга
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

    # --- ОБЩАЯ ДЛЯ ВСЕХ КНОПКА ПОДТВЕРДИТЬ ---
    if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
        print(f"🔗 [Аккаунт {acc_id}] Нажимаю 'Подтвердить обмен'!", flush=True)
        await click(client, message, "trade_confirm")
        await click(client, message, "подтвердить")
        return

    if "подтвердите обмен" in text or "подтвердите" in text:
        if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
            await click(client, message, "trade_confirm")
            await click(client, message, "подтвердить")
            return

    # --- ЛОГИКА ДЛЯ ТВИНКОВ (АКК 1, 3, 4, 5) ---
    if acc_id != 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                if client.collecting:
                    return
                print(f"✅ [Твинк {acc_id}] Трейд принят. Запуск сборщика...", flush=True)
                client.trade_counter = 0
                client.working_phones_empty = False 
                client.failed_working_clicks = 0
                client.collecting = True  
                asyncio.create_task(twink_collect_logic(client, acc_id))
            return

        if "10/10" in text and has_button(message, "готов"):
            print(f"⚡ [Твинк {acc_id}] Страховка: Нажимаю 'Готов' в главном меню.", flush=True)
            await click(client, message, "готов")
            client.collecting = False
        return

    # --- БЕЗУПРЕЧНАЯ ЛОГИКА ДЛЯ ОСНОВЫ (АКК №2) ---
    if acc_id == 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                print(f"✅ [ОСНОВА] Приняла трейд. Запускаю фоновый чекер готовности твинков...", flush=True)
                # Запускаем ежесекундный мониторинг, чтобы основа не проспала завершение сбора твинка
                asyncio.create_task(main_account_wait_loop(client))
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
                try: 
                    await client.send_message(bot_chat, "ткарточка")
                    print(f"🃏 [Акк {acc_id}] Прошла 121 минута. Отправил 'ткарточка'.", flush=True)
                except: pass
                card_timer = 0

        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Запуск фермы. Интегрирован активный фоновый чекер для Основы.", flush=True)

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

    print("🚀 Скрипт запущен! Теперь основа проверяет готовность твинков каждую секунду.", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
