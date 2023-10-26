from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
