#!/bin/bash

# =====================================================================
# [ᛒ ➔ ᚾ ➔ ᛏ ➔ ᚢ ➔ ᚹ] MONADA HARDCORE: OMEGA SYNTHESIS CONTEXT 24K
# =====================================================================
# Архитектура v22.1 (NPU-активирована):
#   8080 — Янус (Gemma-4-E4B-it Q4_0, GGUF, llama-server + Vulkan GPU)
#   8081 — Голова/Head    → lemond: gemma3-4b-FLM       (FLM NPU, ~4 GB)
#   8082 — Сердце/Heart   → lemond: lfm2-2.6b-FLM     (FLM NPU, 1.8 GB)
#   8083 — Тело/Body      → lemond: llama3.1-8b-FLM   (FLM NPU, 5.5 GB)
#   8081/8082/8083 обслуживает прокси monada_npu_proxy.py → lemond:13305

WORK_DIR="/home/angelan/data/Monada-Hardcore"
LOG_DIR="$WORK_DIR/logs"

MODEL_JANUS="/home/angelan/models/gemma-4-E4B-it-Q4_0.gguf"

EXEC_LLAMA="/home/angelan/.cache/lemonade/bin/llamacpp/vulkan/llama-server"

echo "[ᛉ] Тотальное очищение Алтарей и аннигиляция старых процессов..."
pkill -9 -f "llama-server"
pkill -9 -f "monada_terminal_core.py"
pkill -9 -f "monada_npu_proxy.py"
pkill -9 -f "lemond"
sudo fuser -k 8080/tcp 8081/tcp 8082/tcp 8083/tcp 8088/tcp 13305/tcp > /dev/null 2>&1
# Убиваем зомби flm-serve внутри контейнера (иначе NPU блокируется)
podman exec lemonade-npu pkill -9 flm 2>/dev/null || true
sleep 2

mkdir -p "$LOG_DIR"

# ── Танцпол: кристаллизация прошлого цикла и монтирование RAM-диска ──────────
DANCEFLOOR="$WORK_DIR/dancefloor"
echo "[ᚢ] Монтирование Танцпола (tmpfs, 256MB RAM)..."
# Если уже смонтирован — сохранить кристалл и перемонтировать
if mountpoint -q "$DANCEFLOOR" 2>/dev/null; then
    python3 "$WORK_DIR/dancefloor_save.py"
    sudo umount "$DANCEFLOOR"
fi
mkdir -p "$DANCEFLOOR"
sudo mount -t tmpfs -o size=256m,uid="$(id -u)",gid="$(id -g)",mode=0770 tmpfs "$DANCEFLOOR"
python3 "$WORK_DIR/dancefloor_init.py"
echo " -> [OK] Танцпол в RAM: $DANCEFLOOR"

echo "[ᚲ] Возжигание Януса (Gemma-4-E4B-it Q4_0) на порту 8080 | Контекст 24К | GPU..."
"$EXEC_LLAMA" -m "$MODEL_JANUS" \
  --host 127.0.0.1 \
  --port 8080 \
  -c 24576 \
  --n-gpu-layers 99 \
  -fa on \
  --parallel 1 \
  --temp 0.2 \
  > "$LOG_DIR/janus.log" 2>&1 &
sleep 5

echo "[ᚦ] Запуск lemonade-npu контейнера (Podman/FLM)..."
if podman ps --format "{{.Names}}" | grep -q "lemonade-npu"; then
    echo " -> lemonade-npu уже запущен"
else
    podman start lemonade-npu 2>/dev/null || echo " -> [!!] Контейнер lemonade-npu не найден"
fi
sleep 2

echo "[ᚦ] Запуск lemonade daemon (lemond) для NPU-Триады..."
lemond > "$LOG_DIR/lemond.log" 2>&1 &
LEMOND_PID=$!
echo " -> lemond PID: $LEMOND_PID"

echo "[ᚨ] Ожидание инициализации lemond на порту 13305..."
for i in $(seq 1 30); do
    if ss -tulpn | grep -q "13305"; then
        echo " -> lemond готов (${i}s)"
        break
    fi
    sleep 1
done

echo "[ᚾ] Запуск NPU-прокси Триады (порты 8081/8082/8083 → lemond:13305)..."
python3 "$WORK_DIR/monada_npu_proxy.py" > "$LOG_DIR/npu_proxy.log" 2>&1 &
sleep 3

echo "[ᛃ] Проверка верификации сокетов..."
ALL_OK=1
for PORT in 8080 8081 8082 8083 13305; do
    if ss -tulpn | grep -q ":$PORT"; then
        echo " -> [OK] Порт $PORT активен"
    else
        echo " -> [!!] Порт $PORT НЕ отвечает"
        ALL_OK=0
    fi
done

if [ "$ALL_OK" -eq 1 ]; then
    echo -e "\033[1;32m[УСПЕХ] Контур Монады v21.0 OMEGA SYNTHESIS развернут.\033[0m"
    echo -e "\033[0;36m        Янус: Gemma-4-E4B-it Q4_0 (GPU) | Триада: gemma3-4b / lfm2-2.6b / llama3.1-8b (lemond FLM NPU)\033[0m"
    echo -e "\033[0;36m        Монитор: python3 $WORK_DIR/monada_monitor.py\033[0m"

    # ── Прогрев Триады в фоне (не блокирует запуск терминала) ────────────────
    echo "[ᚹ] Прогрев Триады запущен в фоне → $LOG_DIR/warmup.log"
    (
        WARMUP_LOG="$LOG_DIR/warmup.log"
        WARMUP_PAYLOAD='{"model":"X","messages":[{"role":"user","content":"1"}],"max_tokens":1,"stream":false}'
        for PORT_MODEL in "8081:gemma3-4b-FLM" "8082:lfm2-2.6b-FLM" "8083:llama3.1-8b-FLM"; do
            PORT="${PORT_MODEL%%:*}"
            MODEL="${PORT_MODEL##*:}"
            PAYLOAD=$(echo "$WARMUP_PAYLOAD" | sed "s/\"model\":\"X\"/\"model\":\"$MODEL\"/")
            RESP=$(curl -s --max-time 300 -X POST "http://127.0.0.1:$PORT/v1/chat/completions" \
                -H "Content-Type: application/json" -d "$PAYLOAD" 2>&1)
            if echo "$RESP" | grep -q '"choices"'; then
                echo "[ᚹ warm] Порт $PORT / $MODEL — прогрет [OK]" >> "$WARMUP_LOG"
            else
                echo "[ᚹ warm] Порт $PORT / $MODEL — таймаут или ошибка" >> "$WARMUP_LOG"
            fi
        done
        echo "[ᚹ warm] Прогрев завершён." >> "$WARMUP_LOG"
    ) &
    disown
else
    echo -e "\033[1;31m[ЧАСТИЧНЫЙ СБОЙ] Не все сокеты поднялись. Проверь логи в $LOG_DIR\033[0m"
fi
