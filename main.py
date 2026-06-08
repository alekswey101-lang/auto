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

# Стандартные 5 сессий
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

bot_chat = "phonegetcardsbot"
iris_bot_chat = "iris_moon_bot"

clients = []

# Макросы для трейда (@kuznecovvb на 5-м слоте)
ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "kuznecovvb"
}

twink_finished_event = asyncio.Event()
AUTO_TRADE_ENABLED = True

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
                                timeout=2
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

# --- ОБНОВЛЕННЫЙ АВТОСБОР ТВИНКА (ПОД БЫСТРЫЙ ВЫБОР) ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Фоновый автосбор через БЫСТРЫЙ ВЫБОР начат.", flush=True)
    
    client.trade_counter = 0
    client.dynamic_limit = 10 
    
    working_phones_depleted = False 
    empty_rarities = set()        
    last_clicked_rarity = None    
    last_menu_state = None        

    for tick in range(100):
        try:
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.5)
                continue

            text = msg.text.lower() if msg.text else ""

            # Если трейд уже забит или бот пишет, что слоты заняты
            if client.trade_counter >= client.dynamic_limit or "занято слотов" in text:
                if has_button(msg, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Нажимаю Готов!", flush=True)
                    await click(client, msg, "готов")
                    twink_finished_event.set()
                    client.collecting = False 
                    return 

                if "готовность: ✅" in text or "✅" in text:
                    twink_finished_event.set()
                    client.collecting = False
                    return

                if has_button(msg, "вернуться назад") or has_button(msg, "назад"):
                    await click(msg, "назад")
                    await asyncio.sleep(1.0)
                continue

            # Фильтруем системные кнопки
            all_buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        all_buttons.append(btn)

            action_buttons = [b for b in all_buttons if not any(x in b.text.lower() or x in b.callback_data.lower() for x in ["назад", "back", "меню", "отмена", "готов"])]

            # Проверка вылета из редкостей (если категория оказалась пустой)
            work_btn_check = next((b for b in action_buttons if "рабоч" in b.text.lower()), None)
            if last_menu_state == "rarity" and work_btn_check and last_clicked_rarity:
                print(f"🚫 [Твинк {acc_id}] Категория '{last_clicked_rarity}' пуста. В ЧС её.", flush=True)
                empty_rarities.add(last_clicked_rarity)
                last_clicked_rarity = None

            # --- МЕНЮ ВЫБОРА МОДЕЛЕЙ (image_bf2ff2.png / image_bf2cc9.png) ---
            fast_mode_btn = next((b for b in all_buttons if "быстрый выбор:" in b.text.lower()), None)
            if fast_mode_btn:
                # Шаг 1: Если быстрый выбор выключен — включаем его
                if "выкл" in fast_mode_btn.text.lower():
                    print(f"⚙️ [Твинк {acc_id}] Включаю режим 'Быстрый выбор'...", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, fast_mode_btn.callback_data, timeout=2)
                    await asyncio.sleep(1.0)
                    continue

                # Шаг 2: Если включен — прокликиваем модели, у которых еще нет галочки [❌]
                add_selected_btn = next((b for b in all_buttons if "добавить выбранное" in b.text.lower()), None)
                
                # Ищем телефоны (исключаем кнопки переключения режима и назад)
                phone_buttons = [b for b in action_buttons if "быстрый выбор" not in b.text.lower() and "добавить" not in b.text.lower()]
                
                # Отбираем те, которые еще НЕ выбраны (содержат [❌] или не имеют [✅])
                available_phones = [b for b in phone_buttons if "✅" not in b.text.lower()]

                if available_phones and client.trade_counter < client.dynamic_limit:
                    target_phone = available_phones[0]
                    client.trade_counter += 1
                    print(f"📱 [Твинк {acc_id}] Выбираю телефон: {target_phone.text} [{client.trade_counter}/{client.dynamic_limit}]", flush=True)
                    await client.request_callback_answer(msg.chat.id, msg.id, target_phone.callback_data, timeout=2)
                    await asyncio.sleep(0.6)  # Быстрый проклик без долгого ожидания
                    continue
                else:
                    # Шаг 3: Набрали 10 штук или телефоны кончились — жмем "Добавить выбранное"
                    if add_selected_btn:
                        print(f"📥 [Твинк {acc_id}] Все телефоны отмечены. Нажимаю 'Добавить выбранное'", flush=True)
                        await client.request_callback_answer(msg.chat.id, msg.id, add_selected_btn.callback_data, timeout=2)
                        last_menu_state = "trade_main"
                        await asyncio.sleep(1.5)
                        continue

            # --- МЕНЮ ВЫБОРА РЕДКОСТЕЙ ---
            rarity_buttons = [b for b in action_buttons if any(x in b.text.lower() for x in ["обычн", "редк", "мистич", "легенд"])]
            if rarity_buttons:
                available_rarities = [b for b in rarity_buttons if b.text.lower() not in empty_rarities]
                
                if not available_rarities:
                    await click(client, msg, "назад")
                    working_phones_depleted = True
                    last_menu_state = "rarity_empty"
                    await asyncio.sleep(1.5)
                    continue

                target_rarity = next((b for b in available_rarities if any(x in b.text.lower() for x in ["мистич", "редк", "легенд"])), available_rarities[0])
                last_clicked_rarity = target_rarity.text.lower()
                last_menu_state = "rarity"
                
                await client.request_callback_answer(msg.chat.id, msg.id, target_rarity.callback_data, timeout=2)
                await asyncio.sleep(1.5)
                continue

            # --- МЕНЮ ВЫБОРА СОСТОЯНИЯ (Рабочий / Сломанный) ---
            work_btn = next((b for b in action_buttons if "рабоч" in b.text.lower()), None)
            broken_btn = next((b for b in action_buttons if "сломан" in b.text.lower()), None)

            if work_btn or broken_btn:
                if working_phones_depleted and broken_btn:
                    target_btn = broken_btn
                    client.dynamic_limit = 5
                elif work_btn:
                    target_btn = work_btn
                    client.dynamic_limit = 10
                else:
                    target_btn = broken_btn or work_btn

                last_menu_state = "state"
                try:
                    res = await client.request_callback_answer(msg.chat.id, msg.id, target_btn.callback_data, timeout=2)
                    if res and hasattr(res, 'message') and any(x in res.message.lower() for x in ["нет", "доступных", "отсутствуют", "пусто"]):
                        if target_btn == work_btn:
                            working_phones_depleted = True
                except:
                    pass
                await asyncio.sleep(1.5)
                continue

            # --- ГЛАВНОЕ МЕНЮ ОБМЕНА ---
            add_btn = next((b for b in all_buttons if "добавить телефон" in b.text.lower() or "add_phone" in b.callback_data.lower()), None)
            if add_btn:
                last_menu_state = "trade_main"
                await client.request_callback_answer(msg.chat.id, msg.id, add_btn.callback_data, timeout=2)
                await asyncio.sleep(1.2)
                continue

        except Exception as e:
            print(f"⚠️ Ошибка автосбора твинка {acc_id}: {e}", flush=True)
        await asyncio.sleep(0.5)

    client.collecting = False

# --- ФОНОВАЯ ЗАДАЧА СИНХРОНИЗАЦИИ ДЛЯ ОСНОВЫ ---
async def basis_sync_loop(basis_client):
    while True:
        await twink_finished_event.wait()
        
        if not AUTO_TRADE_ENABLED:
            twink_finished_event.clear()
            await asyncio.sleep(1)
            continue
            
        print("🔗 [СИНХРОНИЗАЦИЯ] Твинк закончил сбор. Основа прожимает готовность...", flush=True)
        
        for _ in range(5):
            try:
                msg = None
                async for m in basis_client.get_chat_history(bot_chat, limit=1):
                    msg = m
                    break
                
                if msg:
                    if has_button(msg, "готов"):
                        await click(basis_client, msg, "готов")
                        break
                    else:
                        for row in msg.reply_markup.inline_keyboard if msg.reply_markup else []:
                            for btn in row:
                                if "назад" in btn.text.lower() or "вернуться" in btn.text.lower():
                                    await basis_client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=1)
                                    break
            except: pass
            await asyncio.sleep(0.5)
            
        twink_finished_event.clear()

