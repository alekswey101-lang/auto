# -*- coding: utf-8 -*-
import os
import re
import asyncio
import datetime
from aiohttp import web
from pyrogram import Client, handlers, filters
from pyrogram import raw
from pyrogram.errors import PeerIdInvalid, FloodWait

PORT = int(os.environ.get("PORT", 10000))

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

# --- ИСПРАВЛЕННЫЙ УНИВЕРСАЛЬНЫЙ RAW КЛИК (ИЩЕТ ПО ТЕКСТУ И DATA) ---
async def click(client, message, keyword: str) -> bool:
    try:
        if not message or not message.reply_markup:
            return False
        
        peer = await client.resolve_peer(message.chat.id)
        
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                t_low = btn.text.lower().replace("✅", "").replace("❌", "").strip()
                d_low = (btn.callback_data or "").lower()
                
                # Проверяем вхождение ключевого слова как в текст кнопки, так и в её callback_data
                if keyword.lower() in t_low or keyword.lower() in d_low:
                    if btn.callback_data:
                        await client.invoke(
                            raw.functions.messages.GetBotCallbackAnswer(
                                peer=peer,
                                msg_id=message.id,
                                data=btn.callback_data,
                                game=False
                            )
                        )
                        return True
    except Exception as e:
        print(f"⚠️ Ошибка при клике на '{keyword}': {e}", flush=True)
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

