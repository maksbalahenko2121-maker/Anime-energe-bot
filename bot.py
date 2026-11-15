import asyncio

import random

import sqlite3

import time

from aiogram import Bot, Dispatcher, F, types

from aiogram.filters import Command

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery

 

# --- НАСТРОЙКИ ---

BOT_TOKEN = "9297074957:AAH1MatXEIEX3QI8m2uj0n9iLJGH1I72hDI"

ADMIN_ID = 6921885296  # Ваш числовой Telegram ID

COOLDOWN = 3 * 3600   # 3 часа в секундах

 

LEVELS = {

    1: {"name": "Наруто (Генин)", "need": 500, "reward": "Мишка (15 ⭐)"},

    2: {"name": "Танджиро (Истребитель)", "need": 2000, "reward": "Кольцо (100 ⭐)"},

    3: {"name": "Годжо Сатору", "need": 6000, "reward": "NFT Pet Snake"},

}

 

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

 

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

    if username and user[1] != username:

        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))

        db.commit()

    return user

 

def main_keyboard(user_id, level, energy, need):

    buttons = []

    if level in LEVELS:

        if energy >= need:

            buttons.append([InlineKeyboardButton(text="🎁 Оставить заявку на подарок", callback_data=f"claim_{user_id}")])

        else:

            buttons.append([InlineKeyboardButton(text="⚡ Впитать энергию", callback_data=f"farm_{user_id}")])

        buttons.append([InlineKeyboardButton(text="🛒 Магазин бустов (Stars)", callback_data=f"shop_{user_id}")])

    buttons.append([InlineKeyboardButton(text="🗺 Список всех 10 уровней", callback_data=f"levels_{user_id}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

 

def shop_keyboard(user_id):

    return InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text="🔮 Амулет удачи 48ч (50-150⚡) — 40 ⭐", callback_data=f"buy_amulet_{user_id}")],

        [InlineKeyboardButton(text="📦 Кейс с удачей (1-100⚡) — 25 ⭐", callback_data=f"buy_case_{user_id}")],

        [InlineKeyboardButton(text="⚡ Попытка прорыва уровня — 100 ⭐", callback_data=f"buy_skip_{user_id}")],

        [InlineKeyboardButton(text="⬅️ Назад к карточке", callback_data=f"back_{user_id}")]

    ])

def get_card_text(user):

    _, uname, level, energy, last_farm, amulet_until, _ = user

    now = int(time.time())

   

    if level not in LEVELS:

        return (

            f"👤 Игрок: <b>@{uname}</b>\n"

            f"🏆 <b>Уровень {level} из 10</b>\n\n"

            "🔒 Новые аниме-карточки и подарки уже в разработке! Ожидайте обновления."

        )

   

    lvl_data = LEVELS[level]

    amulet_status = "✅ Активен" if amulet_until > now else "❌ Не активен"

   

    wait_time = (last_farm + COOLDOWN) - now

    if wait_time <= 0:

        timer_text = "🟢 Готово к сбору!"

    else:

        hours = wait_time // 3600

        mins = (wait_time % 3600) // 60

        timer_text = f"⏳ Осталось ждать: {hours}ч {mins}м"

 

    return (

        f"👤 Игрок: <b>@{uname}</b>\n"

        f"🎴 <b>Уровень {level}/10: {lvl_data['name']}</b>\n"

        f"🎁 Награда: <b>{lvl_data['reward']}</b>\n\n"

        f"⚡ Энергия: <b>{energy} / {lvl_data['need']}</b>\n"

        f"🔮 Амулет удачи: {amulet_status}\n"

        f"{timer_text}"

    )

 

def check_owner(call: types.CallbackQuery, target_id: int):

    return call.from_user.id == target_id

 

@dp.message(Command("start", "card"))

async def cmd_card(message: types.Message):

    user = get_user(message.from_user.id, message.from_user.username)

    uid, _, lvl, energy, _, _, _ = user

    need = LEVELS[lvl]["need"] if lvl in LEVELS else 0

    await message.answer(

        get_card_text(user),

        parse_mode="HTML",

        reply_markup=main_keyboard(uid, lvl, energy, need)

    )

 

@dp.message(Command("farm"))

async def cmd_farm_text(message: types.Message):

    user = get_user(message.from_user.id, message.from_user.username)

    uid, uname, level, energy, last_farm, amulet_until, _ = user

    now = int(time.time())

 

    if level not in LEVELS:

        return await message.reply("🔒 Все доступные уровни пройдены, ждите обновления!")

 

    if energy >= LEVELS[level]["need"]:

        return await message.reply("🎁 Карточка уже заряжена! Нажмите кнопку заявки в /card")

 

    if now - last_farm < COOLDOWN:

        rem = (last_farm + COOLDOWN) - now

        return await message.reply(f"⏳ @{uname}, рано! Ждать ещё {rem // 3600}ч {(rem % 3600) // 60}м")

 

    gain = random.randint(50, 150) if amulet_until > now else random.randint(1, 50)

    new_energy = min(energy + gain, LEVELS[level]["need"])

 

    cur.execute("UPDATE users SET energy = ?, last_farm = ? WHERE user_id = ?", (new_energy, now, uid))

    db.commit()

 

    await message.reply(f"⚡ @{uname} впитал <b>+{gain} энергии</b>! ({new_energy}/{LEVELS[level]['need']})", parse_mode="HTML")

 

