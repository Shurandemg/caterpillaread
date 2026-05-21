FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download ru_core_news_sm && \
    python -m spacy download en_core_web_sm

COPY . .

RUN mkdir -p uploads logs

CMD ["python", "bot.py"]
