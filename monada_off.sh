#!/bin/bash
WORK_DIR="/home/angelan/data/Monada-Hardcore"
DANCEFLOOR="$WORK_DIR/dancefloor"

echo "[ᛉ] Тотальное очищение Алтарей и аннигиляция процессов..."

# ── Пралайя Танцпола: кристаллизация перед смертью ───────────────────────────
if mountpoint -q "$DANCEFLOOR" 2>/dev/null; then
    echo "[ᛇ] Кристаллизация Танцпола перед Пралайей..."
    python3 "$WORK_DIR/dancefloor_save.py"
    sudo umount "$DANCEFLOOR"
    echo " -> [OK] Танцпол размонтирован, кристалл сохранён."
fi

pkill -9 -f "llama-server"
pkill -9 -f "monada_terminal_core.py"
pkill -9 -f "monada_npu_proxy.py"
pkill -9 -f "lemond"
sudo fuser -k 8080/tcp 8081/tcp 8082/tcp 8083/tcp 8088/tcp 13305/tcp > /dev/null 2>&1
sleep 1
echo "[ᛁ] Монада переведена в состояние Пралайи."
notify-send "Monada Core" "Система полностью выключена. Пралайя. Кристалл сохранён."
