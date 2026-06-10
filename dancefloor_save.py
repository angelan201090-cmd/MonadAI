#!/usr/bin/env python3
"""
Кристаллизация RAM-Танцпола перед размонтированием.
Сохраняет состояние в dancefloor_crystal.json (persistent).
"""
import json
import math
import os
import shutil
import time

MONADA_ROOT      = "/home/angelan/data/Monada-Hardcore"
DANCEFLOOR       = "/mnt/dancefloor"
CRYSTAL          = os.path.join(MONADA_ROOT, "dancefloor_crystal.json")
GLYPH_PERSISTENT = os.path.join(MONADA_ROOT, "glyph_codex_persistent.json")
MIDTERM_MEMORY   = os.path.join(DANCEFLOOR, "midterm_memory.jsonl")

ARCHETYPE_RUNE = {
    "Reality over Interpretation":     "ᚱ",
    "Recovery through Verification":   "ᛒ",
    "Signal over Noise":               "ᚨ",
    "Compression over Accumulation":   "ᛜ",
}

MAX_CLUSTERS       = 48
MAX_SOURCE_HASHES  = 50
MAX_LESSON_SAMPLES = 3


def _safe_float(value, default: float = 0.0) -> float:
    """Терпимое приведение к float — None/мусор/нечисло → default."""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        return default
    return f


def _safe_int(value, default: int = 0) -> int:
    """Терпимое приведение к int через _safe_float."""
    return int(_safe_float(value, default))


def _finite_float(value) -> tuple[bool, float]:
    """Возвращает (valid, value). valid=False для None/нечисла/NaN/inf."""
    if value is None:
        return False, 0.0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False, 0.0
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        return False, 0.0
    return True, f


def _aggregate_archetype_clusters() -> dict:
    """Собирает archetype-кластеры из WARM (midterm_memory.jsonl).

    Только dict-записи с candidate_for_crystal == True. Без LLM/эмбеддингов.
    WARM-файл не мутируется (только чтение).
    """
    if not os.path.exists(MIDTERM_MEMORY):
        return {}

    agg: dict = {}
    try:
        with open(MIDTERM_MEMORY, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(rec, dict):
                    continue
                if rec.get("candidate_for_crystal") is not True:
                    continue

                # Одна битая candidate-запись не должна срывать всю агрегацию.
                try:
                    arch = str(rec.get("archetype", "")).strip()
                    if not arch:
                        continue

                    # Невалидные числовые поля → ПРОПУСК кандидата (не зануление).
                    # Отсутствующие поля (sentinel None) тоже невалидны.
                    ok_pain,   pain   = _finite_float(rec.get("pain_score"))
                    ok_recov,  recov  = _finite_float(rec.get("recovery_score"))
                    ok_ground, ground = _finite_float(rec.get("grounding"))
                    ok_cycle,  cyclef = _finite_float(rec.get("cycle"))
                    if not (ok_pain and ok_recov and ok_ground and ok_cycle):
                        continue
                    cycle = int(cyclef)

                    sha    = str(rec.get("sha256", ""))
                    lesson = str(rec.get("lesson", ""))

                    c = agg.get(arch)
                    if c is None:
                        c = {
                            "archetype":     arch,
                            "rune":          ARCHETYPE_RUNE.get(arch, "ᛜ"),
                            "count":         0,
                            "first_cycle":   cycle,
                            "last_cycle":    cycle,
                            "source_hashes": [],
                            "_sum_pain":     0.0,
                            "_sum_recovery": 0.0,
                            "_sum_grounding": 0.0,
                            "lesson_samples": [],
                        }
                        agg[arch] = c

                    c["count"]          += 1
                    c["first_cycle"]     = min(c["first_cycle"], cycle)
                    c["last_cycle"]      = max(c["last_cycle"], cycle)
                    c["_sum_pain"]      += pain
                    c["_sum_recovery"]  += recov
                    c["_sum_grounding"] += ground
                    # Границы соблюдаются ВО ВРЕМЯ накопления (не только в конце).
                    if sha and sha not in c["source_hashes"]:
                        c["source_hashes"].append(sha)
                        if len(c["source_hashes"]) > MAX_SOURCE_HASHES:
                            c["source_hashes"] = c["source_hashes"][-MAX_SOURCE_HASHES:]
                    if lesson and lesson not in c["lesson_samples"]:
                        c["lesson_samples"].append(lesson)
                        if len(c["lesson_samples"]) > MAX_LESSON_SAMPLES:
                            c["lesson_samples"] = c["lesson_samples"][-MAX_LESSON_SAMPLES:]
                except Exception:
                    continue

    except OSError:
        return {}

    clusters = []
    for arch, c in agg.items():
        n = max(c["count"], 1)
        avg_pain     = round(c["_sum_pain"] / n, 3)
        avg_recovery = round(c["_sum_recovery"] / n, 3)
        avg_ground   = round(c["_sum_grounding"] / n, 3)
        weight = round(
            (avg_recovery - avg_pain) * max(avg_ground, 0.0) * math.log1p(c["count"]),
            3,
        )
        clusters.append({
            "archetype":      c["archetype"],
            "rune":           c["rune"],
            "count":          c["count"],
            "first_cycle":    c["first_cycle"],
            "last_cycle":     c["last_cycle"],
            "source_hashes":  c["source_hashes"][-MAX_SOURCE_HASHES:],
            "avg_pain":       avg_pain,
            "avg_recovery":   avg_recovery,
            "avg_grounding":  avg_ground,
            "weight":         weight,
            "lesson_samples": c["lesson_samples"][-MAX_LESSON_SAMPLES:],
        })

    clusters.sort(key=lambda x: abs(x["weight"]), reverse=True)
    clusters = clusters[:MAX_CLUSTERS]
    return {c["archetype"]: c for c in clusters}


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

        # ── Archetype-кластеры из WARM → в кристалл (детерминированно, без LLM) ──
        try:
            clusters = _aggregate_archetype_clusters()
            if clusters:
                state["archetype_clusters"] = clusters
                print(f"[ᛇ] Archetype-кластеров кристаллизовано: {len(clusters)}")
            else:
                state.setdefault("archetype_clusters", {})
        except Exception as _ce:
            print(f"[ᛁ] Archetype-агрегация пропущена: {_ce}")
            state.setdefault("archetype_clusters", {})

        tmp = CRYSTAL + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CRYSTAL)

        cycle = state.get("cycle", "?")
        rune  = state.get("active_rune", "?")
        print(f"[ᛇ] Кристалл сохранён → dancefloor_crystal.json | Цикл: {cycle} | Руна: {rune}")

        glyph_src = os.path.join(DANCEFLOOR, "glyph_codex.json")
        if os.path.exists(glyph_src):
            shutil.copy2(glyph_src, GLYPH_PERSISTENT)
            print(f"[ᛇ] Кодекс глифов сохранён → glyph_codex_persistent.json")

    except Exception as e:
        print(f"[ᛁ] Ошибка кристаллизации: {e}")


if __name__ == "__main__":
    main()
