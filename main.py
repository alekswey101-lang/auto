# -*- coding: utf-8 -*-
import os
import re
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

twink_finished_event = asyncio.Event()

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
    working_phones_depleted = False 
    stuck_counter = 0  # Счетчик зависания на одном месте

    if not hasattr(client, "dynamic_limit"):
        client.dynamic_limit = 10 

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

            # Проверка на жесткое зависание в меню выбора
            if "выберите категорию телефона" in text:
                stuck_counter += 1
                if stuck_counter > 4:
                    print(f"🔄 [Твинк {acc_id}] Похоже, меню выбора категорий зависло. Сбрасываю триггеры.", flush=True)
                    last_clicked_callback = ""
                    stuck_counter = 0
            else:
                stuck_counter = 0

            if client.trade_counter >= client.dynamic_limit or f"занято слотов: {client.dynamic_limit}/{client.dynamic_limit}" in text or "занято слотов: 10/10" in text:
                back_button_found = False
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "вернуться назад" in btn.text.lower() or "назад" in btn.text.lower():
                            print(f"⚖️ [Твинк {acc_id}] Лимит {client.dynamic_limit} достигнут! Выхожу в меню...", flush=True)
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
                    twink_finished_event.set()
                    client.collecting = False 
                    return 

                if "готовность: ✅" in text or "✅" in text:
                    print(f"✨ [Твинк {acc_id}] Готовность подтверждена. Выхожу.", flush=True)
                    twink_finished_event.set()
                    client.collecting = False
                    return
                
                continue

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
                elif "рабоч" in b_text or "сломан" in b_text or "phone_cond" in c_data:
                    cond_buttons.append(btn)
                else:
                    item_buttons.append(btn)

            if single_buttons:
                target = single_buttons[0]
                if target.callback_data != last_clicked_callback:
                    last_clicked_callback = target.callback_data
                    client.trade_counter += 1
                    print(f"📦 [Твинк {acc_id}] Клик: 'Добавить 1 шт.' (Загружено: {client.trade_counter}/{client.dynamic_limit})", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    await asyncio.sleep(0.5) 
                continue

            if add_buttons:
                target = add_buttons[0]
                last_clicked_callback = "" 
                print(f"➕ [Твинк {acc_id}] Клик: 'Добавить телефон'", flush=True)
                await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                await asyncio.sleep(0.4)
                continue

            if cond_buttons:
                work_btn = None
                broken_btn = None
                
                for btn in cond_buttons:
                    if "рабоч" in btn.text.lower():
                        work_btn = btn
                    if "сломан" in btn.text.lower():
                        broken_btn = btn

                if working_phones_depleted or (last_clicked_callback == "work_triggered" and not broken_btn):
                    target = broken_btn if broken_btn else cond_buttons[0]
                elif work_btn:
                    target = work_btn
                else:
                    target = broken_btn if broken_btn else cond_buttons[0]

                if target == work_btn:
                    client.dynamic_limit = 10
                    last_clicked_callback = "work_triggered"
                    print(f"📱 [Твинк {acc_id}] Пробую категорию РАБОЧИЕ (Лимит 10)...", flush=True)
                    
                    try:
                        res = await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=2)
                        if res and hasattr(res, 'message') and ("нет" in res.message.lower() or "доступных" in res.message.lower()):
                            print(f"⚠️ [Твинк {acc_id}] Бот вернул alert: '{res.message}'. Переключаюсь на СЛОМАННЫЕ!", flush=True)
                            working_phones_depleted = True
                            last_clicked_callback = ""
                            continue
                    except:
                        print(f"⚠️ [Твинк {acc_id}] Ошибка клика рабочих. Переключаюсь на СЛОМАННЫЕ.", flush=True)
                        working_phones_depleted = True
                        last_clicked_callback = ""
                        continue
                else:
                    client.dynamic_limit = 5
                    last_clicked_callback = target.callback_data
                    print(f"🛠 [Твинк {acc_id}] Выбрана категория СЛОМАННЫЕ. Целевой лимит: 5 штук.", flush=True)
                    try:
                        await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                    except:
                        pass
                
                await asyncio.sleep(0.5) 
                continue

            if item_buttons:
                target = item_buttons[0]
                
                if "редкость" in text:
                    if target.callback_data != last_clicked_callback:
                        last_clicked_callback = target.callback_data
                        print(f"🔮 [Твинк {acc_id}] Клик по редкости: [{target.text}]", flush=True)
                        await client.request_callback_answer(msg.chat.id, msg.id, target.callback_data, timeout=1)
                        await asyncio.sleep(0.5)
                    continue
                
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

