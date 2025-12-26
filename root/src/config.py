import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PROTALK_TOKEN = os.getenv("PROTALK_TOKEN")
PROTALK_BOT_ID = os.getenv("PROTALK_BOT_ID")
