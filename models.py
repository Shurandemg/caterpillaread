import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean,
    DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class LanguageEnum(str, enum.Enum):
    RU = "ru"
    EN = "en"
    AUTO = "auto"


class ScheduleEnum(str, enum.Enum):
    SEC_10 = "10_sec"
    SEC_30 = "30_sec"
    MIN_1 = "1_min"
    MIN_3 = "3_min"
    MIN_15 = "15_min"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    chat_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    language = Column(SAEnum(LanguageEnum), default=LanguageEnum.AUTO, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    books = relationship("Book", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    original_filename = Column(String(512), nullable=False)
    file_format = Column(String(10), nullable=False)
    detected_language = Column(SAEnum(LanguageEnum), default=LanguageEnum.AUTO, nullable=False)
    title = Column(String(512), nullable=True)
    author = Column(String(255), nullable=True)
    total_chunks = Column(Integer, default=0, nullable=False)
    current_chunk = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="books")
    chunks = relationship("Chunk", back_populates="book", cascade="all, delete-orphan")
    schedule = relationship("Schedule", back_populates="book", uselist=False, cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    chunk_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    character_count = Column(Integer, default=0, nullable=False)
    word_count = Column(Integer, default=0, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    book = relationship("Book", back_populates="chunks")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, unique=True)
    interval = Column(SAEnum(ScheduleEnum), nullable=False)
    interval_minutes = Column(Integer, nullable=False)
    next_send_time = Column(DateTime, nullable=False)
    last_sent_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="schedules")
    book = relationship("Book", back_populates="schedule")