# --- ФОНОВАЯ ЗАДАЧА СИНХРОНИЗАЦИИ ДЛЯ ОСНОВЫ ---
async def basis_sync_loop(basis_client):
    while True:
        await twink_finished_event.wait()
        print("🔗 [СИНХРОНИЗАЦИЯ] Получен прямой сигнал от твинка! Основа начинает клик...", flush=True)
        
        for _ in range(5):
            try:
                msg = None
                async for m in basis_client.get_chat_history(bot_chat, limit=1):
                    msg = m
                    break
                
                if msg:
                    if has_button(msg, "готов"):
                        print("👑 [ОСНОВА] Кнопка 'Готов' найдена. Прожимаю!", flush=True)
                        await click(basis_client, msg, "готов")
                        break
                    else:
                        for row in msg.reply_markup.inline_keyboard if msg.reply_markup else []:
                            for btn in row:
                                if "вернуться назад" in btn.text.lower() or "назад" in btn.text.lower():
                                    await basis_client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                                    break
            except Exception as e:
                print(f"⚠️ Ошибка при синхронном клике основы: {e}", flush=True)
            await asyncio.sleep(0.3)
            
        twink_finished_event.clear()

# --- ГЛАВНЫЙ ОБРАБОТЧИК БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return

    if not hasattr(client, "collecting"): client.collecting = False
    if not hasattr(client, "trade_counter"): client.trade_counter = 0

    # АВТОКЛИКЕР НА СБОР ПРИБЫЛИ И ЕЖЕДНЕВНУЮ НАГРАДУ
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                
                if any(x in btn.text.lower() for x in ["собрать деньги", "собрать прибыль", "забрать", "забрать✅"]) or "farm_claim" in btn.callback_data.lower():
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        print(f"🎁 [Акк {acc_id}] Успешно прожал инлайн-кнопку сбора/награды ({btn.text}).", flush=True)
                        return
                    except: pass

    if not message.text: return
    text = message.text.lower()

    # --- УМНЫЙ ПАРСИНГ ТАЙМЕРА КАРТОЧЕК ---
    if "вы сможете выбить карту еще раз через" in text:
        hours_match = re.search(r'(\d+)\s*ч', text)
        minutes_match = re.search(r'(\d+)\s*мин', text)
        seconds_match = re.search(r'(\d+)\s*сек', text)

        hours = int(hours_match.group(1)) if hours_match else 0
        minutes = int(minutes_match.group(1)) if minutes_match else 0
        seconds = int(seconds_match.group(1)) if seconds_match else 0

        total_sleep_seconds = (hours * 3600) + (minutes * 60) + seconds + 60 
        
        # Защита от микро-таймеров меньше 3 минут, чтобы избежать спама
        if total_sleep_seconds < 180:
            total_sleep_seconds = 180

        minutes_display = total_sleep_seconds // 60

        print(f"⏳ [Acc {acc_id}] Бот сообщил о КД. Изменяю таймер карточек: жду {minutes_display} мин.", flush=True)
        client.card_timer_override = total_sleep_seconds
        return

    # --- АВТОМАТИЧЕСКИЙ ПРИЕМ ЗАКАЗОВ НА РЕМОНТ ---
    if "вам пришел запрос на ремонт" in text or "запрос на ремонт" in text:
        if has_button(message, "принять заказ"):
            print(f"🛠 [Аккаунт {acc_id}] Обнаружен запрос на ремонт! Нажимаю 'Принять заказ'...", flush=True)
            await click(client, message, "принять заказ")
            return

    # --- ОБЩАЯ ДЛЯ ВСЕХ КНОПКА ПОДТВЕРДИТЬ ОБМЕН ---
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
                client.dynamic_limit = 10 
                twink_finished_event.clear() 
                client.collecting = True
                asyncio.create_task(twink_collect_logic(client, acc_id))
            return

    # --- ЛОГИКА ДЛЯ ОСНОВЫ (АКК №2) ---
    if acc_id == 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                print(f"✅ [ОСНОВА - Акк 2] Приняла трейд. Включена прямая синхронизация.", flush=True)
                twink_finished_event.clear()
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