# --- АВТОСБОР ---
async def twink_collect_logic(client, acc_id):
    print(f"⚡ [Твинк {acc_id}] Начало автосбора.", flush=True)
    empty_rarities = set()  
    current_mode = "working" 

    for tick in range(100):
        try:
            await asyncio.sleep(1.5) 
            
            msg = None
            async for m in client.get_chat_history(bot_chat, limit=5):
                m_text = m.text.lower() if m.text else ""
                if m.reply_markup and any(x in m_text or has_button(m, x) for x in ["выберите", "обмен", "добавить", "категорию", "редкость", "готов"]):
                    msg = m
                    break
            
            if not msg or not msg.reply_markup:
                continue

            text = msg.text.lower() if msg.text else ""

            if "готовность: ✅" in text and not has_button(msg, "добавить телефон"):
                print(f"🎉 [Твинк {acc_id}] Трейд успешно укомплектован!", flush=True)
                twink_finished_event.set()
                client.collecting = False
                return

            slots_full = "занято слотов" in text or "слотов: 10/10" in text or "слотов: 5/5" in text
            if slots_full and has_button(msg, "готов"):
                print(f"⚡ [Твинк {acc_id}] Слот-лимит забит. Завершаем сбор.", flush=True)
                await click(client, msg, "готов")
                twink_finished_event.set()
                client.collecting = False 
                return

            all_buttons = []
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        all_buttons.append(btn)

            action_buttons = []
            for b in all_buttons:
                b_text = b.text.lower()
                if any(x in b_text for x in ["назад", "back", "меню", "отмена", "готов", "вернуться"]):
                    if not any(cat in b_text for cat in ["рабоч", "сломан"]):
                        continue
                action_buttons.append(b)

            # ЭКРАН: ВЫБОР КАТЕГОРИИ (РАБОЧИЙ / СЛОМАННЫЙ)
            if "выберите категорию" in text:
                work_btn = next((b for b in all_buttons if "рабоч" in b.text.lower()), None)
                broken_btn = next((b for b in all_buttons if "сломан" in b.text.lower()), None)

                target_btn = None
                if current_mode == "broken" and broken_btn:
                    target_btn = broken_btn
                elif work_btn:
                    target_btn = work_btn
                else:
                    target_btn = broken_btn or work_btn

                if target_btn:
                    print(f"🛠 [Твинк {acc_id}] RAW-клик по категории: {target_btn.text}", flush=True)
                    await click(client, msg, target_btn.text)
                else:
                    print(f"⚠️ [Твинк {acc_id}] Категории не найдены, принудительный клик по первой кнопке", flush=True)
                    await click(client, msg, all_buttons[0].text)
                continue

            # ЭКРАН: ВЫБОР КОНКРЕТНЫХ МОДЕЛЕЙ ТЕЛЕФОНОВ
            elif "выберите телефон" in text:
                if "нет доступных" in text or "отсутствуют" in text or not action_buttons:
                    print(f"📭 [Твинк {acc_id}] В этой редкости пусто. Выходим.", flush=True)
                    await click(client, msg, "назад")
                    await asyncio.sleep(1.0)
                    continue

                if has_button(msg, "быстрый выбор:"):
                    fast_mode_btn = next((b for b in all_buttons if "быстрый выбор:" in b.text.lower()), None)
                    if fast_mode_btn and "выкл" in fast_mode_btn.text.lower():
                        await click(client, msg, fast_mode_btn.text)
                        await asyncio.sleep(0.5)
                        continue

                    phone_buttons = [b for b in action_buttons if "быстрый выбор" not in b.text.lower() and "добавить" not in b.text.lower()]
                    current_selected = sum(1 for b in phone_buttons if "✅" in b.text)
                    available_phones = [b for b in phone_buttons if "✅" not in b.text]

                    if available_phones and current_selected < 10 and not slots_full:
                        print(f"📱 [Твинк {acc_id}] Выбираю телефон: {available_phones[0].text}", flush=True)
                        await click(client, msg, available_phones[0].text)
                        continue
                    else:
                        add_selected_btn = next((b for b in all_buttons if "добавить выбранное" in b.text.lower()), None)
                        if add_selected_btn:
                            print(f"📥 [Твинк {acc_id}] Подтверждаю добавление выбранных телефонов", flush=True)
                            await click(client, msg, add_selected_btn.text)
                            await asyncio.sleep(1.0)
                            continue
                else:
                    if action_buttons and not slots_full:
                        print(f"📱 [Твинк {acc_id}] Выбираю телефон (без быстрого выбора): {action_buttons[0].text}", flush=True)
                        await click(client, msg, action_buttons[0].text)
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        await click(client, msg, "назад")
                        await asyncio.sleep(1.0)
                        continue

            # ЭКРАН: ВЫБОР РЕДКОСТЕЙ
            elif "выберите редкость" in text:
                rarity_buttons = [b for b in action_buttons if any(x in b.text.lower() for x in ["обычн", "редк", "мистич", "легенд", "аркан", "платин", "артеф", "ширпотреб", "хроматич"])]
                available_rarities = [b for b in rarity_buttons if b.text.lower().replace("✅","").replace("❌","").strip() not in empty_rarities]

                if not available_rarities:
                    print(f"🔄 [Твинк {acc_id}] Редкости кончились. Смена режима с {current_mode} на сломанные.", flush=True)
                    empty_rarities.clear()
                    current_mode = "broken"
                    await click(client, msg, "назад")
                    await asyncio.sleep(1.0)
                    continue

                target_rarity = available_rarities[0]
                rarity_name = target_rarity.text.lower().replace("✅","").replace("❌","").strip()
                empty_rarities.add(rarity_name) 
                print(f"💎 [Твинк {acc_id}] Выбираю редкость: {target_rarity.text}", flush=True)
                await click(client, msg, target_rarity.text)
                continue

            # КОРНЕВОЙ ЭКРАН
            else:
                add_btn = next((b for b in all_buttons if "добавить телефон" in b.text.lower() or "add_phone" in b.callback_data.lower()), None)
                if add_btn:
                    print(f"➕ [Твинк {acc_id}] Нажимаю Добавить телефон", flush=True)
                    await click(client, msg, add_btn.text)
                    continue
                if has_button(msg, "готов"):
                    await click(client, msg, "готов")
                    twink_finished_event.set()
                    client.collecting = False
                    return

        except Exception as e:
            print(f"⚠️ Ошибка алгоритма сбора: {e}", flush=True)
            await asyncio.sleep(1.0)
            
    client.collecting = False

async def basis_sync_loop(basis_client):
    while True:
        await twink_finished_event.wait()
        if not AUTO_TRADE_ENABLED:
            twink_finished_event.clear()
            await asyncio.sleep(1)
            continue
        print("🔗 [СИНХРОНИЗАЦИЯ] Твинк закончил. Основа подтверждает трейд...", flush=True)
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
                                    await click(basis_client, msg, btn.text)
                                    break
            except: pass
            await asyncio.sleep(0.5)
        twink_finished_event.clear()

