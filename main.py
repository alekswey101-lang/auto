import threading
import os
import asyncio
import re
import datetime
from flask import Flask
from pyrogram import Client, handlers, filters
from pyrogram import raw

# --- СЕРВЕР ДЛЯ RENDER (KEEP-ALIVE) ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Ready and Running", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

bot_chat = "phonegetcardsbot"
iris_bot_chat = "iris_moon_bot"
clients = []

ACC_MACROS = {"1": "boymorale", "2": "tintedwindow", "3": "cutemald", "4": "dennyom", "5": "kuznecovvb"}
twink_finished_event = asyncio.Event()
AUTO_TRADE_ENABLED = True  

# --- НАДЕЖНЫЙ КЛИКЕР ---
async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup: return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                t_low = btn.text.lower()
                d_low = (btn.callback_data or "").lower()
                if keyword.lower() in t_low or keyword.lower() in d_low:
                    if btn.callback_data:
                        try:
                            await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                            return True
                        except: return True
    except: pass
    return False

def has_button(message, keyword: str) -> bool:
    if not message or not message.reply_markup: return False
    for row in message.reply_markup.inline_keyboard:
        for btn in row:
            t_low = btn.text.lower()
            d_low = (btn.callback_data or "").lower()
            if keyword.lower() in t_low or keyword.lower() in d_low: return True
    return False

