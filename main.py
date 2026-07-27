import os
import re
import datetime
import asyncio
import threading
from flask import Flask
from pyrogram import Client, handlers, filters
from pyrogram.raw.functions.contacts import ResolveUsername

# --- 1. ВЕБ-СЕРВЕР ДЛЯ CRON-JOB.ORG (KEEP-ALIVE) ---
app = Flask(__name__)

@app.route('/')
def health():
    return "OK", 200

@app.route('/ping')
def ping():
    return "PONG", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # Запускаем Flask в отдельном потоке без отладки
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# --- CONFIG ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]

BOT_USERNAME = "phonegetcardsbot"
IRIS_USERNAME = "iris_moon_bot"

ACC_MACROS = {
    "1": "boymorale",
    "2": "tintedwindow",
    "3": "cutemald",
    "4": "dennyom",
    "5": "kuznecovvb"
}

twink_finished_event = asyncio.Event()
AUTO_TRADE_ENABLED = True

# --- 2. ПРИНУДИТЕЛЬНАЯ И НАДЕЖНАЯ ОТПРАВКА ---
async def force_send(client, target_username: str, text: str):
    try:
        resolved_peer = await client.invoke(ResolveUsername(username=target_username))
        target_id = resolved_peer.peer.user_id
        await client.send_message(target_id, text)
        print(f"✅ [{client.acc_id}] Отправлено '{text}' в @{target_username}", flush=True)
    except Exception as e:
        print(f"❌ [{client.acc_id}] Ошибка отправки '{text}' в @{target_username}: {e}", flush=True)

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

# --- ТЕХНИЧЕСКИЙ АВТОСБОР ТВИНКА ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Фоновый автосбор НАЧАТ.", flush=True)
    
    client.trade_counter = 0
    client.dynamic_limit = 10 
    
    working_phones_depleted = False 
    empty_rarities = set()        
    last_clicked_rarity = None    
    last_menu_state = None        

    for tick in range(80):
        try:
            msg = None
            async for m in client.get_chat_history(BOT_USERNAME, limit=1):
                msg = m
                break

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.5)
                continue

            text = msg.text.lower() if msg.text else ""

            if client.trade_counter >= client.dynamic_limit or "занято слотов" in text:
                if has_button(msg, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Трейд заполнен. Нажимаю Готов!", flush=True)
                    await click(client, msg, "готов")
                    twink_finished_event.set()
                    client.collecting = False 
                    return 

                if "готовность: ✅" in text or "✅" in text:
                    twink_finished_event.set()
                    client.collecting = False
                    return

                if has_button(msg, "вернуться назад") or has_button(msg, "назад"):
                    await click(client, msg, "назад")
                    await asyncio.sleep(1.0)
                continue

            all_buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        all_buttons.append(btn)

            action_buttons = [b for b in all_buttons if not any(x in b.text.lower() or x in b.callback_data.lower() for x in ["назад", "back", "меню", "отмена", "готов"])]

            work_btn_check = next((b for b in action_buttons if "рабоч" in b.text.lower()), None)
            if last_menu_state == "rarity" and work_btn_check and last_clicked_rarity:
                empty_rarities.add(last_clicked_rarity)
                last_clicked_rarity = None

            single_btn = next((b for b in action_buttons if "1 шт" in b.text.lower() or "single" in b.callback_data.lower()), None)
            if single_btn:
                client.trade_counter += 1
                last_menu_state = "model_select"
                await client.request_callback_answer(msg.chat.id, msg.id, single_btn.callback_data, timeout=2)
                await asyncio.sleep(1.5)
                continue

            has_categories = any(any(x in b.text.lower() for x in ["рабоч", "сломан", "обычн", "редк", "мистич", "легенд"]) for b in action_buttons)
            if action_buttons and not has_categories:
                target_model = action_buttons[0]
                last_menu_state = "model_list"
                await client.request_callback_answer(msg.chat.id, msg.id, target_model.callback_data, timeout=2)
                await asyncio.sleep(1.5)
                continue

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
                except: pass

                await asyncio.sleep(1.5)
                continue

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

# --- ФОНОВАЯ ЗАДАЧА СИНХРОНИЗАЦИИ ---
async def basis_sync_loop(basis_client):
    while True:
        await twink_finished_event.wait()
        
        if not AUTO_TRADE_ENABLED:
            twink_finished_event.clear()
            await asyncio.sleep(1)
            continue
            
        print("🔗 [СИНХРОНИЗАЦИЯ] Основа прожимает готовность...", flush=True)
        
        for _ in range(5):
            try:
                msg = None
                async for m in basis_client.get_chat_history(BOT_USERNAME, limit=1):
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

# --- ГЛАВНЫЙ ОБРАБОТЧИК ЛОГИКИ ---
async def process_bot_logic(client, message, acc_id):
    try:
        if not message or not message.text: return
        text = message.text.lower()

        if "вам пришло предложение обмена от" in text or has_button(message, "принять"):
            if has_button(message, "принять") or has_button(message, "trade_accept"):
                print(f"🎯 [Аккаунт {acc_id}] Принимаю обмен...", flush=True)
                if await click(client, message, "trade_accept") or await click(client, message, "принять"):
                    twink_finished_event.clear()
                    if acc_id != 2:
                        if getattr(client, 'collecting', False): return
                        client.collecting = True
                        asyncio.create_task(twink_collect_logic(client, acc_id))
                return

        # Сбор денег с майнинга по кнопке
        if message.reply_markup:
            for row in message.reply_markup.inline_keyboard:
                for btn in row:
                    if not btn.callback_data: continue
                    b_text = btn.text.lower()
                    if any(x in b_text for x in ["снять деньги с фермы", "снять прибыль", "собрать деньги", "собрать прибыль", "забрать"]) or "farm_claim" in btn.callback_data.lower():
                        try:
                            print(f"💰 [Аккаунт {acc_id}] Снимаю прибыль с майнинга", flush=True)
                            await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                            return
                        except: pass

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

        if not AUTO_TRADE_ENABLED: return

        if has_button(message, "подтвердить") or has_button(message, "trade_confirm") or "подтвердите обмен" in text:
            await click(client, message, "trade_confirm")
            await click(client, message, "подтвердить")
            return
    except Exception as e:
        pass

# --- ХЕНДЛЕР КОМАНД ПОЛЬЗОВАТЕЛЯ ---
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
            await message.edit(f"🤖 **Автотрейд:** {status_text}")
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
        await force_send(client, BOT_USERNAME, bot_cmd)

# --- ТАЙМЕР КАРТОЧЕК ---
async def card_timer_loop(client, acc_id):
    await asyncio.sleep(5)
    await force_send(client, BOT_USERNAME, "ткарточка")

    while True:
        try:
            if getattr(client, 'card_timer_override', None) and client.card_timer_override > 0:
                await asyncio.sleep(client.card_timer_override)
                client.card_timer_override = None
                await force_send(client, BOT_USERNAME, "ткарточка")
                continue

            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)
            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                await force_send(client, BOT_USERNAME, "ткарточка")
        except: pass
        await asyncio.sleep(30)

