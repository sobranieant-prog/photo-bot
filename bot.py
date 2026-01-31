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


# ================= FILE HELPERS =================

def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ================= DATE =================

def get_date_kb(prefix="date"):
    today = datetime.now()
    btns = []

    for i in range(14):
        d = today + timedelta(days=i)
        s = d.strftime("%d.%m.%Y")
        btns.append(
            InlineKeyboardButton(
                text=s,
                callback_data=f"{prefix}_{s}"
            )
        )

    rows = [btns[i:i+2] for i in range(0, len(btns), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def get_busy_slots(date):
    busy = set()
    for r in parse_bookings():
        if r["date"] == date:
            busy.add(r["time"])
    return busy


# ================= TIME =================

def get_time_kb(date):
    times = ["10:00","11:00","12:00","13:00",
             "14:00","15:00","16:00",
             "17:00","18:00","19:00"]

    busy = get_busy_slots(date)
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


# ================= CHECKLIST =================

CHECK_ITEMS = [
    "Созвон с клиентом",
    "Подтверждение локации",
    "Оборудование",
    "Свет",
    "Референсы",
    "Оплата",
    "Передача фото"
]


def get_check_state(idx):
    for line in read_lines("checklists.txt"):
        i, data = line.strip().split("|")
        if int(i) == idx:
            return data.split(",")
    return ["0"] * len(CHECK_ITEMS)


def save_check_state(idx, state):
    lines = read_lines("checklists.txt")
    new = []

    found = False
    for line in lines:
        i, _ = line.strip().split("|")
        if int(i) == idx:
            new.append(f"{idx}|{','.join(state)}\n")
            found = True
        else:
            new.append(line)

    if not found:
        new.append(f"{idx}|{','.join(state)}\n")

    write_lines("checklists.txt", new)


def checklist_kb(idx):
    state = get_check_state(idx)
    rows = []

    for n, item in enumerate(CHECK_ITEMS):
        mark = "✅" if state[n] == "1" else "⬜"
        rows.append([InlineKeyboardButton(
            text=f"{mark} {item}",
            callback_data=f"check_{idx}_{n}"
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
    await message.answer("Бот записи 📸", reply_markup=start_kb)


@dp.message(lambda m: m.text == "▶️ Начать")
async def menu(message: Message):
    await message.answer("Меню:", reply_markup=menu_kb)


# ================= PORTFOLIO =================

@dp.message(lambda m: m.text == "📸 Портфолио")
async def portfolio(message: Message):
    for i in range(1, 11):
        p = f"photo{i}.jpg"
        if os.path.exists(p):
            await message.answer_photo(FSInputFile(p))


# ================= BOOKING FLOW =================

@dp.message(lambda m: m.text == "📅 Записаться")
async def b_start(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Свадебная")],
            [KeyboardButton(text="Репортаж")],
            [KeyboardButton(text="Индивидуальная")]
        ],
        resize_keyboard=True
    )
    await message.answer("Тип съемки:", reply_markup=kb)
    await state.set_state(Booking.shoot_type)


@dp.message(Booking.shoot_type)
async def b_type(message: Message, state: FSMContext):
    await state.update_data(shoot_type=message.text)
    await message.answer("Дата:", reply_markup=get_date_kb())
    await state.set_state(Booking.date)


@dp.callback_query(lambda c: c.data.startswith("date_"))
async def b_date(cb: CallbackQuery, state: FSMContext):
    d = cb.data.split("_")[1]
    await state.update_data(date=d)
    await cb.message.answer("Время:", reply_markup=get_time_kb(d))
    await state.set_state(Booking.time)
    await cb.answer()


@dp.callback_query(lambda c: c.data == "busy")
async def busy(cb: CallbackQuery):
    await cb.answer("Занято", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("time_"))
async def b_time(cb: CallbackQuery, state: FSMContext):
    t = cb.data.split("_")[1]
    await state.update_data(time=t)
    await cb.message.answer("Телефон:", reply_markup=phone_kb)
    await state.set_state(Booking.phone)
    await cb.answer()


@dp.message(Booking.phone)
async def b_phone(message: Message, state: FSMContext):
    if not message.contact:
        return

    await state.update_data(phone=message.contact.phone_number)
    d = await state.get_data()

    await message.answer(
        f"{d['shoot_type']}\n{d['date']} {d['time']}\n{d['phone']}",
        reply_markup=confirm_kb
    )
    await state.set_state(Booking.confirm)


@dp.message(Booking.confirm)
async def b_confirm(message: Message, state: FSMContext):

    if message.text != "✅ Подтвердить":
        await state.clear()
        return

    d = await state.get_data()
    u = message.from_user

    rec = (
        f"{d['date']}|{d['time']}|{d['shoot_type']}|{d['phone']}|"
        f"{u.full_name}|@{u.username}|{u.id}|NEW\n"
    )

    with open("bookings.txt", "a", encoding="utf-8") as f:
        f.write(rec)

    await bot.send_message(ADMIN_ID, "Новая заявка\n" + rec)

    await message.answer("Записано", reply_markup=menu_kb)
    await state.clear()


# ================= USER CANCEL =================

@dp.message(lambda m: m.text == "❌ Отменить мою запись")
async def cancel_my(message: Message):
    uid = str(message.from_user.id)
    lines = read_lines("bookings.txt")
    new = [l for l in lines if f"|{uid}|" not in l]
    write_lines("bookings.txt", new)
    await message.answer("Отменено")


# ================= CRM =================

@dp.message(Command("crm"))
async def crm(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = parse_bookings()
    kb = [[InlineKeyboardButton(
        text=f"{r['date']} {r['time']} — {r['name']}",
        callback_data=f"card_{r['index']}"
    )] for r in rows]

    await message.answer(
        "CRM заявки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(lambda c: c.data.startswith("card_"))
async def crm_card(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    r = parse_bookings()[idx]

    text = (
        f"{r['name']}\n{r['phone']}\n"
        f"{r['date']} {r['time']}\n"
        f"{r['type']}\nСтатус: {r['status']}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✉️ Написать",
            url=f"tg://user?id={r['user_id']}"
        )],
        [InlineKeyboardButton(
            text="📋 Чек-лист",
            callback_data=f"checkopen_{idx}"
        )],
        [InlineKeyboardButton(
            text="✅ DONE",
            callback_data=f"done_{idx}"
        )],
        [InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"del_{idx}"
        )]
    ])

    await cb.message.answer(text, reply_markup=kb)


@dp.callback_query(lambda c: c.data.startswith("done_"))
async def crm_done(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    lines = read_lines("bookings.txt")
    p = lines[idx].strip().split("|")
    p[7] = "DONE"
    lines[idx] = "|".join(p) + "\n"
    write_lines("bookings.txt", lines)
    await cb.answer("DONE")


@dp.callback_query(lambda c: c.data.startswith("del_"))
async def crm_del(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    lines = read_lines("bookings.txt")
    lines.pop(idx)
    write_lines("bookings.txt", lines)
    await cb.answer("Удалено")


# ================= CHECKLIST =================

@dp.callback_query(lambda c: c.data.startswith("checkopen_"))
async def check_open(cb: CallbackQuery):
    idx = int(cb.data.split("_")[1])
    await cb.message.answer(
        "Чек-лист:",
        reply_markup=checklist_kb(idx)
    )


@dp.callback_query(lambda c: c.data.startswith("check_"))
async def check_toggle(cb: CallbackQuery):
    _, idx, n = cb.data.split("_")
    idx = int(idx)
    n = int(n)

    state = get_check_state(idx)
    state[n] = "0" if state[n] == "1" else "1"
    save_check_state(idx, state)

    await cb.message.edit_reply_markup(
        reply_markup=checklist_kb(idx)
    )
    await cb.answer()


# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
