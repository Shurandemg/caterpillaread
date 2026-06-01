import html
import logging
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab

from config import REDIS_URL, SCHEDULE_OPTIONS

logger = logging.getLogger(__name__)

celery_app = Celery(
    "caterpillaread",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "send-scheduled-chunks": {
        "task": "tasks.send_scheduled_chunks",
        "schedule": 60.0,  # каждую минуту
    },
}


@celery_app.task(name="tasks.process_book_task", bind=True, max_retries=3)
def process_book_task(self, book_id: int, file_path: str, language: str = "auto"):
    """Асинхронная обработка книги: парсинг и нарезка на куски."""
    try:
        from file_parser import FileParser
        from chunk_generator import create_chunk_generator
        from database import db

        logger.info(f"Processing book {book_id}: {file_path}")

        text, file_format, detected_language = FileParser.parse(file_path)

        lang = detected_language if language == "auto" else language
        generator = create_chunk_generator(lang)
        chunks = generator.generate_chunks(text)

        db.create_chunks(book_id, chunks)
        db.update_book_chunks(book_id, len(chunks))

        logger.info(f"Book {book_id} processed: {len(chunks)} chunks")
        return {"book_id": book_id, "chunks": len(chunks)}

    except Exception as exc:
        logger.error(f"Error processing book {book_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="tasks.send_scheduled_chunks")
def send_scheduled_chunks():
    """Отправляет куски по расписанию всем пользователям."""
    import asyncio
    from telegram import Bot
    from config import TELEGRAM_TOKEN
    from database import db

    schedules = db.get_pending_schedules()
    if not schedules:
        return

    # Collect all work synchronously before touching async — avoids detached session issues
    pending = []
    for schedule in schedules:
        try:
            book = db.get_book(schedule.book_id)
            if not book or book.is_completed or not book.is_active:
                db.deactivate_schedule(schedule.id)
                continue

            chunk = db.get_next_chunk(book.id)
            if not chunk:
                db.deactivate_schedule(schedule.id)
                continue

            pending.append({
                "schedule_id": schedule.id,
                "interval_minutes": schedule.interval_minutes,
                "chat_id": schedule.user.chat_id,
                "book_id": book.id,
                "book_title": book.title,
                "chunk_id": chunk.id,
                "chunk_number": chunk.chunk_number,
                "total_chunks": book.total_chunks,
                "chunk_text": chunk.text,
            })
        except Exception as e:
            logger.error(f"Error preparing schedule {schedule.id}: {e}")

    if not pending:
        return

    async def send_all():
        async with Bot(token=TELEGRAM_TOKEN) as bot:
            for item in pending:
                try:
                    header = (
                        f"📚 <b>{html.escape(item['book_title'])}</b> "
                        f"(кусок {item['chunk_number']}/{item['total_chunks']})\n\n"
                    )
                    # Truncate raw text BEFORE escaping to avoid splitting HTML entities
                    max_raw = 4096 - len(header)
                    body = html.escape(item['chunk_text'][:max_raw])
                    await bot.send_message(
                        chat_id=item["chat_id"],
                        text=header + body,
                        parse_mode="HTML",
                    )
                    item["sent"] = True
                    logger.info(f"Sent chunk {item['chunk_number']} of book {item['book_id']} to chat {item['chat_id']}")
                except Exception as e:
                    item["sent"] = False
                    logger.error(f"Error sending chunk for schedule {item['schedule_id']}: {e}")

    asyncio.run(send_all())

    # Update DB only for successfully sent chunks
    for item in pending:
        if not item.get("sent"):
            continue
        try:
            db.mark_chunk_sent(item["chunk_id"])
            db.update_book_progress(item["book_id"], item["chunk_number"])
            next_send = datetime.utcnow() + timedelta(minutes=item["interval_minutes"])
            db.update_schedule(item["schedule_id"], next_send)
        except Exception as e:
            logger.error(f"Error updating DB after send for schedule {item['schedule_id']}: {e}")
