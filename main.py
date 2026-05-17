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
    try:
        if not message.reply_markup:
            return False
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                    print(f"[КЛИК] Нажимаю кнопку: '{btn.text}'", flush=True)
                    try:
                        await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                        return True
                    except:
                        return True
    except Exception as e:
        print(f"❌ Ошибка click(): {e}", flush=True)
    return False

# --- УМНЫЙ ТУРБО-ДВИЖОК КЛИКОВ ---
async def execute_menu_step(client, step_name, keywords, pick_first, last_fp):
    await asyncio.sleep(0.35)
    
    for attempt in range(8):
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                if not msg.reply_markup:
                    continue

                fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
                
                if "Добавить телефон" not in step_name:
                    if last_fp and fp == last_fp:
                        await asyncio.sleep(0.2)
                        continue

                # Если подзависли в подменю — сбрасываем назад
                if attempt == 4 and pick_first:
                    print(f"⚠️ [{step_name}] Меню не отвечает. Нажимаю 'Назад'...", flush=True)
                    for row in msg.reply_markup.inline_keyboard:
                        for btn in row:
                            if "назад" in btn.text.lower() or "back" in (btn.callback_data or "").lower():
                                try: await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=2)
                                except: pass
                                return False, fp

                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        text_lower = btn.text.lower().strip()
                        data_lower = (btn.callback_data or "").lower().strip()

                        if pick_first:
                            if any(x in text_lower or x in data_lower for x in ["назад", "back", "изменить", "отмена", "подтвердить", "главное"]):
                                continue
                            try: await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=2)
                            except: pass
                            return True, fp
                        else:
                            for kw in keywords:
                                kw_l = kw.lower().strip()
                                if kw_l in text_lower or kw_l in data_lower:
                                    try: await client.request_callback_answer(msg.chat.id, msg.id, btn.callback_data, timeout=2)
                                    except: pass
                                    return True, fp
        except:
            pass
        await asyncio.sleep(0.2)
            
    print(f"🛑 [{step_name}] Тайм-аут шага.", flush=True)
    return False, last_fp

# --- УЛУЧШЕННЫЙ СБОРЩИК: КОНТРОЛЬ СЛОТОВ БОТА ---
async def receiver_trade_logic(client, acc_id):
    print(f"⚡ [Акк {acc_id}] Запуск умного сборщика слотов...", flush=True)
    
    # Даем скрипту право сделать до 25 попыток добавления, пока слоты РЕАЛЬНО не забьются до 10/10
    for loop_index in range(1, 26):
        
        # ПРОВЕРКА СЛОТОВ ПЕРЕД КАЖДЫМ КРУГОМ
        slots_full = False
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                msg_text = (msg.text or "").lower()
                # Если бот пишет, что слоты забиты 10/10, останавливаем заполнение
                if "10/10" in msg_text and "слот" in msg_text:
                    print(f"🎯 [Акк {acc_id}] Ботом зафиксировано заполнение слотов 10/10! Завершаю сборку.", flush=True)
                    slots_full = True
                    break
        except:
            pass
            
        if slots_full:
            break

        print(f"📱 [Акк {acc_id}] Попытка забить слот. Круг {loop_index}...", flush=True)
        last_fp = ""

        # Шаг 1: Добавить телефон
        res, last_fp = await execute_menu_step(client, f"Добавить телефон (круг {loop_index})", ["добавить телефон", "trade_add_phone"], False, last_fp)
        if not res: 
            # Если кнопки "Добавить телефон" больше нет на экране, значит слоты физически кончились
            print(f"ℹ️ [Акк {acc_id}] Кнопка 'Добавить телефон' исчезла. Слоты полные.", flush=True)
            break

        # Шаг 2: Выбор состояния
        res, last_fp = await execute_menu_step(client, f"Выбор Состояния", [], True, last_fp)
        if not res: await asyncio.sleep(0.5); continue

        # Шаг 3: Выбор редкости
        res, last_fp = await execute_menu_step(client, f"Выбор Редкости", [], True, last_fp)
        if not res: await asyncio.sleep(0.5); continue

        # Шаг 4: Выбор модели
        res, last_fp = await execute_menu_step(client, f"Выбор Модели", [], True, last_fp)
        if not res: await asyncio.sleep(0.5); continue

        # Шаг 5: Выбор количества (1 шт)
        res, last_fp = await execute_menu_step(client, f"Количество 1шт", ["добавить 1 шт.", "trade_add_single"], False, last_fp)
        if not res: await asyncio.sleep(0.5); continue
        
        await asyncio.sleep(0.4)

    # Шаг 6: Финальное подтверждение инвентаря
    print(f"⚖️ [Акк {acc_id}] Сборка завершена. Нажимаю Подтвердить...", flush=True)
    res, last_fp = await execute_menu_step(client, "Финал Получателя", ["подтвердить", "trade_confirm"], False, "")
    
    # Шаг 7: Автоматический клик по кнопке Готов
    print(f"🚀 [Акк {acc_id}] Предметы зафиксированы. Жду 1.5 сек и жму 'Готов'...", flush=True)
    await asyncio.sleep(1.5)
    try:
        async for msg in client.get_chat_history(bot_chat, limit=1):
            await click(client, msg, "готов")
    except Exception as e:
        print(f"❌ Ошибка авто-готовности: {e}", flush=True)

