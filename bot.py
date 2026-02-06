print("BOT STARTED")

import os
import asyncio
import calendar
import sqlite3
import secrets
import string
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage


# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1428673148
SITE_URL = "https://anikovich.netlify.app/"  
TZ = ZoneInfo("Europe/Moscow")

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= DATABASE =================

db = sqlite3.connect("bookings.db")
cursor = db.cursor()


# ================= HELPERS =================

def generate_code(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


# ================= PRICES =================

PRICES = {
    "❤️ Свадебная": "от 600р",
    "🏢 Корпоративная": "от 250р",
    "🎤 Репортажная": "от 200р",
    "📸 Индивидуальная / Семейная": "от 150р"
}


# ================= MENU =================

def get_menu(uid):
    kb = [
        [KeyboardButton(text="📸 Портфолио")],
        [KeyboardButton(text="📅 Записаться")],
        [KeyboardButton(text="❌ Моя запись")]
    ]
    if uid == ADMIN_ID:
        kb.append([KeyboardButton(text="📊 CRM")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="▶️ Начать")]],
    resize_keyboard=True
)

phone_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

confirm_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить"),
         KeyboardButton(text="❌ Отменить")]
    ],
    resize_keyboard=True
)


# ================= FSM =================

class Booking(StatesGroup):
    shoot = State()
    date = State()
    time = State()
    phone = State()
    confirm = State()


# ================= START =================

@dp.message(Command("start"))
async def start(message: Message):
    if message.text and "site" in message.text:
        await message.answer(
            "👋 Вы пришли с сайта\n\n"
            "Нажмите «Начать», чтобы записаться 📸",
            reply_markup=start_kb
        )
    else:
        await message.answer("Бот записи на съёмку 📸", reply_markup=start_kb)


@dp.message(lambda m: m.text == "▶️ Начать")
async def menu(message: Message):
    await message.answer("Меню:", reply_markup=get_menu(message.from_user.id))


# ================= PORTFOLIO =================

@dp.message(lambda m: m.text == "📸 Портфолио")
async def portfolio(message: Message):
    found = False
    for i in range(1, 11):
        path = f"photo{i}.jpg"
        if os.path.exists(path):
            await message.answer_photo(FSInputFile(path))
            found = True
    if not found:
        await message.answer("Портфолио пусто")


# ================= MY BOOKING =================

@dp.message(lambda m: m.text == "❌ Моя запись")
async def my_booking(message: Message):
    cursor.execute("""
        SELECT id, date, time, shoot, status, access_code
        FROM bookings
        WHERE user_id=? AND status='Новая'
        ORDER BY id DESC
        LIMIT 1
    """, (message.from_user.id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("У вас нет активных записей 📭")
        return

    bid, date, time, shoot, status, code = row

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отменить запись",
            callback_data=f"user_cancel_{bid}"
        )]
    ])

    await message.answer(
        f"📌 Ваша запись:\n\n"
        f"📸 {shoot}\n"
        f"📅 {date}\n"
        f"⏰ {time}\n"
        f"📄 {status}\n\n"
        f"🔐 Доступ к фото:\n{SITE_URL}/report/{code}",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("user_cancel_"))
async def user_cancel(cb: CallbackQuery):
    bid = cb.data.split("_")[2]
    cursor.execute("UPDATE bookings SET status='Отменено' WHERE id=?", (bid,))
    db.commit()
    await cb.message.edit_text("❌ Ваша запись отменена")
    await cb.answer()


# ================= BOOKING FLOW =================

@dp.message(lambda m: m.text == "📅 Записаться")
async def booking_start(message: Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"{k} ({v})")] for k, v in PRICES.items()],
        resize_keyboard=True
    )
    await message.answer("Выберите тип съёмки:", reply_markup=kb)
    await state.set_state(Booking.shoot)


@dp.message(Booking.shoot)
async def booking_type(message: Message, state: FSMContext):
    await state.update_data(shoot=message.text.split(" (")[0])
    await message.answer("Введите дату (пример: 25.03.2026):")
    await state.set_state(Booking.date)


@dp.message(Booking.date)
async def booking_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Введите время (пример: 18:00):")
    await state.set_state(Booking.time)


@dp.message(Booking.time)
async def booking_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Отправьте номер:", reply_markup=phone_kb)
    await state.set_state(Booking.phone)


@dp.message(Booking.phone)
async def booking_phone(message: Message, state: FSMContext):
    if not message.contact:
        return

    await state.update_data(
        phone=message.contact.phone_number,
        name=message.from_user.full_name,
        username=message.from_user.username or "",
        user_id=message.from_user.id
    )

    d = await state.get_data()
    await message.answer(
        f"Проверьте заявку:\n\n📸 {d['shoot']}\n📅 {d['date']}\n⏰ {d['time']}",
        reply_markup=confirm_kb
    )
    await state.set_state(Booking.confirm)


@dp.message(Booking.confirm)
async def booking_confirm(message: Message, state: FSMContext):
    if message.text != "✅ Подтвердить":
        await message.answer("Отменено", reply_markup=get_menu(message.from_user.id))
        await state.clear()
        return

    d = await state.get_data()
    code = generate_code()

    cursor.execute("""
        INSERT INTO bookings
        (date, time, shoot, phone, name, username, user_id, status, access_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Новая', ?)
    """, (
        d["date"], d["time"], d["shoot"], d["phone"],
        d["name"], d["username"], d["user_id"], code
    ))
    db.commit()

    await message.answer(
        f"✅ Запись подтверждена!\n\n"
        f"🔐 Доступ к фотоотчёту:\n"
        f"{SITE_URL}/report/{code}\n\n"
        f"⚠️ Сохраните эту ссылку",
        reply_markup=get_menu(message.from_user.id)
    )

    await bot.send_message(
        ADMIN_ID,
        f"📥 НОВАЯ ЗАЯВКА\n\n"
        f"👤 {d['name']}\n"
        f"📸 {d['shoot']}\n"
        f"📅 {d['date']} {d['time']}\n"
        f"🔐 {code}"
    )

    await state.clear()


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
