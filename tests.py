"""
Тесты для CaterpillarRead.
Запуск: pytest tests.py -v
"""

import os
import sys
import pytest
import tempfile

os.environ.setdefault("TELEGRAM_TOKEN", "test_token")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


# ==================== config ====================

class TestConfig:
    def test_schedule_options_keys(self):
        from config import SCHEDULE_OPTIONS
        expected = {"15_min", "30_min", "1_hour", "3_hours", "6_hours", "daily", "2_days", "weekly"}
        assert set(SCHEDULE_OPTIONS.keys()) == expected

    def test_schedule_options_values_are_positive(self):
        from config import SCHEDULE_OPTIONS
        for key, minutes in SCHEDULE_OPTIONS.items():
            assert minutes > 0, f"{key} должен быть > 0"

    def test_chunk_sizes(self):
        from config import CHUNK_SIZE_MIN, CHUNK_SIZE_MAX
        assert CHUNK_SIZE_MIN > 0
        assert CHUNK_SIZE_MAX > CHUNK_SIZE_MIN

    def test_language_codes(self):
        from config import LANGUAGE_CODES
        assert "ru" in LANGUAGE_CODES
        assert "en" in LANGUAGE_CODES
        assert "auto" in LANGUAGE_CODES

    def test_max_file_size(self):
        from config import MAX_FILE_SIZE
        assert MAX_FILE_SIZE > 0


# ==================== models ====================

class TestModels:
    def test_language_enum_values(self):
        from models import LanguageEnum
        assert LanguageEnum.RU == "ru"
        assert LanguageEnum.EN == "en"
        assert LanguageEnum.AUTO == "auto"

    def test_schedule_enum_values(self):
        from models import ScheduleEnum
        assert ScheduleEnum.MIN_15 == "15_min"
        assert ScheduleEnum.DAILY == "daily"
        assert ScheduleEnum.WEEKLY == "weekly"

    def test_user_model_has_required_columns(self):
        from models import User
        cols = {c.name for c in User.__table__.columns}
        assert {"id", "telegram_id", "chat_id", "language"}.issubset(cols)

    def test_book_model_has_required_columns(self):
        from models import Book
        cols = {c.name for c in Book.__table__.columns}
        assert {"id", "user_id", "filename", "title", "total_chunks", "current_chunk"}.issubset(cols)

    def test_chunk_model_has_required_columns(self):
        from models import Chunk
        cols = {c.name for c in Chunk.__table__.columns}
        assert {"id", "book_id", "chunk_number", "text"}.issubset(cols)

    def test_schedule_model_has_required_columns(self):
        from models import Schedule
        cols = {c.name for c in Schedule.__table__.columns}
        assert {"id", "user_id", "book_id", "interval", "next_send_time"}.issubset(cols)


# ==================== chunk_generator ====================

class TestChunkGenerator:
    def test_create_generator_auto(self):
        from chunk_generator import create_chunk_generator
        gen = create_chunk_generator("auto")
        assert gen is not None

    def test_create_generator_ru(self):
        from chunk_generator import create_chunk_generator
        gen = create_chunk_generator("ru")
        assert gen.language == "ru"

    def test_create_generator_en(self):
        from chunk_generator import create_chunk_generator
        gen = create_chunk_generator("en")
        assert gen.language == "en"

    def test_generate_chunks_returns_list(self):
        from chunk_generator import create_chunk_generator
        gen = create_chunk_generator("auto")
        chunks = gen.generate_chunks("Привет мир. Это тест.")
        assert isinstance(chunks, list)

    def test_generate_chunks_not_empty(self):
        from chunk_generator import create_chunk_generator
        text = "Это длинный тест. " * 50
        gen = create_chunk_generator("auto")
        chunks = gen.generate_chunks(text)
        assert len(chunks) > 0

    def test_chunks_respect_max_size(self):
        from chunk_generator import create_chunk_generator
        from config import CHUNK_SIZE_MAX
        text = "Тест предложение. " * 200
        gen = create_chunk_generator("auto")
        chunks = gen.generate_chunks(text)
        for chunk in chunks:
            assert len(chunk) <= CHUNK_SIZE_MAX + 200, f"Chunk too large: {len(chunk)}"

    def test_empty_text_returns_empty(self):
        from chunk_generator import create_chunk_generator
        gen = create_chunk_generator("auto")
        chunks = gen.generate_chunks("")
        assert chunks == []

    def test_russian_splitter(self):
        from chunk_generator import RussianSentenceSplitter
        splitter = RussianSentenceSplitter()
        sentences = splitter.split("Первое предложение. Второе предложение.")
        assert len(sentences) >= 1

    def test_english_splitter(self):
        from chunk_generator import EnglishSentenceSplitter
        splitter = EnglishSentenceSplitter()
        sentences = splitter.split("First sentence. Second sentence.")
        assert len(sentences) >= 1

    def test_generic_splitter(self):
        from chunk_generator import GenericSentenceSplitter
        splitter = GenericSentenceSplitter()
        sentences = splitter.split("First. Second. Third.")
        assert len(sentences) >= 1


# ==================== file_parser ====================

