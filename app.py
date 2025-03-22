from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
import asyncio
import sqlite3
from datetime import datetime, timedelta


TOKEN = "8131510121:AAGR7IVolw0HEYPwKZ2gv2FC6qcY3D1aHs0"
ADMINS = [5699757894,8131510121]
bot = Bot(token=TOKEN)
dp = Dispatcher()


class TestStates(StatesGroup):
    selecting_subject = State()
    entering_answers = State()
    finishing_test = State()
    checking_test = State()


class AnswerStates(StatesGroup):
    get_code = State()
    enter_answers = State()

class BroadCast(StatesGroup):
    text = State()

def get_db_connection():
    conn = sqlite3.connect("test_bot.db")
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS tests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subject TEXT,
                        answers TEXT,
                        author_id INTEGER,
                        status TEXT DEFAULT 'open')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        full_name TEXT,
                        chatId INTEGER,
                        test_id INTEGER,
                        user_answers TEXT,
                        correct_count INTEGER,
                        incorrect_count INTEGER,
                        accuracy REAL)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS User(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER UNIQUE,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
create_tables()


async def get_statistics():

    conn = sqlite3.connect("test_bot.db")
    cursor = conn.cursor()

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    first_day_of_month = today.replace(day=1)

    cursor.execute("SELECT COUNT(*) FROM User WHERE DATE(joined_at) = ?", (today,))
    today_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM User WHERE DATE(joined_at) = ?", (yesterday,))
    yesterday_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM User WHERE DATE(joined_at) >= ?", (first_day_of_month,))
    month_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM User")
    total_count = cursor.fetchone()[0]

    conn.close()

    return today_count, yesterday_count, month_count, total_count

@dp.message(Command("start"))
async def start_handler(message: Message):

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Test yaratish", callback_data="create_test")],
        [InlineKeyboardButton(text="📊 Test natijalarini ko‘rish", callback_data="view_ranking")],
        [InlineKeyboardButton(text="⛔ Testni yakunlash", callback_data="stop_test")],
        [InlineKeyboardButton(text="🏆 Umumiy reyting", callback_data="view_results")],
        [InlineKeyboardButton(text="🗄️ Admin Panelga Kirish", callback_data="enter_panel")]
    ])
    user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Testni tekshirish", callback_data="check_test")],
        [InlineKeyboardButton(text="🏆 Umumiy reyting", callback_data="view_results")]
    ])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT OR IGNORE INTO User (telegram_id) VALUES (?)", (message.from_user.id,))

    conn.commit()
    conn.close()

    if message.from_user.id in ADMINS:
        await message.answer("Assalomu aleykum! Kerakli bo‘limni tanlang:", reply_markup=admin_keyboard)
    else:
        await message.answer("Assalomu aleykum! Kerakli bo‘limni tanlang:", reply_markup=user_keyboard)

#CREATE TEST

