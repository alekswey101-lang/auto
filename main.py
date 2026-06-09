# -*- coding: utf-8 -*-
import os
import re
import asyncio
import datetime
import threading
from flask import Flask
from pyrogram import Client, handlers, filters
from pyrogram import raw

app = Flask(__name__)

@app.route('/')
def health():
    return "Ready and Running", 200

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
    "5": "kuznecovvb"
}

twink_finished_event = asyncio.Event()
AUTO_TRADE_ENABLED = True

async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                t_low = btn.text.lower().replace("✅", "").replace("❌", "").strip()
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
            t_low = btn.text.lower().replace("✅", "").replace("❌", "").strip()
            d_low = (btn.callback_data or "").lower()
            if keyword.lower() in t_low or keyword.lower() in d_low:
                return True
    return False

# --- ИСПРАВЛЕННЫЙ АВТОСБОР ПО КАТЕГОРИЯМ ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Старт зачистки категорий.", flush=True)
    
    empty_rarities = set()  
    last_clicked_rarity = None    
    current_mode = "working" # Сначала собираем "рабочий", затем "сломанный"

    for tick in range(150):
        try:
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m
                break

            if not msg or not msg.reply_markup:
                await asyncio.sleep(0.5)
                continue

            text = msg.text.lower() if msg.text else ""

            if "готовность: ✅" in text and not has_button(msg, "добавить телефон"):
                twink_finished_event.set()
                client.collecting = False
                return

            slots_full = "занято слотов" in text or "слотов: 10/10" in text or "слотов: 5/5" in text
            if slots_full and has_button(msg, "готов"):
                print(f"⚡ [Твинк {acc_id}] Все слоты заполнены. Жму готов.", flush=True)
                await click(client, msg, "готов")
                twink_finished_event.set()
                client.collecting = False 
                return

            all_buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        all_buttons.append(btn)

            action_buttons = [b for b in all_buttons if not any(x in b.text.lower() or x in b.callback_data.lower() for x in ["назад", "back", "меню", "отмена", "готов", "вернуться"])]

            # КАТЕГОРИЯ 1: ВЫБОР МОДЕЛЕЙ (ЭКРАН С ТЕЛЕФОНАМИ)
            if "выберите телефон" in text or has_button(msg, "добавить выбранное"):
                if "нет доступных" in text or "отсутствуют" in text or not action_buttons:
                    print(f"📭 [Твинк {acc_id}] Модели закончились. Шаг назад.", flush=True)
                    if last_clicked_rarity:
                        empty_rarities.add(last_clicked_rarity)
                    await click(client, msg, "назад")
                    await asyncio.sleep(1.2)
                    continue

                if has_button(msg, "быстрый выбор:"):
                    fast_mode_btn = next((b for b in all_buttons if "быстрый выбор:" in b.text.lower()), None)
                    if fast_mode_btn and "выкл" in fast_mode_btn.text.lower():
                        await client.request_callback_answer(msg.chat.id, msg.id, fast_mode_btn.callback_data, timeout=2)
                        await asyncio.sleep(0.8)
                        continue

                    # Фильтруем кнопки: убираем системные и те, где стоит маркер выбранного [✅]
                    phone_buttons = [b for b in action_buttons if "быстрый выбор" not in b.text.lower() and "добавить" not in b.text.lower()]
                    current_selected = sum(1 for b in phone_buttons if "[✅]" in b.text or "✅" in b.text)
                    available_phones = [b for b in phone_buttons if "[❌]" in b.text or "❌" in b.text or ("[✅]" not in b.text and "✅" not in b.text)]

                    if available_phones and current_selected < 10 and not slots_full:
                        target_phone = available_phones[0]
                        await client.request_callback_answer(msg.chat.id, msg.id, target_phone.callback_data, timeout=2)
                        await asyncio.sleep(0.6)
                        continue
                    else:
                        add_selected_btn = next((b for b in all_buttons if "добавить выбранное" in b.text.lower()), None)
                        if add_selected_btn:
                            if last_clicked_rarity:
                                empty_rarities.add(last_clicked_rarity)
                            await client.request_callback_answer(msg.chat.id, msg.id, add_selected_btn.callback_data, timeout=2)
                            await asyncio.sleep(1.5)
                            continue
                else:
                    # Поштучный сбор (для сломанных, если нет быстрого выбора)
                    if action_buttons and not slots_full:
                        target_phone = action_buttons[0]
                        await client.request_callback_answer(msg.chat.id, msg.id, target_phone.callback_data, timeout=2)
                        await asyncio.sleep(1.2) 
                        continue
                    else:
                        if last_clicked_rarity:
                            empty_rarities.add(last_clicked_rarity)
                        await click(client, msg, "назад")
                        await asyncio.sleep(1.2)
                        continue

            # КАТЕГОРИЯ 2: ВЫБОР РЕДКОСТЕЙ
            elif "выберите редкость" in text:
                rarity_buttons = [b for b in action_buttons if any(x in b.text.lower() for x in ["обычн", "редк", "мистич", "легенд", "аркан", "платин", "артеф", "ширпотреб", "хроматич"])]
                available_rarities = [b for b in rarity_buttons if b.text.lower().replace("✅","").replace("❌","").strip() not in empty_rarities]

                if not available_rarities:
                    print(f"🔄 [Твинк {acc_id}] В режиме {current_mode} редкостей больше нет. Выхожу.", flush=True)
                    await click(client, msg, "вернуться")
                    await click(client, msg, "назад")
                    if current_mode == "working":
                        current_mode = "broken"
                    await asyncio.sleep(1.5)
                    continue

                target_rarity = available_rarities[0]
                last_clicked_rarity = target_rarity.text.lower().replace("✅","").replace("❌","").strip()
                await client.request_callback_answer(msg.chat.id, msg.id, target_rarity.callback_data, timeout=2)
                await asyncio.sleep(1.2)
                continue

            # КАТЕГОРИЯ 3: ГЛАВНЫЙ ЭКРАН ВЫБОРА КАТЕГОРИИ (РАБОЧИЙ / СЛОМАННЫЙ)
            elif "выберите категорию" in text:
                work_btn = next((b for b in action_buttons if "рабоч" in b.text.lower()), None)
                broken_btn = next((b for b in action_buttons if "сломан" in b.text.lower()), None)

                if current_mode == "broken" and broken_btn:
                    target_btn = broken_btn
                elif work_btn:
                    target_btn = work_btn
                else:
                    target_btn = broken_btn or work_btn

                print(f"🛠 [Твинк {acc_id}] Нажимаю на категорию: {target_btn.text}", flush=True)
                await client.request_callback_answer(msg.chat.id, msg.id, target_btn.callback_data, timeout=2)
                await asyncio.sleep(1.5)
                continue

            # КАТЕГОРИЯ 4: КОРНЕВОЙ ЭКРАН ОБМЕНА
            else:
                add_btn = next((b for b in all_buttons if "добавить телефон" in b.text.lower() or "add_phone" in b.callback_data.lower()), None)
                if add_btn:
                    await client.request_callback_answer(msg.chat.id, msg.id, add_btn.callback_data, timeout=2)
                    await asyncio.sleep(1.2)
                    continue
                if has_button(msg, "готов"):
                    await click(client, msg, "готов")
                    twink_finished_event.set()
                    client.collecting = False
                    return

        except Exception as e:
            print(f"⚠️ Ошибка циклического автосбора твинка {acc_id}: {e}", flush=True)
        await asyncio.sleep(0.4)
    client.collecting = False

