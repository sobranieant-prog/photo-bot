print("BOT STARTED")

import os
import asyncio
import calendar
from datetime import datetime

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

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= FILE HELPERS =================

def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.readlines()

def write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ================= PARSE BOOKINGS =================

def parse_bookings():
    rows = []
    for i, line in enumerate(read_lines("bookings.txt")):
        p = line.strip().split("|")
        if len(p) < 8:
            continue

        rows.append({
            "index": i,
            "date": p[0],
            "time": p[1],
            "type": p[2],
            "phone": p[3],
            "name": p[4],
            "username": p[5],
            "user_id": p[6],
            "status": p[7]
        })
    return rows


def is_slot_busy(date, time):
    for r in parse_bookings():
        if r["date"] == date and r["time"] == time:
            return True
    return False


# ================= KEYBOARDS =================

start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="▶️ Начать")]],
    resize_keyboard=True
)

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Портфолио")],
        [KeyboardButton(text="📅 Записаться")],
        [KeyboardButton(text="❌ Моя запись")],
        [KeyboardButton(text="📊 CRM")]
    ],
    resize_keyboard=True
)

phone_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(
        text="📞 Отправить номер",
        request_contact=True
    )]],
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


# ================= CALENDAR (CURRENT MONTH) =================

def get_calendar_month():
    now = datetime.now()
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
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                d = datetime(y, m, day)
                if d.date() < now.date():
                    row.append(InlineKeyboardButton(text="—", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{y}_{m}_{day}"
                    ))
        kb.append(row)

    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_time_kb(date):
    times = ["10:00","11:00","12:00","13:00","14:00",
             "15:00","16:00","17:00","18:00","19:00"]

    rows = []
    for t in times:
        text = f"❌ {t}" if is_slot_busy(date, t) else t
        cb = "busy" if is_slot_busy(date, t) else f"time_{t}"
        rows.append([InlineKeyboardButton(text=text, callback_data=cb)])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= START =================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привет! Бот записи на съёмку 📸",
        reply_markup=start_kb
    )

@dp.message(lambda m: m.text == "▶️ Начать")
async def menu(message: Message):
    await message.answer("Меню:", reply_markup=menu_kb)


# ================= PORTFOLIO =================

@dp.message(lambda m: m.text == "📸 Портфолио")
async def portfolio(message: Message):
    found = False
    for i in range(1, 11):
        p = f"photo{i}.jpg"
        if os.path.exists(p):
            await message.answer_photo(FSInputFile(p))
            found = True
    if not found:
        await message.answer("Портфолио пусто")


# ================= BOOKING =================

@dp.message(lambda m: m.text == "📅 Записаться")
async def booking_start(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Свадебная")],
            [KeyboardButton(text="Корпоративная")],
            [KeyboardButton(text="Репортажная")],
            [KeyboardButton(text="Индивидуальная")]
        ],
        resize_keyboard=True
    )

    await message.answer("Тип съёмки:", reply_markup=kb)
    await state.set_state(Booking.shoot)


@dp.message(Booking.shoot)
async def pick_shoot(message: Message, state: FSMContext):
    await state.update_data(shoot=message.text)

    await message.answer(
        "Выберите дату:",
        reply_markup=get_calendar_month()
    )
    await state.set_state(Booking.date)


@dp.callback_query(lambda c: c.data.startswith("date_"))
async def pick_date(cb: CallbackQuery, state: FSMContext):
    _, y, m, d = cb.data.split("_")
    date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"

    await state.update_data(date=date)

    await cb.message.answer(
        "Выберите время:",
        reply_markup=get_time_kb(date)
    )
    await state.set_state(Booking.time)
    await cb.answer()


@dp.callback_query(lambda c: c.data == "busy")
async def busy(cb: CallbackQuery):
    await cb.answer("Слот занят")


@dp.callback_query(lambda c: c.data.startswith("time_"))
async def pick_time(cb: CallbackQuery, state: FSMContext):
    t = cb.data.split("_")[1]
    await state.update_data(time=t)

    await cb.message.answer(
        "Отправьте номер:",
        reply_markup=phone_kb
    )
    await state.set_state(Booking.phone)
    await cb.answer()


@dp.message(Booking.phone)
async def save_phone(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("Нажмите кнопку отправки номера")
        return

    data = await state.get_data()
    u = message.from_user

    record = "|".join([
        data["date"],
        data["time"],
        data["shoot"],
        message.contact.phone_number,
        u.full_name,
        "@"+u.username if u.username else "-",
        str(u.id),
        "NEW"
    ]) + "\n"

    with open("bookings.txt","a",encoding="utf-8") as f:
        f.write(record)

    await message.answer("✅ Запись сохранена", reply_markup=menu_kb)

    await bot.send_message(
        ADMIN_ID,
        f"""📥 НОВАЯ ЗАЯВКА

👤 {u.full_name}
@{u.username}

📞 {message.contact.phone_number}
📸 {data['shoot']}
📅 {data['date']}
⏰ {data['time']}
"""
    )

    await state.clear()


# ================= USER CANCEL =================

@dp.message(lambda m: m.text == "❌ Моя запись")
async def my_booking(message: Message):
    uid = str(message.from_user.id)
    rows = parse_bookings()

    kb = []
    for r in rows:
        if r["user_id"] == uid:
            kb.append([InlineKeyboardButton(
                text=f"{r['date']} {r['time']}",
                callback_data=f"ucancel_{r['index']}"
            )])

    if not kb:
        await message.answer("У вас нет записей")
        return

    await message.answer(
        "Ваша запись:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(lambda c: c.data.startswith("ucancel_"))
async def user_cancel(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    lines = read_lines("bookings.txt")
    p = lines[idx].strip().split("|")

    lines.pop(idx)
    write_lines("bookings.txt", lines)

    await cb.message.answer("❌ Запись отменена")

    await bot.send_message(
        ADMIN_ID,
        f"🚫 Отмена: {p[4]} {p[0]} {p[1]}"
    )

    await cb.answer()


# ================= CRM =================

@dp.message(lambda m: m.text == "📊 CRM")
async def crm(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = parse_bookings()
    kb = []

    for r in rows:
        kb.append([InlineKeyboardButton(
            text=f"{r['date']} {r['time']} — {r['name']}",
            callback_data=f"card_{r['index']}"
        )])

    await message.answer(
        "CRM заявки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(lambda c: c.data.startswith("card_"))
async def card(cb: CallbackQuery):
    r = parse_bookings()[int(cb.data.split("_")[1])]

    text = (
        f"{r['name']}\n{r['username']}\n"
        f"{r['phone']}\n\n"
        f"{r['type']}\n"
        f"{r['date']} {r['time']}\n"
        f"Статус: {r['status']}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ DONE",
            callback_data=f"done_{r['index']}"
        )]
    ])

    await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@dp.callback_query(lambda c: c.data.startswith("done_"))
async def done(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    lines = read_lines("bookings.txt")
    p = lines[idx].strip().split("|")
    p[7] = "DONE"
    lines[idx] = "|".join(p)+"\n"
    write_lines("bookings.txt", lines)

    await cb.answer("Готово")


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
