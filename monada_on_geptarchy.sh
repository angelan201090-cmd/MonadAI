#!/bin/bash

# =====================================================================
# MONADA v35.0 HARDCORE GEPTARCHY — ЗАПУСК ГЕПТАРХИИ
# =====================================================================
# Порты:
#   8081 — УМ       : Llama-3.2-3B-Instruct-abliterated  Q4_K_M  ctx=4096
#   8082 — СЕРДЦЕ   : Phi-3.5-mini-instruct               Q3_K_M  ctx=4096
#   8083 — ТЕЛО     : Qwen2.5-Coder-7B-Instruct-heretic      Q4_K_M  ctx=4096
#   8084 — ПЕРСОНА  : Hermes-3-Llama-3.2-3B-abliterated  Q4_K_M  ctx=4096
#   8085 — ТЕНЬ     : stablelm-zephyr-3b-Heretic           IQ4_NL  ctx=4096
#   8086 — СИНТЕЗ   : Luna-7B-A4B-absolute-heresy          Q4_K_M  ctx=8192
#   13305— ПОДСОЗНАНИЕ: nomic-embed-text-v1-GGUF (lemond/llamacpp)
# =====================================================================

set -euo pipefail

WORK_DIR="/home/angelan/data/Monada-Hardcore"
LOG_DIR="$WORK_DIR/logs"
MODELS_DIR="/home/angelan/models/monadaAI"
EXEC="$WORK_DIR/llama-b9521/llama-b9521/llama-server"
DANCEFLOOR="/mnt/dancefloor"

MODEL_UM="$MODELS_DIR/Llama-3.2-3B-Instruct-abliterated.Q4_K_M.gguf"
MODEL_SERDCE="$MODELS_DIR/Phi-3.5-mini-instruct-Q3_K_M.gguf"
MODEL_TELO="$MODELS_DIR/Qwen2.5-Coder-7B-Instruct-heretic.Q4_K_M.gguf"
MODEL_PERSONA="$MODELS_DIR/Hermes-3-Llama-3.2-3B-abliterated.Q4_K_M.gguf"
MODEL_TEN="$MODELS_DIR/stablelm-zephyr-3b-Heretic_IQ4_NL.gguf"
MODEL_SINTEZ="$MODELS_DIR/Luna-7B-A4B-absolute-heresy.Q4_K_M.gguf"

echo "[ᛉ] Аннигиляция старых процессов..."
pkill -9 -f "llama-server" 2>/dev/null || true
pkill -9 -f "podsoznanie_daemon.py" 2>/dev/null || true
sudo fuser -k 8081/tcp 8082/tcp 8083/tcp 8084/tcp 8085/tcp 8086/tcp 2>/dev/null || true
sleep 2

mkdir -p "$LOG_DIR"

# ── Проверка моделей ──────────────────────────────────────────────────────────
for MODEL_PATH in "$MODEL_UM" "$MODEL_SERDCE" "$MODEL_TELO" "$MODEL_PERSONA" "$MODEL_TEN" "$MODEL_SINTEZ"; do
    if [ ! -f "$MODEL_PATH" ]; then
        echo "[!!] Модель не найдена: $MODEL_PATH"
        exit 1
    fi
done
echo "[OK] Все 6 модельных весов найдены."

# ── Танцпол ───────────────────────────────────────────────────────────────────
if mountpoint -q "$DANCEFLOOR" 2>/dev/null; then
    echo "[ᚢ] Танцпол уже смонтирован: $DANCEFLOOR"
else
    echo "[ᚢ] Монтирование Танцпола (tmpfs, 1GB)..."
    sudo mkdir -p "$DANCEFLOOR"
    sudo mount -t tmpfs -o size=1g,uid="$(id -u)",gid="$(id -g)",mode=0770 tmpfs "$DANCEFLOOR"
fi
echo "[OK] Танцпол: $DANCEFLOOR"

echo "[ᛃ] Инициализация Танцпола из кристалла..."
python3 "$WORK_DIR/dancefloor_init.py"

# ── Подсознание: lemond + nomic-embed-text ───────────────────────────────────
echo "[ᚾ] Запуск Подсознания (nomic-embed-text @ lemond:13305)..."
pkill -9 -f "lemond" 2>/dev/null || true
sleep 1
lemond --port 13305 > "$LOG_DIR/lemond.log" 2>&1 &
LEMOND_PID=$!
LEMOND_READY=0
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:13305/api/v0/health > /dev/null 2>&1; then
        LEMOND_READY=1; break
    fi
    if ! kill -0 "$LEMOND_PID" 2>/dev/null; then
        echo "[!!] lemond упал. Лог:"; tail -5 "$LOG_DIR/lemond.log"; exit 1
    fi
    sleep 1
done
if [ "$LEMOND_READY" -eq 0 ]; then
    echo "[!!] lemond не поднялся за 30с."; tail -5 "$LOG_DIR/lemond.log"; exit 1