# --- ОБРАБОТЧИК ---
async def process_bot_logic(client, message, acc_id):
    if not message or not message.text:
        return

    text = message.text.lower()

    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text:
            return

        print(f"🤝 [Акк {acc_id}] Принимаю трейд...", flush=True)
        await click(client, message, "принять")
        await asyncio.sleep(0.8) 
        asyncio.create_task(receiver_trade_logic(client, acc_id))
        return

    if ("готовность:" in text and "❌" in text and "✅" in text) or "занято слотов: 10/10" in text:
        print(f"⚡ [Акк {acc_id}] Обнаружено заполнение слотов (10/10)! Нажимаю 'Готов'...", flush=True)
        await delay(0.2, 0.5)
        await click(client, message, "готов")
        return

    if "подтвердите обмен" in text or "подтвердите" in text:
        await delay(0.3, 0.6)
        await click(client, message, "подтвердить")
        return

# --- СКОРОСТНОЙ ПУЛИНГ ---
async def poll_bot_messages(client, acc_id):
    last_msg_id = 0
    last_buttons_fp = ""
    
    while True:
        try:
            async for msg in client.get_chat_history(bot_chat, limit=1):
                buttons_fp = ""
                if msg.reply_markup:
                    buttons_fp = "|".join([btn.text for row in msg.reply_markup.inline_keyboard for btn in row])
                
                if msg.id != last_msg_id or buttons_fp != last_buttons_fp:
                    last_msg_id = msg.id
                    last_buttons_fp = buttons_fp
                    await process_bot_logic(client, msg, acc_id)
                break
        except:
            pass
        await asyncio.sleep(0.5)

# --- ОТПРАВИТЕЛЬ ---
async def sender_confirm_logic(client, acc_id):
    # Увеличил время до 55 секунд на случай, если у тебя много дубликатов и скрипту придется делать много кругов
    print(f"⏳ [Акк {acc_id} - Отправитель] Жду 55 секунд до авто-подтверждения...", flush=True)
    await asyncio.sleep(55)
    print(f"✍️ [Акк {acc_id} - Отправитель] Подтверждаю...", flush=True)
    try:
        async for msg in client.get_chat_history(bot_chat, limit=1):
            await click(client, msg, "подтвердить")
    except Exception as e:
        print(f"❌ Ошибка отправителя: {e}", flush=True)

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
        try: await message.edit("🚀 **Юзербот онлайн!**")
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

        print(f"📣 [Акк {acc_id}] Запуск быстрого трейда на: {target}...", flush=True)
        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        await client.send_message(bot_chat, bot_cmd)
        asyncio.create_task(sender_confirm_logic(client, acc_id))

async def bg_tasks(client, acc_id):
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    while True:
        await asyncio.sleep(121 * 60)
        try: await client.send_message(bot_chat, "ткарточка")
        except: pass

async def start_bot():
    global clients
    print("🛠 Запуск Pyrofork фермы с контролем слотов (10/10)...", flush=True)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue
            
        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )
        
        c.add_handler(handlers.MessageHandler(handle_my_messages))
        
        try:
            await c.start()
            await c.invoke(raw.functions.updates.GetState())
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            async for _ in c.get_dialogs(limit=5): pass
            print(f"✅ Аккаунт {i+1} запущен: @{me.username}", flush=True)
            asyncio.create_task(bg_tasks(c, i+1))
            asyncio.create_task(poll_bot_messages(c, i+1))
        except Exception as e:
            print(f"⚠️ Ошибка аккаунта {i+1}: {e}", flush=True)

    print("🚀 Скрипт обновлен. Теперь он забивает строго 10/10 слотов независимо от дубликатов предметов!", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