# --- ИЗОЛИРОВАННЫЙ ТАЙМЕР ДЛЯ КАРТОЧЕК ---
async def card_timer_loop(client, acc_id):
    await asyncio.sleep(5)
    print(f"📡 [Акк {acc_id}] Первичный запуск: проверяю статус 'ткарточка'...", flush=True)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass

    while True:
        try:
            if client.card_timer_override is not None and client.card_timer_override > 0:
                print(f"💤 [Акк {acc_id}] Логика карточек засыпает на {client.card_timer_override // 60} мин. КД...", flush=True)
                await asyncio.sleep(client.card_timer_override)
                
                print(f"🎉 [Акк {acc_id}] Время КД вышло! Отправляю команду 'ткарточка'.", flush=True)
                client.card_timer_override = None
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
                
                client.card_timer_override = 7260
                continue

            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)
            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                print(f"⏰ [Акк {acc_id}] Плановый чётный час. Проверяю 'ткарточка'...", flush=True)
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass

        except Exception as e:
            print(f"⚠️ Ошибка в цикле карточек аккаунта {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(30)

# --- ГЛАВНЫЕ ФОНОВЫЕ ЗАДАЧИ ---
async def bg_tasks(client, acc_id):
    asyncio.create_task(card_timer_loop(client, acc_id))

    await asyncio.sleep(8)
    print(f"🪙 [Акк {acc_id}] Проверяю статус майнинга при запуске через 'тмайнинг'...", flush=True)
    try: await client.send_message(bot_chat, "тмайнинг")
    except: pass

    if acc_id in [1, 2]:
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass

    claimed_today = False
    reward_claimed_today = False
    iris_timer = 0

    while True:
        try:
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)

            # --- ЕЖЕДНЕВНАЯ НАГРАДА В 03:00 по КЗ (01:00 по МСК) ---
            if msk_now.hour == 1 and msk_now.minute == 0:
                if not reward_claimed_today:
                    print(f"🌟 [Акк {acc_id}] Время ежедневной награды (03:00 КЗ / 01:00 МСК)! Отправляю команду...", flush=True)
                    await client.send_message(bot_chat, "ежедневная награда")
                    reward_claimed_today = True
            else:
                if msk_now.hour == 1 and msk_now.minute == 2:
                    reward_claimed_today = False

            # --- СБОР МАЙНИНГА СТРОГО В 02:10 по КЗ (00:10 по МСК) ---
            if msk_now.hour == 0 and msk_now.minute == 10:
                if not claimed_today:
                    print(f"🎰 [Акк {acc_id}] Время ежедневного сбора! Отправляю тмайнинг...", flush=True)
                    await client.send_message(bot_chat, "тмайнинг")
                    claimed_today = True
            else:
                if msk_now.hour == 0 and msk_now.minute == 11: 
                    claimed_today = False

            # Таймер Ирис-бота (каждые 4 часа)
            if acc_id in [1, 2]:
                iris_timer += 1
                if iris_timer >= 240:
                    try: await client.send_message(iris_bot_chat, "фарма")
                    except: pass
                    iris_timer = 0

        except Exception as e:
            print(f"⚠️ Ошибка в фоновых задачах майнинга {acc_id}: {e}", flush=True)
        
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Запуск фермы. Исправлено зависание категорий обмена.", flush=True)

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
            c.card_timer_override = None

            async for _ in c.get_dialogs(limit=5): pass
            
            acc_id = i + 1
            if acc_id == 2:
                print(f"👑 ГЛАВНАЯ ОСНОВА (Аккаунт 2) запущена: @{me.username}", flush=True)
                asyncio.create_task(basis_sync_loop(c))
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

    print("🚀 Скрипт запущен! Баги с меню устранены.", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
