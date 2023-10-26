from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

date_picking_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='Почати тестування', callback_data='start_test'),
        ],
    ]
)

get_stat_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='Отримати дані торгівлі', callback_data='get_stat'),
        ],
    ]
)