async def process_bot_logic(client, message, acc_id):
    try:
        if not message: return
        if not hasattr(client, "collecting"): client.collecting = False

        if message.reply_markup:
            for row in message.reply_markup.inline_keyboard:
                for btn in row:
                    if not btn.callback_data: continue
                    btn_text = btn.text.lower()
                    if "снять деньги" in btn_text or "собрать деньги" in btn_text or "farm_claim" in btn.callback_data.lower():
                        try:
                            print(f"💰 [Аккаунт {acc_id}] Снимаю деньги с фермы через RAW-клик!", flush=True)
                            await click(client, message, btn.text)
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
                if has_button(message, "trade_accept") or has_button(message, "принять"):
                    if client.collecting: return
                    print(f"✅ [Твинк {acc_id}] Принимаю обмен...", flush=True)
                    await click(client, message, "trade_accept")
                    await click(client, message, "принять")
                    twink_finished_event.clear() 
                    client.collecting = True
                    client.loop.create_task(twink_collect_logic(client, acc_id))
                return

        if acc_id == 2:
            if "предложение обмена" in text or "пришло предложение" in text:
                if "ваше предложение обмена отправлено" in text: return
                if has_button(message, "trade_accept") or has_button(message, "принять"):
                    await click(client, message, "trade_accept")
                    await click(client, message, "принять")
                    twink_finished_event.clear()
                return
    except Exception as e:
        print(f"Ошибка логики бота: {e}")

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
    while True:
        if getattr(client, "collecting", False):
            await asyncio.sleep(5)
            continue
        try: 
            await client.send_message(bot_chat, "ткарточка")
        except: pass
        
        try:
            if client.card_timer_override is not None and client.card_timer_override > 0:
                await asyncio.sleep(client.card_timer_override)
                client.card_timer_override = None
                continue
            utc_now = datetime.datetime.utcnow()
            msk_now = utc_now + datetime.timedelta(hours=3)
            if msk_now.minute == 0 and msk_now.hour % 2 == 0:
                try: await client.send_message(bot_chat, "ткарточка")
                except: pass
        except: pass
        await asyncio.sleep(30)

async def bg_tasks(client, acc_id):
    client.loop.create_task(card_timer_loop(client, acc_id))
    await asyncio.sleep(8)
    
    if not getattr(client, "collecting", False):
        try: await client.send_message(bot_chat, "тмайнинг")
        except: pass

    if acc_id in [1, 2] and not getattr(client, "collecting", False):
        try: await client.send_message(iris_bot_chat, "фарма")
        except: pass

    client.loop.create_task(farm_trigger_loop(client))

    claimed_today = False
    reward_claimed_today = False
    iris_timer = 0

    while True:
        try:
            if getattr(client, "collecting", False):
                await asyncio.sleep(10)
                continue

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
        await asyncio.sleep(3900)
        if getattr(client, "collecting", False):
            continue
        try:
            await client.send_message(bot_chat, "тмайнинг")
        except: pass

async def start_pyrogram_clients(loop):
    global clients
    print("🛠 Инициализация клиентов Pyrogram...", flush=True)

    for i, session in enumerate(SESSIONS):
        if not session or session.strip() == "": continue
        c = Client(
            name=f"session_active_{i+1}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session.strip(),
            in_memory=True,
        )
        c.loop = loop
        c.add_handler(handlers.MessageHandler(handle_my_messages, filters.me))

        try:
            await c.start()
            clients.append(c)
            me = await c.get_me()
            c.me_id = me.id
            c.card_timer_override = None
            c.collecting = False
            
            acc_id = i + 1
            if acc_id == 2:
                print(f"👑 ОСНОВА запущена: @{me.username}", flush=True)
                loop.create_task(basis_sync_loop(c))
            else:
                print(f"✅ Аккаунт {acc_id} запущен: @{me.username}", flush=True)

            c.add_handler(handlers.MessageHandler(
                lambda client, message, a_id=acc_id: client.loop.create_task(process_bot_logic(client, message, a_id)), 
                filters.chat(bot_chat)
            ), group=0)
            
            c.add_handler(handlers.EditedMessageHandler(
                lambda client, message, a_id=acc_id: client.loop.create_task(process_bot_logic(client, message, a_id)), 
                filters.chat(bot_chat)
            ), group=0)
            
            loop.create_task(bg_tasks(c, acc_id))
        except PeerIdInvalid:
            pass
        except Exception as e:
            print(f"⚠️ Ошибка запуска аккаунта {i+1}: {e}", flush=True)
    print("🚀 Все активные аккаунты успешно подключены к Telegram!", flush=True)

async def handle_http(request):
    return web.Response(text="Ready and Running", status=200)

async def run_web_server():
    server = web.Application()
    server.router.add_get('/', handle_http)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 Асинхронный веб-сервер успешно запущен на порту {PORT}", flush=True)

async def main():
    loop = asyncio.get_running_loop()
    await run_web_server()
    await start_pyrogram_clients(loop)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🤖 Скрипт остановлен.")
