#!/usr/bin/env bash

# ==============================================================================
# Универсальный установщик Telegram Post Bot с защитой от сбоев и анимацией
# ==============================================================================

set -o pipefail

# Цветовая палитра
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

LOG_FILE="$(pwd)/install.log"
CURRENT_DIR="$(pwd)"
TARGET_USER="${SUDO_USER:-$USER}"

# Очистка старого лога
: > "$LOG_FILE"

# --- Функция красивой анимации (спиннера) ---
run_task() {
    local text="$1"
    shift
    local pid
    local spin='-\|/'
    local i=0

    echo -ne "  ${CYAN}[..]${NC} $text..."

    # Запуск команды в фоне с записью в install.log
    "$@" >> "$LOG_FILE" 2>&1 &
    pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        i=$(( (i+1) % 4 ))
        echo -ne "\r  ${YELLOW}[${spin:$i:1}]${NC} $text..."
        sleep 0.15
    done

    wait "$pid"
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo -e "\r  ${GREEN}[✔]${NC} $text                    "
    else
        echo -e "\r  ${RED}[✖]${NC} $text — ${RED}ОШИБКА!${NC}           "
        echo -e "\n${RED}---------------- ПОСЛЕДНИЕ СТРОКИ ОШИБКИ ----------------${NC}"
        tail -n 25 "$LOG_FILE"
        echo -e "${RED}--------------------------------------------------------${NC}"
        echo -e "${YELLOW}Полный лог сохранен в: $LOG_FILE${NC}\n"
        exit 1
    fi
}

echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║     🚀 УСТАНОВЩИК И ЗАПУСК TELEGRAM ПОСТ-БОТА В ФОНЕ     ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════╝${NC}\n"

# 1. Проверка прав Root / Sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️ Требуются права суперпользователя для настройки фоновой службы.${NC}"
    echo -e "${YELLOW}Попытка перезапуска через sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

# 2. Проверка, что скрипт запущен в папке с ботом
if [ ! -f "$CURRENT_DIR/main.py" ]; then
    echo -e "${RED}✖ Ошибка: Файл main.py не найден в текущей папке ($CURRENT_DIR)!${NC}"
    echo -e "${YELLOW}Перейдите в папку с ботом командой: cd путь_к_боту${NC}"
    exit 1
fi

# 3. Защита от блокировок пакетного менеджера (APT Lock)
wait_for_apt_lock() {
    local locks=(
        "/var/lib/dpkg/lock-frontend"
        "/var/lib/dpkg/lock"
        "/var/lib/apt/lists/lock"
        "/var/cache/apt/archives/lock"
    )
    for lock in "${locks[@]}"; do
        while fuser "$lock" >/dev/null 2>&1; do
            echo -e "${YELLOW}⏳ Система занята обновлением. Ждём снятия блокировки $lock...${NC}"
            sleep 3
        done
    done
}

# 4. Установка необходимых системных зависимостей
install_system_dependencies() {
    export DEBIAN_FRONTEND=noninteractive
    wait_for_apt_lock

    if command -v apt-get &>/dev/null; then
        apt-get update -y
        apt-get install -y python3 python3-pip python3-venv python3-full \
                           build-essential libffi-dev git curl psmisc
    elif command -v dnf &>/dev/null; then
        dnf install -y python3 python3-pip python3-devel gcc git curl psmisc
    elif command -v yum &>/dev/null; then
        yum install -y python3 python3-pip python3-devel gcc git curl psmisc
    else
        echo -e "${RED}✖ Неизвестный дистрибутив Linux. Установите Python 3.9+ вручную.${NC}"
        exit 1
    fi
}

run_task "Обновление репозиториев и установка системных пакетов" install_system_dependencies

# 5. Проверка и настройка версии Python (>= 3.9)
check_python_version() {
    if ! command -v python3 &>/dev/null; then
        return 1
    fi
    python3 -c '
import sys
if sys.version_info < (3, 9):
    sys.exit(1)
'
}

if ! check_python_version; then
    echo -e "${RED}✖ На сервере версия Python ниже 3.9!${NC}"
    echo -e "${YELLOW}Установка Python 3.11 через репозиторий deadsnakes...${NC}"
    if command -v apt-get &>/dev/null; then
        run_task "Подключение PPA deadsnakes и установка Python 3.11" bash -c "
            apt-get install -y software-properties-common
            add-apt-repository -y ppa:deadsnakes/ppa
            apt-get update -y
            apt-get install -y python3.11 python3.11-venv python3.11-dev
        "
        PYTHON_EXEC="python3.11"
    else
        echo -e "${RED}✖ Обновите Python до версии 3.9 или выше вручную.${NC}"
        exit 1
    fi
else
    PYTHON_EXEC="python3"
fi

PY_VER=$($PYTHON_EXEC --version)
echo -e "  ${GREEN}[✔]${NC} Используется интерпретатор: ${BOLD}$PY_VER${NC}"

# 6. Создание безопасного виртуального окружения (.venv)
setup_virtualenv() {
    if [ ! -d "$CURRENT_DIR/.venv" ]; then
        $PYTHON_EXEC -m venv "$CURRENT_DIR/.venv" || {
            apt-get install -y python3-virtualenv virtualenv
            virtualenv -p "$PYTHON_EXEC" "$CURRENT_DIR/.venv"
        }
    fi

    # Обновление pip и базовых сборочных инструментов
    "$CURRENT_DIR/.venv/bin/pip" install --upgrade pip setuptools wheel
}

run_task "Создание изолированного окружения Python (.venv)" setup_virtualenv