@dp.message(Command("shop"))

async def cmd_shop_text(message: types.Message):

    uid = message.from_user.id

    get_user(uid, message.from_user.username)

    await message.answer(

        "🛒 <b>Магазин усилений за Telegram Stars ⭐</b>\n\n"

        "🔮 <b>Амулет удачи (40 ⭐):</b> на 48 часов повышает добычу до 50–150 энергии за раз.\n"

        "📦 <b>Кейс с удачей (25 ⭐):</b> мгновенно даёт от 1 до 100 энергии.\n"

        "⚡ <b>Попытка прорыва (100 ⭐):</b> даёт шанс мгновенно закрыть карточку и забрать приз!",

        parse_mode="HTML",

        reply_markup=shop_keyboard(uid)

    )

 

@dp.message(Command("levels"))

async def cmd_levels_text(message: types.Message):

    text = "🗺 <b>Список уровней:</b>\n\n"

    for i in range(1, 11):

        if i in LEVELS:

            text += f"✅ <b>Ур. {i}:</b> {LEVELS[i]['name']} ({LEVELS[i]['need']}⚡) — 🎁 {LEVELS[i]['reward']}\n"

        else:

            text += f"🔒 <b>Ур. {i}:</b> В ожидании...\n"

    await message.answer(text, parse_mode="HTML")

@dp.message(Command("admin"))

async def cmd_admin(message: types.Message):

    if message.from_user.id != ADMIN_ID:

        return

 

    cur.execute("SELECT COUNT(*), SUM(stars_spent) FROM users")

    total_users, total_stars = cur.fetchone()

    total_stars = total_stars or 0

 

    cur.execute("SELECT COUNT(*) FROM claims WHERE status = 'pending'")

    pending_claims = cur.fetchone()[0]

 

    kb = InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text=f"🎁 Активные заявки ({pending_claims})", callback_data="admin_claims")],

        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin_refresh")]

    ])

 

    await message.answer(

        f"👑 <b>Админ-панель бота</b>\n\n"

        f"👥 Всего игроков в базе: <b>{total_users}</b>\n"

        f"⭐ Заработано звёзд: <b>{total_stars} ⭐</b>\n"

        f"📦 Ожидают подарка: <b>{pending_claims} чел.</b>",

        parse_mode="HTML",

        reply_markup=kb

    )

 

@dp.callback_query(F.data == "admin_refresh")

async def cb_admin_refresh(call: types.CallbackQuery):

    if call.from_user.id != ADMIN_ID:

        return

    cur.execute("SELECT COUNT(*), SUM(stars_spent) FROM users")

    total_users, total_stars = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM claims WHERE status = 'pending'")

    pending_claims = cur.fetchone()[0]

 

    kb = InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text=f"🎁 Активные заявки ({pending_claims})", callback_data="admin_claims")],

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

    cid = int(call.data.split("_")[2])

    cur.execute("UPDATE claims SET status = 'done' WHERE id = ?", (cid,))

    db.commit()

    await call.answer(f"Заявка #{cid} отмечена как выполненная!", show_alert=True)

    await cb_admin_claims(call)

@dp.callback_query(F.data.startswith("back_"))

async def cb_back(call: types.CallbackQuery):

    target_id = int(call.data.split("_")[1])

    if not check_owner(call, target_id):

        return await call.answer("Это не ваша карточка! Вызовите свою командой /card", show_alert=True)

    user = get_user(target_id)

    _, _, lvl, energy, _, _, _ = user

    need = LEVELS[lvl]["need"] if lvl in LEVELS else 0

    await call.message.edit_text(

        get_card_text(user),

        parse_mode="HTML",

        reply_markup=main_keyboard(target_id, lvl, energy, need)

    )

 

@dp.callback_query(F.data.startswith("levels_"))

async def cb_levels(call: types.CallbackQuery):

    target_id = int(call.data.split("_")[1])

    if not check_owner(call, target_id):

        return await call.answer("Вызовите своё меню командой /card", show_alert=True)

    text = "🗺 <b>Прогресс уровней:</b>\n\n"

    for i in range(1, 11):

        if i in LEVELS:

            text += f"✅ <b>Ур. {i}:</b> {LEVELS[i]['name']} ({LEVELS[i]['need']}⚡) — 🎁 {LEVELS[i]['reward']}\n"

        else:

            text += f"🔒 <b>Ур. {i}:</b> В ожидании...\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_{target_id}")]])

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

 

@dp.callback_query(F.data.startswith("farm_"))

