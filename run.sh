#!/bin/bash

# Скрипт запуска системы обработки почты
# Запуск: bash run.sh [папка_с_письмами]

INBOX_DIR="${1:-inbox}"
OUTPUT_DIR="processed"
LOG_FILE="processing.log"
PYTHON_CMD="python3"

echo "========================================"
echo "  Система обработки корпоративной почты"
echo "========================================"

# Проверяем что Python есть
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "[ОШИБКА] Python3 не найден. Установите Python 3.9+"
    exit 1
fi

# Проверяем что папка inbox существует
if [ ! -d "$INBOX_DIR" ]; then
    echo "[ОШИБКА] Папка с письмами не найдена: $INBOX_DIR"
    echo "Использование: bash run.sh [папка_с_письмами]"
    exit 1
fi

# Считаем сколько писем в inbox
LETTER_COUNT=$(find "$INBOX_DIR" -maxdepth 1 -type f ! -name ".*" | wc -l)
echo "Писем в папке '$INBOX_DIR': $LETTER_COUNT"

if [ "$LETTER_COUNT" -eq 0 ]; then
    echo "[ПРЕДУПРЕЖДЕНИЕ] Папка пустая, обрабатывать нечего."
    exit 0
fi

echo "Запускаем обработку..."
echo ""

# Запускаем Python приложение и сохраняем код возврата
$PYTHON_CMD main.py --inbox "$INBOX_DIR" --output "$OUTPUT_DIR" --log-file "$LOG_FILE"
EXIT_CODE=$?

echo ""

# Проверяем результат
if [ $EXIT_CODE -eq 0 ]; then
    echo "[OK] Обработка завершена успешно"
else
    echo "[WARN] Обработка завершена с ошибками (код: $EXIT_CODE)"
fi

# Показываем что получилось в папках
if [ -d "$OUTPUT_DIR" ]; then
    echo ""
    echo "Результаты в папке '$OUTPUT_DIR':"
    for dir in "$OUTPUT_DIR"/*/; do
        if [ -d "$dir" ]; then
            cat_name=$(basename "$dir")
            count=$(find "$dir" -maxdepth 1 -type f | wc -l)
            if [ "$count" -gt 0 ]; then
                echo "  $cat_name: $count писем"
            fi
        fi
    done
fi

# Выводим последние строки лога если он есть
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "Последние записи лога ($LOG_FILE):"
    tail -5 "$LOG_FILE"
fi

exit $EXIT_CODE