# --- ГЛАВНЫЙ ОБРАБОТЧИК БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return
    if not hasattr(client, "collecting"): client.collecting = False

    # Принудительный сбор денег с фермы
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                btn_text = btn.text.lower()
                if "снять деньги с фермы" in btn_text or "собрать деньги" in btn_text or "farm_claim" in btn.callback_data.lower():
                    try:
                        print(f"💰 [Аккаунт {acc_id}] Обнаружена кнопка фермы! Принудительно кликаю...", flush=True)
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                    except Exception as e:
                        print(f"⚠️ Ошибка клика по ферме: {e}", flush=True)

    if not message.text: return
    text = message.text.lower()

    if "вы сможете выбить карту еще раз через" in text:
        hours_match = re.search(r'(\d+)\s*ч', text)
        minutes_match = re.search(r'(\d+)\s*мин', text)
        seconds_match = re.search(r'(\d+)\s*сек', text)

        hours = int(hours_match.group(1)) if hours_match else 0
        minutes = int(minutes_match.group(1)) if minutes_match else 0
        seconds = int(seconds_match.group(1)) if seconds_match else 0

        total_sleep_seconds = (hours * 3600) + (minutes * 60) + seconds + 60 
        if total_sleep_seconds < 180: total_sleep_seconds = 180

        client.card_timer_override = total_sleep_seconds
        return

    if "вам пришел запрос на ремонт" in text or "запрос на ремонт" in text:
        if has_button(message, "принять заказ"):
            await click(client, message, "принять заказ")
            return

    if not AUTO_TRADE_ENABLED:
        return

    if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
        await click(client, message, "trade_confirm")
        await click(client, message, "подтвердить")
        return

    if "подтвердите обмен" in text or "подтвердите" in text:
        if has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
            await click(client, message, "trade_confirm")
            await click(client, message, "подтвердить")
            return

    if acc_id != 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                if client.collecting: return
                print(f"✅ [Твинк {acc_id}] Трейд принят. Запуск быстрого автосбора.", flush=True)
                twink_finished_event.clear() 
                client.collecting = True
                asyncio.create_task(twink_collect_logic(client, acc_id))
            return

    if acc_id == 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                twink_finished_event.clear()
            return