fi
echo " -> [OK] lemond pid=$LEMOND_PID"

echo "[ᚾ] Загрузка nomic-embed-text-v1-GGUF..."
lemonade load nomic-embed-text-v1-GGUF > /dev/null 2>&1 && echo " -> [OK] embed model loaded" || echo "[WARN] embed model load failed"

# ── Функция запуска сервера + ожидание ────────────────────────────────────────
start_server() {
    local NAME="$1" PORT="$2" MODEL="$3" CTX="$4"
    shift 4
    local EXTRA_FLAGS="$*"

    echo "[ᚲ] Запуск $NAME (порт $PORT, ctx=$CTX)..."
    # shellcheck disable=SC2086
    "$EXEC" \
        -m "$MODEL" \
        --host 127.0.0.1 \
        --port "$PORT" \
        -c "$CTX" \
        --n-gpu-layers 99 \
        -fa auto \
        --parallel 1 \
        --reasoning off \
        $EXTRA_FLAGS \
        > "$LOG_DIR/${NAME,,}.log" 2>&1 &

    local PID=$!
    local READY=0
    for i in $(seq 1 60); do
        if grep -q "server is listening" "$LOG_DIR/${NAME,,}.log" 2>/dev/null; then
            READY=1; break
        fi
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "[!!] $NAME упал. Последние строки лога:"
            tail -10 "$LOG_DIR/${NAME,,}.log"
            exit 1
        fi
        sleep 1
    done

    if [ "$READY" -eq 0 ]; then
        echo "[!!] $NAME не поднялся за 60с. Последние строки лога:"
        tail -10 "$LOG_DIR/${NAME,,}.log"
        exit 1
    fi
    echo " -> [OK] $NAME pid=$PID"
}

# Мягкий запуск: WARN вместо exit при ошибке (для моделей с несовместимостью)
start_server_optional() {
    local NAME="$1" PORT="$2" MODEL="$3" CTX="$4"
    shift 4
    local EXTRA_FLAGS="$*"

    echo "[ᚲ] Запуск $NAME (порт $PORT, ctx=$CTX) [опционально]..."
    # shellcheck disable=SC2086
    "$EXEC" \
        -m "$MODEL" \
        --host 127.0.0.1 \
        --port "$PORT" \
        -c "$CTX" \
        --n-gpu-layers 99 \
        -fa auto \
        --parallel 1 \
        --reasoning off \
        $EXTRA_FLAGS \
        > "$LOG_DIR/${NAME,,}.log" 2>&1 &

    local PID=$!
    for i in $(seq 1 30); do
        if grep -q "server is listening" "$LOG_DIR/${NAME,,}.log" 2>/dev/null; then
            echo " -> [OK] $NAME pid=$PID"
            return 0
        fi
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "[WARN] $NAME не запустился — работаем без него."
            tail -3 "$LOG_DIR/${NAME,,}.log" | sed 's/^/    /'
            return 0  # не fatal
        fi
        sleep 1
    done
    echo "[WARN] $NAME не ответил за 30с — работаем без него."
    return 0
}

# ── Запуск Триады ─────────────────────────────────────────────────────────────
start_server "UM"     8081 "$MODEL_UM"     4096
start_server "SERDCE" 8082 "$MODEL_SERDCE" 4096
start_server "TELO" 8083 "$MODEL_TELO" 4096

# ── Запуск Януса ─────────────────────────────────────────────────────────────
start_server "PERSONA" 8084 "$MODEL_PERSONA" 4096
start_server "TEN"     8085 "$MODEL_TEN"     4096
start_server "SINTEZ"  8086 "$MODEL_SINTEZ"  8192

# ── Запуск Подсознания-демона ─────────────────────────────────────────────────
echo "[ᛈ] Запуск podsoznanie_daemon.py..."
python3 "$WORK_DIR/podsoznanie_daemon.py" \
    > "$LOG_DIR/podsoznanie.log" 2>&1 &
echo " -> [OK] podsoznanie_daemon pid=$!"

# ── Запуск inbox_watcher (Proton Bridge присутствие) ─────────────────────────
echo "[ᛚ] Запуск inbox_watcher.py..."
python3 -m presence.inbox_watcher \
    > "$LOG_DIR/inbox_watcher.log" 2>&1 &
echo " -> [OK] inbox_watcher pid=$!"

echo ""
echo "[ᚹ] ГЕПТАРХИЯ АКТИВНА"
echo "    УМ      :8081  СЕРДЦЕ   :8082  ТЕЛО    :8083"
echo "    ПЕРСОНА :8084  ТЕНЬ     :8085  СИНТЕЗ  :8086"
echo "    ПОДСОЗНАНИЕ :13305 (lemond/nomic-embed)"
echo "    ПРИСУТСТВИЕ :inbox_watcher (Proton Bridge)"
echo ""
echo "Логи: $LOG_DIR/"
