# 🚀 Быстрый Старт CaterpillarRead

Этот гайд поможет вам за 5 минут развернуть бота локально.

## Вариант 1: Docker (Рекомендуется) 🐳

### Требования
- Docker
- Docker Compose

### Шаги

1. **Клонируем проект**
```bash
git clone <repository_url>
cd caterpillar_read
```

2. **Конфигурируем переменные окружения**
```bash
cp .env.example .env

# Отредактируйте .env и добавьте TELEGRAM_TOKEN
nano .env
```

Обязательно установите:
```env
TELEGRAM_TOKEN=your_actual_token_from_botfather
POSTGRES_PASSWORD=change_me_to_secure_password
```

3. **Запускаем контейнеры**
```bash
docker-compose up -d
```

4. **Проверяем статус**
```bash
docker-compose ps

# Должны быть запущены:
# - postgres
# - redis
# - bot
# - celery_worker
# - celery_beat
# - flower (мониторинг)
```

5. **Проверяем логи**
```bash
# Логи бота
docker-compose logs -f bot

# Логи worker
docker-compose logs -f celery_worker

# Логи beat
docker-compose logs -f celery_beat
```

6. **Мониторинг**
```
Открыть в браузере: http://localhost:5555
```

7. **Остановить**
```bash
docker-compose down
```

---

## Вариант 2: Локальная установка (Linux/macOS)

### Требования
- Python 3.9+
- PostgreSQL 12+
- Redis 6.0+

### Шаги

1. **Клонируем проект**
```bash
git clone <repository_url>
cd caterpillar_read
```

2. **Создаем виртуальное окружение**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate      # Windows
```

3. **Устанавливаем зависимости**
```bash
pip install -r requirements.txt
```

4. **PostgreSQL**
```bash
# Создаем БД
createdb -U postgres caterpillar_read

# Создаем пользователя
psql -U postgres -c "CREATE USER caterpillar WITH PASSWORD 'password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE caterpillar_read TO caterpillar;"
```

5. **Redis**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis
```

6. **Конфигурируем окружение**
```bash
cp .env.example .env
nano .env

# Установите:
# TELEGRAM_TOKEN=your_token
# DATABASE_URL=postgresql://caterpillar:password@localhost:5432/caterpillar_read
```

7. **Инициализируем проект**
```bash
python init_project.py
```

8. **Запускаем компоненты (в отдельных терминалах)**

Терминал 1 - Бот:
```bash
source venv/bin/activate
python bot.py
```

Терминал 2 - Celery Worker:
```bash
source venv/bin/activate
celery -A tasks worker --loglevel=info
```

Терминал 3 - Celery Beat:
```bash
source venv/bin/activate
celery -A tasks beat --loglevel=info
```

---

## Вариант 3: Windows

### Требования
- Python 3.9+
- PostgreSQL
- Redis для Windows (WSL2 рекомендуется)

### Шаги

1. **Клонируем проект**
```bash
git clone <repository_url>
cd caterpillar_read
```

2. **Создаем и активируем виртуальное окружение**
```bash
python -m venv venv
venv\Scripts\activate
```

3. **Устанавливаем зависимости**
```bash
pip install -r requirements.txt
```

4. **Конфигурируем**
```bash
copy .env.example .env

# Отредактируйте .env в текстовом редакторе
```

5. **Запускаем**

PowerShell 1 - Бот:
```powershell
.\venv\Scripts\Activate.ps1
python bot.py
```

PowerShell 2 - Worker:
```powershell
.\venv\Scripts\Activate.ps1
celery -A tasks worker --loglevel=info
```

PowerShell 3 - Beat:
```powershell
.\venv\Scripts\Activate.ps1
celery -A tasks beat --loglevel=info
```

---

## 🔐 Получение Telegram Token

1. Откройте @BotFather в Telegram
2. Выполните `/start`
3. Выполните `/newbot`
4. Следуйте инструкциям
5. Скопируйте полученный token в `.env`

---

## ✅ Проверка работы

1. **Отправьте сообщение боту**
   - Должен ответить с приветствием

2. **Загрузите файл**
   - Отправьте .txt или .pdf файл
   - Бот должен обработать файл

3. **Выберите интервал**
   - Нажмите кнопку интервала
   - Бот должен отправить первый кусок

---

## 🐛 Частые проблемы

### PostgreSQL ошибка подключения
```bash
# Проверьте DATABASE_URL в .env
# Проверьте, что PostgreSQL запущен
sudo systemctl status postgresql

# Или используйте Docker вариант
```

### Redis ошибка подключения
```bash
# Проверьте, что Redis запущен
redis-cli ping

# Если выключен:
redis-server  # Linux/macOS
```

### Модели spaCy не скачались
```bash
python -m spacy download en_core_web_sm
python -m spacy download ru_core_news_sm
```

### Telegram токен не работает
- Проверьте, что скопировали полный токен
- Убедитесь, что нет пробелов в .env
- Создайте новый бот у BotFather

---

## 📊 Мониторинг (Docker)

```bash
# Все контейнеры
docker-compose ps

# Логи всех компонентов
docker-compose logs

# Логи конкретного компонента
docker-compose logs -f bot

# Веб интерфейс Flower
http://localhost:5555
```

---

## 🛑 Остановка

### Docker
```bash
docker-compose down

# С удалением данных
docker-compose down -v
```

### Локально
```
Ctrl+C в каждом терминале
```

---

## 📚 Используемые текстовые файлы для тестирования

Вот примеры текстов на русском для тестирования:

### 1. Классическая русская литература
- Война и мир - Толстой
- Преступление и наказание - Достоевский
- Мёртвые души - Гоголь

### 2. Русскоязычные тексты
- Любая статья на Википедии
- Новостные статьи
- Научные статьи

**Где найти:**
- Project Gutenberg RU (https://www.gutenberg.org/browse/languages/ru)
- Lib.ru (https://lib.ru/)
- Флибустьер (https://flibusta.site/)

---

## ⚙️ Дополнительные команды

```bash
# Просмотр БД
psql -U caterpillar -d caterpillar_read

# Просмотр Redis
redis-cli

# Просмотр Celery задач
celery -A tasks events

# Перестройка контейнеров
docker-compose build --no-cache
```

---

## 📞 Нужна помощь?

- 📖 Полная документация: README.md
- 🐛 Ошибки: смотрите логи (logs/)
- 💬 Вопросы: создавайте Issue

---

**Поздравляем! CaterpillarRead готов к работе! 🎉**

Отправьте первую книгу боту и начните читать кусочками! 📚
