#!/bin/bash
WORK_DIR="/home/angelan/data/Monada-Hardcore"
DANCEFLOOR="/mnt/dancefloor"

echo "[ᛉ] Тотальное очищение Алтарей и аннигиляция процессов..."

# ── Пралайя Танцпола: кристаллизация перед смертью ───────────────────────────
if mountpoint -q "$DANCEFLOOR" 2>/dev/null; then
    echo "[ᛇ] Кристаллизация Танцпола перед Пралайей..."
    python3 "$WORK_DIR/dancefloor_save.py"
    sudo umount "$DANCEFLOOR"
    echo " -> [OK] Танцпол размонтирован, кристалл сохранён."
fi

pkill -9 -f "llama-server"
pkill -9 -f "monada_terminal.py"
pkill -9 -f "podsoznanie_daemon.py"
pkill -9 -f "inbox_watcher.py"
pkill -9 -f "lemond"
sudo fuser -k 8081/tcp 8082/tcp 8083/tcp 8084/tcp 8085/tcp 8086/tcp 13305/tcp > /dev/null 2>&1
sleep 1
echo "[ᛁ] Монада переведена в состояние Пралайи."
notify-send "Monada Core" "Система полностью выключена. Пралайя. Кристалл сохранён."