# --- ХЕНДЛЕР КОМАНД ЮЗЕРА ---
async def handle_my_messages(client, message):
    global AUTO_TRADE_ENABLED
    if not message.text: return
    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    if cmd == ".ping":
        try: await message.edit("🚀 Юзербот активен!")
        except: pass
        return

    if cmd == ".at":
        AUTO_TRADE_ENABLED = not AUTO_TRADE_ENABLED
        status_text = "✅ ВКЛЮЧЕН" if AUTO_TRADE_ENABLED else "❌ ВЫКЛЮЧЕН"
        try:
            await message.edit(f"🤖 **Автотрейд сейчас:** {status_text}")
            await asyncio.sleep(3)
            await message.delete()
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

# --- ИЗОЛИРОВАННЫЙ ТАЙМЕР КАРТОЧЕК ---
async def card_timer_loop(client, acc_id):
    await asyncio.sleep(5)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass

    while True:
        try:
            if client.card_timer_override is not None and client.card_timer_override > 0:
                await asyncio.sleep(client.card_timer_override)
                client.card_timer_override = None
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
                continue

            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)
            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
        except: pass
        await asyncio.sleep(30)

# --- ГЛАВНЫЕ ФОНОВЫЕ ЗАДАЧИ ---
async def bg_tasks(client, acc_id):
    asyncio.create_task(card_timer_loop(client, acc_id))

    await asyncio.sleep(8)
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

            if msk_now.hour == 1 and msk_now.minute == 0:
                if not reward_claimed_today:
                    await client.send_message(bot_chat, "ежедневная награда")
                    reward_claimed_today = True
            else:
                if msk_now.hour == 1 and msk_now.minute == 2:
                    reward_claimed_today = False

            if msk_now.hour == 0 and msk_now.minute == 10:
                if not claimed_today:
                    await client.send_message(bot_chat, "тмайнинг")
                    claimed_today = True
            else:
                if msk_now.hour == 0 and msk_now.minute == 11: 
                    claimed_today = False

            if acc_id in [1, 2]:
                iris_timer += 1
                if iris_timer >= 240:
                    try: await client.send_message(iris_bot_chat, "фарма")
                    except: pass
                    iris_timer = 0
        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Перезапуск фермы. Логика обновлена под режим 'Быстрый выбор'.", flush=True)

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
                print(f"✅ Аккаунт {acc_id} запущен: @{me.username}", flush=True)

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

    print("🚀 Скрипт запущен! Быстрый выбор 10 телефонов работает стабильно.", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
