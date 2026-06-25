import os
import re
import asyncio
import threading
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from flask import Flask

# --- ДАННЫЕ ИЗ ENVIRONMENT VARIABLES RENDER ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

BOT_ID = @phonegetcardsbot       # Актуальный ID игрового бота PhoneGet
IRIS_BOT_ID = "@iris_moon_bot"  # Юзернейм Ирис бота для фармы
AUTO_TRADE_ENABLED = True

# Подгружаем строки сессий из панели управления Render
SESSIONS = [
    os.environ.get("SESSION_1", ""),  # Твинк 1 (Acc 1) -> Нужен Ирис
    os.environ.get("SESSION_2", ""),  # ОСНОВА (Acc 2)  -> Нужен Ирис
    os.environ.get("SESSION_3", ""),  # Твинк 2 (Acc 3)
    os.environ.get("SESSION_4", ""),  # Твинк 3 (Acc 4)
    os.environ.get("SESSION_5", "")   # Твинк 4 (Acc 5)
]

OWNER_IDS = []  # Наполняется автоматически при запуске скрипта
clients = []
twink_finished_event = asyncio.Event()

# --- СЕРВЕР ДЛЯ RENDER (KEEP-ALIVE) ---
app_flask = Flask(__name__)

@app_flask.route('/')
def health():
    return "Ready and Running", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def has_button(message, target_text):
    if not message.reply_markup: return False
    for row in message.reply_markup.inline_keyboard:
        for btn in row:
            if target_text.lower() in btn.text.lower() or (btn.callback_data and target_text.lower() in btn.callback_data.lower()):
                return True
    return False

async def click(client, message, target_text):
    if not message.reply_markup: return False
    for row in message.reply_markup.inline_keyboard:
        for btn in row:
            if target_text.lower() in btn.text.lower() or (btn.callback_data and target_text.lower() in btn.callback_data.lower()):
                try:
                    await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=3)
                    return True
                except:
                    return False
    return False


# --- ЛОГИКА АВТОСБОРА ДЛЯ ТВИНКОВ (PhoneGet) ---
async def twink_collect_logic(client, acc_id):
    print(f"🚀 [Аккаунт {acc_id}] Алгоритм сбора запущен.", flush=True)
    try:
        while not twink_finished_event.is_set():
            await asyncio.sleep(1.5)
            try:
                history = await client.get_chat_history(BOT_ID, limit=1)
                if not history: continue
                msg = history[0]
            except Exception as e:
                print(f"⚠️ [Аккаунт {acc_id}] Ошибка чтения истории: {e}", flush=True)
                continue

            if "обмен завершен" in msg.text.lower() or "обмен был отменен" in msg.text.lower():
                print(f"🏁 [Аккаунт {acc_id}] Трейд окончен. Выход.", flush=True)
                break

            if has_button(msg, "рабочий телефон"):
                await click(client, msg, "рабочий телефон")
                continue
            if has_button(msg, "сломанный телефон"):
                await click(client, msg, "сломанный телефон")
                continue
            if has_button(msg, "добавить телефон"):
                await click(client, msg, "добавить телефон")
                continue

            if msg.reply_markup:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if btn.text and ("📱" in btn.text or "iphone" in btn.text.lower() or "xiaomi" in btn.text.lower() or "📳" in btn.text):
                            try:
                                await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=2)
                            except: pass
    except Exception as e:
        print(f"❌ [Аккаунт {acc_id}] Ошибка в цикле автосбора: {e}", flush=True)
    finally:
        client.collecting = False


# --- ГЛАВНЫЙ ОБРАБОТЧИК БОТА ---
async def process_bot_logic(client, message, acc_id):
    if not message: return
    if not hasattr(client, "collecting"): client.collecting = False

    # 1. Сбор прибыли и наград
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                b_text = btn.text.lower()
                b_data = btn.callback_data.lower()
                
                if any(x in b_text for x in ["собрать деньги", "собрать прибыль", "забрать", "забрать✅", "снять деньги"]) or "farm_claim" in b_data or "reward" in b_data:
                    try:
                        print(f"💰 [Аккаунт {acc_id}] Клик по сбору прибыли [{btn.text}].", flush=True)
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=3)
                    except: pass

    if not message.text: return
    text = message.text.lower()

    # 2. Обработка таймера карточек
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
        print(f"⏳ [Аккаунт {acc_id}] Новый оверрайд таймера: {total_sleep_seconds} сек.", flush=True)
        return

    # 3. Запрос на ремонт
    if "вам пришел запрос на ремонт" in text or "запрос на ремонт" in text:
        if has_button(message, "принять заказ"):
            await click(client, message, "принять заказ")
            return

    if not AUTO_TRADE_ENABLED: return

    # 4. Подтверждение обмена
    if has_button(message, "подтвердить") or has_button(message, "trade_confirm") or "подтвердите обмен" in text or "подтвердите" in text:
        await click(client, message, "trade_confirm")
        await click(client, message, "подтвердить")
        return

    # 5. Перехват начала предложения обмена
    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text: return
        if await click(client, message, "trade_accept") or await click(client, message, "принять"):
            twink_finished_event.clear()
            if acc_id != 2 and not client.collecting:
                print(f"✅ [Аккаунт {acc_id}] Трейд принят. Запуск автосбора.", flush=True)
                client.collecting = True
                asyncio.create_task(twink_collect_logic(client, acc_id))
            return

    # АВТО-ПОДХВАТ МЕНЮ ОБМЕНА
    if acc_id != 2:
        if "выберите категорию телефона" in text or "открываю меню обмена" in text or has_button(message, "рабочий телефон") or has_button(message, "сломанный телефон"):
            if not client.collecting:
                print(f"🔗 [Аккаунт {acc_id}] Найдено зависшее меню категорий! Принудительно толкаю сбор.", flush=True)
                twink_finished_event.clear()
                client.collecting = True
                asyncio.create_task(twink_collect_logic(client, acc_id))
            else:
                work_btn = next((b for row in message.reply_markup.inline_keyboard for b in row if "рабоч" in b.text.lower()), None)
                if work_btn:
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, work_btn.callback_data, timeout=2)
                    except: pass


