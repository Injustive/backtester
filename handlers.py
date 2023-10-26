from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram3_calendar import simple_cal_callback, SimpleCalendar
from loader import dp, bot
from aiogram.types import Message
from utils.keyboards import date_picking_kb, get_stat_kb
from utils.fsm import TestParamsState
from utils.handlers_utils import test_strategy, buffer_to_bytes
from binance.exceptions import BinanceAPIException
from datetime import datetime


@dp.message(Command(commands=['start']))
async def cmd_start(message: Message, state: FSMContext):
    """Обробка команди start"""
    await state.clear()
    await message.reply('Привіт! Я бот для тестування spot grid trading. Почнімо?', reply_markup=date_picking_kb)


@dp.callback_query(lambda call: call.data == 'start_test')
async def process_start_test(call: CallbackQuery, state: FSMContext):
    """Обробка команди start"""
    await call.answer()
    await call.message.answer('Добре. Для початку виберемо діапазон, протягом якого будемо тестувати стратегію.'
                            'Виберіть дату початку тестування:', reply_markup=await SimpleCalendar().start_calendar())
    await state.set_state(TestParamsState.start_date)


@dp.callback_query(simple_cal_callback.filter(), TestParamsState.start_date)
async def process_picking_start_date(call: CallbackQuery, callback_data: dict, state: FSMContext):
    """Обробка вибору стортової дати"""
    await call.answer()
    selected, date = await SimpleCalendar().process_selection(call, callback_data)
    if selected:
        if date > datetime.now():
            await call.message.answer(f'Схоже ви вказали некоректну дату. Спробуйте ще раз: ',
                                      reply_markup=await SimpleCalendar().start_calendar())
            await state.set_state(TestParamsState.start_date)
        else:
            await call.message.answer(
                f'Чудово, стартова дата: {date.strftime("%Y-%m-%d")}.Тепер виберіть кінцеву дату:',
                reply_markup=await SimpleCalendar().start_calendar()
            )
            await state.update_data(start_date=date.strftime("%Y-%m-%d"))
            await state.set_state(TestParamsState.end_date)


@dp.callback_query(simple_cal_callback.filter(), TestParamsState.end_date)
async def process_picking_end_date(call: CallbackQuery, callback_data: dict, state: FSMContext):
    """Обробка вибору кінечної дати"""
    await call.answer()
    date_format = "%Y-%m-%d"
    selected, date = await SimpleCalendar().process_selection(call, callback_data)
    if selected:
        start_date = (await state.get_data())['start_date']
        start_datetime = datetime.strptime(start_date, date_format)
        if start_datetime > date or date > datetime.now() or start_datetime == date:
            await call.message.answer(f'Схоже ви вказали некоректну дату. Спробуйте ще раз: ',
                                      reply_markup=await SimpleCalendar().start_calendar())
            await state.set_state(TestParamsState.end_date)
        else:
            await call.message.answer(
                f'Кінцева дата: {date.strftime(date_format)}.Вкажіть депозит (мін 100) в $. Приклад: 100, 200, 1000, ...')
            await state.update_data(end_date=date.strftime(date_format))
            await state.set_state(TestParamsState.deposit)


@dp.message(TestParamsState.deposit)
async def process_picking_deposit(message: Message, state: FSMContext):
    """Логіка після вказання депозиту"""
    try:
        deposit = max(100, int(message.text))
    except ValueError:
        await message.answer(f'Схоже ви вказали некоректне число. Спробуйте ще раз: ')
        await state.set_state(TestParamsState.deposit)
        return
    await state.update_data(deposit=deposit)
    await message.answer(f'Ваш депозит: {deposit} .Вкажіть монету. Приклад: BTC, ETH, MATIC, ...')
    await state.set_state(TestParamsState.symbol)


@dp.message(TestParamsState.symbol)
async def process_picking_symbol(message: Message, state: FSMContext):
    """Логіка після вказання монети"""
    if message.text.upper() == 'USDT':
        await message.answer(f'Ця пара недоступна, введіть іншу: ')
    else:
        symbol = message.text.upper() + 'USDT'
        data = await state.get_data()
        if 'orders' in data:
            data.pop('orders')
        await message.answer(f'Ваша торгова пара: {symbol}. Розпочинаю тестування, це може зайняти деякий час...')
        try:
            data = await test_strategy(**data, symbol=symbol)
            results = '\n'.join(f'{k}: {str(v)}' for k, v in data[0].items())
            plot = data[1]
            plot = buffer_to_bytes(plot, 'plot')
            orders = data[2]
            await bot.send_photo(message.chat.id,
                                 plot,
                                 caption=f'Готово! Ось результати торгівлі: \n{results}.\n'
                                         'Зверніть увагу, що це тестові дані і комісія за ордери не враховується. ',
                                 reply_markup=get_stat_kb)
            await state.update_data(orders=orders)
            await state.set_state(TestParamsState.orders)
        except BinanceAPIException:
            await message.answer(f'Схоже ви вказали невірну торгову пару. Спробуйте ще раз: ')
            await state.set_state(TestParamsState.symbol)


@dp.callback_query(lambda call: call.data == 'get_stat', TestParamsState.orders)
async def process_start_test(call: CallbackQuery, state: FSMContext):
    """Отримання статистики ордерів"""
    await call.answer()
    file = (await state.get_data())['orders']
    file = buffer_to_bytes(file, 'orders.txt')
    await bot.send_document(call.message.chat.id, file)
