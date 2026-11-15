import asyncio

import random

import sqlite3

import time

from aiogram import Bot, Dispatcher, F, types

from aiogram.filters import Command

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery, BotCommand, InputMediaPhoto

 

# --- НАСТРОЙКИ ---

BOT_TOKEN = "9297074957:AAH1MatXEIEX3QI8m2uj0n9iLJGH1I72hDI"

ADMIN_ID = 6921885296  # Ваш числовой Telegram ID

COOLDOWN = 3 * 3600   # 3 часа в секундах

 

# В поле "photo" вставьте file_id картинки (отправьте фото боту в личку, чтобы узнать его код)

LEVELS = {

    1: {"name": "Наруто (Генин на минималках)", "need": 500, "reward": "Мишка (15 ⭐)", "photo": ""},

    2: {"name": "Танджиро (Угольный барон)", "need": 2000, "reward": "Кольцо (100 ⭐)", "photo": ""},

    3: {"name": "Годжо Сатору (Без повязки)", "need": 6000, "reward": "NFT Pet Snake", "photo": ""},

    4: {"name": "Итачи Учиха (Мастер яичницы)", "need": 10000, "reward": "NFT Input Key", "photo": ""},

    5: {"name": "Сейлор Мун (В поисках обеда)", "need": 15000, "reward": "NFT Moon Pendant", "photo": ""},

    6: {"name": "Аня Форджер (Агент Сумрак-младший)", "need": 22000, "reward": "NFT Spy Agaric", "photo": ""},

}

 

FARM_TEXTS = [

    "🍜 Герой плотно поел рамена в Ичираку и выдал +{gain}⚡!",

    "🧘‍♂️ Час медитации под водопадом (правда, он проспал) принесли +{gain}⚡!",

    "🔥 Сенсей наорал так громко, что чакра подскочила на +{gain}⚡!",

    "🍙 Нашёл в кармане вчерашний онигири и зарядился на +{gain}⚡!",

    "⚡ Вспомнил грустный флешбэк из детства и превозмог на +{gain}⚡!",

    "🐱 Погладил уличного кота и словил дзен на +{gain}⚡!",

    "💪 Сделал 100 отжиманий (ладно, 3 отжимания и 97 приседаний на диван): +{gain}⚡!"

]

 

WAIT_TEXTS = [

    "😴 Герой дрыхнет без задних ног! Потерпи ещё {h}ч {m}м.",

    "🍜 Он сейчас на обеде в Ичираку, не мешай! Возвращайся через {h}ч {m}м.",

    "🪫 Чакра на нуле, батарейка села. Зарядка закончится через {h}ч {m}м.",

    "🚽 Герой отошёл по важным делам шиноби. Будет через {h}ч {m}м.",

    "🎮 Он залип в приставку и отказывается тренироваться! Жди {h}ч {m}м."

]

 

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

admin_waiting_broadcast = set()

 

# --- БАЗА ДАННЫХ ---

db = sqlite3.connect("game.db")

cur = db.cursor()

 

cur.execute("""

CREATE TABLE IF NOT EXISTS users (

    user_id INTEGER PRIMARY KEY,

    username TEXT,

    level INTEGER DEFAULT 1,

    energy INTEGER DEFAULT 0,

    last_farm INTEGER DEFAULT 0,

    amulet_until INTEGER DEFAULT 0,

    stars_spent INTEGER DEFAULT 0

)

""")

 

cur.execute("""

CREATE TABLE IF NOT EXISTS claims (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    username TEXT,

    level INTEGER,

    reward TEXT,

    status TEXT DEFAULT 'pending'

)

""")

db.commit()

 

def get_user(user_id, username=""):

    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))

    user = cur.fetchone()

    if not user:

        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username or "Без_ника"))

        db.commit()

        return (user_id, username or "Без_ника", 1, 0, 0, 0, 0)

    if username and user != username:

        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))

        db.commit()

    return user

 

