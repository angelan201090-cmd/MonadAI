#!/usr/bin/env python3
import os
import json
import subprocess

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
INBOX_DIR = os.path.join(MONADA_ROOT, "inbox")
TASK_FILE = os.path.join(INBOX_DIR, "triad_task.json")
RESPONSE_FILE = os.path.join(INBOX_DIR, "triad_response.json")
CONDUCTOR = os.path.join(MONADA_ROOT, "core/janus_conductor.py")

print("[ᚾ] Инициация чистого Python-теста MCE контура...")

# Очистка старых блокировок
for f in [TASK_FILE, RESPONSE_FILE]:
    if os.path.exists(f):
        try:
            os.remove(f)
        except Exception:
            pass

# 1. Формируем валидный буфер обмена без участия Bash-экранирования
os.makedirs(INBOX_DIR, exist_ok=True)
task_data = {"task": "Тестовый параллельный аккорд Триады. Верификация асинхронных шлюзов Lower_Manas, Kama_Value и Higher_Manas."}

try:
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)
    print("[УСПЕХ] Буфер triad_task.json кристаллизован.")
except Exception as e:
    print(f"[КРИТИЧЕСКИЙ СБОЙ] Запись буфера сорвана: {e}")
    exit(1)

# 2. Вызов асинхронного Кондуктора
print("[ᚾ] Запуск параллельного инференса Триады серверов...")
proc = subprocess.run(f"python3 {CONDUCTOR}", shell=True, capture_output=True, text=True)

print("\n=== ВНУТРЕННИЙ ВЫХЛОП КОНДУКТОРА (STDOUT/STDERR) ===")
print(proc.stdout)
print(proc.stderr)
print("===================================================\n")

# 3. Чтение финального графа
if os.path.exists(RESPONSE_FILE):
    try:
        with open(RESPONSE_FILE, "r", encoding="utf-8") as f:
            res = json.load(f)
        print("\033[1;32m[УСПЕХ] Финальный дифференциальный граф успешно собран:\033[0m")
        print(json.dumps(res, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[ОШИБКА] Не удалось прочитать ответ: {e}")
else:
    print("\033[1;31m[СБОЙ] Асинхронный ответ triad_response.json не был сгенерирован.\033[0m")
