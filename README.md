# CaterpillarRead (Caterpillar Read) 📚

Telegram бот для чтения электронных книг маленькими порциями с заданной периодичностью.

## 📋 Оглавление

- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Запуск](#запуск)
- [Архитектура](#архитектура)
- [API Документация](#api-документация)

## 🔧 Требования

- Python 3.9+
- PostgreSQL 12+
- Redis 6.0+
- Telegram Bot Token

## 📦 Установка

### 1. Клонируем репозиторий
```bash
git clone <repository_url>
cd caterpillar_read
```

### 2. Создаем виртуальное окружение
```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Устанавливаем зависимости
```bash
pip install -r requirements.txt
```

### 4. Конфигурируем окружение
```bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем .env с вашими параметрами
nano .env  # или используйте ваш редактор
```

## ⚙️ Конфигурация

### Переменные окружения (.env)

```env
# Telegram Bot
TELEGRAM_TOKEN=your_telegram_bot_token_here

# PostgreSQL Database
DATABASE_URL=postgresql://username:password@localhost:5432/caterpillar_read

# Redis (для Celery)
REDIS_URL=redis://localhost:6379/0

# Логирование
LOG_LEVEL=INFO

# Настройки разбиения текста
CHUNK_SIZE_MIN=300          # Минимум символов в куске
CHUNK_SIZE_MAX=2000         # Максимум символов в куске
MAX_MESSAGES=2              # Максимум сообщений в рассылке

# Языковые модели spaCy
SPACY_MODEL_EN=en_core_web_sm
SPACY_MODEL_RU=ru_core_news_sm

# Загрузка файлов
MAX_FILE_SIZE=50000000      # 50MB в байтах
UPLOAD_DIR=./uploads
TEMP_DIR=./temp
```

### Создание базы данных PostgreSQL

```bash
# Подключитесь к PostgreSQL
psql -U postgres

# Создайте базу данных
CREATE DATABASE caterpillar_read;
CREATE USER caterpillar WITH PASSWORD 'your_password';
ALTER ROLE caterpillar SET client_encoding TO 'utf8';
ALTER ROLE caterpillar SET default_transaction_isolation TO 'read committed';
ALTER ROLE caterpillar SET default_transaction_deferrable TO on;
ALTER ROLE caterpillar SET default_transaction_read_only TO off;
GRANT ALL PRIVILEGES ON DATABASE caterpillar_read TO caterpillar;
\q
```

### Установка Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:7
```

### Установка NLP моделей

```bash
# Английская модель
python -m spacy download en_core_web_sm

# Русская модель
python -m spacy download ru_core_news_sm
```

## 🚀 Запуск

### 1. Инициализация проекта

```bash
python init_project.py
```

Это выполнит:
- Проверку конфигурации
- Создание таблиц БД
- Загрузку языковых моделей
- Проверку подключений

### 2. Запуск Telegram бота

```bash
python bot.py
```

Вывод:
```
2024-01-15 10:30:45 - root - INFO - Starting bot...
2024-01-15 10:30:45 - root - INFO - Bot handlers setup completed
```

### 3. Запуск Celery Worker (в отдельном терминале)

```bash
celery -A tasks worker --loglevel=info
```

### 4. Запуск Celery Beat (в отдельном терминале)

```bash
celery -A tasks beat --loglevel=info
```

Celery Beat проверяет расписания каждую минуту и отправляет готовые куски.

### Полная инструкция для Linux

```bash
# Откройте 3 терминала

# Терминал 1: Telegram бот
source venv/bin/activate
python bot.py

# Терминал 2: Celery Worker
source venv/bin/activate
celery -A tasks worker --loglevel=info

# Терминал 3: Celery Beat Scheduler
source venv/bin/activate
celery -A tasks beat --loglevel=info
```

## 🏗️ Архитектура

### Компоненты

```
CaterpillarRead/
├── bot.py                 # Главный Telegram бот
├── database.py           # Слой работы с БД
├── models.py             # SQLAlchemy модели
├── file_parser.py        # Парсинг файлов (TXT, PDF, EPUB, MOBI, DOCX)
├── chunk_generator.py    # Умное разбиение текста
├── tasks.py              # Celery задачи для планирования
├── config.py             # Конфигурация приложения
├── init_project.py       # Скрипт инициализации
├── requirements.txt      # Зависимости Python
└── .env.example          # Пример конфигурации
```

### Поток данных

```
┌─────────────────────┐
│   Telegram User     │
│   (отправляет файл) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   bot.py            │
│  handle_file_upload │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  file_parser.py     │
│  (парсит файл)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ chunk_generator.py  │
│ (разбивает текст)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  database.py        │
│  (сохраняет куски)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Celery Beat         │
│ (проверка каждую    │
│  минуту)            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Celery Worker       │
│ (отправляет куски)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Telegram User      │
│  (получает куски)   │
└─────────────────────┘
```

### Модели БД

#### User
- `id` - Уникальный ID
- `telegram_id` - ID в Telegram
- `chat_id` - ID чата
- `username` - Имя пользователя
- `language` - Язык для обработки (ru/en/auto)
- `timezone` - Часовой пояс
- `is_active` - Активен ли пользователь

#### Book
- `id` - Уникальный ID
- `user_id` - ID пользователя
- `filename` - Имя файла на диске
- `original_filename` - Оригинальное имя
- `file_format` - Формат файла (txt, pdf, epub, mobi, docx)
- `title` - Название книги
- `author` - Автор
- `total_chunks` - Всего кусков
- `current_chunk` - Текущий куск
- `detected_language` - Обнаруженный язык
- `is_completed` - Завершена ли книга

#### Chunk
- `id` - Уникальный ID
- `book_id` - ID книги
- `chunk_number` - Номер куска
- `text` - Текст куска
- `character_count` - Количество символов
- `word_count` - Количество слов
- `sent_at` - Когда был отправлен

#### Schedule
- `id` - Уникальный ID
- `user_id` - ID пользователя
- `book_id` - ID книги
- `interval` - Интервал отправки
- `interval_minutes` - Интервал в минутах
- `next_send_time` - Время следующей отправки
- `is_active` - Активно ли расписание

## 📱 Команды бота

| Команда | Описание |
|---------|---------|
| `/start` | Приветствие и инструкции |
| `/help` | Справка по командам |
| `/books` | Список загруженных книг |
| `/progress` | Прогресс чтения |
| `/settings` | Настройки (выбор языка) |
| `/cancel` | Отмена операции |

## 📤 Поддерживаемые форматы

- ✅ TXT (текстовые файлы)
- ✅ PDF (с использованием PyPDF2 и pdfplumber)
- ✅ EPUB (электронные книги)
- ✅ MOBI (Amazon Kindle)
- ✅ DOCX (Microsoft Word)
- ✅ DOC (старые Word документы)

## ⏱️ Интервалы рассылки

- ⏱️ 15 минут
- ⏱️ 30 минут
- ⏰ 1 час
- ⏰ 3 часа
- ⏰ 6 часов
- 📅 1 день
- 📅 2 дня
- 📅 1 неделя

## 🔧 Настройка разбиения текста

Параметры в `.env`:

```env
# Минимальный размер куска (если меньше, объединяется с соседним)
CHUNK_SIZE_MIN=300

# Максимальный размер куска (если больше, разбивается по предложениям)
CHUNK_SIZE_MAX=2000
```

### Алгоритм разбиения

1. Текст разбивается по параграфам (`\n\n`)
2. Каждый параграф разбивается на предложения (используется spaCy для русского/английского)
3. Куски собираются таким образом, чтобы:
   - Не рвались слова
   - Не рвались предложения
   - Не разрывались по смыслу
   - Размер был между MIN и MAX
4. Маленькие куски объединяются с соседними

## 🐛 Отладка

### Проверка логов

```bash
# Телеграм бот
tail -f logs/bot.log

# Celery worker
tail -f logs/worker.log

# Celery beat
tail -f logs/beat.log
```

### Проверка БД

```bash
psql -U caterpillar -d caterpillar_read

# Список таблиц
\dt

# Просмотр пользователей
SELECT * FROM users;

# Просмотр книг
SELECT * FROM books;

# Просмотр расписаний
SELECT * FROM schedules;
```

### Проверка Redis

```bash
redis-cli

# Проверка статуса
PING  # Should return PONG

# Просмотр ключей
KEYS *
```

## 🚨 Решение проблем

### PostgreSQL не подключается
```bash
# Проверьте DATABASE_URL в .env
# Убедитесь, что PostgreSQL запущен
sudo systemctl status postgresql

# Проверьте пароль и доступ
psql -U caterpillar -d caterpillar_read
```

### Redis не подключается
```bash
# Проверьте, что Redis запущен
redis-cli ping

# Если выключен, запустите
redis-server
```

### spaCy модель не скачалась
```bash
# Скачайте вручную
python -m spacy download en_core_web_sm
python -m spacy download ru_core_news_sm
```

### Бот не отвечает
```bash
# Проверьте TELEGRAM_TOKEN в .env
# Убедитесь, что токен корректный
# Перезагрузите бота

# Проверьте логи
tail -100 logs/*.log
```

## 📊 Мониторинг

### Celery Flower (веб-интерфейс)

```bash
# Установка
pip install flower

# Запуск (порт 5555)
celery -A tasks flower
```

Откройте http://localhost:5555 для просмотра статуса задач.

## 🔐 Безопасность

- Не коммитьте `.env` файл в git
- Используйте сильные пароли для PostgreSQL
- Ограничивайте доступ к серверу
- Регулярно обновляйте зависимости

## 📝 Логирование

Логирование настроено на уровне INFO. Для изменения:

```env
LOG_LEVEL=DEBUG    # Более подробные логи
LOG_LEVEL=WARNING  # Только важные события
```

## 🤝 Развитие проекта

Возможные улучшения:

- [ ] Web админка для управления расписаниями
- [ ] Поддержка аудиокниг (TTS)
- [ ] Синхронизация между устройствами
- [ ] Статистика по чтению
- [ ] Группы и списки чтения
- [ ] Интеграция с GoodReads

## 📄 Лицензия

MIT License - смотрите LICENSE файл

## 💬 Поддержка

Для вопросов и предложений создавайте Issues в репозитории.

---

**Автор:** CaterpillarRead Bot Project  
**Версия:** 1.0.0  
**Последнее обновление:** 2024