def main_keyboard(user_id, level, energy, need):

    buttons = []

    if level in LEVELS:

        if energy >= need:

            buttons.append([InlineKeyboardButton(text="🎁 ЗАБРАТЬ ПОДАРОК (Оставить заявку)", callback_data=f"claim_{user_id}")])

        else:

            buttons.append([InlineKeyboardButton(text="⚡ Впитать энергию", callback_data=f"farm_{user_id}")])

        buttons.append([InlineKeyboardButton(text="🛒 Лавка читера (Бусты за Stars)", callback_data=f"shop_{user_id}")])

    buttons.append([InlineKeyboardButton(text="🗺 Дорога славы (Все 10 уровней)", callback_data=f"levels_{user_id}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

 

def shop_keyboard(user_id):

    return InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text="🔮 Амулет удачи 48ч (50-150⚡) — 40 ⭐", callback_data=f"buy_amulet_{user_id}")],

        [InlineKeyboardButton(text="📦 Кейс с удачей (1-100⚡) — 25 ⭐", callback_data=f"buy_case_{user_id}")],

        [InlineKeyboardButton(text="⚡ Попытка прорыва уровня — 100 ⭐", callback_data=f"buy_skip_{user_id}")],

        [InlineKeyboardButton(text="⬅️ Вернуться к герою", callback_data=f"back_{user_id}")]

    ])

def get_card_text(user):

    _, uname, level, energy, last_farm, amulet_until, _ = user

    now = int(time.time())

   

    if level not in LEVELS:

        return (

            f"👤 Сенсей: <b>@{uname}</b>\n"

            f"🏆 <b>Уровень {level} из 10</b>\n\n"

            "🔒 Вы настолько мощный, что сломали игру! Новые аниме-легенды и жирные NFT уже рисуются в секретной лаборатории. Ждите обнову!"

        )

   

    lvl_data = LEVELS[level]

    amulet_status = "🔥 Включён на полную (50–150⚡)" if amulet_until > now else "💤 Спит (обычный режим 1–50⚡)"

   

    wait_time = (last_farm + COOLDOWN) - now

    if wait_time <= 0:

        timer_text = "🟢 <b>Герой выспался и готов качаться!</b>"

    else:

        hours = wait_time // 3600

        mins = (wait_time % 3600) // 60

        timer_text = f"⏳ <b>Перекур после тренировки:</b> ещё {hours}ч {mins}м"

 

    return (

        f"👤 Сенсей: <b>@{uname}</b>\n"

        f"🎴 <b>Уровень {level}/10: {lvl_data['name']}</b>\n"

        f"🎁 Приз за прокачку: <b>{lvl_data['reward']}</b>\n\n"

        f"⚡ Шкала чакры: <b>{energy} / {lvl_data['need']}</b>\n"

        f"🔮 Амулет удачи: {amulet_status}\n"

        f"{timer_text}"

    )

 

async def send_or_edit_card(target, user, is_edit=False):

    uid, _, lvl, energy, _, _, _ = user

    need = LEVELS[lvl]["need"] if lvl in LEVELS else 0

    photo_id = LEVELS[lvl]["photo"] if lvl in LEVELS else ""

    text = get_card_text(user)

    kb = main_keyboard(uid, lvl, energy, need)

 

    if not is_edit:

        if photo_id:

            await target.answer_photo(photo=photo_id, caption=text, parse_mode="HTML", reply_markup=kb)

        else:

            await target.answer(text=text, parse_mode="HTML", reply_markup=kb)

    else:

        if photo_id:

            if target.photo:

                await target.edit_media(media=InputMediaPhoto(media=photo_id, caption=text, parse_mode="HTML"), reply_markup=kb)

            else:

                await target.delete()

                await target.answer_photo(photo=photo_id, caption=text, parse_mode="HTML", reply_markup=kb)

        else:

            if target.photo:

                await target.delete()

                await target.answer(text=text, parse_mode="HTML", reply_markup=kb)

            else:

                await target.edit_text(text=text, parse_mode="HTML", reply_markup=kb)

 

async def edit_menu_safe(message: types.Message, text: str, kb: InlineKeyboardMarkup):

    if message.photo:

        await message.delete()

        await message.answer(text=text, parse_mode="HTML", reply_markup=kb)

    else:

        await message.edit_text(text=text, parse_mode="HTML", reply_markup=kb)

 

def check_owner(call: types.CallbackQuery, target_id: int):

    return call.from_user.id == target_id

 

@dp.message(Command("start"))

