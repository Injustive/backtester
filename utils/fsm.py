from aiogram.fsm.state import StatesGroup, State


class TestParamsState(StatesGroup):
    start_date = State()
    end_date = State()
    deposit = State()
    symbol = State()
    orders = State()
