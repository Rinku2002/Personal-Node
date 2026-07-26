"""Application configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")

SERVER_PORT = 8000
SERVER_PORT_TEST = 8080

ROOT_FOLDER = r"C:\\"

PROD_LOG_DIR = str(BASE_DIR / "logs")

print(PROD_LOG_DIR)