async def cmd_start(message: types.Message):

    user = get_user(message.from_user.id, message.from_user.username)

    welcome_text = (

        f"👋 <b>Йо, @{user}! Добро пожаловать в Аниме-Качалку!</b>\n\n"

        "Здесь ты станешь великим сенсеем и будешь вливать энергию в легендарных героев — от голодного Наруто до самой Ани Форджер.\n\n"

        "📜 <b>Как тут всё устроено:</b>\n"

        "1️⃣ Раз в 3 часа жми <b>«Впитать энергию»</b> — твой герой пойдёт тренироваться (или есть рамен) и принесёт от 1 до 50⚡.\n"

        "2️⃣ Заполнишь шкалу — забирай реальные <b>подарки Telegram и редкие NFT</b> прямо себе в профиль!\n"

        "3️⃣ Лень ждать? Загляни в <b>Лавку читера</b> за Звёздами, чтобы ускорить процесс.\n\n"

        "👇 <i>Вот твой первый подопечный, не дай ему заскучать!</i>"

    )

    await message.answer(welcome_text, parse_mode="HTML")

    await send_or_edit_card(message, user, is_edit=False)

 

@dp.message(Command("card"))

async def cmd_card(message: types.Message):

    user = get_user(message.from_user.id, message.from_user.username)

    await send_or_edit_card(message, user, is_edit=False)

 

@dp.message(Command("farm"))

async def cmd_farm_text(message: types.Message):

    user = get_user(message.from_user.id, message.from_user.username)

    uid, uname, level, energy, last_farm, amulet_until, _ = user

    now = int(time.time())

 

    if level not in LEVELS:

        return await message.reply("🔒 Все доступные герои уже на пике формы, ждите обновления!")

    if energy >= LEVELS[level]["need"]:

        return await message.reply("🎁 Шкала полная! Хватит качать, жми кнопку подарка в /card!")

    if now - last_farm < COOLDOWN:

        rem = (last_farm + COOLDOWN) - now

        msg = random.choice(WAIT_TEXTS).format(h=rem // 3600, m=(rem % 3600) // 60)

        return await message.reply(f"@{uname}, {msg}")

 

    gain = random.randint(50, 150) if amulet_until > now else random.randint(1, 50)

    new_energy = min(energy + gain, LEVELS[level]["need"])

 

    cur.execute("UPDATE users SET energy = ?, last_farm = ? WHERE user_id = ?", (new_energy, now, uid))

    db.commit()

 

    phrase = random.choice(FARM_TEXTS).format(gain=gain)

    await message.reply(f"👤 @{uname}: {phrase}\n📊 Прогресс: <b>{new_energy} / {LEVELS[level]['need']}⚡</b>", parse_mode="HTML")

 

@dp.message(Command("shop"))

async def cmd_shop_text(message: types.Message):

    uid = message.from_user.id

    get_user(uid, message.from_user.username)

    await message.answer(

        "🛒 <b>Лавка читера за Telegram Stars ⭐</b>\n\n"

        "🔮 <b>Амулет удачи (40 ⭐):</b> на 48 часов отменяет лень героя — выпадает строго от 50 до 150⚡!\n"

        "📦 <b>Кейс с удачей (25 ⭐):</b> кот в мешке с энергией! Внутри от 1 до 100⚡ без ожидания.\n"

        "⚡ <b>Попытка прорыва (100 ⭐):</b> секретная запрещённая техника! Может мгновенно закрыть весь уровень.",

        parse_mode="HTML",

        reply_markup=shop_keyboard(uid)

    )

 

@dp.message(Command("levels"))

async def cmd_levels_text(message: types.Message):

    text = "🗺 <b>Дорога славы (Все 10 уровней):</b>\n\n"

    for i in range(1, 11):

        if i in LEVELS:

            text += f"✅ <b>Ур. {i}:</b> {LEVELS[i]['name']} ({LEVELS[i]['need']}⚡) — 🎁 <b>{LEVELS[i]['reward']}</b>\n"

        else:

            text += f"🔒 <b>Ур. {i}:</b> Секретный босс (В ожидании...)\n"

    await message.answer(text, parse_mode="HTML")

@dp.message(F.photo, F.from_user.id == ADMIN_ID)

async def admin_get_photo_id(message: types.Message):

    if message.from_user.id in admin_waiting_broadcast:

        return

    file_id = message.photo[-1].file_id

    await message.reply(f"🖼 <b>Код картинки (file_id):</b>\n<code>{file_id}</code>", parse_mode="HTML")

 

@dp.message(Command("admin"))

async def cmd_admin(message: types.Message):

    if message.from_user.id != ADMIN_ID:

        return

    admin_waiting_broadcast.discard(ADMIN_ID)

 

    cur.execute("SELECT COUNT(*), SUM(stars_spent) FROM users")

    total_users, total_stars = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM claims WHERE status = 'pending'")

    pending_claims = cur.fetchone()

 

    kb = InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text=f"🎁 Активные заявки ({pending_claims})", callback_data="admin_claims")],

        [InlineKeyboardButton(text="📢 Рассылка игрокам", callback_data="admin_broadcast")],

        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin_refresh")]

    ])

 

    await message.answer(

        f"👑 <b>Админ-панель бота</b>\n\n"

        f"👥 Всего игроков в базе: <b>{total_users}</b>\n"

        f"⭐ Заработано звёзд: <b>{total_stars or 0} ⭐</b>\n"

        f"📦 Ожидают подарка: <b>{pending_claims} чел.</b>",

        parse_mode="HTML",

        reply_markup=kb

    )

 