class TestFileParser:
    def test_supported_formats(self):
        from file_parser import FileParser
        assert "txt" in FileParser.SUPPORTED_FORMATS
        assert "pdf" in FileParser.SUPPORTED_FORMATS
        assert "epub" in FileParser.SUPPORTED_FORMATS

    def test_detect_language_russian(self):
        from file_parser import FileParser
        text = "Это русский текст для тестирования определения языка. Здесь много русских слов."
        lang = FileParser.detect_language(text)
        assert lang in ["ru", "auto"]

    def test_detect_language_english(self):
        from file_parser import FileParser
        text = "This is an English text for language detection testing. Many English words here."
        lang = FileParser.detect_language(text)
        assert lang in ["en", "auto"]

    def test_detect_language_empty_returns_default(self):
        from file_parser import FileParser
        lang = FileParser.detect_language("", default="auto")
        assert lang == "auto"

    def test_clean_text_removes_extra_spaces(self):
        from file_parser import FileParser
        text = "Hello   world\n\n\n\nSecond paragraph"
        cleaned = FileParser.clean_text(text)
        assert "   " not in cleaned
        assert "\n\n\n" not in cleaned

    def test_clean_text_strips(self):
        from file_parser import FileParser
        text = "  \n Hello world \n  "
        cleaned = FileParser.clean_text(text)
        assert cleaned == cleaned.strip()

    def test_parse_txt_file(self):
        from file_parser import FileParser
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Тестовый текст для парсинга.\nВторая строка.")
            tmp = f.name
        try:
            text, fmt, lang = FileParser.parse(tmp)
            assert fmt == "txt"
            assert len(text) > 0
            assert "Тестовый" in text
        finally:
            os.unlink(tmp)

    def test_parse_unsupported_format_raises(self):
        from file_parser import FileParser
        with pytest.raises(ValueError):
            FileParser.parse("somefile.xyz")

    def test_parse_txt_utf8(self):
        from file_parser import FileParser
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Привет мир")
            tmp = f.name
        try:
            text = FileParser.parse_txt(tmp)
            assert "Привет" in text
        finally:
            os.unlink(tmp)


# ==================== database ====================

class TestDatabase:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        import database
        original_engine = database.db.engine
        original_session = database.db.SessionLocal
        database.db.engine = engine
        database.db.SessionLocal = Session

        yield

        database.db.engine = original_engine
        database.db.SessionLocal = original_session

    def test_create_user(self):
        from database import db
        user = db.get_or_create_user(telegram_id=12345, chat_id=12345, username="testuser")
        assert user is not None
        assert user.telegram_id == 12345

    def test_get_or_create_user_idempotent(self):
        from database import db
        user1 = db.get_or_create_user(telegram_id=99999, chat_id=99999)
        user2 = db.get_or_create_user(telegram_id=99999, chat_id=99999)
        assert user1.id == user2.id

    def test_create_book(self):
        from database import db
        db.get_or_create_user(telegram_id=11111, chat_id=11111)
        book = db.create_book(
            telegram_id=11111,
            filename="test.txt",
            original_filename="test.txt",
            file_format="txt",
            detected_language="ru",
            title="Test Book"
        )
        assert book is not None
        assert book.title == "Test Book"

    def test_get_user_books_empty(self):
        from database import db
        db.get_or_create_user(telegram_id=22222, chat_id=22222)
        books = db.get_user_books(22222)
        assert books == []

    def test_create_and_get_chunks(self):
        from database import db
        db.get_or_create_user(telegram_id=33333, chat_id=33333)
        book = db.create_book(
            telegram_id=33333,
            filename="book.txt",
            original_filename="book.txt",
            file_format="txt",
            detected_language="ru",
            title="Chunk Test"
        )
        chunks_text = ["Chunk 1 text.", "Chunk 2 text.", "Chunk 3 text."]
        db.create_chunks(book.id, chunks_text)
        db.update_book_chunks(book.id, len(chunks_text))

        chunk = db.get_next_chunk(book.id)
        assert chunk is not None
        assert chunk.chunk_number == 1

    def test_update_book_progress(self):
        from database import db
        db.get_or_create_user(telegram_id=44444, chat_id=44444)
        book = db.create_book(
            telegram_id=44444,
            filename="progress.txt",
            original_filename="progress.txt",
            file_format="txt",
            detected_language="en",
            title="Progress Test"
        )
        db.update_book_chunks(book.id, 5)
        db.update_book_progress(book.id, 3)
        updated = db.get_book(book.id)
        assert updated.current_chunk == 3

    def test_book_completed_when_all_chunks_sent(self):
        from database import db
        db.get_or_create_user(telegram_id=55555, chat_id=55555)
        book = db.create_book(
            telegram_id=55555,
            filename="done.txt",
            original_filename="done.txt",
            file_format="txt",
            detected_language="ru",
            title="Complete Test"
        )
        db.update_book_chunks(book.id, 3)
        db.update_book_progress(book.id, 3)
        updated = db.get_book(book.id)
        assert updated.is_completed is True

    def test_update_user_language(self):
        from database import db
        db.get_or_create_user(telegram_id=66666, chat_id=66666)
        db.update_user_language(66666, "en")
        user = db.get_user(66666)
        assert str(user.language) == "en"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
