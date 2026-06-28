FROM python:3.12-slim

# Отключаем буферизацию логов Python, чтобы принты воркера сразу летели в docker logs
ENV PYTHONUNBUFFERED=1
# Запрещаем Python писать файлы кэша .pyc внутри контейнера
ENV PYTHONDONTWRITEBYTECODE=1

# Устанавливаем системные утилиты, необходимые для сборки некоторых библиотек (например, curl_cffi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Шаг кэширования: сначала копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем весь проект целиком, чтобы воркер видел и папку parser, и config.py, и logger.py
COPY . .

# Команду запуска мы вынесли в docker-compose.yml, поэтому здесь CMD можно не писать, 
# либо оставить как дефолтный вариант на случай ручного запуска контейнера:
CMD ["taskiq", "worker", "parser.broker:broker", "parser.tasks"]