print("BOT STARTED")

import os
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State



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
    keyboard=[
        [KeyboardButton(text="📞 Отправить номер", request_contact=True)]
    ],
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

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Все записи")],
        [KeyboardButton(text="🗑 Очистить записи")]
    ],
    resize_keyboard=True
)


# ================= CALENDAR =================

MONTHS_RU = [
    "", "Январь","Февраль","Март","Апрель","Май","Июнь",
    "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"
]


def get_calendar_kb(year=None, month=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    kb = []

    # заголовок
    kb.append([
        InlineKeyboardButton(
            text=f"{calendar.month_name[month]} {year}",
            callback_data="ignore"
        )
    ])

    # дни недели
    kb.append([
        InlineKeyboardButton(text=d, callback_data="ignore")
        for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    ])

    cal = calendar.monthcalendar(year, month)

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(
                    InlineKeyboardButton(text=" ", callback_data="ignore")
                )
            else:
                row.append(
                    InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{year}_{month}_{day}"
                    )
                )
        kb.append(row)

    # переключение месяцев
    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year

    next_month = month + 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year

    kb.append([
        InlineKeyboardButton(
            text="⬅️",
            callback_data=f"cal_{prev_year}_{prev_month}"
        ),
        InlineKeyboardButton(
            text="➡️",
            callback_data=f"cal_{next_year}_{next_month}"
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_time_kb():
    times = [
        "10:00","11:00","12:00","13:00","14:00",
        "15:00","16:00","17:00","18:00","19:00"
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=f"time_{t}")]
            for t in times
        ]
    )


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
    found = False
    for i in range(1, 11):
        path = f"photo{i}.jpg"
        if os.path.exists(path):
            await message.answer_photo(FSInputFile(path))
            found = True

    if not found:
        await message.answer("Портфолио пусто")


# ================= BOOKING FLOW =================

@dp.message(lambda m: m.text == "📅 Записаться")
async def booking_start(message: Message, state: FSMContext):
    await state.clear()

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❤️ Свадебная")],
            [KeyboardButton(text="🎤 Репортаж / Корпоратив")],
            [KeyboardButton(text="📸 Индивидуальная / Семейная")]
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите тип фотосессии:", reply_markup=kb)
    await state.set_state(Booking.shoot_type)


@dp.message(Booking.shoot_type)
async def booking_type(message: Message, state: FSMContext):

    valid = [
        "❤️ Свадебная",
        "🎤 Репортаж / Корпоратив",
        "📸 Индивидуальная / Семейная"
    ]

    if message.text not in valid:
        await message.answer("Нажмите кнопку выбора 👇")
        return

    await state.update_data(shoot_type=message.text)

    await message.answer(
        "📅 Выберите дату:",
        reply_markup=get_calendar_kb()
    )

    await state.set_state(Booking.date)


# ================= CALENDAR =================

@dp.callback_query(lambda c: c.data.startswith("cal_"))
async def change_month(callback: CallbackQuery):
    _, y, m = callback.data.split("_")
    await callback.message.edit_reply_markup(
        reply_markup=get_calendar_kb(int(y), int(m))
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "ignore")
async def ignore(callback: CallbackQuery):
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("date_"))
async def pick_date(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[1]
    await state.update_data(date=date)

    await callback.message.answer(
        "Выберите время:",
        reply_markup=get_time_kb()
    )

    await state.set_state(Booking.time)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("time_"))
async def pick_time(callback: CallbackQuery, state: FSMContext):
    time = callback.data.split("_")[1]
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

    phone = message.contact.phone_number
    await state.update_data(phone=phone)

    data = await state.get_data()

    await message.answer(
        f"Проверьте заявку:\n\n"
        f"📷 Тип: {data['shoot_type']}\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}\n"
        f"📞 Телефон: {phone}",
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

    with open("bookings.txt", "a", encoding="utf-8") as f:
        f.write(
            f"{data['date']} {data['time']} | "
            f"{data['shoot_type']} | "
            f"{data['phone']}\n"
        )

    await bot.send_message(
        ADMIN_ID,
        f"НОВАЯ ЗАЯВКА:\n"
        f"{data['date']} {data['time']}\n"
        f"{data['shoot_type']}\n"
        f"{data['phone']}"
    )

    await message.answer("✅ Запись сохранена", reply_markup=start_kb)
    await state.clear()


# ================= ADMIN =================

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Админ панель", reply_markup=admin_kb)


@dp.message(lambda m: m.text == "📋 Все записи")
async def admin_all(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        with open("bookings.txt", encoding="utf-8") as f:
            await message.answer(f.read() or "Пусто")
    except:
        await message.answer("Файл не найден")


@dp.message(lambda m: m.text == "🗑 Очистить записи")
async def admin_clear(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    open("bookings.txt", "w").close()
    await message.answer("Очищено")


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
