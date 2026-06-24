# -*- coding: utf-8 -*-
import os, re, asyncio, datetime, threading
from flask import Flask
from pyrogram import Client, handlers, filters, raw

app = Flask(__name__)
@app.route('/')
def health(): return "Ready and Running", 200
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()

API_ID, API_HASH = int(os.environ["API_ID"]), os.environ["API_HASH"]
SESSIONS = [os.environ.get(f"SESSION_{i}") for i in range(1, 6)]
bot_chat, iris_bot_chat = "phonegetcardsbot", "iris_moon_bot"
clients, twink_finished_event, AUTO_TRADE_ENABLED = [], asyncio.Event(), True
ACC_MACROS = {"1": "boymorale", "2": "tintedwindow", "3": "cutemald", "4": "dennyom", "5": "kuznecovvb"}

async def click(client, message, keyword: str) -> bool:
    if not message or not message.reply_markup: return False
    for row in message.reply_markup.inline_keyboard:
        for btn in row:
            if keyword.lower() in btn.text.lower() or keyword.lower() in (btn.callback_data or "").lower():
                if btn.callback_data:
                    try: await client.request_callback_answer(message.chat.id, message.id, btn.callback_data, timeout=2)
                    except: pass
                    return True
    return False

def has_button(message, keyword: str) -> bool:
    if not message or not message.reply_markup: return False
    return any(keyword.lower() in b.text.lower() or keyword.lower() in (b.callback_data or "").lower() for r in message.reply_markup.inline_keyboard for b in r)

async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Фоновый автосбор НАЧАТ С НУЛЯ.", flush=True)
    client.trade_counter, client.dynamic_limit = 0, 10
    working_phones_depleted, empty_rarities = False, set()
    last_clicked_rarity, last_menu_state = None, None

    for tick in range(80):
        try:
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=1):
                msg = m; break
            if not msg or not msg.reply_markup: raise asyncio.TimeoutError
            text = msg.text.lower() if msg.text else ""

            if client.trade_counter >= client.dynamic_limit or "занято слотов" in text:
                if has_button(msg, "готов"):
                    print(f"⚡ [Твинк {acc_id}] Трейд заполнен ({client.trade_counter}). Готов!", flush=True)
                    await click(client, msg, "готов"); twink_finished_event.set(); client.collecting = False; return
                if "готовность: ✅" in text or "✅" in text:
                    twink_finished_event.set(); client.collecting = False; return
                if has_button(msg, "назад") or has_button(msg, "вернуться назад"):
                    await click(client, msg, "назад"); await asyncio.sleep(1.0)
                continue

            all_btns = [b for r in msg.reply_markup.inline_keyboard for b in r if b.callback_data]
            act_btns = [b for b in all_btns if not any(x in b.text.lower() or x in b.callback_data.lower() for x in ["назад", "back", "меню", "отмена", "готов"])]

            if last_menu_state == "rarity" and next((b for b in act_btns if "рабоч" in b.text.lower()), None) and last_clicked_rarity:
                print(f"🚫 [Твинк {acc_id}] Бот сбросил назад! Редкость '{last_clicked_rarity}' в ЧС.", flush=True)
                empty_rarities.add(last_clicked_rarity); last_clicked_rarity = None

            single_btn = next((b for b in act_btns if "1 шт" in b.text.lower() or "single" in b.callback_data.lower()), None)
            if single_btn:
                client.trade_counter += 1; last_menu_state = "model_select"
                print(f"📦 [Твинк {acc_id}] Добавляю телефон [{client.trade_counter}/{client.dynamic_limit}]", flush=True)
                await client.request_callback_answer(msg.chat.id, msg.id, single_btn.callback_data, timeout=2)
                await asyncio.sleep(1.5); continue

            if act_btns and not any(any(x in b.text.lower() for x in ["рабоч", "сломан", "обычн", "редк", "мистич", "легенд"]) for b in act_btns):
                print(f"💎 [Твинк {acc_id}] Выбираю модель телефона: [{act_btns[0].text}]", flush=True)
                last_menu_state = "model_list"
                await client.request_callback_answer(msg.chat.id, msg.id, act_btns[0].callback_data, timeout=2)
                await asyncio.sleep(1.5); continue

            rarity_btns = [b for b in act_btns if any(x in b.text.lower() for x in ["обычн", "редк", "мистич", "легенд"])]
            if rarity_btns:
                avail = [b for b in rarity_btns if b.text.lower() not in empty_rarities]
                if not avail:
                    print(f"⚠️ [Твинк {acc_id}] Пустая категория. Назад.", flush=True)
                    await click(client, msg, "назад"); working_phones_depleted, last_menu_state = True, "rarity_empty"
                    await asyncio.sleep(1.5); continue
                tgt = next((b for b in avail if any(x in b.text.lower() for x in ["мистич", "редк", "легенд"])), avail[0])
                last_clicked_rarity, last_menu_state = tgt.text.lower(), "rarity"
                print(f"🔮 [Твинк {acc_id}] Выбираю редкость: [{tgt.text}]", flush=True)
                await client.request_callback_answer(msg.chat.id, msg.id, tgt.callback_data, timeout=2)
                await asyncio.sleep(1.5); continue

            w_btn, b_btn = next((b for b in act_btns if "рабоч" in b.text.lower()), None), next((b for b in act_btns if "сломан" in b.text.lower()), None)
            if w_btn or b_btn:
                if working_phones_depleted and b_btn: tgt, client.dynamic_limit = b_btn, 5
                elif w_btn: tgt, client.dynamic_limit = w_btn, 10
                else: tgt = b_btn or w_btn
                last_menu_state = "state"
                print(f"📱 [Твинк {acc_id}] Клик по состоянию: '{tgt.text}'", flush=True)
                try:
                    res = await client.request_callback_answer(msg.chat.id, msg.id, tgt.callback_data, timeout=2)
                    if res and hasattr(res, 'message') and any(x in res.message.lower() for x in ["нет", "доступных", "пусто"]):
                        if tgt == w_btn: working_phones_depleted = True
                except: pass
                await asyncio.sleep(1.5); continue

            add_btn = next((b for b in [b for r in msg.reply_markup.inline_keyboard for b in r] if "добавить телефон" in b.text.lower() or "add_phone" in (b.callback_data or "").lower()), None)
            if add_btn:
                last_menu_state = "trade_main"
                print(f"➕ [Твинк {acc_id}] Нажимаю 'Добавить телефон'", flush=True)
                await client.request_callback_answer(msg.chat.id, msg.id, add_btn.callback_data, timeout=1.2)
                await asyncio.sleep(1.2); continue
        except: pass
        await asyncio.sleep(0.5)
    client.collecting = False

