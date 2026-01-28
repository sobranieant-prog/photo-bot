from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

import os
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not found in environment variables")

ADMIN_ID = 1428673148 

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

phone_kb = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,
    keyboard=[
        [KeyboardButton(text="📞 Отправить номер", request_contact=True)]
    ]
)

class Booking(StatesGroup):
    shoot_type = State()
    datetime = State()
    phone = State()

@dp.message(Command("start"))
async def start(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="▶️ Начать")]],
        resize_keyboard=True
    )
    await message.answer(
        "Привет! Я бот для записи на фотосессию 📸\n\nНажмите «Начать» 👇",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text == "▶️ Начать")
async def start_menu(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Портфолио")],
            [KeyboardButton(text="📅 Записаться")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите действие:", reply_markup=keyboard)


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




@dp.message(lambda m: m.text == "📅 Записаться")
async def booking_start(message: Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❤️ Свадебная")],
            [KeyboardButton(text="🎤 Репортаж / корпоратив")],
            [KeyboardButton(text="📸 Индивидуальная / Семейная")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите тип фотосессии:", reply_markup=keyboard)
    await state.set_state(Booking.shoot_type)

@dp.message(Booking.shoot_type)
async def booking_type(message: Message, state: FSMContext):
    await state.update_data(shoot_type=message.text)
    await message.answer("📅 Напишите дату и время\nПример: 12.02 с 14:00 до 16:00")
    await state.set_state(Booking.datetime)

@dp.message(Booking.datetime)
async def booking_datetime(message: Message, state: FSMContext):
    date_text = message.text.strip()

    try:
        with open("bookings.txt", "r", encoding="utf-8") as f:
            booked = f.read().splitlines()
    except FileNotFoundError:
        booked = []

    if date_text in booked:
        await message.answer("❌ Это время уже занято. Выберите другое.")
        return

    await state.update_data(datetime=date_text)

    await message.answer(
        "📞 Отлично!\nТеперь отправьте номер телефона 👇",
        reply_markup=phone_kb
    )
    await state.set_state(Booking.phone)


@dp.message(Booking.phone)
async def booking_phone(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("❗ Пожалуйста, нажмите кнопку и отправьте номер")
        return

    phone = message.contact.phone_number
    data = await state.get_data()

    # сохраняем дату в файл
    with open("bookings.txt", "a", encoding="utf-8") as f:
        f.write(data["datetime"] + "\n")

    user = message.from_user

    text = (
        "📸 НОВАЯ ЗАЯВКА\n\n"
        f"👤 Имя: {user.first_name}\n"
        f"🔗 Username: @{user.username if user.username else 'нет'}\n"
        f"🆔 Telegram ID: {user.id}\n"
        f"📞 Телефон: {phone}\n\n"
        f"📷 Тип съёмки: {data['shoot_type']}\n"
        f"📅 Дата и время: {data['datetime']}"
    )

    await bot.send_message(ADMIN_ID, text)

    await message.answer(
        "✅ Заявка принята!\nМы свяжемся с вами в ближайшее время 📞",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="▶️ Начать")]],
            resize_keyboard=True
        )
    )

    await state.clear()
