#!/usr/bin/env python3
"""
Инициализация RAM-Танцпола при старте Монады.
Восстанавливает кристалл прошлого цикла, создаёт рунический field_state.json.
Ключевое отличие v2: восстанавливает SOC-состояние, ноту и shared_memory из кристалла
для обеспечения межсессионной непрерывности памяти.
"""
import json
import os
import time

MONADA_ROOT       = "/home/angelan/data/Monada-Hardcore"
DANCEFLOOR        = "/mnt/dancefloor"
CRYSTAL           = os.path.join(MONADA_ROOT, "dancefloor_crystal.json")
GLYPH_PERSISTENT  = os.path.join(MONADA_ROOT, "glyph_codex_persistent.json")

RUNE_JERA = "ᛃ"

NOTE_MAP = {
    1: "ДО (Инициация Воли)",
    2: "РЕ (Разворот Структуры)",
    3: "МИ (Формирование Направления)",
    4: "ФА (Материализация Действия)",
    5: "СОЛЬ (Анализ Следа)",
    6: "ЛЯ (Критика и Фиксация Зазоров)",
    7: "СИ (Синтез в Кристалл)",
    8: "🔥 ПРОВАЛ_1 (Призыв Героя ᛏ)",
    9: "🌀 ПРОВАЛ_2 (Призыв Трикстера ᚨ)",
}

DEVA_MAP = {
    "Janus":   {"rune": RUNE_JERA, "face": "Persona",  "port": 8080, "param": "orchestration",   "center": "Janus"},
    "Budha":   {"rune": RUNE_JERA, "center": "Head",   "port": 8081, "param": "top_k",            "soc_tension": 0.0},
    "Shani":   {"rune": RUNE_JERA, "center": "Head",   "port": 8081, "param": "rep_penalty",      "soc_tension": 0.0},
    "Rahu":    {"rune": RUNE_JERA, "center": "Head",   "port": 8081, "param": "temperature",      "soc_tension": 0.0},
    "Chandra": {"rune": RUNE_JERA, "center": "Heart",  "port": 8082, "param": "presence_penalty", "soc_tension": 0.0},
    "Surya":   {"rune": RUNE_JERA, "center": "Heart",  "port": 8082, "param": "min_p",            "soc_tension": 0.0},
    "Shukra":  {"rune": RUNE_JERA, "center": "Heart",  "port": 8082, "param": "top_p",            "soc_tension": 0.0},
    "Mangala": {"rune": RUNE_JERA, "center": "Body",   "port": 8083, "param": "repeat_last_n",   "soc_tension": 0.0},
    "Ketu":    {"rune": RUNE_JERA, "center": "Body",   "port": 8083, "param": "ctx_compress",     "soc_tension": 0.0},
    "Guru":    {"rune": RUNE_JERA, "center": "Body",   "port": 8083, "param": "sys_weight",       "soc_tension": 0.0},
}

# Доля тензии SOC, которая сохраняется после перезапуска (затухание)
SOC_RESTART_DECAY = 0.6


def load_crystal() -> dict:
    try:
        with open(CRYSTAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build_state(crystal: dict) -> dict:
    """
    Строит начальное состояние Танцпола.
    Ключевые поля восстанавливаются из кристалла для межсессионной непрерывности:
    - SOC-тензии (с коэффициентом затухания SOC_RESTART_DECAY)
    - sigma_window и k_jera
    - current_note и current_note_name
    - shared_memory (последние 10 записей)
    - tensor_last, janus_dyad, current_chord
    """
    dm = crystal.get("diagnostic_metrics", {})

    # SOC-тензии из кристалла с затуханием (перезапуск — не пустота)
    soc_crystal = dm.get("soc_tension", {})
    restored_tensions = {
        c: round(float(soc_crystal.get(c, 0.0)) * SOC_RESTART_DECAY, 4)
        for c in ("Head", "Heart", "Body")
    }

    # Нота октавы
    restored_note = int(crystal.get("current_note", 1))
    if restored_note not in range(1, 10):
        restored_note = 1

    # Shared memory: берём последние 10 записей из кристалла
    crystal_mem = crystal.get("shared_memory", [])
    restored_mem = crystal_mem[-10:] if crystal_mem else []

    return {
        "dancefloor_type":   "tmpfs_RAM",
        "mounted_at":        int(time.time()),
        "shared_memory":     restored_mem,
        "cycle":             crystal.get("cycle", 0),
        "current_note":      restored_note,
        "current_note_name": NOTE_MAP.get(restored_note, NOTE_MAP[1]),
        "current_node":      "Node_Initialization",
        "active_role":       "Janus_Conductor",
        "marker":            "Nominal",
        "active_rune":       crystal.get("active_rune", RUNE_JERA),
        "rune_meaning":      crystal.get("rune_meaning", "Йера — Урожай, начало нового цикла Октавы"),
        "devas_state":       DEVA_MAP.copy(),
        "diagnostic_metrics": {
            "branching_coefficient_sigma": dm.get("branching_coefficient_sigma", 1.0),
            "sigma_last":                  dm.get("sigma_last", 1.0),
            "sigma_window":                dm.get("sigma_window", []),
            "soc_tension":                 restored_tensions,
            "k_jera_soc":                  round(float(dm.get("k_jera_soc", 0.0)) * SOC_RESTART_DECAY, 4),
            "largest_lyapunov_exponent_lambda": 0.11,
            "degradation_count":           0,
            "stasis_count":                0,
            "context_entropy":             dm.get("context_entropy", 0.0),
        },
        # Планетарные данные из кристалла — stargazer не стартует вслепую
        "stellar_viscosities": crystal.get("stellar_viscosities", {}),
        "stellar_positions":   crystal.get("stellar_positions", {}),
        "stellar_timestamp":   crystal.get("stellar_timestamp", 0),
        # Заземление (Кодекс §5): восстанавливается из кристалла, но не падает ниже 0.5 при рестарте
        "grounding_score":    max(0.5, float(crystal.get("grounding_score", 1.0))),
        # Состояние аккорда и тензора из кристалла
        "current_chord":      crystal.get("current_chord", {}),
        "current_chord_name": crystal.get("current_chord_name", ""),
        "current_plane":      crystal.get("current_plane", 3),
        "tensor_last":        crystal.get("tensor_last", {}),
        "janus_dyad":         crystal.get("janus_dyad", {}),
        # Archetype-кластеры восстанавливаются, но НЕ инжектятся в HOT-промпт (пока)
        "archetype_clusters": crystal.get("archetype_clusters", {}),
    }


import shutil

def main():
    os.makedirs(DANCEFLOOR, exist_ok=True)
    crystal = load_crystal()
    state   = build_state(crystal)

    field_path = os.path.join(DANCEFLOOR, "field_state.json")
    with open(field_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    if os.path.exists(GLYPH_PERSISTENT):
        shutil.copy2(GLYPH_PERSISTENT, os.path.join(DANCEFLOOR, "glyph_codex.json"))
        print(f"[ᛃ] Кодекс глифов восстановлен из {GLYPH_PERSISTENT}")

    prev_cycle = crystal.get("cycle", 0)
    restored   = f"нота={state['current_note']} σ-окно={len(state['diagnostic_metrics']['sigma_window'])} mem={len(state['shared_memory'])}"
    print(f"[ᛃ] Танцпол (RAM) инициализирован | Цикл возобновлён с {prev_cycle} | Руна: {RUNE_JERA}")
    print(f"[ᛃ] Восстановлено из кристалла: {restored}")
    print(f"[ᛃ] Путь: {field_path}")


if __name__ == "__main__":
    main()
