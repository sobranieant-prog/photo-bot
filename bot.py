import asyncio
import os
import calendar
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


# ================== CONFIG ==================

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not found")

ADMIN_ID = 1428673148

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================== KEYBOARDS ==================

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

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

phone_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📞 Отправить номер", request_contact=True)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

confirm_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="✅ Подтвердить"),
            KeyboardButton(text="❌ Отменить")
        ]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Все записи")],
        [KeyboardButton(text="📅 Сегодня")],
        [KeyboardButton(text="🗑 Очистить записи")]
    ],
    resize_keyboard=True
)


# ================== CALENDAR ==================

def get_calendar_kb(year=None, month=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    cal = calendar.monthcalendar(year, month)

    rows = []

    rows.append([
        InlineKeyboardButton(text=d, callback_data="ignore")
        for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    ])

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{year}-{month:02d}-{day:02d}"
                    )
                )
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_time_kb():
    times = ["10:00","12:00","14:00","16:00","18:00","20:00"]

    buttons = [
        InlineKeyboardButton(text=t, callback_data=f"time_{t}")
        for t in times
    ]

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# ================== FSM ==================

class Booking(StatesGroup):
    shoot_type = State()
    date = State()
    time = State()
    phone = State()
    confirm = State()


# ================== START ==================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привет! Я бот для записи на фотосессию 📸",
        reply_markup=start_kb
    )


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа")
        return

    await message.answer("Админ-панель:", reply_markup=admin_kb)


# ================== MENU ==================

@dp.message(lambda m: m.text == "▶️ Начать")
async def start_menu(message: Message):
    await message.answer("Выберите действие:", reply_markup=menu_kb)


@dp.message(lambda m: m.text == "📸 Портфолио")
async def portfolio(message: Message):
    found = False
    for i in range(1, 11):
        path = f"photo{i}.jpg"
        if os.path.exists(path):
            await message.answer_photo(FSInputFile(path))
            found = True

    if not found:
        await message.answer("📂 Портфолио пока пустое")


# ================== BOOKING FLOW ==================

@dp.message(lambda m: m.text == "📅 Записаться")
async def booking_start(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❤️ Свадебная")],
            [KeyboardButton(text="🎤 Репортаж")],
            [KeyboardButton(text="📸 Индивидуальная")]
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите тип съёмки:", reply_markup=kb)
    await state.set_state(Booking.shoot_type)


@dp.message(Booking.shoot_type)
async def booking_type(message: Message, state: FSMContext):
    await state.update_data(shoot_type=message.text)

    await message.answer(
        "📅 Выберите дату:",
        reply_markup=get_calendar_kb()
    )
    await state.set_state(Booking.date)


# ---------- DATE PICK ----------

@dp.callback_query(lambda c: c.data.startswith("date_"))
async def pick_date(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[1]
    await state.update_data(date=date)

    await callback.message.answer(
        "⏰ Выберите время:",
        reply_markup=get_time_kb()
    )

    await state.set_state(Booking.time)
    await callback.answer()


# ---------- TIME PICK ----------

@dp.callback_query(lambda c: c.data.startswith("time_"))
async def pick_time(callback: CallbackQuery, state: FSMContext):
    time = callback.data.split("_")[1]
    data = await state.get_data()

    slot = f"{data['date']} {time}"

    try:
        with open("bookings.txt", "r") as f:
            booked = f.read().splitlines()
    except:
        booked = []

    if slot in booked:
        await callback.message.answer("❌ Слот занят")
        await callback.answer()
        return

    await state.update_data(time=time)

    await callback.message.answer(
        "📞 Отправьте номер телефона",
        reply_markup=phone_kb
    )

    await state.set_state(Booking.phone)
    await callback.answer()


# ---------- PHONE ----------

@dp.message(Booking.phone)
async def booking_phone(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("Нажмите кнопку отправки номера")
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


# ---------- CONFIRM ----------

@dp.message(Booking.confirm)
async def booking_confirm(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await message.answer("Заявка отменена", reply_markup=start_kb)
        await state.clear()
        return

    if message.text != "✅ Подтвердить":
        return

    data = await state.get_data()
    slot = f"{data['date']} {data['time']}"

    with open("bookings.txt", "a") as f:
        f.write(slot + "\n")

    await bot.send_message(
        ADMIN_ID,
        f"📸 Новая заявка\n\n"
        f"{data['shoot_type']}\n"
        f"{slot}\n"
        f"{data['phone']}"
    )

    await message.answer("✅ Запись принята!", reply_markup=start_kb)
    await state.clear()


# ================== CANCEL ==================

@dp.message(lambda m: m.text == "❌ Отмена")
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено", reply_markup=start_kb)


# ================== ADMIN ==================

@dp.message(lambda m: m.text == "📋 Все записи")
async def admin_all(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        with open("bookings.txt") as f:
            data = f.read()
    except:
        data = ""

    await message.answer(data or "Записей нет")


@dp.message(lambda m: m.text == "📅 Сегодня")
async def admin_today(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    today = datetime.now().strftime("%Y-%m-%d")

    try:
        with open("bookings.txt") as f:
            lines = f.read().splitlines()
    except:
        lines = []

    result = [x for x in lines if today in x]
    await message.answer("\n".join(result) or "Сегодня пусто")


@dp.message(lambda m: m.text == "🗑 Очистить записи")
async def admin_clear(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    open("bookings.txt", "w").close()
    await message.answer("Очищено")


# ================== RUN ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
