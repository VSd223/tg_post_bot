#!/usr/bin/env bash

# ==============================================================================
# Скрипт полного удаления Telegram Post Bot и очистки сервера
# ==============================================================================

set -o pipefail

# Цвета
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

CURRENT_DIR="$(pwd)"
SERVICE_NAME="tgpostbot"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo -e "\n${BOLD}${RED}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${RED}║          🗑 УДАЛЕНИЕ И ОЧИСТКА TELEGRAM ПОСТ-БОТА         ║${NC}"
echo -e "${BOLD}${RED}╚══════════════════════════════════════════════════════════╝${NC}\n"

# Проверка прав Root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️ Требуются права суперпользователя для удаления системной службы.${NC}"
    echo -e "${YELLOW}Перезапуск через sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

# 1. Остановка и отключение системной службы
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    echo -ne "  ${CYAN}[..]${NC} Остановка фоновой службы $SERVICE_NAME..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    echo -e "\r  ${GREEN}[✔]${NC} Служба $SERVICE_NAME остановлена и отключена.         "
else
    echo -e "  ${YELLOW}[i]${NC} Фоновая служба не найдена в системе."
fi

# 2. Удаление файла службы
if [ -f "$SERVICE_PATH" ]; then
    rm -f "$SERVICE_PATH"
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
    echo -e "  ${GREEN}[✔]${NC} Файл службы $SERVICE_PATH успешно удален."
fi

# 3. Удаление виртуального окружения (.venv) и кэша
echo -ne "  ${CYAN}[..]${NC} Очистка окружения Python (.venv) и временных файлов..."
rm -rf "$CURRENT_DIR/.venv"
find "$CURRENT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -f "$CURRENT_DIR/install.log"
echo -e "\r  ${GREEN}[✔]${NC} Окружение .venv, кэш и логи удалены.                    "

# 4. Вопрос про базу данных и файл токена (.env)
echo ""
read -rp "❓ Удалить базу данных SQLite (bot_database.sqlite3)? Все посты и каналы будут стёрты! (y/N): " DEL_DB
if [[ "$DEL_DB" =~ ^[YyДд]$ ]]; then
    rm -f "$CURRENT_DIR/bot_database.sqlite3"
    echo -e "  ${GREEN}[✔]${NC} База данных удалена."
else
    echo -e "  ${YELLOW}[i]${NC} База данных сохранена: bot_database.sqlite3"
fi

read -rp "❓ Удалить файл с сохраненным токеном (.env)? (y/N): " DEL_ENV
if [[ "$DEL_ENV" =~ ^[YyДд]$ ]]; then
    rm -f "$CURRENT_DIR/.env"
    echo -e "  ${GREEN}[✔]${NC} Файл .env удален."
else
    echo -e "  ${YELLOW}[i]${NC} Токен сохранен в .env"
fi

echo -e "\n${BOLD}${GREEN}====================================================${NC}"
echo -e "${BOLD}${GREEN}   ✅ БОТ ПОЛНОСТЬЮ ОСТАНОВЛЕН И УДАЛЕН С СЕРВЕРА!  ${NC}"
echo -e "${BOLD}${GREEN}====================================================${NC}\n"