print("BOT STARTED")

import os
import asyncio
from datetime import datetime, timedelta

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
if not TOKEN:
    raise RuntimeError("BOT_TOKEN not found")

ADMIN_ID = 1428673148

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= KEYBOARDS =================

start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="▶️ Начать")]],
    resize_keyboard=True
)

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Портфолио")],
        [KeyboardButton(text="📅 Записаться")],
        [KeyboardButton(text="❌ Отменить мою запись")]
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
    keyboard=[[
        KeyboardButton(text="✅ Подтвердить"),
        KeyboardButton(text="❌ Отменить")
    ]],
    resize_keyboard=True
)


# ================= DATE =================

def get_date_kb(prefix="date"):
    today = datetime.now()
    buttons = []

    for i in range(14):
        d = today + timedelta(days=i)
        text = d.strftime("%d.%m.%Y")
        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{prefix}_{text}"
            )
        )

    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= BUSY =================

def read_bookings():
    if not os.path.exists("bookings.txt"):
        return []

    with open("bookings.txt", encoding="utf-8") as f:
        return f.readlines()


def write_bookings(lines):
    with open("bookings.txt", "w", encoding="utf-8") as f:
        f.writelines(lines)


def get_busy_slots(date_str):
    busy = set()

    for line in read_bookings():
        if "|" not in line:
            continue

        left = line.split("|")[0].strip()
        parts = left.split()

        if len(parts) >= 2:
            d, t = parts[0], parts[1]
            if d == date_str:
                busy.add(t)

    return busy


# ================= TIME =================

def get_time_kb(date_str):
    times = ["10:00","11:00","12:00","13:00",
             "14:00","15:00","16:00",
             "17:00","18:00","19:00"]

    busy = get_busy_slots(date_str)
    rows = []

    for t in times:
        if t in busy:
            rows.append([InlineKeyboardButton(
                text=f"❌ {t}",
                callback_data="busy"
            )])
        else:
            rows.append([InlineKeyboardButton(
                text=t,
                callback_data=f"time_{t}"
            )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= FSM =================

class Booking(StatesGroup):
    shoot_type = State()
    date = State()
    time = State()
    phone = State()
    confirm = State()


# ================= START =================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Бот записи на фотосессию 📸",
        reply_markup=start_kb
    )


@dp.message(lambda m: m.text == "▶️ Начать")
async def menu(message: Message):
    await message.answer("Меню:", reply_markup=menu_kb)


# ================= PORTFOLIO =================

@dp.message(lambda m: m.text == "📸 Портфолио")
async def portfolio(message: Message):
    sent = False
    for i in range(1, 11):
        path = f"photo{i}.jpg"
        if os.path.exists(path):
            await message.answer_photo(FSInputFile(path))
            sent = True

    if not sent:
        await message.answer("Портфолио пусто")


# ================= BOOKING =================

@dp.message(lambda m: m.text == "📅 Записаться")
async def booking_start(message: Message, state: FSMContext):
    await state.clear()

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❤️ Свадебная")],
            [KeyboardButton(text="🎤 Репортаж")],
            [KeyboardButton(text="📸 Индивидуальная")]
        ],
        resize_keyboard=True
    )

    await message.answer("Тип съемки:", reply_markup=kb)
    await state.set_state(Booking.shoot_type)


@dp.message(Booking.shoot_type)
async def booking_type(message: Message, state: FSMContext):
    await state.update_data(shoot_type=message.text)

    await message.answer("Выберите дату:", reply_markup=get_date_kb())
    await state.set_state(Booking.date)


@dp.callback_query(lambda c: c.data.startswith("date_"))
async def pick_date(callback: CallbackQuery, state: FSMContext):
    date = callback.data.replace("date_", "")
    await state.update_data(date=date)

    await callback.message.answer(
        "Выберите время:",
        reply_markup=get_time_kb(date)
    )

    await state.set_state(Booking.time)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "busy")
async def busy(callback: CallbackQuery):
    await callback.answer("Слот занят", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("time_"))
async def pick_time(callback: CallbackQuery, state: FSMContext):
    time = callback.data.replace("time_", "")

    data = await state.get_data()
    if time in get_busy_slots(data["date"]):
        await callback.answer("Уже занято", show_alert=True)
        return

    await state.update_data(time=time)

    await callback.message.answer(
        "Отправьте номер:",
        reply_markup=phone_kb
    )

    await state.set_state(Booking.phone)
    await callback.answer()


# ================= PHONE =================

@dp.message(Booking.phone)
async def booking_phone(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("Нажмите кнопку отправки номера")
        return

    await state.update_data(phone=message.contact.phone_number)
    data = await state.get_data()

    await message.answer(
        f"Проверьте:\n{data['shoot_type']}\n{data['date']} {data['time']}\n{data['phone']}",
        reply_markup=confirm_kb
    )

    await state.set_state(Booking.confirm)


# ================= CONFIRM =================

@dp.message(Booking.confirm)
async def confirm(message: Message, state: FSMContext):

    if message.text != "✅ Подтвердить":
        await message.answer("Отменено", reply_markup=start_kb)
        await state.clear()
        return

    data = await state.get_data()
    u = message.from_user

    record = (
        f"{data['date']} {data['time']} | "
        f"{data['shoot_type']} | {data['phone']} | "
        f"{u.full_name} | @{u.username} | id:{u.id}\n"
    )

    with open("bookings.txt", "a", encoding="utf-8") as f:
        f.write(record)

    await bot.send_message(ADMIN_ID, "📥 Новая заявка\n" + record)

    await message.answer(
        "✅ Записано\nМожно отменить через меню",
        reply_markup=menu_kb
    )

    await state.clear()


# ================= USER CANCEL =================

@dp.message(lambda m: m.text == "❌ Отменить мою запись")
async def cancel_my_booking(message: Message):
    uid = f"id:{message.from_user.id}"

    lines = read_bookings()
    new_lines = [l for l in lines if uid not in l]

    if len(lines) == len(new_lines):
        await message.answer("Запись не найдена")
        return

    write_bookings(new_lines)

    await message.answer("✅ Ваша запись отменена")


# ================= ADMIN CALENDAR =================

@dp.message(Command("admin_calendar"))
async def admin_calendar(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "Выберите дату:",
        reply_markup=get_date_kb(prefix="admin_date")
    )


@dp.callback_query(lambda c: c.data.startswith("admin_date_"))
async def admin_date(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    date = callback.data.replace("admin_date_", "")

    rows = []
    for line in read_bookings():
        if line.startswith(date):
            rows.append(line)

    text = "".join(rows) if rows else "Нет записей"

    await callback.message.answer(f"📅 {date}\n\n{text}")
    await callback.answer()


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
