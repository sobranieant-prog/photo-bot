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
        [KeyboardButton(text="📅 Записаться")]
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


# ================= DATE KEYBOARD =================

def get_date_kb():
    today = datetime.now()
    buttons = []

    for i in range(14):
        d = today + timedelta(days=i)
        text = d.strftime("%d.%m.%Y")
        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"date_{text}"
            )
        )

    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= BUSY SLOTS =================

def get_busy_slots(date_str):
    busy = set()

    if not os.path.exists("bookings.txt"):
        return busy

    with open("bookings.txt", encoding="utf-8") as f:
        for line in f:
            if "|" not in line:
                continue

            left = line.split("|")[0].strip()
            parts = left.split()

            if len(parts) >= 2:
                d, t = parts[0], parts[1]
                if d == date_str:
                    busy.add(t)

    return busy


# ================= TIME KEYBOARD =================

def get_time_kb(date_str):
    times = [
        "10:00","11:00","12:00","13:00",
        "14:00","15:00","16:00",
        "17:00","18:00","19:00"
    ]

    busy = get_busy_slots(date_str)
    rows = []

    for t in times:
        if t in busy:
            rows.append([
                InlineKeyboardButton(
                    text=f"❌ {t}",
                    callback_data="busy"
                )
            ])
        else:
            rows.append([
                InlineKeyboardButton(
                    text=t,
                    callback_data=f"time_{t}"
                )
            ])

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
        "Привет! Я бот записи на фотосессию 📸",
        reply_markup=start_kb
    )


@dp.message(lambda m: m.text == "▶️ Начать")
async def menu(message: Message):
    await message.answer("Выберите действие:", reply_markup=menu_kb)


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

    await message.answer("Тип фотосессии:", reply_markup=kb)
    await state.set_state(Booking.shoot_type)


@dp.message(Booking.shoot_type)
async def booking_type(message: Message, state: FSMContext):
    await state.update_data(shoot_type=message.text)

    await message.answer(
        "Выберите дату:",
        reply_markup=get_date_kb()
    )

    await state.set_state(Booking.date)


# ================= DATE =================

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


# ================= BUSY CLICK =================

@dp.callback_query(lambda c: c.data == "busy")
async def busy_click(callback: CallbackQuery):
    await callback.answer("Это время уже занято", show_alert=True)


# ================= TIME =================

@dp.callback_query(lambda c: c.data.startswith("time_"))
async def pick_time(callback: CallbackQuery, state: FSMContext):
    time = callback.data.replace("time_", "")

    data = await state.get_data()
    busy = get_busy_slots(data["date"])

    if time in busy:
        await callback.answer("Слот уже занят", show_alert=True)
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
        await message.answer("Нажмите кнопку отправки номера 👇")
        return

    await state.update_data(phone=message.contact.phone_number)
    data = await state.get_data()

    await message.answer(
        f"Проверьте заявку:\n\n"
        f"📷 {data['shoot_type']}\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}\n"
        f"📞 {data['phone']}",
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

    user = message.from_user
    name = user.full_name
    username = f"@{user.username}" if user.username else "нет username"
    user_id = user.id

    record = (
        f"{data['date']} {data['time']} | "
        f"{data['shoot_type']} | "
        f"{data['phone']} | "
        f"{name} | {username} | id:{user_id}\n"
    )

    with open("bookings.txt", "a", encoding="utf-8") as f:
        f.write(record)

    await bot.send_message(
        ADMIN_ID,
        f"📥 НОВАЯ ЗАЯВКА\n\n"
        f"👤 Имя: {name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 ID: {user_id}\n\n"
        f"📷 {data['shoot_type']}\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}\n"
        f"📞 {data['phone']}"
    )

    await message.answer("✅ Запись сохранена", reply_markup=start_kb)
    await state.clear()


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