@dp.callback_query(F.data == "admin_refresh")

async def cb_admin_refresh(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        return

    admin_waiting_broadcast.discard(ADMIN_ID)

    cur.execute("SELECT COUNT(*), SUM(stars_spent) FROM users")

    total_users, total_stars = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM claims WHERE status = 'pending'")

    pending_claims = cur.fetchone()

 

    kb = InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text=f"🎁 Активные заявки ({pending_claims})", callback_data="admin_claims")],

        [InlineKeyboardButton(text="📢 Рассылка игрокам", callback_data="admin_broadcast")],

        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin_refresh")]

    ])

    await call.message.edit_text(

        f"👑 <b>Админ-панель бота</b>\n\n"

        f"👥 Всего игроков в базе: <b>{total_users}</b>\n"

        f"⭐ Заработано звёзд: <b>{total_stars or 0} ⭐</b>\n"

        f"📦 Ожидают подарка: <b>{pending_claims} чел.</b>",

        parse_mode="HTML",

        reply_markup=kb

    )

 

@dp.callback_query(F.data == "admin_broadcast")

async def cb_admin_broadcast(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        return

    admin_waiting_broadcast.add(ADMIN_ID)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_refresh")]])

    await call.message.edit_text(

        "📢 <b>Режим рассылки</b>\n\nОтправьте следующим сообщением текст (или фото с подписью), который получат все игроки бота.",

        parse_mode="HTML",

        reply_markup=kb

    )

 

@dp.message(F.from_user.id == ADMIN_ID, lambda m: m.from_user.id in admin_waiting_broadcast)

async def process_broadcast(message: types.Message):

    admin_waiting_broadcast.discard(ADMIN_ID)

    cur.execute("SELECT user_id FROM users")

    users = cur.fetchall()

 

    sent = 0

    for (uid,) in users:

        try:

            await message.copy_to(chat_id=uid)

            sent += 1

            await asyncio.sleep(0.05)

        except Exception:

            pass

 

    await message.answer(f"✅ <b>Рассылка завершена!</b>\nДоставлено: <b>{sent}</b> из {len(users)} игроков.", parse_mode="HTML")

 

@dp.callback_query(F.data == "admin_claims")

async def cb_admin_claims(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        return

    cur.execute("SELECT id, user_id, username, level, reward FROM claims WHERE status = 'pending' LIMIT 10")

    rows = cur.fetchall()

    if not rows:

        return await call.answer("Активных заявок нет!", show_alert=True)

 

    text = "🎁 <b>Невыданные подарки (нажмите чтобы закрыть заявку):</b>\n\n"

    buttons = []

    for cid, uid, uname, lvl, rew in rows:

        text += f"#{cid} | @{uname} (ID: <code>{uid}</code>) — Ур.{lvl} ({rew})\n"

        buttons.append([InlineKeyboardButton(text=f"✅ Выдано #{cid} (@{uname})", callback_data=f"done_claim_{cid}")])

   

    buttons.append([InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_refresh")])

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

 

@dp.callback_query(F.data.startswith("done_claim_"))

async def cb_done_claim(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        return

    cid = int(call.data.split("_"))

    cur.execute("UPDATE claims SET status = 'done' WHERE id = ?", (cid,))

    db.commit()

    await call.answer(f"Заявка #{cid} отмечена как выполненная!", show_alert=True)

    await cb_admin_claims(call)

@dp.callback_query(F.data.startswith("back_"))

async def cb_back(call: types.CallbackQuery):

    target_id = int(call.data.split("_"))

    if not check_owner(call, target_id):

        return await call.answer("Руки прочь от чужого героя! Вызови своего командой /card", show_alert=True)

    user = get_user(target_id)

    await send_or_edit_card(call.message, user, is_edit=True)

 

@dp.callback_query(F.data.startswith("levels_"))

async def cb_levels(call: types.CallbackQuery):

    target_id = int(call.data.split("_"))

    if not check_owner(call, target_id):

        return await call.answer("Вызови своё меню командой /card", show_alert=True)

    text = "🗺 <b>Дорога славы (Все 10 уровней):</b>\n\n"

    for i in range(1, 11):

        if i in LEVELS:

            text += f"✅ <b>Ур. {i}:</b> {LEVELS[i]['name']} ({LEVELS[i]['need']}⚡) — 🎁 <b>{LEVELS[i]['reward']}</b>\n"

        else:

            text += f"🔒 <b>Ур. {i}:</b> Секретный босс (В ожидании...)\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_{target_id}")]])

    await edit_menu_safe(call.message, text, kb)

 

@dp.callback_query(F.data.startswith("farm_"))

async def cb_farm(call: types.CallbackQuery):

    target_id = int(call.data.split("_"))

    if not check_owner(call, target_id):

        return await call.answer("Не трогай чужого персонажа! Напиши /card", show_alert=True)

 

    user = get_user(target_id)

    uid, _, level, energy, last_farm, amulet_until, _ = user

    now = int(time.time())

 

    if level not in LEVELS:

        return await call.answer("Уровень в разработке!", show_alert=True)

 

    if now - last_farm < COOLDOWN:

        rem = (last_farm + COOLDOWN) - now

        msg = random.choice(WAIT_TEXTS).format(h=rem // 3600, m=(rem % 3600) // 60)

        return await call.answer(msg, show_alert=True)

 

    gain = random.randint(50, 150) if amulet_until > now else random.randint(1, 50)

    new_energy = min(energy + gain, LEVELS[level]["need"])

 

    cur.execute("UPDATE users SET energy = ?, last_farm = ? WHERE user_id = ?", (new_energy, now, uid))

    db.commit()

 

    phrase = random.choice(FARM_TEXTS).format(gain=gain)

    await call.answer(phrase, show_alert=True)

    updated_user = get_user(uid)

    await send_or_edit_card(call.message, updated_user, is_edit=True)

 

@dp.callback_query(F.data.startswith("claim_"))

async def cb_claim(call: types.CallbackQuery):

    target_id = int(call.data.split("_"))

    if not check_owner(call, target_id):

        return await call.answer("Это чужой приз, даже не пытайся!", show_alert=True)

 

    user = get_user(target_id)

    uid, uname, level, energy, _, _, _ = user

    if level not in LEVELS or energy < LEVELS[level]["need"]:

        return await call.answer("Рановато! Сначала докачай энергию до конца!", show_alert=True)

 

    reward_name = LEVELS[level]["reward"]

    next_level = level + 1

 

    cur.execute("INSERT INTO claims (user_id, username, level, reward) VALUES (?, ?, ?, ?)", (uid, uname, level, reward_name))

    cur.execute("UPDATE users SET level = ?, energy = 0 WHERE user_id = ?", (next_level, uid))

    db.commit()

 

    await bot.send_message(

        ADMIN_ID,

        f"🎉 <b>НОВАЯ ЗАЯВКА НА ПОДАРОК!</b>\nИгрок: @{uname} (ID: <code>{uid}</code>)\nУровень: {level}\nПриз: <b>{reward_name}</b>\n\nУправление заявками: /admin",

        parse_mode="HTML"

    )

 

    await call.answer("🎉 Красавчик! Голубь с заявкой на подарок уже летит к админу!", show_alert=True)

    updated_user = get_user(uid)

    await send_or_edit_card(call.message, updated_user, is_edit=True)

 

@dp.callback_query(F.data.startswith("shop_"))

async def cb_shop(call: types.CallbackQuery):

    target_id = int(call.data.split("_"))

    if not check_owner(call, target_id):

        return await call.answer("Открой свою лавку командой /shop", show_alert=True)

 

    text = (

        "🛒 <b>Лавка читера за Telegram Stars ⭐</b>\n\n"

        "🔮 <b>Амулет удачи (40 ⭐):</b> на 48 часов отменяет лень героя — выпадает строго от 50 до 150⚡!\n"

        "📦 <b>Кейс с удачей (25 ⭐):</b> кот в мешке с энергией! Внутри от 1 до 100⚡ без ожидания.\n"

        "⚡ <b>Попытка прорыва (100 ⭐):</b> секретная запрещённая техника! Может мгновенно закрыть весь уровень."

    )

    await edit_menu_safe(call.message, text, shop_keyboard(target_id))

 

@dp.callback_query(F.data.startswith("buy_"))

async def cb_buy(call: types.CallbackQuery):

    parts = call.data.split("_")

    item = parts

    target_id = int(parts)

    if not check_owner(call, target_id):

        return await call.answer("Это чужое меню!", show_alert=True)

 

    prices_map = {

        "amulet": ("Амулет удачи на 48ч", "Добыча 50-150 энергии без лени героя", 40),

        "case": ("Кейс с удачей", "Случайный бонус от 1 до 100 энергии прямо сейчас", 25),

        "skip": ("Попытка прорыва уровня", "Запрещённая техника мгновенного закрытия уровня", 100),

    }

    title, desc, amount = prices_map[item]

    await call.message.answer_invoice(

        title=title,

        description=desc,

        payload=item,

        currency="XTR",

        prices=[LabeledPrice(label=title, amount=amount)]

    )

    await call.answer()

 

@dp.pre_checkout_query()

async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):

    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

 

@dp.message(F.successful_payment)

async def process_payment(message: types.Message):

    payload = message.successful_payment.invoice_payload

    paid_stars = message.successful_payment.total_amount

    uid = message.from_user.id

    user = get_user(uid)

    _, _, level, energy, _, amulet_until, _ = user

    now = int(time.time())

 

    cur.execute("UPDATE users SET stars_spent = stars_spent + ? WHERE user_id = ?", (paid_stars, uid))

    db.commit()

 

    if level not in LEVELS:

        return

 

    need = LEVELS[level]["need"]

 

    if payload == "amulet":

        new_until = max(amulet_until, now) + (48 * 3600)

        cur.execute("UPDATE users SET amulet_until = ? WHERE user_id = ?", (new_until, uid))

        db.commit()

        await message.answer("🔮 <b>Амулет удачи надет!</b> Ближайшие 48 часов твой герой пашет как проклятый (50–150⚡)!", parse_mode="HTML")

 

    elif payload == "case":

        bonus = random.randint(1, 100)

        new_energy = min(energy + bonus, need)

        cur.execute("UPDATE users SET energy = ? WHERE user_id = ?", (new_energy, uid))

        db.commit()

        await message.answer(f"📦 <b>Ты вскрыл ящик и вытащил +{bonus}⚡!</b> Герой в шоке, но доволен!", parse_mode="HTML")

 

    elif payload == "skip":

        if random.randint(1, 100) <= 5:

            cur.execute("UPDATE users SET energy = ? WHERE user_id = ?", (need, uid))

            db.commit()

            await message.answer("🔥 <b>БЕЗУМИЕ! Запрещённая техника сработала!</b> Уровень пройден за секунду! Беги забирать подарок в /card!", parse_mode="HTML")

        else:

            await message.answer("💨 <b>ПУФ! Техника пшикнула дымом...</b> Герой закашлялся, прорыв не удался. Попробуй ещё раз!", parse_mode="HTML")

 

async def set_bot_commands():

    commands = [

        BotCommand(command="card", description="🎴 Мой аниме-герой и энергия"),

        BotCommand(command="farm", description="⚡ Отправить героя на тренировку"),

        BotCommand(command="shop", description="🛒 Лавка читера (Бусты за Stars)"),

        BotCommand(command="levels", description="🗺 Дорога славы (Все 10 уровней)"),

    ]

    await bot.set_my_commands(commands)

 

async def main():

    await set_bot_commands()

    await dp.start_polling(bot)

 

if __name__ == "__main__":

    asyncio.run(main())

