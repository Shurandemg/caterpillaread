import os
import html
import logging
from datetime import datetime
import uuid
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.constants import ChatAction

from config import (
    TELEGRAM_TOKEN, UPLOAD_DIR, CHUNK_SIZE_MAX,
    MAX_FILE_SIZE, SCHEDULE_OPTIONS, LANGUAGE_CODES, LOG_LEVEL
)
from database import db
from file_parser import FileParser
from chunk_generator import create_chunk_generator
from tasks import process_book_task

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=LOG_LEVEL
)
logger = logging.getLogger(__name__)

# Состояния конверсации
CHOOSING_LANGUAGE = 1
CHOOSING_INTERVAL = 2
CHOOSING_ACTION = 3

class CaterpillarReadBot:
    """Telegram бот для Caterpillar Read"""
    
    def __init__(self):
        self.application = None
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настраивает обработчики команд"""
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("books", self.list_books))
        self.application.add_handler(CommandHandler("settings", self.settings))
        self.application.add_handler(CommandHandler("progress", self.progress))
        self.application.add_handler(CommandHandler("next", self.next_chunk))
        self.application.add_handler(CommandHandler("cancel", self.cancel))
        
        # Обработчики файлов
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_file_upload))
        
        # Callback кнопки
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Ошибки
        self.application.add_error_handler(self.error_handler)
        
        logger.info("Bot handlers setup completed")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /start"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Создаем или получаем пользователя
        db_user = db.get_or_create_user(
            telegram_id=user.id,
            chat_id=chat_id,
            username=user.username
        )
        
        welcome_text = (
            f"👋 Добро пожаловать в <b>Caterpillar Read</b> ({html.escape(user.first_name)})!\n\n"
            "Я помогу вам читать книги небольшими порциями. Вот что я умею:\n\n"
            "📚 /books - Посмотреть список загруженных книг\n"
            "⚙️ /settings - Изменить язык и другие настройки\n"
            "📊 /progress - Посмотреть прогресс чтения\n"
            "❓ /help - Справка по командам\n\n"
            "<b>Как начать:</b>\n"
            "1. Отправьте мне файл книги (TXT, PDF, EPUB, MOBI, DOCX)\n"
            "2. Выберите периодичность отправки (раз в час, раз в день и т.д.)\n"
            "3. Я буду отправлять вам куски текста по расписанию 📖\n\n"
            "<b>Форматы:</b> TXT, PDF, EPUB, MOBI, DOC, DOCX\n"
            "<b>Максимальный размер:</b> 50MB"
        )

        await update.message.reply_text(welcome_text, parse_mode='HTML')
        logger.info(f"User {user.id} started the bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📖 **Доступные команды:**

/start - Перезагрузить приветствие
/books - Список ваших книг
/next - Получить следующий кусок прямо сейчас
/settings - Настройки (язык и т.д.)
/progress - Прогресс чтения каждой книги
/help - Эта справка

**Как загрузить книгу:**
1. Просто отправьте файл боту (TXT, PDF, EPUB, MOBI, DOCX)
2. Выберите интервал отправки
3. Готово! Начнется отправка кусочков текста

**Доступные интервалы:**
⏱️ 10 секунд
⏱️ 30 секунд
⏰ 1 минута
⏰ 3 минуты
📅 15 минут
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def list_books(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /books"""
        user = update.effective_user
        
        books = db.get_user_books(user.id, active_only=False)
        
        if not books:
            await update.message.reply_text("📚 У вас пока нет загруженных книг.")
            return
        
        books_text = "📚 <b>Ваши книги:</b>\n\n"

        for i, book in enumerate(books, 1):
            progress = (book.current_chunk / book.total_chunks * 100) if book.total_chunks > 0 else 0
            status = "✅ Прочитана" if book.is_completed else "📖 Читается"

            books_text += f"{i}. <b>{html.escape(book.title)}</b>\n"
            books_text += f"   Автор: {html.escape(book.author or 'Неизвестен')}\n"
            books_text += f"   Статус: {status}\n"
            books_text += f"   Прогресс: {book.current_chunk}/{book.total_chunks} кусков ({progress:.1f}%)\n"
            books_text += f"   Формат: {book.file_format.upper()}\n\n"

        await update.message.reply_text(books_text, parse_mode='HTML')
    
    async def progress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /progress"""
        user = update.effective_user
        
        books = db.get_user_books(user.id, active_only=True)
        
        if not books:
            await update.message.reply_text("📊 Нет активных книг для чтения.")
            return
        
        progress_text = "📊 <b>Ваш прогресс:</b>\n\n"

        for book in books:
            schedule = db.get_schedule(book.id)
            progress = (book.current_chunk / book.total_chunks * 100) if book.total_chunks > 0 else 0

            progress_text += f"📖 <b>{html.escape(book.title)}</b>\n"
            progress_text += f"Прочитано: {book.current_chunk}/{book.total_chunks} ({progress:.1f}%)\n"
            
            if schedule:
                next_send = schedule.next_send_time
                interval_text = {
                    '10_sec': 'каждые 10 секунд',
                    '30_sec': 'каждые 30 секунд',
                    '1_min': 'каждую минуту',
                    '3_min': 'каждые 3 минуты',
                    '15_min': 'каждые 15 минут',
                }.get(schedule.interval, 'неизвестный')
                
                progress_text += f"Отправка: {interval_text}\n"
                progress_text += f"Следующая отправка: {next_send.strftime('%d.%m.%Y %H:%M UTC')}\n"
            
            progress_text += "\n"
        
        await update.message.reply_text(progress_text, parse_mode='HTML')
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /settings"""
        user = update.effective_user
        db_user = db.get_user(user.id)
        
        # Создаем кнопки для выбора языка
        keyboard = [
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🔄 Auto-detect", callback_data="lang_auto")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_lang = db_user.language if db_user else "auto"
        settings_text = f"⚙️ **Текущие настройки:**\n\nЯзык: {current_lang}\n\n**Выберите язык для обработки:**"
        
        await update.message.reply_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик загрузки файла"""
        user = update.effective_user
        file = update.message.document
        
        # Проверяем размер файла
        if file.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(f"❌ Файл слишком большой. Максимум: {MAX_FILE_SIZE // 1024 // 1024}MB")
            return
        
        # Получаем расширение
        filename = file.file_name
        file_extension = filename.split('.')[-1].lower()
        
        if file_extension not in ['txt', 'pdf', 'epub', 'mobi', 'doc', 'docx']:
            await update.message.reply_text(
                "❌ Неподдерживаемый формат файла.\n"
                "Поддерживаются: TXT, PDF, EPUB, MOBI, DOC, DOCX"
            )
            return
        
        # Отправляем статус обработки
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        processing_msg = await update.message.reply_text("⏳ Обработка файла...")
        
        try:
            # Скачиваем файл
            file_obj = await context.bot.get_file(file.file_id)
            
            # Создаем уникальное имя для файла
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            await file_obj.download_to_drive(file_path)
            logger.info(f"Downloaded file: {file_path}")
            
            # Парсим файл
            await processing_msg.edit_text("📖 Парсинг файла...")
            text, file_format, detected_language = FileParser.parse(file_path)
            
            # Создаем запись о книге
            await processing_msg.edit_text("💾 Сохранение в базу...")
            book = db.create_book(
                telegram_id=user.id,
                filename=unique_filename,
                original_filename=filename,
                file_format=file_format,
                detected_language=detected_language,
                title=filename.rsplit('.', 1)[0]
            )
            
            # Генерируем куски (в фоне через Celery, но для простоты делаем синхронно)
            await processing_msg.edit_text("✂️ Разбиение текста на куски...")
            generator = create_chunk_generator(detected_language)
            chunks = generator.generate_chunks(text)
            
            # Сохраняем куски
            db.create_chunks(book.id, chunks)
            db.update_book_chunks(book.id, len(chunks))
            
            logger.info(f"Created book {book.id} with {len(chunks)} chunks")
            
            # Показываем варианты интервалов
            keyboard = [
                [
                    InlineKeyboardButton("⏱️ 10 сек", callback_data=f"interval_10_sec_{book.id}"),
                    InlineKeyboardButton("⏱️ 30 сек", callback_data=f"interval_30_sec_{book.id}")
                ],
                [
                    InlineKeyboardButton("⏰ 1 мин", callback_data=f"interval_1_min_{book.id}"),
                    InlineKeyboardButton("⏰ 3 мин", callback_data=f"interval_3_min_{book.id}")
                ],
                [
                    InlineKeyboardButton("📅 15 мин", callback_data=f"interval_15_min_{book.id}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            summary_text = (
                "✅ <b>Файл успешно загружен!</b>\n\n"
                f"📚 <b>{html.escape(filename)}</b>\n"
                f"📄 Язык: {detected_language.upper()}\n"
                f"📖 Кусков текста: {len(chunks)}\n"
                f"📏 Объем: ~{sum(len(c) for c in chunks) // 1000}KB\n\n"
                "Выберите, как часто отправлять куски:"
            )

            await processing_msg.edit_text(summary_text, reply_markup=reply_markup, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            await processing_msg.edit_text(f"❌ Ошибка при обработке файла:\n{str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок"""
        query = update.callback_query
        user = update.effective_user
        
        await query.answer()
        
        # Обработка выбора книги для /next
        if query.data.startswith('next_'):
            book_id = int(query.data.split('_')[1])
            await query.edit_message_text("⏳ Отправляю следующий кусок...")
            await self._send_next_chunk_for_book(update.effective_chat.id, book_id)
            return

        # Обработка выбора языка
        if query.data.startswith('lang_'):
            language = query.data.split('_')[1]
            db.update_user_language(user.id, language)
            await query.edit_message_text(f"✅ Язык изменён на: {language}")
            return
        
        # Обработка выбора интервала
        if query.data.startswith('interval_'):
            parts = query.data.split('_')
            interval = '_'.join(parts[1:-1])
            book_id = int(parts[-1])
            
            # Создаем расписание
            schedule = db.create_schedule(user.id, book_id, interval)
            
            interval_names = {
                '10_sec': '10 секунд',
                '30_sec': '30 секунд',
                '1_min': '1 минуту',
                '3_min': '3 минуты',
                '15_min': '15 минут',
            }
            
            success_text = (
                "✅ <b>Расписание создано!</b>\n\n"
                f"Куски будут отправляться каждый(е) <b>{interval_names.get(interval, interval)}</b>\n"
                f"Первый кусок отправится в: {schedule.next_send_time.strftime('%d.%m.%Y %H:%M UTC')}\n\n"
                "Используйте /progress для отслеживания прогресса чтения."
            )

            await query.edit_message_text(success_text, parse_mode='HTML')
            
            # Отправляем первый кусок сразу
            chunk = db.get_next_chunk(book_id)
            if chunk:
                book = db.get_book(book_id)
                await self.send_chunk_to_user(update.effective_chat.id, chunk.text, book.title, chunk.chunk_number)
                db.mark_chunk_sent(chunk.id)
                db.update_book_progress(book_id, chunk.chunk_number)
    
    async def send_chunk_to_user(self, chat_id: int, chunk_text: str, book_title: str = None, chunk_num: int = 0):
        """Отправляет кусок текста пользователю"""
        try:
            header = ""
            if book_title:
                header = f"📚 <b>{html.escape(book_title)}</b> (кусок {chunk_num})\n\n"
            body = html.escape(chunk_text)
            message = header + body

            # Разбиваем на части если очень длинный
            if len(message) > 4096:
                parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
                for part in parts:
                    await self.application.bot.send_message(chat_id, part, parse_mode='HTML')
            else:
                await self.application.bot.send_message(chat_id, message, parse_mode='HTML')
            
            logger.info(f"Sent chunk {chunk_num} to chat {chat_id}")
        except Exception as e:
            logger.error(f"Error sending chunk: {e}")
    
    async def next_chunk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /next — отправляет следующий кусок немедленно"""
        user = update.effective_user

        books = db.get_user_books(user.id, active_only=True)
        if not books:
            await update.message.reply_text("📚 Нет активных книг.")
            return

        # Если несколько книг — показываем кнопки выбора
        if len(books) > 1:
            keyboard = [
                [InlineKeyboardButton(
                    f"📖 {book.title[:40]}",
                    callback_data=f"next_{book.id}"
                )]
                for book in books
            ]
            await update.message.reply_text(
                "Выберите книгу:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        await self._send_next_chunk_for_book(update.effective_chat.id, books[0].id)

    async def _send_next_chunk_for_book(self, chat_id: int, book_id: int):
        """Отправляет следующий кусок для указанной книги"""
        book = db.get_book(book_id)
        if not book or book.is_completed:
            await self.application.bot.send_message(chat_id, "✅ Книга уже дочитана!")
            return

        chunk = db.get_next_chunk(book_id)
        if not chunk:
            await self.application.bot.send_message(chat_id, "✅ Больше кусков нет — книга дочитана!")
            db.update_book_progress(book_id, book.total_chunks)
            return

        await self.send_chunk_to_user(chat_id, chunk.text, book.title, chunk.chunk_number)
        db.mark_chunk_sent(chunk.id)
        db.update_book_progress(book_id, chunk.chunk_number)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /cancel"""
        await update.message.reply_text("❌ Операция отменена.")
        return ConversationHandler.END
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Update {update} caused error {context.error}")
    
    def run(self):
        """Запускает бота"""
        logger.info("Starting bot...")
        self.application.run_polling()


def main():
    """Главная функция"""
    bot = CaterpillarReadBot()
    bot.run()


if __name__ == '__main__':
    main()