# --- ИСТИННАЯ СОБЫТИЙНАЯ ЛОГИКА АВТОСБОРА (БЕЗ ЦИКЛОВ) ---
async def execute_trade_step(client, message, acc_id):
    # Если на этом аккаунте сейчас не запущен сбор трейда — выходим
    if not getattr(client, "collecting", False):
        return

    # Защита от слишком частых кликов по одному и тому же состоянию сообщения
    now = asyncio.get_event_loop().time()
    if hasattr(client, "last_click_time") and (now - client.last_click_time) < 1.0:
        return

    text = message.text.lower() if message.text else ""
    
    # Собираем все инлайн-кнопки
    all_buttons = []
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data:
                    all_buttons.append(btn)

    action_buttons = [b for b in all_buttons if not any(x in b.text.lower() or x in b.callback_data.lower() for x in ["назад", "back", "меню", "отмена", "готов"])]

    # 1. ПРОВЕРКА ЛИМИТОВ И ЗАВЕРШЕНИЕ
    if "занято слотов" in text or "готовность:" in text:
        slots_match = re.search(r"занято слотов:\s*(\d+)/(\d+)", text)
        if slots_match:
            current_slots = int(slots_match.group(1))
            max_slots = int(slots_match.group(2))
            if current_slots >= max_slots or (getattr(client, "working_depleted", False) and current_slots > 0):
                if has_button(message, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Трейд заполнен ({current_slots}/{max_slots}). Нажимаю Готов!", flush=True)
                    await click(client, message, "готов")
                    client.collecting = False
                    twink_finished_event.set()
                    return

        if "готовность: ✅" in text or "✅" in text:
            print(f"✅ [Твинк {acc_id}] Обмен успешно завершен ботами.", flush=True)
            client.collecting = False
            twink_finished_event.set()
            return

    # 2. КНОПКА ДОБАВИТЬ ТЕЛЕФОН (СТАРТ)
    add_btn = next((b for b in all_buttons if "добавить телефон" in b.text.lower() or "add_phone" in b.callback_data.lower()), None)
    if add_btn:
        print(f"➕ [Твинк {acc_id}] Нажимаю Добавить телефон", flush=True)
        client.last_click_time = now
        await client.request_callback_answer(message.chat.id, message.id, add_btn.callback_data, timeout=2)
        return

    # 3. РЕЖИМ БЫСТРОГО ВЫБОРА (ВКЛЮЧЕНИЕ)
    fast_mode_off_btn = next((b for b in all_buttons if "быстрый выбор: выкл" in b.text.lower()), None)
    if fast_mode_off_btn:
        print(f"⚙️ [Твинк {acc_id}] Включаю Быстрый Выбор", flush=True)
        client.last_click_time = now
        await client.request_callback_answer(message.chat.id, message.id, fast_mode_off_btn.callback_data, timeout=2)
        return

    # 4. СПИСОК МОДЕЛЕЙ (ПРОСТАВЛЕНИЕ ГАЛОЧКИ)
    not_selected_model = next((b for b in action_buttons if "❌" in b.text), None)
    selected_model = next((b for b in action_buttons if "✅" in b.text), None)
    add_selected_btn = next((b for b in all_buttons if "добавить выбранное" in b.text.lower() or "добавить выбранные" in b.text.lower()), None)

    if not_selected_model and not selected_model:
        print(f"💎 [Твинк {acc_id}] Выбираю модель телефона: [{not_selected_model.text}]", flush=True)
        client.last_click_time = now
        await client.request_callback_answer(message.chat.id, message.id, not_selected_model.callback_data, timeout=2)
        return

    # ПОДТВЕРЖДЕНИЕ ВЫБРАННОГО ПАКА
    if add_selected_btn or selected_model:
        target_confirm = add_selected_btn or next((b for b in all_buttons if "добавить" in b.text.lower()), None)
        if target_confirm:
            print(f"🚀 [Твинк {acc_id}] Подтверждаю добавление стека моделей", flush=True)
            client.last_click_time = now
            await client.request_callback_answer(message.chat.id, message.id, target_confirm.callback_data, timeout=2)
        return

    # 5. МЕНЮ ВЫБОРА СОСТОЯНИЯ (РАБОЧИЙ / СЛОМАННЫЙ)
    work_btn = next((b for b in action_buttons if "рабоч" in b.text.lower()), None)
    broken_btn = next((b for b in action_buttons if "сломан" in b.text.lower()), None)

    if work_btn or broken_btn:
        if getattr(client, "working_depleted", False) and broken_btn:
            target_btn = broken_btn
        elif work_btn and not getattr(client, "working_depleted", False):
            target_btn = work_btn
        else:
            target_btn = broken_btn or work_btn

        print(f"📱 [Твинк {acc_id}] Нажимаю на категорию состояния: '{target_btn.text}'", flush=True)
        client.last_click_time = now
        await client.request_callback_answer(message.chat.id, message.id, target_btn.callback_data, timeout=2)
        return

    # 6. МЕНЮ ВЫБОРА РЕДКОСТЕЙ
    rarity_buttons = [b for b in action_buttons if any(x in b.text.lower() for x in ["обычн", "редк", "мистич", "легенд"])]
    if rarity_buttons:
        if not hasattr(client, "empty_rarities"): client.empty_rarities = set()
        available_rarities = [b for b in rarity_buttons if b.text.lower() not in client.empty_rarities]
        
        if not available_rarities:
            print(f"⚠️ [Твинк {acc_id}] Все редкости пусты. Возврат назад.", flush=True)
            client.working_depleted = True
            client.last_click_time = now
            await click(client, message, "назад")
            return

        target_rarity = next((b for b in available_rarities if any(x in b.text.lower() for x in ["мистич", "редк", "легенд"])), available_rarities[0])
        print(f"🔮 [Твинк {acc_id}] Выбираю редкость: [{target_rarity.text}]", flush=True)
        client.last_click_time = now
        await client.request_callback_answer(message.chat.id, message.id, target_rarity.callback_data, timeout=2)
        return

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

# --- ГЛАВНЫЙ ОБРАБОТЧИК СОБЫТИЙ БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return
    if not hasattr(client, "collecting"): client.collecting = False

    # Сбор автоприбыли (независимо от трейда)
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                if any(x in btn.text.lower() for x in ["собрать деньги", "собрать прибыль", "забрать", "забрать✅"]) or "farm_claim" in btn.callback_data.lower():
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        return
                    except: pass

    if not message.text: return
    text = message.text.lower()

    # Таймер карт
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

    # Запросы на ремонт
    if "вам пришел запрос на ремонт" in text or "запрос на ремонт" in text:
        if has_button(message, "принять заказ"):
            await click(client, message, "принять заказ")
            return

    if not AUTO_TRADE_ENABLED: return

    # Подтверждения обмена
    if "подтвердите обмен" in text or "подтвердите" in text or has_button(message, "подтвердить") or has_button(message, "trade_confirm"):
        await click(client, message, "trade_confirm")
        await click(client, message, "подтвердить")
        return

    # Прием входящего трейда на твинках
    if acc_id != 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                print(f"✅ [Твинк {acc_id}] Трейд принят. Запуск автосбора.", flush=True)
                twink_finished_event.clear() 
                client.collecting = True
                client.working_depleted = False
                client.empty_rarities = set()
                # Сразу делаем первый шаг по принятому сообщению
                await execute_trade_step(client, message, acc_id)
            return

    # Прием входящего трейда на основе
    if acc_id == 2:
        if "предложение обмена" in text or "пришло предложение" in text:
            if "ваше предложение обмена отправлено" in text: return
            if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                twink_finished_event.clear()
            return

    # Если мы уже находимся в режиме активного сбора твинка — обрабатываем изменения интерфейса
    if getattr(client, "collecting", False):
        await execute_trade_step(client, message, acc_id)

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
        if len(parts) == 2 and parts[1] in ACC_MACROS: target = ACC_MACROS[parts[1]]
        elif message.reply_to_message and message.reply_to_message.from_user:
            user = message.reply_to_message.from_user
            target = user.username or str(user.id)
        elif len(parts) >= 2: target = parts[1].replace("@", "").strip()

        if not target: return
        try: await message.delete()
        except: pass
        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        await client.send_message(bot_chat, bot_cmd)

# --- ТАЙМЕРЫ КАРТОЧЕК И БЭКГРАУНД ---
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

async def bg_tasks(client, acc_id):
    asyncio.create_task(card_timer_loop(client, acc_id))
    await asyncio.sleep(8)
    try: await client.send_message(bot_chat, "тмайнинг")
    except: pass
    if acc_id in [1, 2]:
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass

    claimed_today, reward_claimed_today, iris_timer = False, False, 0
    while True:
        try:
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)
            if msk_now.hour == 1 and msk_now.minute == 0:
                if not reward_claimed_today:
                    await client.send_message(bot_chat, "ежедневная награда")
                    reward_claimed_today = True
            else:
                if msk_now.hour == 1 and msk_now.minute == 2: reward_claimed_today = False

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
        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    global clients
    print("🛠 Перезапуск фермы. Инициализация событийно-ориентированных сессий...", flush=True)

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
            c.collecting = False
            
            async if_dialogs = c.get_dialogs(limit=5)
            async for _ in if_dialogs: pass
            
            acc_id = i + 1
            if acc_id == 2:
                print(f"👑 ГЛАВНАЯ ОСНОВА (Аккаунт 2) запущена: @{me.username}", flush=True)
                asyncio.create_task(basis_sync_loop(c))
            else:
                print(f"✅ Аккаунт {acc_id} запущен: @{me.username}", flush=True)

            # РЕГИСТРИРУЕМ ОБРАБОТЧИКИ НА ПОЛУЧЕНИЕ И РЕДАКТИРОВАНИЕ ТЕКСТА/КНОПОК
            c.add_handler(handlers.MessageHandler(
                lambda client, message, a_id=acc_id: client.loop.create_task(process_bot_logic(client, message, a_id)),
                filters.chat(bot_chat)
            ), group=0)

            c.add_handler(handlers.EditedMessageHandler(
                lambda client, message, a_id=acc_id: client.loop.create_task(process_bot_logic(client, message, a_id)),
                filters.chat(bot_chat)
            ), group=0)
            
            asyncio.create_task(bg_tasks(c, acc_id))
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {i+1}: {e}", flush=True)

    print("🚀 Скрипт полностью переведён на Event-Driven архитектуру!", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
        
