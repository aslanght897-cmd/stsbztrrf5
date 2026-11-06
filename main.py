import asyncio
import os
import random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

START_BALANCE = 100
MIN_BET = 10
MAX_BET = 50

ANTI_MINUS_ENABLED = True
BASKETBALL_WIN_CHANCE_ON = 0.40
BASKETBALL_WIN_CHANCE_OFF = 0.50

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
balances = {}

class BetStates(StatesGroup):
    waiting_basketball_amount = State()
    waiting_roulette_amount = State()
    waiting_roulette_choice = State()

def get_balance(user_id: int) -> int:
    return balances.get(user_id, START_BALANCE)

def change_balance(user_id: int, delta: int):
    balances[user_id] = get_balance(user_id) + delta

def get_basketball_chance() -> float:
    return BASKETBALL_WIN_CHANCE_ON if ANTI_MINUS_ENABLED else BASKETBALL_WIN_CHANCE_OFF

def main_kb(user_id: int = None):
    buttons = [
        [InlineKeyboardButton(text="🏀 Баскетбол", callback_data="play_basketball")],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="play_roulette")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="➕ Пополнить (+50)", callback_data="refill")],
    ]
    if user_id == ADMIN_ID:
        status = "ВКЛ ✅" if ANTI_MINUS_ENABLED else "ВЫКЛ ❌"
        buttons.append([InlineKeyboardButton(
            text=f"⚙️ Антиминус: {status}",
            callback_data="toggle_antimminus"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id not in balances:
        balances[user_id] = START_BALANCE

    status = "включён" if ANTI_MINUS_ENABLED else "выключен"
    await message.answer(
        f"Демо-казино (только виртуальные очки)\n\n"
        f"Баланс: <b>{get_balance(user_id)}</b> очков\n"
        f"Антиминус сейчас: <b>{status}</b>\n\n"
        f"Это симуляция. Реальных денег нет.",
        reply_markup=main_kb(user_id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    await callback.message.edit_text(
        f"💰 Твой баланс: <b>{get_balance(callback.from_user.id)}</b> очков",
        reply_markup=main_kb(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "refill")
async def refill(callback: CallbackQuery):
    change_balance(callback.from_user.id, 50)
    await callback.message.edit_text(
        f"Виртуально пополнено +50\nНовый баланс: <b>{get_balance(callback.from_user.id)}</b>",
        reply_markup=main_kb(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "toggle_antimminus")
async def toggle_antimminus(callback: CallbackQuery):
    global ANTI_MINUS_ENABLED
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Только для администратора", show_alert=True)
        return

    ANTI_MINUS_ENABLED = not ANTI_MINUS_ENABLED
    status = "ВКЛЮЧЁН ✅" if ANTI_MINUS_ENABLED else "ВЫКЛЮЧЕН ❌"
    await callback.message.edit_text(
        f"Антиминус теперь: <b>{status}</b>\n\n"
        f"Баскетбол: шанс игрока {int(get_basketball_chance()*100)}%\n"
        f"Рулетка: всегда европейская (с 0)",
        reply_markup=main_kb(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer(f"Антиминус {status}")

@dp.callback_query(F.data == "play_basketball")
async def basketball_start(callback: CallbackQuery, state: FSMContext):
    balance = get_balance(callback.from_user.id)
    if balance < MIN_BET:
        await callback.answer("Недостаточно очков", show_alert=True)
        return

    chance = int(get_basketball_chance() * 100)
    await state.set_state(BetStates.waiting_basketball_amount)
    await callback.message.edit_text(
        f"🏀 <b>Баскетбол</b>\n"
        f"Ставка от {MIN_BET} до {MAX_BET}\n"
        f"Шанс выигрыша игрока: <b>{chance}%</b>\n"
        f"{'(антиминус включён)' if ANTI_MINUS_ENABLED else '(честный режим)'}\n\n"
        f"Введи сумму ставки:",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(BetStates.waiting_basketball_amount)
async def basketball_bet(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("Введи число")
        return

    balance = get_balance(message.from_user.id)
    if amount < MIN_BET or amount > MAX_BET or amount > balance:
        await message.answer(f"Ставка от {MIN_BET} до {min(MAX_BET, balance)}")
        return

    win = random.random() < get_basketball_chance()

    if win:
        change_balance(message.from_user.id, amount)
        result = f"✅ Попал! +{amount}"
    else:
        change_balance(message.from_user.id, -amount)
        result = f"❌ Мимо. -{amount}"

    await state.clear()
    await message.answer(
        f"{result}\nБаланс: <b>{get_balance(message.from_user.id)}</b>",
        reply_markup=main_kb(message.from_user.id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "play_roulette")
async def roulette_start(callback: CallbackQuery, state: FSMContext):
    balance = get_balance(callback.from_user.id)
    if balance < MIN_BET:
        await callback.answer("Недостаточно очков", show_alert=True)
        return

    await state.set_state(BetStates.waiting_roulette_amount)
    await callback.message.edit_text(
        f"🎰 <b>Рулетка</b> (европейская 0–36)\n"
        f"Ставка от {MIN_BET} до {MAX_BET}\n\n"
        f"Введи сумму ставки:",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(BetStates.waiting_roulette_amount)
async def roulette_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("Введи число")
        return

    balance = get_balance(message.from_user.id)
    if amount < MIN_BET or amount > MAX_BET or amount > balance:
        await message.answer(f"Ставка от {MIN_BET} до {min(MAX_BET, balance)}")
        return

    await state.update_data(bet_amount=amount)
    await state.set_state(BetStates.waiting_roulette_choice)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Красное", callback_data="r_red"),
            InlineKeyboardButton(text="⚫ Чёрное", callback_data="r_black"),
        ],
        [InlineKeyboardButton(text="🟢 Зеро (0)", callback_data="r_zero")],
    ])
    await message.answer("Выбери:", reply_markup=kb)

@dp.callback_query(F.data.startswith("r_"), BetStates.waiting_roulette_choice)
async def roulette_play(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data["bet_amount"]
    choice = callback.data

    number = random.randint(0, 36)
    red = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

    if number == 0:
        color = "zero"
    elif number in red:
        color = "red"
    else:
        color = "black"

    win = False
    payout = 0

    if choice == "r_zero" and color == "zero":
        win = True
        payout = amount * 35
    elif choice == "r_red" and color == "red":
        win = True
        payout = amount
    elif choice == "r_black" and color == "black":
        win = True
        payout = amount

    if win:
        change_balance(callback.from_user.id, payout)
        text = f"Выпало: <b>{number}</b> ({'🔴' if color == 'red' else '⚫' if color == 'black' else '🟢'})\n✅ Выигрыш +{payout}"
    else:
        change_balance(callback.from_user.id, -amount)
        text = f"Выпало: <b>{number}</b> ({'🔴' if color == 'red' else '⚫' if color == 'black' else '🟢'})\n❌ Проигрыш -{amount}"

    await state.clear()
    await callback.message.edit_text(
        f"{text}\nБаланс: <b>{get_balance(callback.from_user.id)}</b>",
        reply_markup=main_kb(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен")
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