async def basis_sync_loop(basis_client):
    while True:
        await twink_finished_event.wait()
        if not AUTO_TRADE_ENABLED: twink_finished_event.clear(); await asyncio.sleep(1); continue
        print("🔗 [СИНХРОНИЗАЦИЯ] Твинк закончил сбор. Основа прожимает готовность...", flush=True)
        for _ in range(5):
            try:
                msg = None
                async for m in basis_client.get_chat_history(bot_chat, limit=1): msg = m; break
                if msg:
                    if has_button(msg, "готов"): await click(basis_client, msg, "готов"); break
                    for r in (msg.reply_markup.inline_keyboard if msg.reply_markup else []):
                        for b in r:
                            if any(x in b.text.lower() for x in ["назад", "вернуться"]):
                                await basis_client.request_callback_answer(msg.chat.id, msg.id, b.callback_data, timeout=1); break
            except: pass
            await asyncio.sleep(0.5)
        twink_finished_event.clear()

async def process_bot_logic(client, message, acc_id):
    if not message: return
    if not hasattr(client, "collecting"): client.collecting = False
    if message.reply_markup:
        for r in message.reply_markup.inline_keyboard:
            for b in r:
                if b.callback_data and (any(x in b.text.lower() for x in ["собрать деньги", "собрать прибыль", "забрать", "забрать✅", "снять деньги"]) or any(x in b.callback_data.lower() for x in ["farm_claim", "reward"])):
                    try:
                        print(f"💰 [Аккаунт {acc_id}] Сбор прибыли/награды [{b.text}]", flush=True)
                        await client.request_callback_answer(message.chat.id, message.id, b.callback_data, timeout=3)
                    except: pass
    if not message.text: return
    text = message.text.lower()

    if "вы сможете выбить карту еще раз через" in text:
        m = [int(x) for x in re.findall(r'(\d+)\s*(?:ч|мин|сек)', text)]
        client.card_timer_override = max(180, sum(x * y for x, y in zip(m, [3600, 60, 1][:len(m)])) + 60)
        return

    if ("вам пришел запрос на ремонт" in text or "запрос на ремонт" in text) and has_button(message, "принять заказ"):
        await click(client, message, "принять заказ"); return

    if not AUTO_TRADE_ENABLED: return
    if has_button(message, "подтвердить") or has_button(message, "trade_confirm") or "подтвердите обмен" in text or "подтвердите" in text:
        await click(client, message, "trade_confirm"); await click(client, message, "подтвердить"); return

    if "предложение обмена" in text or "пришло предложение" in text:
        if "ваше предложение обмена отправлено" in text: return
        if await click(client, message, "trade_accept") or await click(client, message, "принять"):
            twink_finished_event.clear()
            if acc_id != 2 and not client.collecting:
                print(f"✅ [Твинк {acc_id}] Трейд принят. Запуск автосбора.", flush=True)
                client.collecting = True; asyncio.create_task(twink_collect_logic(client, acc_id))