# 7. Установка библиотек бота
install_python_packages() {
    if [ -f "$CURRENT_DIR/requirements.txt" ]; then
        "$CURRENT_DIR/.venv/bin/pip" install --no-cache-dir -r "$CURRENT_DIR/requirements.txt"
    else
        "$CURRENT_DIR/.venv/bin/pip" install --no-cache-dir "aiogram>=3.15.0" "aiosqlite>=0.20.0" "tzdata"
    fi
}

run_task "Установка библиотек (aiogram, aiosqlite, tzdata)" install_python_packages

# 8. Запрос и проверка токена бота через API Telegram
echo -e "\n${BOLD}${CYAN}──────────────────────────────────────────────────────────${NC}"
echo -e "${BOLD}${CYAN}               ВВОД И ПРОВЕРКА ТОКЕНА БОТА               ${NC}"
echo -e "${BOLD}${CYAN}──────────────────────────────────────────────────────────${NC}"

CONFIG_ENV_FILE="$CURRENT_DIR/.env"
BOT_TOKEN=""

if [ -f "$CONFIG_ENV_FILE" ]; then
    # Загружаем существующий токен
    source "$CONFIG_ENV_FILE" 2>/dev/null || true
fi

validate_token() {
    local token="$1"
    local response
    response=$(curl -s --max-time 10 "https://api.telegram.org/bot${token}/getMe" 2>/dev/null || true)
    if echo "$response" | grep -q '"ok":true'; then
        BOT_NAME=$(echo "$response" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
        return 0
    fi
    return 1
}

# Если токен уже был сохранен ранее, спросим подтверждение
ASK_FOR_TOKEN=true
if [ -n "$BOT_TOKEN" ] && [ "$BOT_TOKEN" != "ВАШ_ТОКЕН_БОТА_ЗДЕСЬ" ]; then
    echo -ne "  ${CYAN}⏳ Проверка сохраненного токена...${NC}"
    if validate_token "$BOT_TOKEN"; then
        echo -e "\r  ${GREEN}[✔] Найден рабочий токен бота: ${BOLD}@${BOT_NAME}${NC}         "
        read -rp "Использовать этот токен? [Y/n]: " KEEP_TOKEN < /dev/tty
        if [[ ! "$KEEP_TOKEN" =~ ^[NnНн]$ ]]; then
            ASK_FOR_TOKEN=false
        fi
    fi
fi

if [ "$ASK_FOR_TOKEN" = true ]; then
    while true; do
        echo -e "\n${YELLOW}Введите токен вашего бота (полученный у @BotFather):${NC}"
        read -rp "🔑 BOT_TOKEN: " USER_TOKEN < /dev/tty
        USER_TOKEN="$(echo "$USER_TOKEN" | xargs)"

        if [ -z "$USER_TOKEN" ]; then
            echo -e "${RED}Токен не может быть пустым!${NC}"
            continue
        fi

        echo -ne "  ${CYAN}⏳ Проверка токена через Telegram API...${NC}"
        if validate_token "$USER_TOKEN"; then
            echo -e "\r  ${GREEN}[✔] Токен успешно подтвержден! Бот: @${BOT_NAME}${NC}         "
            BOT_TOKEN="$USER_TOKEN"
            echo "BOT_TOKEN=$BOT_TOKEN" > "$CONFIG_ENV_FILE"
            chmod 600 "$CONFIG_ENV_FILE"
            break
        else
            echo -e "\r  ${RED}[✖] Ошибка: Токен недействителен или нет доступа к api.telegram.org!${NC}"
            echo -e "${YELLOW}Пожалуйста, проверьте токен и попробуйте снова.${NC}"
        fi
    done
fi

# 9. Назначение прав пользователю на папку проекта
chown -R "$TARGET_USER:$TARGET_USER" "$CURRENT_DIR"

# 10. Создание и регистрация службы в Systemd
SERVICE_NAME="tgpostbot"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

setup_systemd_service() {
    cat <<EOF > "$SERVICE_PATH"
[Unit]
Description=Telegram Post Bot Service
After=network.target

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$CURRENT_DIR
Environment="BOT_TOKEN=$BOT_TOKEN"
ExecStart=$CURRENT_DIR/.venv/bin/python main.py
Restart=always
RestartSec=5
KillMode=process
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
}

run_task "Настройка службы автозапуска systemd ($SERVICE_NAME)" setup_systemd_service

# 11. Финальная проверка работоспособности
echo -ne "  ${CYAN}[..]${NC} Проверка фонового процесса..."
sleep 3

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "\r  ${GREEN}[✔] Служба активна и работает в фоне!${NC}                \n"
    echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}   🎉 БОТ @${BOT_NAME} УСПЕШНО ЗАПУЩЕН НА СЕРВЕРЕ 24/7!   ${NC}"
    echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════${NC}\n"
    echo -e "Полезные команды для управления:"
    echo -e "  • Онлайн логи бота:        ${CYAN}sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "  • Перезапустить бота:      ${CYAN}sudo systemctl restart $SERVICE_NAME${NC}"
    echo -e "  • Остановить бота:         ${CYAN}sudo systemctl stop $SERVICE_NAME${NC}"
    echo -e "  • Статус службы:           ${CYAN}sudo systemctl status $SERVICE_NAME${NC}\n"
else
    echo -e "\r  ${RED}[✖] Ошибка: Процесс завершился сбоем.${NC}               \n"
    echo -e "${RED}Лог последних ошибок службы:${NC}"
    journalctl -u "$SERVICE_NAME" -n 25 --no-pager
    exit 1
fi