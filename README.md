# CaterpillarRead 📚

Telegram-бот для чтения электронных книг небольшими порциями с заданной периодичностью.

---

## Оглавление

- [Как получить Telegram-токен](#как-получить-telegram-токен)
- [Быстрый старт — Docker (рекомендуется)](#быстрый-старт--docker-рекомендуется)
- [Развёртывание на VPS-сервере](#развёртывание-на-vps-сервере)
- [Переменные окружения](#переменные-окружения)
- [Команды бота](#команды-бота)
- [Мониторинг и логи](#мониторинг-и-логи)
- [Полезные команды](#полезные-команды)
- [Решение проблем](#решение-проблем)
- [Архитектура](#архитектура)
- [Известные ограничения](#известные-ограничения)

---

## Как получить Telegram-токен

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Введите имя и username бота
4. Скопируйте полученный токен вида `123456789:AAF...`

---

## Быстрый старт — Docker (рекомендуется)

### Требования

- Docker 20.10+
- Docker Compose v2 (входит в Docker Desktop и современные версии Docker Engine)

### Шаги

**1. Клонируем репозиторий**

```bash
git clone https://github.com/Shurandemg/caterpillaread.git
cd caterpillaread/caterpillaread
git checkout claude/keen-goodall-Ut2XM
```

**2. Создаём файл `.env`**

```bash
cp .env.example .env
nano .env
```

Обязательно заполните:

```env
TELEGRAM_TOKEN=токен_от_BotFather
POSTGRES_PASSWORD=придумайте_надёжный_пароль
```

Остальные значения можно оставить по умолчанию.

**3. Запускаем**

```bash
docker compose up -d --build
```

**4. Проверяем статус**

```bash
docker compose ps
```

Все контейнеры должны быть в состоянии `running`:

| Контейнер          | Роль                        |
|--------------------|-----------------------------|
| caterpillar_postgres | База данных PostgreSQL      |
| caterpillar_redis    | Брокер задач Redis          |
| caterpillar_bot      | Telegram-бот                |
| caterpillar_worker   | Celery Worker (выполнение)  |
| caterpillar_beat     | Celery Beat (расписание)    |
| caterpillar_flower   | Веб-интерфейс мониторинга   |

**5. Проверяем логи бота**

```bash
docker compose logs -f bot
```

---

## Развёртывание на VPS-сервере

### 1. Установка Docker на чистый сервер (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com | sh
```

Проверяем:

```bash
docker --version
docker compose version
```

### 2. Клонируем проект

```bash
git clone https://github.com/Shurandemg/caterpillaread.git /opt/caterpillaread
cd /opt/caterpillaread/caterpillaread
git checkout claude/keen-goodall-Ut2XM
```

### 3. Создаём `.env`

```bash
cp .env.example .env
nano .env
```

### 4. Запускаем

```bash
docker compose up -d --build
```

### 5. Настройка автозапуска после перезагрузки

Контейнеры уже настроены на `restart: unless-stopped`, то есть поднимутся сами после перезагрузки сервера при условии, что Docker-демон запускается автоматически:

```bash
systemctl enable docker
```

### Обновление до новой версии

```bash
cd /opt/caterpillaread/caterpillaread
git pull origin claude/keen-goodall-Ut2XM
docker compose build bot celery_worker celery_beat
docker compose up -d bot celery_worker celery_beat
```

Базу данных и Redis пересобирать не нужно — данные сохраняются в Docker volumes.

---

## Переменные окружения

Все переменные задаются в файле `.env` в папке `caterpillaread/`.

| Переменная         | Обязательно | Значение по умолчанию                  | Описание                                 |
|--------------------|-------------|----------------------------------------|------------------------------------------|
| `TELEGRAM_TOKEN`   | ✅           | —                                      | Токен бота от @BotFather                 |
| `POSTGRES_PASSWORD`| ✅           | `caterpillar_pass`                     | Пароль PostgreSQL (смените!)             |
| `POSTGRES_USER`    |             | `caterpillar`                          | Пользователь PostgreSQL                  |
| `POSTGRES_DB`      |             | `caterpillaread`                       | Имя базы данных                          |
| `POSTGRES_HOST`    |             | `postgres`                             | Хост PostgreSQL (внутри Docker — `postgres`) |
| `POSTGRES_PORT`    |             | `5432`                                 | Порт PostgreSQL                          |
| `REDIS_URL`        |             | `redis://redis:6379/0`                 | URL Redis                                |
| `CHUNK_SIZE_MIN`   |             | `500`                                  | Минимальный размер куска (символов)      |
| `CHUNK_SIZE_MAX`   |             | `3000`                                 | Максимальный размер куска (символов)     |
| `MAX_FILE_SIZE`    |             | `52428800` (50 MB)                     | Максимальный размер загружаемого файла   |
| `UPLOAD_DIR`       |             | `uploads`                              | Папка для загруженных файлов             |
| `LOG_LEVEL`        |             | `INFO`                                 | Уровень логирования (`DEBUG`/`INFO`/`WARNING`) |

> **Важно:** переменные `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` используются только при запуске **без Docker** (локально). В Docker-режиме соединение задаётся через `DATABASE_URL`, который docker-compose формирует автоматически.

---

## Команды бота

| Команда      | Описание                            |
|--------------|-------------------------------------|
| `/start`     | Приветствие и краткая инструкция    |
| `/help`      | Справка по командам и форматам      |
| `/books`     | Список загруженных книг с прогрессом|
| `/progress`  | Прогресс чтения и расписание        |
| `/settings`  | Смена языка обработки текста        |
| `/cancel`    | Отмена текущей операции             |

### Поддерживаемые форматы файлов

| Формат | Поддержка    |
|--------|--------------|
| TXT    | ✅ Полная     |
| PDF    | ✅ Полная     |
| DOCX   | ✅ Полная     |
| EPUB   | ✅ Полная     |
| DOC    | ⚠️ Только если файл совместим с DOCX |
| MOBI   | ❌ Не поддерживается (библиотека не установлена) |

### Интервалы рассылки

15 мин · 30 мин · 1 час · 3 часа · 6 часов · 1 день · 2 дня · 1 неделя

---

## Мониторинг и логи

### Логи контейнеров

```bash
# Логи бота (в реальном времени)
docker compose logs -f bot

# Логи Celery Worker
docker compose logs -f celery_worker

# Логи Celery Beat (расписание)
docker compose logs -f celery_beat

# Логи всех сервисов сразу
docker compose logs -f

# Последние 100 строк бота
docker compose logs --tail=100 bot
```

### Веб-интерфейс Flower (Celery)

После запуска откройте в браузере: **http://ваш_ip:5555**

Там видны все задачи, воркеры и очереди.

### Статус контейнеров

```bash
docker compose ps
```

### Использование ресурсов

```bash
docker stats
```

---

## Полезные команды

### Управление контейнерами

```bash
# Запустить всё
docker compose up -d

# Остановить всё (данные сохраняются)
docker compose down

# Остановить и удалить данные (БД, Redis)
docker compose down -v

# Перезапустить один сервис
docker compose restart bot

# Пересобрать образы и перезапустить
docker compose up -d --build
```

### Работа с базой данных

```bash
# Подключиться к PostgreSQL внутри контейнера
docker compose exec postgres psql -U caterpillar -d caterpillar_read

# Список таблиц
\dt

# Посмотреть пользователей
SELECT * FROM users;

# Посмотреть книги
SELECT id, title, total_chunks, current_chunk, is_completed FROM books;

# Посмотреть расписания
SELECT * FROM schedules;

# Выйти из psql
\q
```

### Работа с Redis

```bash
# Подключиться к Redis внутри контейнера
docker compose exec redis redis-cli

# Проверить соединение
PING   # должен ответить PONG

# Посмотреть все ключи
KEYS *

# Выйти
exit
```

### Отладка внутри контейнера

```bash
# Открыть shell в контейнере бота
docker compose exec bot bash

# Проверить переменные окружения
docker compose exec bot env | grep TELEGRAM
docker compose exec bot env | grep DATABASE
```

### Принудительный перезапуск после сбоя

```bash
docker compose down
docker compose up -d
```

---

## Решение проблем

### Бот не отвечает

```bash
# Смотрим логи
docker compose logs --tail=50 bot

# Проверяем, что токен задан
docker compose exec bot env | grep TELEGRAM_TOKEN
```

Частые причины:
- Неверный или пустой `TELEGRAM_TOKEN` в `.env`
- Контейнер упал — проверьте `docker compose ps`

### Куски не отправляются по расписанию

```bash
# Проверяем, что Beat и Worker запущены
docker compose ps

# Смотрим логи Beat
docker compose logs --tail=50 celery_beat

# Смотрим логи Worker
docker compose logs --tail=50 celery_worker
```

### PostgreSQL не запускается

```bash
docker compose logs postgres
```

Частая причина — уже занят порт 5432. Проверьте:
```bash
# Linux
ss -tlnp | grep 5432

# macOS
lsof -i :5432
```

### Ошибка при загрузке файла

```bash
docker compose logs --tail=100 bot | grep ERROR
```

### Пересборка с нуля (если что-то пошло совсем не так)

```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

> ⚠️ `down -v` удалит все данные базы данных.

---

## Архитектура

```
Пользователь
    │
    │ отправляет файл
    ▼
bot.py  ──── скачивает ────► file_parser.py  (TXT / PDF / EPUB / DOCX)
    │                              │
    │                              ▼
    │                        chunk_generator.py  (разбивка на куски)
    │                              │
    │                              ▼
    │                         database.py  (сохранение в PostgreSQL)
    │
    │ пользователь выбирает интервал
    ▼
database.py  (создаёт расписание Schedule)
    │
    │ каждую минуту
    ▼
Celery Beat  ──► tasks.send_scheduled_chunks  ──► Celery Worker
                                                        │
                                                        ▼
                                                 bot.send_message
                                                        │
                                                        ▼
                                                 Пользователь получает кусок
```

### Файлы проекта

| Файл                 | Назначение                                      |
|----------------------|-------------------------------------------------|
| `bot.py`             | Telegram-бот, обработчики команд и файлов       |
| `tasks.py`           | Celery-задачи: обработка и рассылка по расписанию |
| `database.py`        | Все операции с PostgreSQL через SQLAlchemy      |
| `models.py`          | Модели данных: User, Book, Chunk, Schedule      |
| `file_parser.py`     | Парсинг форматов TXT, PDF, EPUB, DOCX           |
| `chunk_generator.py` | Умная разбивка текста на смысловые куски        |
| `config.py`          | Конфигурация из переменных окружения            |
| `init_project.py`    | Скрипт проверки окружения (для локального запуска) |

---

## Известные ограничения

- **MOBI** — формат не поддерживается: библиотека `mobi` отсутствует в `requirements.txt`. Для добавления поддержки установите `pip install mobi` и добавьте её в `requirements.txt`.
- **DOC (старый формат Word)** — поддерживается только если файл совместим с DOCX. Настоящие `.doc` файлы (до Office 2007) не обрабатываются.
- **Большие файлы** — парсинг происходит синхронно в обработчике бота. Очень большие книги (>10 MB текста) могут обрабатываться несколько секунд.
