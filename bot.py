import os
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
        
        welcome_text = f"""
👋 Добро пожаловать в **Caterpillar Read** ({user.first_name})!

Я помогу вам читать книги небольшими порциями. Вот что я умею:

📚 **/books** - Посмотреть список загруженных книг
⚙️ **/settings** - Изменить язык и другие настройки
📊 **/progress** - Посмотреть прогресс чтения
❓ **/help** - Справка по командам

**Как начать:**
1. Отправьте мне файл книги (TXT, PDF, EPUB, MOBI, DOCX)
2. Выберите периодичность отправки (раз в час, раз в день и т.д.)
3. Я буду отправлять вам куски текста по расписанию 📖

**Форматы:** TXT, PDF, EPUB, MOBI, DOC, DOCX
**Максимальный размер:** 50MB
        """
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        logger.info(f"User {user.id} started the bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📖 **Доступные команды:**

/start - Перезагрузить приветствие
/books - Список ваших книг
/settings - Настройки (язык и т.д.)
/progress - Прогресс чтения каждой книги
/help - Эта справка

**Как загрузить книгу:**
1. Просто отправьте файл боту (TXT, PDF, EPUB, MOBI, DOCX)
2. Выберите интервал отправки
3. Готово! Начнется отправка кусочков текста

**Доступные интервалы:**
⏱️ 15 минут
⏱️ 30 минут
⏰ 1 час
⏰ 3 часа
⏰ 6 часов
📅 1 день
📅 2 дня
📅 1 неделя
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def list_books(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /books"""
        user = update.effective_user
        
        books = db.get_user_books(user.id, active_only=False)
        
        if not books:
            await update.message.reply_text("📚 У вас пока нет загруженных книг.")
            return
        
        books_text = "📚 **Ваши книги:**\n\n"
        
        for i, book in enumerate(books, 1):
            progress = (book.current_chunk / book.total_chunks * 100) if book.total_chunks > 0 else 0
            status = "✅ Прочитана" if book.is_completed else "📖 Читается"
            
            books_text += f"{i}. **{book.title}**\n"
            books_text += f"   Автор: {book.author or 'Неизвестен'}\n"
            books_text += f"   Статус: {status}\n"
            books_text += f"   Прогресс: {book.current_chunk}/{book.total_chunks} кусков ({progress:.1f}%)\n"
            books_text += f"   Формат: {book.file_format.upper()}\n\n"
        
        await update.message.reply_text(books_text, parse_mode='Markdown')
    
    async def progress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /progress"""
        user = update.effective_user
        
        books = db.get_user_books(user.id, active_only=True)
        
        if not books:
            await update.message.reply_text("📊 Нет активных книг для чтения.")
            return
        
        progress_text = "📊 **Ваш прогресс:**\n\n"
        
        for book in books:
            schedule = db.get_schedule(book.id)
            progress = (book.current_chunk / book.total_chunks * 100) if book.total_chunks > 0 else 0
            
            progress_text += f"📖 **{book.title}**\n"
            progress_text += f"Прочитано: {book.current_chunk}/{book.total_chunks} ({progress:.1f}%)\n"
            
            if schedule:
                next_send = schedule.next_send_time
                interval_text = {
                    '15_min': 'каждые 15 минут',
                    '30_min': 'каждые 30 минут',
                    '1_hour': 'каждый час',
                    '3_hours': 'каждые 3 часа',
                    '6_hours': 'каждые 6 часов',
                    'daily': 'каждый день',
                    '2_days': 'каждые 2 дня',
                    'weekly': 'каждую неделю',
                }.get(schedule.interval, 'неизвестный')
                
                progress_text += f"Отправка: {interval_text}\n"
                progress_text += f"Следующая отправка: {next_send.strftime('%d.%m.%Y %H:%M UTC')}\n"
            
            progress_text += "\n"
        
        await update.message.reply_text(progress_text, parse_mode='Markdown')
    
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
                    InlineKeyboardButton("⏱️ 15 мин", callback_data=f"interval_15_min_{book.id}"),
                    InlineKeyboardButton("⏱️ 30 мин", callback_data=f"interval_30_min_{book.id}")
                ],
                [
                    InlineKeyboardButton("⏰ 1 час", callback_data=f"interval_1_hour_{book.id}"),
                    InlineKeyboardButton("⏰ 3 часа", callback_data=f"interval_3_hours_{book.id}")
                ],
                [
                    InlineKeyboardButton("⏰ 6 часов", callback_data=f"interval_6_hours_{book.id}"),
                    InlineKeyboardButton("📅 1 день", callback_data=f"interval_daily_{book.id}")
                ],
                [
                    InlineKeyboardButton("📅 2 дня", callback_data=f"interval_2_days_{book.id}"),
                    InlineKeyboardButton("📅 1 неделя", callback_data=f"interval_weekly_{book.id}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            summary_text = f"""
✅ **Файл успешно загружен!**

📚 **{filename}**
📄 Язык: {detected_language.upper()}
📖 Кусков текста: {len(chunks)}
📏 Объем: ~{sum(len(c) for c in chunks) // 1000}KB

Выберите, как часто отправлять куски:
            """
            
            await processing_msg.edit_text(summary_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            await processing_msg.edit_text(f"❌ Ошибка при обработке файла:\n{str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок"""
        query = update.callback_query
        user = update.effective_user
        
        await query.answer()
        
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
                '15_min': '15 минут',
                '30_min': '30 минут',
                '1_hour': '1 час',
                '3_hours': '3 часа',
                '6_hours': '6 часов',
                'daily': '1 день',
                '2_days': '2 дня',
                'weekly': '1 неделю',
            }
            
            success_text = f"""
✅ **Расписание создано!**

Куски будут отправляться каждый(е) **{interval_names.get(interval, interval)}**
Первый кусок отправится в: {schedule.next_send_time.strftime('%d.%m.%Y %H:%M UTC')}

Используйте /progress для отслеживания прогресса чтения.
            """
            
            await query.edit_message_text(success_text, parse_mode='Markdown')
            
            # Отправляем первый кусок сразу
            chunk = db.get_next_chunk(book_id)
            if chunk:
                book = db.get_book(book_id)
                await self.send_chunk_to_user(update.effective_chat.id, chunk.text, book.title, chunk.chunk_number)
    
    async def send_chunk_to_user(self, chat_id: int, chunk_text: str, book_title: str = None, chunk_num: int = 0):
        """Отправляет кусок текста пользователю"""
        try:
            message = ""
            if book_title:
                message += f"📚 **{book_title}** (кусок {chunk_num})\n\n"
            message += chunk_text
            
            # Разбиваем на части если очень длинный
            if len(message) > 4096:  # Лимит Telegram
                parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
                for part in parts:
                    await self.application.bot.send_message(chat_id, part, parse_mode='Markdown')
            else:
                await self.application.bot.send_message(chat_id, message, parse_mode='Markdown')
            
            logger.info(f"Sent chunk {chunk_num} to chat {chat_id}")
        except Exception as e:
            logger.error(f"Error sending chunk: {e}")
    
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
