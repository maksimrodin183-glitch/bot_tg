import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import TOKEN
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

menu_gla = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Создать напоминание ✅')],
        [KeyboardButton(text='Мои напоминания 📋'), KeyboardButton(text='Удалить напоминания ❌')]
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие из меню ниже'
)

user_Reminders = {}
reminder_tasks = {}  # Словарь для хранения задач таймеров

class Reminder(StatesGroup):
    waiting_text = State()
    waiting_time = State()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! Я бот создающий напоминания. "
        "Создай своё напоминание, а я отправлю его тебе в указанное время!",
        reply_markup=menu_gla
    )

@dp.message(lambda message: message.text == 'Создать напоминание ✅')
async def create_reminder(message: Message, state: FSMContext):
    await message.answer('Введите своё напоминание:')
    await state.set_state(Reminder.waiting_text)

@dp.message(Reminder.waiting_text)
async def reminder_save(message: Message, state: FSMContext):
    text = message.text
    await state.update_data(reminder_text=text)
    await message.answer("Через сколько минут нужно напомнить? ⏳\nНапример: 5")
    await state.set_state(Reminder.waiting_time)

@dp.message(Reminder.waiting_time)
async def reminder_time(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        minutes = int(message.text)
    except ValueError:
        await message.answer("Введите число! Например: 5")
        return
    data = await state.get_data()
    reminder_text = data.get("reminder_text")

    if user_id not in user_Reminders:
        user_Reminders[user_id] = []
    user_Reminders[user_id].append(reminder_text)

    if user_id not in reminder_tasks:
        reminder_tasks[user_id] = {}
    task = asyncio.create_task(send_reminder_after_time(user_id, reminder_text, minutes))
    reminder_tasks[user_id][reminder_text] = task

    await message.answer(f"Отлично! Я напомню через {minutes} мин ⏰")
    await state.clear()

async def send_reminder_after_time(user_id: int, text: str, minutes: int):
    try:
        await asyncio.sleep(minutes * 60)
        await bot.send_message(user_id, f"🔔 Напоминание:\n{text}")
        if user_id in user_Reminders and text in user_Reminders[user_id]:
            user_Reminders[user_id].remove(text)
        if user_id in reminder_tasks and text in reminder_tasks[user_id]:
            del reminder_tasks[user_id][text]
    except asyncio.CancelledError:
        pass

@dp.message(lambda message: message.text == 'Мои напоминания 📋')
async def show_reminder(message: Message):
    user_id = message.from_user.id
    reminders = user_Reminders.get(user_id, [])
    if reminders:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"❌ {r}", callback_data=f"del_{i}")]
                for i, r in enumerate(reminders)
            ]
        )
        await message.answer("Ваши напоминания (нажмите кнопку для удаления):", reply_markup=kb)
    else:
        await message.answer("У вас нет напоминаний.\nСоздайте новое!")

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_specific_reminder(call: CallbackQuery):
    user_id = call.from_user.id
    index = int(call.data.split("_")[1])
    if user_id in user_Reminders and 0 <= index < len(user_Reminders[user_id]):
        removed = user_Reminders[user_id].pop(index)
        if user_id in reminder_tasks and removed in reminder_tasks[user_id]:
            task = reminder_tasks[user_id].pop(removed)
            task.cancel()
        await call.message.edit_text(f"Удалено напоминание: {removed}")
    else:
        await call.message.edit_text("Ошибка: напоминание не найдено")
    await call.answer()

delete_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Да удалить ❌', callback_data='delete_yes')],
        [InlineKeyboardButton(text='Отмена', callback_data='delete_no')]
    ]
)

@dp.message(lambda message: message.text == 'Удалить напоминания ❌')
async def ask_delete(message: Message):
    await message.answer("Вы уверены что хотите удалить все напоминания?", reply_markup=delete_keyboard)

@dp.callback_query(lambda c: c.data == 'delete_yes')
async def confirm_delete(call: CallbackQuery):
    user_id = call.from_user.id
    for task in reminder_tasks.get(user_id, {}).values():
        task.cancel()
    reminder_tasks[user_id] = {}
    user_Reminders[user_id] = []
    await call.message.edit_text("Все ваши напоминания удалены ❌")
    await call.answer()

@dp.callback_query(lambda c: c.data == 'delete_no')
async def cancel_delete(call: CallbackQuery):
    await call.message.edit_text("Удаление отменено 👀")
    await call.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