# --- ФОНОВЫЕ ЗАДАЧИ ---
async def bg_tasks(client, acc_id):
    asyncio.create_task(card_timer_loop(client, acc_id))

    await asyncio.sleep(8)
    await force_send(client, BOT_USERNAME, "тмайнинг")

    if acc_id in [1, 2]:
        await force_send(client, IRIS_USERNAME, "фарма")

    reward_claimed_today = False
    iris_timer = 0

    while True:
        try:
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)

            # Ежедневная награда (01:00 МСК)
            if msk_now.hour == 1 and msk_now.minute == 0:
                if not reward_claimed_today:
                    await force_send(client, BOT_USERNAME, "ежедневная награда")
                    reward_claimed_today = True
            else:
                if msk_now.hour == 1 and msk_now.minute == 2:
                    reward_claimed_today = False

            # Сбор майнинга каждые 3 часа
            if msk_now.minute == 15 and msk_now.hour % 3 == 0:
                await force_send(client, BOT_USERNAME, "тмайнинг")

            # Фарма Ирис
            if acc_id in [1, 2]:
                iris_timer += 1
                if iris_timer >= 240:
                    await force_send(client, IRIS_USERNAME, "фарма")
                    iris_timer = 0
        except: pass
        await asyncio.sleep(60)

# --- СТАРТ ---
async def start_bot():
    print("🛠 Запуск фермы. Инициализация ботов...", flush=True)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue

        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True
        )

        c.acc_id = i + 1
        c.card_timer_override = None
        c.collecting = False

        c.add_handler(handlers.MessageHandler(handle_my_messages, filters.me))

        try:
            await c.start()
            me = await c.get_me()

            acc_id = i + 1
            if acc_id == 2:
                print(f"👑 ОСНОВА (Аккаунт 2) запущена: @{me.username}", flush=True)
                asyncio.create_task(basis_sync_loop(c))
            else:
                print(f"✅ Аккаунт {acc_id} запущен: @{me.username}", flush=True)

            async def msg_wrapper(client, message, a_id=acc_id):
                await process_bot_logic(client, message, a_id)

            c.add_handler(handlers.MessageHandler(msg_wrapper, filters.private), group=0)
            c.add_handler(handlers.EditedMessageHandler(msg_wrapper, filters.private), group=0)

            asyncio.create_task(bg_tasks(c, acc_id))
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {i+1}: {e}", flush=True)

    print("🚀 Ферма запущена на Web Service и готова принимать пинги!", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