@dp.callback_query(F.data == "create_test")
async def create_test_handler(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer("Sizda ushbu bo‘limga ruxsat yo‘q!", show_alert=True)
        return
    await call.message.answer("Fan nomini kiriting:")
    await state.set_state(TestStates.selecting_subject)


@dp.message(TestStates.selecting_subject)
async def enter_subject(message: types.Message, state: FSMContext):
    await state.update_data(subject=message.text)
    await message.answer("Endi test javoblarini kiriting (masalan: abcdbac...):")
    await state.set_state(TestStates.entering_answers)


@dp.message(TestStates.entering_answers)
async def enter_answers(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    subject = user_data['subject']
    answers = message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tests (subject, answers, author_id) VALUES (?, ?, ?)",
                   (subject, answers, message.from_user.id))
    conn.commit()
    test_id = cursor.lastrowid
    await message.answer(f"✅ Test yaratildi!\nTest kodi: kod{test_id}")
    await state.clear()

#CHECK TEST

@dp.callback_query(F.data == "check_test")
async def check_test_handler(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Test kodini kiriting:")
    await state.set_state(AnswerStates.get_code)


@dp.message(AnswerStates.get_code)
async def enter_test_code(message: Message, state: FSMContext):
    test_id = message.text.replace("kod", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT answers FROM tests WHERE id = ?", (test_id,))
    row = cursor.fetchone()
    if row:
        await state.update_data(test_id=test_id, correct_answers=row['answers'])
        await message.answer("Endi javoblaringizni kiriting(Javoblarni qay tartibda yuborishni kanal adminlari joylagan xabardan ko'ring!):")
        await state.set_state(AnswerStates.enter_answers)
    else:
        await message.answer("❌ Bunday test topilmadi.")
        await state.clear()


@dp.message(AnswerStates.enter_answers)
async def check_answers(message: Message, state: FSMContext):
    user_data = await state.get_data()
    correct_answers = user_data['correct_answers']
    user_answers = message.text

    correct_count = sum(1 for x, y in zip(correct_answers, user_answers) if x == y)
    incorrect_count = len(correct_answers) - correct_count
    accuracy = (correct_count / len(correct_answers)) * 100

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username,full_name, chatId, test_id, user_answers, correct_count, incorrect_count, accuracy) VALUES (?, ?, ?, ?, ?, ?, ?,?)",
        (message.from_user.username,message.from_user.full_name, message.from_user.id, user_data['test_id'], user_answers, correct_count,
         incorrect_count, accuracy))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ Natijalaringiz:\n\n✔️ To‘g‘ri javoblar: {correct_count}\n❌ Noto‘g‘ri javoblar: {incorrect_count}\n📊 Foiz: {accuracy:.2f}%")
    await state.clear()

#STAT TEST

@dp.callback_query(F.data == "view_results")
async def view_results_handler(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Natijalarini ko‘rmoqchi bo‘lgan test kodini kiriting:")
    await state.set_state(TestStates.checking_test)


@dp.message(TestStates.checking_test)
async def show_test_results(message: Message, state: FSMContext):
    test_id = message.text.replace("kod", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username,full_name, correct_count, accuracy FROM users WHERE test_id = ? ORDER BY accuracy DESC",
                   (test_id,))
    rows = cursor.fetchall()

    if rows:
        results_text = f"📊 Test natijalari (Test ID: {test_id}):\n\n"
        for idx, row in enumerate(rows, start=1):
            results_text += f"{idx}. @{row['username']} ,{row['full_name']} - To‘g‘ri javoblar: {row['correct_count']}, Foiz: {row['accuracy']}%\n"
        await message.answer(results_text)
    else:
        await message.answer("❌ Bu test uchun natijalar topilmadi.")

    await state.clear()

#STOP_TEST

@dp.callback_query(F.data == "stop_test")
async def finish_test_handler(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer("Sizda ushbu bo‘limga ruxsat yo‘q!", show_alert=True)
        return
    await call.message.answer("Yakunlanishi kerak bo‘lgan test kodini kiriting:")
    await state.set_state(TestStates.finishing_test)

@dp.message(TestStates.finishing_test)
async def complete_test(message: Message, state: FSMContext):
    test_id = message.text.replace("kod", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tests SET status = 'closed' WHERE id = ?", (test_id,))
    conn.commit()
    await message.answer(f"✅ *Test yakunlandi!* (Test ID: {test_id})")
    await state.clear()

@dp.callback_query(F.data == "view_ranking")
async def view_ranking(call: CallbackQuery):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, SUM(correct_count) as total_correct, AVG(accuracy) as avg_accuracy FROM users GROUP BY username ORDER BY avg_accuracy DESC LIMIT 10")
    rows = cursor.fetchall()

    if rows:
        ranking_text = "🏆 *Umumiy reyting:*\n\n"
        for idx, row in enumerate(rows, start=1):
            ranking_text += f"{idx}. {row['username']} - To‘g‘ri javoblar: {row['total_correct']}, O‘rtacha foiz: {row['avg_accuracy']:.2f}%\n"
        await call.message.answer(ranking_text)
    else:
        await call.message.answer("Hali hech kim testda ishtirok etmagan.")

    await call.answer()

#ADMIN_PANEL

@dp.callback_query(F.data == 'enter_panel')
async def start(call: types.CallbackQuery):
    keyboards = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 Statistika', callback_data='statistic')],
        [InlineKeyboardButton(text='📨 Xabar Yuborish', callback_data='send')]
    ])
    await call.message.edit_text('🗂️ Admin Panelga xush kelibsiz!', reply_markup=keyboards)

@dp.callback_query(F.data == 'statistic')
async def get(call:types.CallbackQuery):
    today_count, yesterday_count, month_count, total_count = await get_statistics()
    await  call.message.answer( f"📊 Statistik ma'lumotlar:\n- Bugun qo'shilgan: {today_count} ta\n- Kecha qo'shilgan: {yesterday_count} ta\n- Bu oy qo'shilgan: {month_count} ta\n- Jami: {total_count} ta")


@dp.callback_query(F.data == "send")
async def ask_for_message(call: types.CallbackQuery, state: FSMContext):
    if call.message.from_user.id in ADMINS:
        await call.message.edit_text("📩 Yubormoqchi bo‘lgan xabaringizni yozing:")
        await state.set_state(BroadCast.text)
    else:
        await call.message.answer("❌ Sizda bu buyruqni ishlatish huquqi yo‘q.")


@dp.message(BroadCast.text)
async def send_message_to_all(message: types.Message, state: FSMContext):
    text = message.text
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT telegram_id FROM User")
    users = cursor.fetchall()

    conn.close()

    success_count = 0
    for user in users:
        telegram_id = user["telegram_id"]
        if telegram_id:
            try:
                await bot.send_message(telegram_id, text)
                success_count += 1
            except Exception as e:
                print(f"Xatolik: {e} - ID: {telegram_id}")

    await message.answer(f"✅ Xabar {success_count} ta foydalanuvchiga yuborildi!")
    await state.clear()

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())