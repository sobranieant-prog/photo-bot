print("BOT STARTED")

import os
import asyncio
import calendar
import sqlite3
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
TZ = ZoneInfo("Europe/Moscow")

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= DATABASE =================

db = sqlite3.connect("bookings.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    time TEXT,
    shoot TEXT,
    phone TEXT,
    name TEXT,
    username TEXT,
    user_id INTEGER,
    status TEXT
)
""")
db.commit()


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


# ================= TIME =================

TIMES = [
    "10:00","11:00","12:00","13:00","14:00",
    "15:00","16:00","17:00","18:00","19:00","20:00","21:00"
]


def is_slot_taken(date, time):
    cursor.execute(
        "SELECT 1 FROM bookings WHERE date=? AND time=? AND status='Новая'",
        (date, time)
    )
    return cursor.fetchone() is not None


def is_time_too_soon(date_str, time_str):
    now = datetime.now(TZ)
    d, m, y = map(int, date_str.split("."))
    h, mi = map(int, time_str.split(":"))
    slot_dt = datetime(y, m, d, h, mi, tzinfo=TZ)
    return slot_dt <= now + timedelta(minutes=60)


# ================= CALENDAR =================

def get_calendar():
    now = datetime.now(TZ)
    y, m = now.year, now.month
    kb = []

    kb.append([InlineKeyboardButton(
        text=f"{calendar.month_name[m]} {y}",
        callback_data="ignore"
    )])

    kb.append([
        InlineKeyboardButton(text=d, callback_data="ignore")
        for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    ])

    for week in calendar.monthcalendar(y, m):
        row = []
        for d in week:
            if d == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                dt = datetime(y, m, d, tzinfo=TZ)
                if dt.date() < now.date():
                    row.append(InlineKeyboardButton(text="—", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(d),
                        callback_data=f"date_{y}_{m}_{d}"
                    ))
        kb.append(row)

    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_time_kb(date):
    rows = []
    for t in TIMES:
        if is_slot_taken(date, t) or is_time_too_soon(date, t):
            rows.append([InlineKeyboardButton(text=f"{t} ❌", callback_data="ignore")])
        else:
            rows.append([InlineKeyboardButton(text=t, callback_data=f"time_{t}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    await message.answer("Бот записи на съёмку 📸", reply_markup=start_kb)


@dp.message(lambda m: m.text == "▶️ Начать")
async def menu(message: Message):
    await message.answer("Меню:", reply_markup=get_menu(message.from_user.id))


# ================= PORTFOLIO =================

@dp.message(lambda m: m.text and m.text.startswith("📸"))
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

@dp.message(lambda m: m.text and m.text.startswith("❌"))
async def my_booking(message: Message):
    cursor.execute("""
        SELECT id, date, time, shoot, status
        FROM bookings
        WHERE user_id=? AND status='Новая'
        ORDER BY id DESC
        LIMIT 1
    """, (message.from_user.id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("У вас нет активных записей 📭")
        return

    bid, date, time, shoot, status = row

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
        f"📄 Статус: {status}",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("user_cancel_"))
async def user_cancel(cb: CallbackQuery):
    bid = cb.data.split("_")[2]
    cursor.execute("UPDATE bookings SET status='Отменено' WHERE id=?", (bid,))
    db.commit()
    await cb.message.edit_text("❌ Ваша запись отменена")
    await cb.answer()
    await bot.send_message(ADMIN_ID, "⚠️ Клиент отменил запись")


# ================= CRM =================

@dp.message(lambda m: m.text and m.text.startswith("📊"))
async def crm(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("""
        SELECT id, date, time, shoot, name, phone, status
        FROM bookings
        WHERE status='Новая'
        ORDER BY id DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Нет новых заявок")
        return

    for r in rows:
        bid, date, time, shoot, name, phone, status = r

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{bid}"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{bid}")
            ]
        ])

        await message.answer(
            f"👤 {name}\n📸 {shoot}\n📅 {date} {time}\n📞 {phone}\n📄 {status}",
            reply_markup=kb
        )


@dp.callback_query(lambda c: c.data.startswith("done_"))
async def mark_done(cb: CallbackQuery):
    bid = cb.data.split("_")[1]
    cursor.execute("UPDATE bookings SET status='Выполнено' WHERE id=?", (bid,))
    db.commit()
    await cb.message.edit_text(cb.message.text + "\n\n✅ Выполнено")
    await cb.answer()


@dp.callback_query(lambda c: c.data.startswith("cancel_"))
async def mark_cancel(cb: CallbackQuery):
    bid = cb.data.split("_")[1]
    cursor.execute("UPDATE bookings SET status='Отменено' WHERE id=?", (bid,))
    db.commit()
    await cb.message.edit_text(cb.message.text + "\n\n❌ Отменено фотографом")
    await cb.answer()


# ================= BOOKING FLOW =================

@dp.message(lambda m: m.text and m.text.startswith("📅"))
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
    shoot = message.text.split(" (")[0]
    await state.update_data(shoot=shoot)
    await message.answer("Выберите дату:", reply_markup=get_calendar())
    await state.set_state(Booking.date)


@dp.callback_query(lambda c: c.data.startswith("date_"))
async def pick_date(cb: CallbackQuery, state: FSMContext):
    _, y, m, d = cb.data.split("_")
    date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"
    await state.update_data(date=date)
    await cb.message.answer("Выберите время:", reply_markup=get_time_kb(date))
    await state.set_state(Booking.time)
    await cb.answer()


@dp.callback_query(lambda c: c.data.startswith("time_"))
async def pick_time(cb: CallbackQuery, state: FSMContext):
    t = cb.data.split("_")[1]
    await state.update_data(time=t)
    await cb.message.answer("Отправьте номер:", reply_markup=phone_kb)
    await state.set_state(Booking.phone)
    await cb.answer()


@dp.message(Booking.phone)
async def get_phone(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("Нажмите кнопку отправки номера")
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
async def confirm(message: Message, state: FSMContext):
    if message.text != "✅ Подтвердить":
        await message.answer("Отменено", reply_markup=get_menu(message.from_user.id))
        await state.clear()
        return

    d = await state.get_data()
    cursor.execute("""
        INSERT INTO bookings
        (date, time, shoot, phone, name, username, user_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Новая')
    """, (
        d["date"], d["time"], d["shoot"], d["phone"],
        d["name"], d["username"], d["user_id"]
    ))
    db.commit()

    await bot.send_message(
        ADMIN_ID,
        f"📥 НОВАЯ ЗАЯВКА\n\n👤 {d['name']}\n📸 {d['shoot']}\n📅 {d['date']} {d['time']}\n📞 {d['phone']}"
    )

    await message.answer("✅ Запись сохранена", reply_markup=get_menu(message.from_user.id))
    await state.clear()


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