async def cb_farm(call: types.CallbackQuery):

    target_id = int(call.data.split("_")[1])

    if not check_owner(call, target_id):

        return await call.answer("Это чужая карточка! Напишите /card", show_alert=True)

 

    user = get_user(target_id)

    uid, _, level, energy, last_farm, amulet_until, _ = user

    now = int(time.time())

 

    if level not in LEVELS:

        return await call.answer("Уровень в разработке!", show_alert=True)

 

    if now - last_farm < COOLDOWN:

        rem = (last_farm + COOLDOWN) - now

        return await call.answer(f"Рано! Ждать ещё {rem // 3600}ч {(rem % 3600) // 60}м", show_alert=True)

 

    gain = random.randint(50, 150) if amulet_until > now else random.randint(1, 50)

    new_energy = min(energy + gain, LEVELS[level]["need"])

 

    cur.execute("UPDATE users SET energy = ?, last_farm = ? WHERE user_id = ?", (new_energy, now, uid))

    db.commit()

 

    await call.answer(f"⚡ Вы получили +{gain} энергии!", show_alert=True)

    updated_user = get_user(uid)

    await call.message.edit_text(

        get_card_text(updated_user),

        parse_mode="HTML",

        reply_markup=main_keyboard(uid, level, new_energy, LEVELS[level]["need"])

    )

 

@dp.callback_query(F.data.startswith("claim_"))

async def cb_claim(call: types.CallbackQuery):

    target_id = int(call.data.split("_")[1])

    if not check_owner(call, target_id):

        return await call.answer("Это чужая карточка!", show_alert=True)

 

    user = get_user(target_id)

    uid, uname, level, energy, _, _, _ = user

    if level not in LEVELS or energy < LEVELS[level]["need"]:

        return await call.answer("Недостаточно энергии!", show_alert=True)

 

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

 

    await call.answer("🎁 Заявка на подарок успешно отправлена админу!", show_alert=True)

    updated_user = get_user(uid)

    need = LEVELS[next_level]["need"] if next_level in LEVELS else 0

    await call.message.edit_text(

        get_card_text(updated_user),

        parse_mode="HTML",

        reply_markup=main_keyboard(uid, next_level, 0, need)

    )

 

@dp.callback_query(F.data.startswith("shop_"))

async def cb_shop(call: types.CallbackQuery):

    target_id = int(call.data.split("_")[1])

    if not check_owner(call, target_id):

        return await call.answer("Откройте свой магазин командой /shop", show_alert=True)

 

    await call.message.edit_text(

        "🛒 <b>Магазин усилений за Telegram Stars ⭐</b>\n\n"

        "🔮 <b>Амулет удачи (40 ⭐):</b> на 48 часов повышает добычу до 50–150 энергии за раз.\n"

        "📦 <b>Кейс с удачей (25 ⭐):</b> мгновенно даёт от 1 до 100 энергии.\n"

        "⚡ <b>Попытка прорыва (100 ⭐):</b> даёт шанс мгновенно закрыть карточку и забрать приз!",

        parse_mode="HTML",

        reply_markup=shop_keyboard(target_id)

    )

 

@dp.callback_query(F.data.startswith("buy_"))

async def cb_buy(call: types.CallbackQuery):

    parts = call.data.split("_")

    item = parts[1]

    target_id = int(parts[2])

    if not check_owner(call, target_id):

        return await call.answer("Это чужое меню!", show_alert=True)

 

    prices_map = {

        "amulet": ("Амулет удачи на 48ч", "Добыча 50-150 энергии раз в 3 часа", 40),

        "case": ("Кейс с удачей", "Случайный бонус от 1 до 100 энергии", 25),

        "skip": ("Попытка прорыва уровня", "Шанс мгновенно закрыть текущую карточку", 100),

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

        await message.answer("🔮 <b>Амулет удачи активирован на 48 часов!</b>", parse_mode="HTML")

 

    elif payload == "case":

        bonus = random.randint(1, 100)

        new_energy = min(energy + bonus, need)

        cur.execute("UPDATE users SET energy = ? WHERE user_id = ?", (new_energy, uid))

        db.commit()

        await message.answer(f"📦 <b>Вы открыли кейс и получили +{bonus} энергии!</b>", parse_mode="HTML")

 

    elif payload == "skip":

        if random.randint(1, 100) <= 5:

            cur.execute("UPDATE users SET energy = ? WHERE user_id = ?", (need, uid))

            db.commit()

            await message.answer("🔥 <b>НЕВЕРОЯТНАЯ УДАЧА! Прорыв удался, уровень пройден!</b> Забирайте подарок в /card!", parse_mode="HTML")

        else:

            await message.answer("💨 <b>Не повезло!</b> Прорыв энергии сорвался. Попробуйте снова!", parse_mode="HTML")

 

async def main():

    await dp.start_polling(bot)

 

if __name__ == "__main__":

    asyncio.run(main())
