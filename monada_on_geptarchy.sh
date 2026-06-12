#!/bin/bash

# =====================================================================
# MONADA v35.0 HARDCORE GEPTARCHY — ЗАПУСК ГЕПТАРХИИ
# =====================================================================
# Порты:
#   8081 — УМ       : Phi-4-mini-instruct                  IQ4_NL  ctx=4096
#   8082 — СЕРДЦЕ   : Gemma-3-4B-it-heretic               IQ4_NL  ctx=4096
#   8083 — ТЕЛО     : Granite-4.0-H-Micro                 Q6_K_XL ctx=4096
#   8084 — ПЕРСОНА+ТЕНЬ : Llama-3.3-8B absolute heresy    IQ4_XS  ctx=4096 (shared)
#   8086 — СИНТЕЗ   : SmolLM3-3B                          IQ4_NL  ctx=8192
#   13305— ПОДСОЗНАНИЕ: nomic-embed-text-v1-GGUF (lemond/llamacpp)
# =====================================================================

set -euo pipefail

WORK_DIR="/home/angelan/data/Monada-Hardcore"
LOG_DIR="$WORK_DIR/logs"
MODELS_DIR="/home/angelan/models/monadaAI"
EXEC="$WORK_DIR/llama-b9521/llama-b9521/llama-server"
DANCEFLOOR="/mnt/dancefloor"

MODEL_UM="$MODELS_DIR/microsoft_Phi-4-mini-instruct-IQ4_NL.gguf"
MODEL_SERDCE="$MODELS_DIR/gemma-3-4b-it-heretic-iq4_nl-imat.gguf"
MODEL_TELO="$MODELS_DIR/granite-4.0-h-micro-UD-Q6_K_XL.gguf"
# ПЕРСОНА и ТЕНЬ делят один llama-server на 8084 (shared Llama-3.3-8B absolute heresy) — экономия RAM
MODEL_PERSONA="/home/angelan/models/monadaAI/Llama-3.3-8B-Instruct-128K-absolute-heresy.IQ4_XS.gguf"
MODEL_SINTEZ="$MODELS_DIR/SmolLM3-3B-IQ4_NL.gguf"

echo "[ᛉ] Аннигиляция старых процессов..."
pkill -9 -f "llama-server" 2>/dev/null || true
pkill -9 -f "podsoznanie_daemon.py" 2>/dev/null || true
sudo fuser -k 8081/tcp 8082/tcp 8083/tcp 8084/tcp 8085/tcp 8086/tcp 2>/dev/null || true
sleep 2

mkdir -p "$LOG_DIR"

# ── Проверка моделей ──────────────────────────────────────────────────────────
_MISSING=0
for MODEL_PATH in "$MODEL_UM" "$MODEL_SERDCE" "$MODEL_TELO" "$MODEL_PERSONA" "$MODEL_SINTEZ"; do
    if [ ! -f "$MODEL_PATH" ]; then
        echo "[WARN] Модель не найдена: $MODEL_PATH — узел будет пропущен"
        _MISSING=$((_MISSING + 1))
    fi
done
if [ "$_MISSING" -eq 0 ]; then
    echo "[OK] Все 5 модельных весов найдены (Персона+Тень делят Gemma)."
else
    echo "[WARN] Пропущено моделей: $_MISSING — запуск продолжается для доступных узлов."
fi

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
    local EXTRA_FLAGS=("$@")

    echo "[ᚲ] Запуск $NAME (порт $PORT, ctx=$CTX)..."
    "$EXEC" \
        -m "$MODEL" \
        --host 127.0.0.1 \
        --port "$PORT" \
        -c "$CTX" \
        --n-gpu-layers 99 \
        -fa auto \
        --parallel 1 \
        --reasoning off \
        "${EXTRA_FLAGS[@]}" \
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
if [ -f "$MODEL_UM" ]; then
    start_server "UM" 8081 "$MODEL_UM" 4096
else
    echo "[SKIP] 8081 УМ      — файл не найден: $MODEL_UM"
fi
if [ -f "$MODEL_SERDCE" ]; then
    start_server "SERDCE" 8082 "$MODEL_SERDCE" 4096
else
    echo "[SKIP] 8082 СЕРДЦЕ  — файл не найден: $MODEL_SERDCE"
fi
if [ -f "$MODEL_TELO" ]; then
    start_server "TELO" 8083 "$MODEL_TELO" 4096
else
    echo "[SKIP] 8083 ТЕЛО    — файл не найден: $MODEL_TELO"
fi

# ── Запуск Януса ─────────────────────────────────────────────────────────────
# ПЕРСОНА и ТЕНЬ обслуживаются ОДНИМ llama-server на 8084 (shared Llama-3.3-8B absolute heresy).
# Отдельный сервер 8085 не поднимается — SHADOW_URL в janus_conductor.py указывает на 8084.
if [ -f "$MODEL_PERSONA" ]; then
    start_server "PERSONA" 8084 "$MODEL_PERSONA" 4096
else
    echo "[SKIP] 8084 ПЕРСОНА+ТЕНЬ — файл не найден: $MODEL_PERSONA"
fi
if [ -f "$MODEL_SINTEZ" ]; then
    start_server "SINTEZ" 8086 "$MODEL_SINTEZ" 8192
else
    echo "[SKIP] 8086 СИНТЕЗ  — файл не найден: $MODEL_SINTEZ"
fi

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
echo "    PERSONA+SHADOW :8084 shared Llama-3.3-8B absolute heresy   СИНТЕЗ  :8086"
echo "    ПОДСОЗНАНИЕ :13305 (lemond/nomic-embed)"
echo "    ПРИСУТСТВИЕ :inbox_watcher (Proton Bridge)"
echo ""
echo "Логи: $LOG_DIR/"
