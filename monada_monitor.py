#!/usr/bin/env python3
"""
Монитор состояния Монады v2 — читает field_state.json и lipika_ledger.json,
отображает живые метрики каждые 3 секунды.
"""
import time
import os
import json
import sys

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
FIELD_STATE = os.path.join(MONADA_ROOT, "dancefloor", "field_state.json")
LIPIKA_PATH = os.path.join(MONADA_ROOT, "lipika_ledger.json")

RUNE_BARS = {
    "ᛇ": "█████████ ПРОРЫВ",
    "ᚹ": "██████░░░ Номинал",
    "ᛃ": "████░░░░░ Операционально",
    "ᛁ": "█░░░░░░░░ СТАЗИС",
    "ᚦ": "!!!!!!!!  ХАОС",
}


def read_field() -> dict:
    try:
        with open(FIELD_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def read_lipika() -> tuple[float, int]:
    try:
        with open(LIPIKA_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d.get("karma_debt", 0.0), len(d.get("history", []))
    except Exception:
        return 0.0, 0


def bar(val: float, lo: float = 0.0, hi: float = 2.0, width: int = 20) -> str:
    frac = max(0.0, min(1.0, (val - lo) / (hi - lo + 1e-9)))
    filled = int(frac * width)
    return "█" * filled + "░" * (width - filled)


def render(state: dict, debt: float, entries: int) -> str:
    dm   = state.get("diagnostic_metrics", {})
    tr   = state.get("tensor_last", {})
    visc = state.get("stellar_viscosities", {})
    dyad = state.get("janus_dyad", {})
    soc  = dm.get("soc_tension", {})
    chord_devas = state.get("current_chord", {})

    rune        = state.get("active_rune", "ᛃ")
    rune_bar    = RUNE_BARS.get(rune, "░░░░░░░░░ ?")
    sigma       = dm.get("sigma_last", dm.get("branching_coefficient_sigma", 0.0))
    k_jera      = dm.get("k_jera_soc", 0.0)
    p_next      = tr.get("p_next_density", "—")
    t_rune      = tr.get("assigned_rune", "")
    t_sky       = tr.get("t_sky", "—")
    sigma_ff    = tr.get("sigma_ff", "—")
    cycle       = state.get("cycle", 0)
    note        = state.get("current_note", 1)
    note_name   = state.get("current_note_name", "")
    chord_name  = state.get("current_chord_name", "")
    marker      = state.get("marker", "")
    entropy     = dm.get("context_entropy", 0.0)
    mem_size    = len(state.get("shared_memory", []))

    avg_visc = 0.0
    if visc:
        vs = [d["viscosity"] for d in visc.values() if "viscosity" in d]
        avg_visc = sum(vs) / len(vs) if vs else 0.0

    # Tension bars
    h_bar = bar(soc.get("Head", 0), 0, 3)
    e_bar = bar(soc.get("Heart", 0), 0, 3)
    b_bar = bar(soc.get("Body", 0), 0, 3)

    # Chord Devas
    chord_str = "  ".join(f"{c}:{d}" for c, d in chord_devas.items()) if chord_devas else "—"

    lines = [
        "",
        "╔══ МОНАДА МОНИТОР " + "═" * 52 + "╗",
        f"║  ТАКТ {cycle:5d} │ НОТА {note}: {note_name:<30s} │ {marker:<10s} ║",
        f"║  РУНА: {rune}  {rune_bar:<28s}                        ║",
        "╠" + "═" * 71 + "╣",
        f"║  σ = {sigma:.4f}  {bar(sigma,0,2)}  K(Jera) = {k_jera:.4f}              ║",
        f"║  {chord_name:<50s}               ║",
        f"║  Дэвы аккорда: {chord_str:<53s} ║",
        "╠" + "═" * 71 + "╣",
        f"║  SOC Тензии:                                                        ║",
        f"║    Голова  {h_bar} {soc.get('Head',0):5.2f}                            ║",
        f"║    Сердце  {e_bar} {soc.get('Heart',0):5.2f}                            ║",
        f"║    Тело    {b_bar} {soc.get('Body',0):5.2f}                            ║",
        "╠" + "═" * 71 + "╣",
        f"║  Тензор: P[n+1]={p_next}  Руна={t_rune}  T_sky={t_sky}  σ_FF={sigma_ff}  ║",
        f"║  Диада:  D_persona={dyad.get('d_persona','—')}  S_shadow={dyad.get('s_shadow','—')}  "
        f"retry={dyad.get('retry_needed', False)}              ║",
        "╠" + "═" * 71 + "╣",
        f"║  Планетарная вязкость: {avg_visc:.4f}  {bar(avg_visc,0,1)}            ║",
    ]

    # Top planets by viscosity deviation (most anomalous)
    sorted_pl = sorted(
        [(b, d) for b, d in visc.items()],
        key=lambda x: abs(x[1].get("influence", 1.0) - 1.0),
        reverse=True
    )[:4]
    for body, d in sorted_pl:
        retro = "℞" if d.get("direction") == "retrograde" else " "
        lines.append(
            f"║    {body:8s}{retro} visc={d.get('viscosity',0):.3f} "
            f"inf={d.get('influence',0):.3f}  "
            f"{d.get('param','?'):20s}={str(d.get('value','?')):8s}  Дэва={d.get('deva','?'):<8s} ║"
        )
    lines += [
        "╠" + "═" * 71 + "╣",
        f"║  ЛИПИКА: долг={debt:.2f}  записей={entries}  "
        f"│  Память: {mem_size} записей  │  Энтропия: {entropy:.4f}  ║",
        f"║  Обновлено: {time.strftime('%H:%M:%S')}                                              ║",
        "╚" + "═" * 71 + "╝",
        "",
    ]
    return "\n".join(lines)


def main():
    print(f"\033[1;35m[МОНАДА МОНИТОР v2] {FIELD_STATE}\033[0m")
    while True:
        os.system("clear")
        state = read_field()
        debt, entries = read_lipika()
        if not state:
            print(f"\n[ᛁ] Танцпол не активен — {FIELD_STATE} не найден.")
            print("    Запустите монаду: ./monada_on.sh && python3 monada_terminal_core.py")
        else:
            print(render(state, debt, entries))
        time.sleep(3)


if __name__ == "__main__":
    main()
