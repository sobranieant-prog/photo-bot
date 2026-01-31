import os
import asyncio
import calendar
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

ADMIN_ID = 1428673148
MAX_BOOK_MONTHS = 6

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= FILE =================

def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ================= BOOKINGS =================

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


def slot_busy(date, time):
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
    keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)


# ================= FSM =================

class Booking(StatesGroup):
    shoot = State()
    date = State()
    time = State()
    phone = State()


# ================= CALENDAR =================

def get_calendar(year=None, month=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    limit = now + timedelta(days=30 * MAX_BOOK_MONTHS)

    kb = []

    kb.append([InlineKeyboardButton(
        text=f"{calendar.month_name[month]} {year}",
        callback_data="ignore"
    )])

    kb.append([
        InlineKeyboardButton(text=d, callback_data="ignore")
        for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    ])

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                d = datetime(year, month, day)
                if d.date() < now.date() or d > limit:
                    row.append(InlineKeyboardButton(text="—", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{year}_{month}_{day}"
                    ))
        kb.append(row)

    prev_m = 12 if month == 1 else month-1
    prev_y = year-1 if month == 1 else year

    next_m = 1 if month == 12 else month+1
    next_y = year+1 if month == 12 else year

    nav = [InlineKeyboardButton("⬅️", callback_data=f"cal_{prev_y}_{prev_m}")]

    if datetime(next_y, next_m, 1) <= limit:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"cal_{next_y}_{next_m}"))

    kb.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_time_kb(date):
    times = ["10:00","11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00"]
    rows = []

    for t in times:
        text = f"{t} ❌" if slot_busy(date, t) else t
        rows.append([InlineKeyboardButton(text=text, callback_data=f"time_{t}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= START =================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Бот записи на фотосессию 📸", reply_markup=start_kb)


@dp.message(lambda m: m.text == "▶️ Начать")
async def menu(message: Message):
    await message.answer("Меню:", reply_markup=menu_kb)


# ================= PORTFOLIO =================

@dp.message(lambda m: m.text == "📸 Портфолио")
async def portfolio(message: Message):
    sent = False
    for i in range(1, 6):
        p = f"photo{i}.jpg"
        if os.path.exists(p):
            await message.answer_photo(FSInputFile(p))
            sent = True
    if not sent:
        await message.answer("Портфолио пока пусто")


# ================= BOOKING =================

@dp.message(lambda m: m.text == "📅 Записаться")
async def book_start(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Свадебная")],
            [KeyboardButton(text="Корпоративная")],
            [KeyboardButton(text="Репортажная")],
            [KeyboardButton(text="Индивидуальная")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите тип съёмки:", reply_markup=kb)
    await state.set_state(Booking.shoot)


@dp.message(Booking.shoot)
async def book_type(message: Message, state: FSMContext):
    await state.update_data(shoot=message.text)
    await message.answer("Выберите дату:", reply_markup=get_calendar())
    await state.set_state(Booking.date)


@dp.callback_query(lambda c: c.data.startswith("cal_"))
async def cal_move(cb: CallbackQuery):
    _, y, m = cb.data.split("_")
    await cb.message.edit_reply_markup(reply_markup=get_calendar(int(y), int(m)))
    await cb.answer()


@dp.callback_query(lambda c: c.data == "ignore")
async def ign(cb: CallbackQuery):
    await cb.answer()


@dp.callback_query(lambda c: c.data.startswith("date_"))
async def pick_date(cb: CallbackQuery, state: FSMContext):
    _, y, m, d = cb.data.split("_")
    picked = datetime(int(y), int(m), int(d))
    limit = datetime.now() + timedelta(days=30 * MAX_BOOK_MONTHS)

    if picked > limit:
        await cb.answer("Доступно только на 6 месяцев вперёд", show_alert=True)
        return

    date = f"{d.zfill(2)}.{m.zfill(2)}.{y}"
    await state.update_data(date=date)

    await cb.message.answer("Выберите время:", reply_markup=get_time_kb(date))
    await state.set_state(Booking.time)
    await cb.answer()


@dp.callback_query(lambda c: c.data.startswith("time_"))
async def pick_time(cb: CallbackQuery, state: FSMContext):
    t = cb.data.split("_")[1]
    data = await state.get_data()

    if slot_busy(data["date"], t):
        await cb.answer("Слот занят", show_alert=True)
        return

    await state.update_data(time=t)
    await cb.message.answer("Отправьте телефон:", reply_markup=phone_kb)
    await state.set_state(Booking.phone)
    await cb.answer()


@dp.message(Booking.phone)
async def save_phone(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("Нажмите кнопку отправки номера")
        return

    data = await state.get_data()
    u = message.from_user

    record = (
        f"{data['date']}|{data['time']}|{data['shoot']}|"
        f"{message.contact.phone_number}|{u.full_name}|"
        f"@{u.username}|{u.id}|NEW\n"
    )

    with open("bookings.txt","a",encoding="utf-8") as f:
        f.write(record)

    await bot.send_message(
        ADMIN_ID,
        f"""📥 <b>НОВАЯ ЗАЯВКА</b>

👤 {u.full_name}
{('@'+u.username) if u.username else ''}

📞 {message.contact.phone_number}

📸 {data['shoot']}
📅 {data['date']}
⏰ {data['time']}

Статус: 🟡 NEW
""",
        parse_mode="HTML"
    )

    await message.answer("✅ Вы успешно записаны!", reply_markup=start_kb)
    await state.clear()


# ================= USER CANCEL =================

@dp.message(lambda m: m.text == "❌ Моя запись")
async def my_book(message: Message):
    uid = str(message.from_user.id)
    kb = []

    for r in parse_bookings():
        if r["user_id"] == uid:
            kb.append([InlineKeyboardButton(
                text=f"{r['date']} {r['time']}",
                callback_data=f"ucancel_{r['index']}"
            )])

    if not kb:
        await message.answer("У вас нет активных записей")
        return

    await message.answer(
        "Ваши записи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(lambda c: c.data.startswith("ucancel_"))
async def user_cancel(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    lines = read_lines("bookings.txt")

    if idx >= len(lines):
        return

    p = lines[idx].strip().split("|")
    lines.pop(idx)
    write_lines("bookings.txt", lines)

    await cb.message.answer(
        f"❌ <b>Запись отменена</b>\n\n📸 {p[2]}\n📅 {p[0]}\n⏰ {p[1]}",
        parse_mode="HTML"
    )

    await bot.send_message(
        ADMIN_ID,
        f"""🚫 <b>ОТМЕНА ЗАПИСИ</b>

👤 {p[4]}
{p[5]}

📸 {p[2]}
📅 {p[0]}
⏰ {p[1]}
📞 {p[3]}
""",
        parse_mode="HTML"
    )

    await cb.answer()


# ================= CRM =================

@dp.message(lambda m: m.text == "📊 CRM")
async def crm_btn(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = parse_bookings()
    if not rows:
        await message.answer("Заявок нет")
        return

    kb = [[InlineKeyboardButton(
        text=f"{r['date']} {r['time']} — {r['name']}",
        callback_data=f"card_{r['index']}"
    )] for r in rows]

    await message.answer(
        "📊 CRM заявки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(lambda c: c.data.startswith("card_"))
async def card(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    r = parse_bookings()[idx]

    status_map = {"NEW":"🟡 Новая","DONE":"🟢 Выполнена"}

    text = (
        f"👤 <b>{r['name']}</b>\n"
        f"{r['username']}\n"
        f"📞 {r['phone']}\n\n"
        f"📸 {r['type']}\n"
        f"📅 {r['date']} {r['time']}\n"
        f"{status_map.get(r['status'], r['status'])}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать", url=f"tg://user?id={r['user_id']}")],
        [InlineKeyboardButton(text="✅ DONE", callback_data=f"done_{idx}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{idx}")]
    ])

    await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


@dp.callback_query(lambda c: c.data.startswith("done_"))
async def done(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    lines = read_lines("bookings.txt")
    p = lines[idx].strip().split("|")
    p[7] = "DONE"
    lines[idx] = "|".join(p) + "\n"
    write_lines("bookings.txt", lines)
    await cb.answer("✅ Отмечено выполненным")


@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    lines = read_lines("bookings.txt")
    lines.pop(idx)
    write_lines("bookings.txt", lines)
    await cb.answer("Удалено")


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
