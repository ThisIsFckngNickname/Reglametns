#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "========================================"
echo "  SRP — запуск сервисов"
echo "========================================"
echo ""

# Clean up old processes
echo "[1/4] Остановка старых процессов..."
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 2
echo "  Готово."

# Start Backend
echo "[2/4] Запуск бэкенда (порт 8000)..."
cd "$BACKEND_DIR"
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "  Бэкенд запущен (PID $BACKEND_PID)"

# Start Frontend
echo "[3/4] Запуск фронтенда (порт 5173)..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
echo "  Фронтенд запущен (PID $FRONTEND_PID)"

# Verify
sleep 3
echo "[4/4] Проверка..."
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "   Бэкенд: http://localhost:8000"
else
  echo "   Бэкенд: НЕ ЗАПУЩЕН"
fi
if lsof -ti:5173 >/dev/null 2>&1; then
  echo "   Фронтенд: http://localhost:5173"
else
  echo "   Фронтенд: НЕ ЗАПУЩЕН"
fi

echo ""
echo "Службы запущены. Нажмите Ctrl+C для остановки."
wait
