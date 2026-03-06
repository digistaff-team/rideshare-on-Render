import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Pro-Talk API
PROTALK_TOKEN = os.getenv("PROTALK_TOKEN")
PROTALK_BOT_ID = os.getenv("PROTALK_BOT_ID")
PROTALK_API_URL = os.getenv("PROTALK_API_URL", "https://api.pro-talk.ru/api/v1.0")

# Server
PORT = int(os.getenv("PORT", 8000))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