async def handle_my_messages(client, message):
    global AUTO_TRADE_ENABLED
    if not message.text: return
    parts = message.text.split()
    if not parts: return
    cmd = parts[0].lower().strip()

    if cmd == ".ping":
        try: await message.edit("🚀 Юзербот активен!")
        except: pass
    elif cmd == ".at":
        AUTO_TRADE_ENABLED = not AUTO_TRADE_ENABLED
        try: await message.edit(f"🤖 **Автотрейд сейчас:** {'✅ ВКЛЮЧЕН' if AUTO_TRADE_ENABLED else '❌ ВЫКЛЮЧЕН'}"); await asyncio.sleep(3); await message.delete()
        except: pass
    elif cmd in [".trade", ".t", ".т"]:
        target = None
        if len(parts) == 2 and parts[1] in ACC_MACROS: target = ACC_MACROS[parts[1]]
        elif message.reply_to_message and message.reply_to_message.from_user:
            target = message.reply_to_message.from_user.username or str(message.reply_to_message.from_user.id)
        elif len(parts) >= 2: target = parts[1].replace("@", "").strip()
        if not target: return
        bot_cmd = f"/trade {target}" if target.isdigit() else f"/trade @{target}"
        try:
            await client.send_message(bot_chat, bot_cmd)
            print(f"➡️ [Команда] Запрос на трейд: {bot_cmd}", flush=True)
        except Exception as e: print(f"⚠️ Ошибка отправки команды: {e}", flush=True)
        try: await message.delete()
        except: pass

async def card_timer_loop(client, acc_id):
    await asyncio.sleep(5)
    try: await client.send_message(bot_chat, "ткарточка")
    except: pass
    while True:
        try:
            if client.card_timer_override and client.card_timer_override > 0:
                await asyncio.sleep(client.card_timer_override); client.card_timer_override = None
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
                continue
            msk = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            if msk.minute == 0 and msk.hour % 2 == 0:
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
        except: pass
        await asyncio.sleep(30)

async def bg_tasks(client, acc_id):
    asyncio.create_task(card_timer_loop(client, acc_id)); await asyncio.sleep(8)
    try: await client.send_message(bot_chat, "тмайнинг")
    except: pass
    if acc_id in [1, 2]:
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass
    rc_today, c_today, iris_timer = False, False, 0
    while True:
        try:
            msk = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            if msk.hour == 1 and msk.minute == 0 and not rc_today:
                print(f"🎁 [Аккаунт {acc_id}] Отправка: 'ежедневная награда'", flush=True)
                await client.send_message(bot_chat, "ежедневная награда"); rc_today = True
            elif msk.hour == 1 and msk.minute == 2: rc_today = False

            if msk.hour == 0 and msk.minute == 10 and not c_today:
                print(f"⛏ [Аккаунт {acc_id}] Отправка: 'тмайнинг'", flush=True)
                await client.send_message(bot_chat, "тмайнинг"); c_today = True
            elif msk.hour == 0 and msk.minute == 11: c_today = False

            if acc_id in [1, 2]:
                iris_timer += 1
                if iris_timer >= 240:
                    try: await client.send_message(iris_bot_chat, "фарма")
                    except: pass
                    iris_timer = 0
        except Exception as e: print(f"⚠️ Ошибка в bg_tasks {acc_id}: {e}", flush=True)
        await asyncio.sleep(60)

async def start_bot():
    global clients
    print("🛠 Запуск распределенной фермы юзерботов...", flush=True)
    for i, session in enumerate(SESSIONS):
        if not session or not session.strip(): continue
        acc_id = i + 1
        c = Client(name=f"session_active_{acc_id}", api_id=API_ID, api_hash=API_HASH, session_string=session.strip(), in_memory=True)
        c.add_handler(handlers.MessageHandler(lambda cl, msg, cur=c: cl.loop.create_task(handle_my_messages(cur, msg)), filters.me), group=1)
        try:
            await c.start(); await c.invoke(raw.functions.updates.GetState()); clients.append(c)
            me = await c.get_me(); c.me_id, c.card_timer_override, c.collecting = me.id, None, False
            print(f"{'👑 ГЛАВНАЯ ОСНОВА' if acc_id == 2 else '✅ Аккаунт'} {acc_id} запущен: @{me.username}", flush=True)
            if acc_id == 2: asyncio.create_task(basis_sync_loop(c))
            
            cb = lambda cl, msg, cur=c, cid=acc_id: cl.loop.create_task(process_bot_logic(cur, msg, cid))
            c.add_handler(handlers.MessageHandler(cb, filters.chat(bot_chat)), group=0)
            c.add_handler(handlers.EditedMessageHandler(cb, filters.chat(bot_chat)), group=0)
            asyncio.create_task(bg_tasks(c, acc_id))
        except Exception as e: print(f"⚠️ Ошибка запуска аккаунта {acc_id}: {e}", flush=True)
    print("🚀 Все аккаунты успешно запущены и готовы к работе!", flush=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
                
