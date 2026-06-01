import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from models import Base, User, Book, Chunk, Schedule, LanguageEnum, ScheduleEnum
from config import DATABASE_URL, SCHEDULE_OPTIONS

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        logger.info("Database initialized")
    
    def get_session(self) -> Session:
        """Получает сессию БД"""
        return self.SessionLocal()
    
    # ============ User Operations ============
    
    def get_or_create_user(self, telegram_id: int, chat_id: int, username: str = None) -> User:
        """Получает или создает пользователя"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    username=username,
                    language=LanguageEnum.AUTO
                )
                session.add(user)
                session.commit()
                logger.info(f"Created new user: {telegram_id}")
            else:
                # Обновляем chat_id если изменился
                if user.chat_id != chat_id:
                    user.chat_id = chat_id
                    session.commit()
            
            return user
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error in get_or_create_user: {e}")
            raise
        finally:
            session.close()
    
    def get_user(self, telegram_id: int) -> Optional[User]:
        """Получает пользователя по telegram_id"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(telegram_id=telegram_id).first()
        finally:
            session.close()
    
    def update_user_language(self, telegram_id: int, language: str):
        """Обновляет язык пользователя"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.language = LanguageEnum(language)
                session.commit()
                logger.info(f"Updated language for user {telegram_id} to {language}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating user language: {e}")
        finally:
            session.close()
    
    # ============ Book Operations ============
    
    def create_book(
        self,
        telegram_id: int,
        filename: str,
        original_filename: str,
        file_format: str,
        detected_language: str,
        title: str = None,
        author: str = None
    ) -> Book:
        """Создает запись о книге"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                raise ValueError(f"User {telegram_id} not found")
            
            book = Book(
                user_id=user.id,
                filename=filename,
                original_filename=original_filename,
                file_format=file_format,
                detected_language=LanguageEnum(detected_language),
                title=title or original_filename,
                author=author
            )
            
            session.add(book)
            session.commit()
            logger.info(f"Created book: {book.id}")
            return book
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error creating book: {e}")
            raise
        finally:
            session.close()
    
    def get_book(self, book_id: int) -> Optional[Book]:
        """Получает книгу по ID"""
        session = self.get_session()
        try:
            return session.query(Book).filter_by(id=book_id).first()
        finally:
            session.close()
    
    def get_user_books(self, telegram_id: int, active_only: bool = True) -> List[Book]:
        """Получает все книги пользователя"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return []
            
            query = session.query(Book).filter_by(user_id=user.id)
            if active_only:
                query = query.filter_by(is_active=True, is_completed=False)
            
            return query.all()
        finally:
            session.close()
    
    def update_book_chunks(self, book_id: int, total_chunks: int):
        """Обновляет количество кусков в книге"""
        session = self.get_session()
        try:
            book = session.query(Book).filter_by(id=book_id).first()
            if book:
                book.total_chunks = total_chunks
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating book chunks: {e}")
        finally:
            session.close()
    
    def update_book_progress(self, book_id: int, current_chunk: int):
        """Обновляет прогресс чтения книги"""
        session = self.get_session()
        try:
            book = session.query(Book).filter_by(id=book_id).first()
            if book:
                book.current_chunk = current_chunk
                
                # Проверяем, завершена ли книга
                if current_chunk >= book.total_chunks:
                    book.is_completed = True
                
                session.commit()
                logger.info(f"Updated book {book_id} progress: {current_chunk}/{book.total_chunks}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating book progress: {e}")
        finally:
            session.close()
    
    def delete_book(self, book_id: int):
        """Удаляет книгу"""
        session = self.get_session()
        try:
            book = session.query(Book).filter_by(id=book_id).first()
            if book:
                session.delete(book)
                session.commit()
                logger.info(f"Deleted book {book_id}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error deleting book: {e}")
        finally:
            session.close()
    
    # ============ Chunk Operations ============
    
    def create_chunks(self, book_id: int, chunk_texts: List[str]):
        """Создает записи о кусках текста"""
        session = self.get_session()
        try:
            for i, text in enumerate(chunk_texts, 1):
                chunk = Chunk(
                    book_id=book_id,
                    chunk_number=i,
                    text=text,
                    character_count=len(text),
                    word_count=len(text.split())
                )
                session.add(chunk)
            
            session.commit()
            logger.info(f"Created {len(chunk_texts)} chunks for book {book_id}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error creating chunks: {e}")
            raise
        finally:
            session.close()
    
    def get_chunk(self, chunk_id: int) -> Optional[Chunk]:
        """Получает кусок по ID"""
        session = self.get_session()
        try:
            return session.query(Chunk).filter_by(id=chunk_id).first()
        finally:
            session.close()
    
    def get_next_chunk(self, book_id: int) -> Optional[Chunk]:
        """Получает следующий кусок для отправки"""
        session = self.get_session()
        try:
            book = session.query(Book).filter_by(id=book_id).first()
            if not book:
                return None
            
            next_chunk_num = book.current_chunk + 1
            return session.query(Chunk).filter_by(
                book_id=book_id,
                chunk_number=next_chunk_num
            ).first()
        finally:
            session.close()
    
    def mark_chunk_sent(self, chunk_id: int):
        """Отмечает кусок как отправленный"""
        session = self.get_session()
        try:
            chunk = session.query(Chunk).filter_by(id=chunk_id).first()
            if chunk:
                chunk.sent_at = datetime.utcnow()
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error marking chunk as sent: {e}")
        finally:
            session.close()
    
    # ============ Schedule Operations ============
    
    def create_schedule(
        self,
        telegram_id: int,
        book_id: int,
        interval: str
    ) -> Schedule:
        """Создает расписание отправки"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                raise ValueError(f"User {telegram_id} not found")
            
            interval_minutes = SCHEDULE_OPTIONS.get(interval, 900)
            next_send_time = datetime.utcnow() + timedelta(seconds=interval_minutes)
            
            schedule = Schedule(
                user_id=user.id,
                book_id=book_id,
                interval=ScheduleEnum(interval),
                interval_minutes=interval_minutes,
                next_send_time=next_send_time
            )
            
            session.add(schedule)
            session.commit()
            logger.info(f"Created schedule for book {book_id}, interval: {interval}")
            return schedule
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error creating schedule: {e}")
            raise
        finally:
            session.close()
    
    def get_schedule(self, book_id: int) -> Optional[Schedule]:
        """Получает расписание книги"""
        session = self.get_session()
        try:
            return session.query(Schedule).filter_by(book_id=book_id).first()
        finally:
            session.close()
    
    def update_schedule(self, schedule_id: int, next_send_time: datetime):
        """Обновляет время следующей отправки"""
        session = self.get_session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            if schedule:
                schedule.next_send_time = next_send_time
                schedule.last_sent_at = datetime.utcnow()
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating schedule: {e}")
        finally:
            session.close()
    
    def get_pending_schedules(self) -> List[Schedule]:
        """Получает все расписания, готовые к отправке"""
        session = self.get_session()
        try:
            now = datetime.utcnow()
            return session.query(Schedule).options(joinedload(Schedule.user)).filter(
                and_(
                    Schedule.is_active == True,
                    Schedule.next_send_time <= now
                )
            ).all()
        finally:
            session.close()
    
    def deactivate_schedule(self, schedule_id: int):
        """Деактивирует расписание"""
        session = self.get_session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            if schedule:
                schedule.is_active = False
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error deactivating schedule: {e}")
        finally:
            session.close()


# Глобальный экземпляр БД
db = Database()
