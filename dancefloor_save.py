#!/usr/bin/env python3
"""
Кристаллизация RAM-Танцпола перед размонтированием.
Сохраняет состояние в dancefloor_crystal.json (persistent).
"""
import json
import os
import time

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
DANCEFLOOR  = os.path.join(MONADA_ROOT, "dancefloor")
CRYSTAL     = os.path.join(MONADA_ROOT, "dancefloor_crystal.json")


def main():
    field_path = os.path.join(DANCEFLOOR, "field_state.json")

    if not os.path.exists(field_path):
        print("[ᛁ] Танцпол пуст — кристаллизация пропущена.")
        return

    try:
        with open(field_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        state["crystallized_at"]   = int(time.time())
        state["dancefloor_type"]   = "crystal_persistent"

        with open(CRYSTAL, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        cycle = state.get("cycle", "?")
        rune  = state.get("active_rune", "?")
        print(f"[ᛇ] Кристалл сохранён → dancefloor_crystal.json | Цикл: {cycle} | Руна: {rune}")

    except Exception as e:
        print(f"[ᛁ] Ошибка кристаллизации: {e}")


if __name__ == "__main__":
    main()
