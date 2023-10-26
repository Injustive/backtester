from concurrent.futures import ProcessPoolExecutor
import asyncio
import os
import io
from aiogram.types import BufferedInputFile
from strategy import Controller


async def test_strategy(start_date: str,
                        end_date: str,
                        symbol: str,
                        deposit: int) -> tuple[dict[str, float], io.BytesIO, io.BytesIO]:
    """Запуск CPU-bound задачі в процесі"""
    API_KEY = os.getenv("API_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY")
    loop = asyncio.get_running_loop()
    controller = Controller(start_date, end_date, symbol, deposit, API_KEY, SECRET_KEY)
    with ProcessPoolExecutor() as executor:
        data = await loop.run_in_executor(executor, controller.run)
    return data


def buffer_to_bytes(fileio: io.BytesIO, filename):
    fileio.seek(0)
    file = BufferedInputFile(fileio.read(), filename=filename)
    return file