# --- ЦИКЛ ОТПРАВКИ КАРТОЧЕК ---
async def card_timer_loop(client, acc_id):
    await asyncio.sleep(15)  # Даем время на полный запуск всех сессий
    while True:
        try:
            client.card_timer_override = None
            print(f"🃏 [Аккаунт {acc_id}] Отправка команды: ткарточка", flush=True)
            await client.send_message(BOT_ID, "ткарточка")
            
            await asyncio.sleep(10)
            
            if client.card_timer_override:
                sleep_time = client.card_timer_override
            else:
                sleep_time = 7300
                
            print(f"💤 [Аккаунт {acc_id}] Спим {sleep_time} сек до следующей карточки.", flush=True)
            await asyncio.sleep(sleep_time)
            
        except Exception as e:
            print(f"⚠️ [Таймер Карточек {acc_id}] Ошибка: {e}. Переповтор через 30 сек.", flush=True)
            await asyncio.sleep(30)


# --- ТАЙМЕР ДЛЯ ИРИС ФАРМЫ (АККАУНТЫ 1 И 2) ---
async def iris_farm_loop(client, acc_id):
    await asyncio.sleep(30)  # Сдвигаем старт фармы, чтобы не спамить одновременно
    while True:
        try:
            prefix = "ОСНОВА" if acc_id == 2 else "Твинк 1"
            print(f"🌌 [Ирис Фарма - {prefix}] Отправка команды: фарма", flush=True)
            await client.send_message(IRIS_BOT_ID, "фарма")
            
            # 241 минута = 241 * 60 = 14460 секунд
            await asyncio.sleep(14460)
        except Exception as e:
            print(f"⚠️ [Ирис Фарма - Acc {acc_id}] Ошибка: {e}. Повтор через 60 сек.", flush=True)
            await asyncio.sleep(60)


# --- ЗАПУСК ВСЕХ КЛИЕНТОВ ---
async def start_bot():
    print("🤖 Запуск инициализации аккаунтов...", flush=True)
    
    if not API_ID or not API_HASH:
        print("❌ ОШИБКА: API_ID или API_HASH не заданы в переменных Render!", flush=True)
        return

    # Шаг 1: Сбор ID владельцев (сессий) и предварительный resolve_peer, чтобы избежать PEER_ID_INVALID
    for i, session in enumerate(SESSIONS, start=1):
        if not session: continue
        try:
            temp_c = Client(f"session_prefix_{i}", api_id=API_ID, api_hash=API_HASH, session_string=session, in_memory=True)
            await temp_c.start()
            me = await temp_c.get_me()
            OWNER_IDS.append(me.id)
            
            # Принудительно знакомим аккаунт с ботами, кэшируя их peer_id в сессию
            try:
                await temp_c.resolve_peer(BOT_ID)
                if i in [1, 2]:  # Для 1 и 2 аккаунтов кэшируем еще и Ирис
                    await temp_c.resolve_peer(IRIS_BOT_ID)
            except Exception as pe:
                print(f"ℹ️ Не критичное предупреждение кэширования пиров для Acc {i}: {pe}", flush=True)

            await temp_c.stop()
            prefix = "ОСНОВА" if i == 2 else f"Твинк {i if i < 2 else i-1}"
            print(f" Loaded Acc {i} ({prefix}): ID {me.id}", flush=True)
        except Exception as e:
            print(f"❌ Не удалось прогрузить сессию {i}: {e}", flush=True)

    # Шаг 2: Запуск основных клиентов
    for i, session in enumerate(SESSIONS, start=1):
        if not session: continue
        cl = Client(f"session_active_{i}", api_id=API_ID, api_hash=API_HASH, session_string=session, in_memory=True)
        cl.card_timer_override = None
        cl.collecting = False

        @cl.on_message(filters.me & filters.text)
        async def manual_commands_handler(client, message, current_acc_id=i):
            """Обработчик ваших личных текстовых команд .т и .ат для взаимного контроля"""
            cmd = message.text.strip().lower()
            if cmd.startswith(".т 1"):
                await client.send_message(BOT_ID, "тмайнинг")
            elif cmd.startswith(".т 2"):
                await client.send_message(BOT_ID, "тработа")
            elif cmd.startswith(".ткарточка") or cmd.startswith(".ат"):
                await client.send_message(BOT_ID, "ткарточка")

        @cl.on_message(filters.chat(BOT_ID))
        async def bot_handler(client, message, current_acc_id=i):
            """Обработчик сообщений от игрового бота PhoneGet"""
            try:
                _ = message.chat.id
            except (ValueError, KeyError, RPCError):
                return
            await process_bot_logic(client, message, current_acc_id)

        await cl.start()
        clients.append(cl)
        
        # Запуск цикла для PhoneGet карточек (для всех аккаунтов)
        asyncio.create_task(card_timer_loop(cl, i))
        
        # Запуск цикла Ирис Фармы только для Первого (i=1) и Второго (i=2) аккаунта
        if i in [1, 2]:
            asyncio.create_task(iris_farm_loop(cl, i))

    print("🚀 Все активные аккаунты успешно запущены, команды исправлены, Ирис фарма на 1 и 2 акках активна!", flush=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_bot())
