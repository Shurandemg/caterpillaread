import os
import logging

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "caterpillar")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "caterpillar_pass")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "caterpillaread")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB

CHUNK_SIZE_MIN = int(os.environ.get("CHUNK_SIZE_MIN", "500"))
CHUNK_SIZE_MAX = int(os.environ.get("CHUNK_SIZE_MAX", "3000"))
MAX_MESSAGES = int(os.environ.get("MAX_MESSAGES", "10"))

SPACY_MODEL_RU = os.environ.get("SPACY_MODEL_RU", "ru_core_news_sm")
SPACY_MODEL_EN = os.environ.get("SPACY_MODEL_EN", "en_core_web_sm")

LANGUAGE_CODES = ["ru", "en", "auto"]

# Values are in SECONDS
SCHEDULE_OPTIONS = {
    "10_sec": 10,
    "30_sec": 30,
    "1_min": 60,
    "3_min": 180,
    "15_min": 900,
}

LOG_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
