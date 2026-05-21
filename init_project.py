#!/usr/bin/env python3
"""
Инициализация проекта CaterpillarRead.
Запустите один раз перед первым стартом: python init_project.py
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def check_python_version():
    if sys.version_info < (3, 9):
        logger.error("Требуется Python 3.9+. Текущая версия: %s", sys.version)
        sys.exit(1)
    logger.info("Python %s — OK", sys.version.split()[0])


def check_env_file():
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            logger.warning("Создан файл .env из .env.example. Заполните TELEGRAM_TOKEN!")
        else:
            logger.warning(".env файл не найден. Создайте его вручную.")
    else:
        logger.info(".env файл — OK")


def check_telegram_token():
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            token = os.environ.get("TELEGRAM_TOKEN", "")
        except ImportError:
            pass

    if not token:
        logger.error("TELEGRAM_TOKEN не установлен! Получите токен у @BotFather в Telegram.")
        return False
    logger.info("TELEGRAM_TOKEN — OK")
    return True


def check_database():
    try:
        from config import DATABASE_URL
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL — OK")
        return True
    except Exception as e:
        logger.error("PostgreSQL недоступен: %s", e)
        return False


def check_redis():
    try:
        import redis
        from config import REDIS_URL
        r = redis.from_url(REDIS_URL)
        r.ping()
        logger.info("Redis — OK")
        return True
    except Exception as e:
        logger.error("Redis недоступен: %s", e)
        return False


def create_tables():
    try:
        from database import db
        logger.info("Таблицы БД созданы — OK")
        return True
    except Exception as e:
        logger.error("Ошибка создания таблиц: %s", e)
        return False


def create_upload_dir():
    from config import UPLOAD_DIR
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info("Папка uploads (%s) — OK", UPLOAD_DIR)


def download_spacy_models():
    from config import SPACY_MODEL_RU, SPACY_MODEL_EN
    for model in [SPACY_MODEL_RU, SPACY_MODEL_EN]:
        try:
            import spacy
            spacy.load(model)
            logger.info("spaCy модель %s — уже установлена", model)
        except OSError:
            logger.info("Загружаю spaCy модель %s ...", model)
            result = subprocess.run(
                [sys.executable, "-m", "spacy", "download", model],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                logger.info("spaCy модель %s — OK", model)
            else:
                logger.warning("Не удалось загрузить %s: %s", model, result.stderr.strip())


def main():
    print("=" * 60)
    print("  CaterpillarRead — инициализация проекта")
    print("=" * 60)

    check_python_version()
    check_env_file()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token_ok = check_telegram_token()
    db_ok = check_database()
    redis_ok = check_redis()

    if db_ok:
        create_tables()

    create_upload_dir()
    download_spacy_models()

    print()
    print("=" * 60)
    if token_ok and db_ok and redis_ok:
        print("  ✅ Всё готово! Запустите: python bot.py")
    else:
        issues = []
        if not token_ok:
            issues.append("TELEGRAM_TOKEN")
        if not db_ok:
            issues.append("PostgreSQL")
        if not redis_ok:
            issues.append("Redis")
        print(f"  ⚠️  Устраните проблемы: {', '.join(issues)}")
        print("  Затем повторно запустите init_project.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