async def basis_sync_loop(basis_client):
    while True:
        await twink_finished_event.wait()
        if not AUTO_TRADE_ENABLED:
            twink_finished_event.clear()
            await asyncio.sleep(1)
            continue
        print("🔗 [СИНХРОНИЗАЦИЯ] Твинк заполнил слоты. Основа прожимает готовность...", flush=True)
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

async def process_bot_logic(client, message, acc_id):
    if not message: return
    if not hasattr(client, "collecting"): client.collecting = False

    # АВТОСБОР ПРИ ОТКРЫТИИ МЕНЮ ФЕРМЫ
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if not btn.callback_data: continue
                btn_text = btn.text.lower()
                if "снять деньги" in btn_text or "собрать деньги" in btn_text or "farm_claim" in btn.callback_data.lower():
                    try:
                        print(f"💰 [Аккаунт {acc_id}] Обнаружена кнопка баланса! Снимаю деньги с фермы...", flush=True)
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                    except: pass

    if not message.text: return
    text = message.text.lower()

    if "вы сможете выбить карту еще раз через" in text:
        hours_match = re.search(r'(\d+)\s*ч', text)
        minutes_match = re.search(r'(\d+)\s*мин', text)
        seconds_match = re.search(r'(\d+)\s*сек', text)
        hours = int(hours_match.group(1)) if hours_match else 0
        minutes = int(minutes_match.group(1)) if minutes_match else 0
        seconds = int(seconds_match.group(1)) if seconds_match else 0
        total = (hours * 3600) + (minutes * 60) + seconds + 60 
        if total < 180: total = 180
        client.card_timer_override = total
        return

    if "вам пришел запрос на ремонт" in text or "запрос на ремонт" in text:
        if has_button(message, "принять заказ"):
            await click(client, message, "принять заказ")
            return

    if not AUTO_TRADE_ENABLED: return

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
                print(f"✅ [Твинк {acc_id}] Обмен принят. Запуск парсинга слотов...", flush=True)
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

    # ТРИГГЕР ЛУП ТЕПЕРЬ ОПРАШИВАЕТ ИМЕННО КОМАНДУ ТМАЙНИНГ ДЛЯ ВЫЗОВА ФЕРМЫ
    asyncio.create_task(farm_trigger_loop(client))

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

async def farm_trigger_loop(client):
    while True:
        try:
            # Раз в 65 минут отправляем команду «тмайнинг» (как на скриншоте 1873.jpg), 
            # чтобы отобразить меню с кнопкой «Снять деньги с фермы»
            await client.send_message(bot_chat, "тмайнинг")
        except: pass
        await asyncio.sleep(3900)

def get_msg_handler(acc_id):
    return lambda c, m: asyncio.create_task(process_bot_logic(c, m, acc_id))

def get_edit_handler(acc_id):
    return lambda c, m: asyncio.create_task(process_bot_logic(c, m, acc_id))

async def start_pyrogram_clients():
    global clients
    print("🛠 Запуск клиентов Pyrogram...", flush=True)

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
                print(f"👑 ОСНОВА запущена: @{me.username}", flush=True)
                asyncio.create_task(basis_sync_loop(c))
            else:
                print(f"✅ Аккаунт {acc_id} запущен: @{me.username}", flush=True)

            c.add_handler(handlers.MessageHandler(get_msg_handler(acc_id), filters.chat(bot_chat)), group=0)
            c.add_handler(handlers.EditedMessageHandler(get_edit_handler(acc_id), filters.chat(bot_chat)), group=0)
            
            asyncio.create_task(bg_tasks(c, acc_id))
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {i+1}: {e}", flush=True)
    print("🚀 Все юзерботы успешно запущены!", flush=True)

def run_async_loop():
    loop = asyncio.new_event_
