#!/bin/bash

# Остановка при любой ошибке
set -e

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log "Начинаем настройку сервера Ubuntu 24.04..."

# 1. Обновление системы
log "Обновление пакетов системы..."
sudo apt update && sudo apt upgrade -y

# 2. Установка необходимых системных утилит и библиотек
log "Установка git, curl и библиотек для PostgreSQL..."
# libpq-dev нужен для сборки драйвера psycopg2/asyncpg
sudo apt install -y curl git build-essential libpq-dev python3-dev python3-venv python3-pip

# 3. Установка Docker и Docker Compose (Официальный репозиторий)
log "Установка Docker..."
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Добавляем текущего пользователя в группу docker (чтобы не писать sudo docker)
sudo usermod -aG docker $USER

# 4. Настройка Firewall (UFW)
log "Настройка Firewall (открываем SSH)..."
sudo ufw allow OpenSSH
# Можно раскомментировать, если API будет смотреть наружу без Nginx
# sudo ufw allow 8000 
sudo ufw --force enable

# 5. Создание структуры проекта
PROJECT_DIR="$HOME/ride_share_bot"
log "Создание структуры проекта в $PROJECT_DIR..."

mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/src/bot"
mkdir -p "$PROJECT_DIR/src/services"
mkdir -p "$PROJECT_DIR/src/database"

cd "$PROJECT_DIR"

# 6. Создание файлов конфигурации

# --- requirements.txt ---
log "Создание requirements.txt..."
cat << EOF > requirements.txt
aiogram>=3.4.0
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.28
geoalchemy2>=0.14.0
asyncpg>=0.29.0
pydantic-settings>=2.2.0
python-dotenv>=1.0.1
EOF

# --- docker-compose.yml ---
log "Создание docker-compose.yml (PostgreSQL + PostGIS)..."
cat << EOF > docker-compose.yml
version: '3.8'

services:
  db:
    image: postgis/postgis:15-3.3
    restart: always
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: ride_share_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:alpine
    restart: always
    ports:
      - "6379:6379"

volumes:
  postgres_data:
EOF

# --- .env (Заглушка) ---
log "Создание файла .env..."
cat << EOF > .env
BOT_TOKEN=replace_me_with_telegram_token
DATABASE_URL=postgresql+asyncpg://user:password@localhost/ride_share_db
OPENAI_API_KEY=replace_me_if_needed
EOF

# 7. Настройка Python Virtual Environment
log "Создание виртуального окружения Python..."
python3 -m venv venv

log "Активация venv и установка зависимостей..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Запуск Docker контейнеров
log "Запуск базы данных через Docker..."
docker compose up -d

success "Установка завершена!"
echo "--------------------------------------------------------"
echo "ВАЖНО: Чтобы Docker заработал без sudo, нужно перелогиниться."
echo "Выполните команду: exit"
echo "Затем зайдите на сервер снова."
echo "--------------------------------------------------------"
echo "Ваш проект находится в папке: $PROJECT_DIR"
echo "Для начала работы:"
echo "1. cd ride_share_bot"
echo "2. nano .env (вставьте свой токен телеграм)"
echo "3. source venv/bin/activate"
echo "--------------------------------------------------------"
