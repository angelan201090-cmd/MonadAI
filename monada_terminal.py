#!/usr/bin/env python3
"""
monada_terminal.py — терминал Монады v35.0 ГЕПТАРХИЯ
Использует core/conductor.py как точку входа.
"""
import os
import sys
import json
import time
import urllib.request

sys.path.insert(0, "/home/angelan/data/Monada-Hardcore")

MONADA_ROOT  = "/home/angelan/data/Monada-Hardcore"
FIELD_STATE  = "/mnt/dancefloor/field_state.json"
CRYSTAL      = os.path.join(MONADA_ROOT, "dancefloor_crystal.json")

PORTS = {
    "УМ":       8081,
    "СЕРДЦЕ":   8082,
    "ТЕЛО":     8083,
    "ПЕРСОНА":  8084,
    "ТЕНЬ":     8085,
    "СИНТЕЗ":   8086,
    "ПОДСОЗНАНИЕ": 13305,
}

ANSI_RESET  = "\033[0m"
ANSI_BOLD   = "\033[1m"
ANSI_DIM    = "\033[2m"
ANSI_CYAN   = "\033[1;36m"
ANSI_GREEN  = "\033[1;32m"
ANSI_YELLOW = "\033[1;33m"
ANSI_RED    = "\033[1;31m"
ANSI_PURPLE = "\033[1;35m"


# ── Утилиты ──────────────────────────────────────────────────────────────────

def _check_port(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/models")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except Exception:
        pass
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v0/health")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except Exception:
        return False


def _load_state() -> dict:
    for path in (FIELD_STATE, CRYSTAL):
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _sigma_color(sigma: float) -> str:
    if sigma < 0.75:
        return ANSI_RED
    if sigma > 1.35:
        return ANSI_YELLOW
    return ANSI_GREEN


def _show_status() -> None:
    state   = _load_state()
    cycle   = state.get("cycle", 0)
    note    = state.get("current_note_name", "—")
    rune    = state.get("active_rune", "ᛞ")
    marker  = state.get("marker", "—")
    sigma   = state.get("janus_dyad", {}).get("d_persona", None)

    tensions = {}
    tensor   = state.get("tensor_last", {})
    if tensor:
        sigma = tensor.get("sigma_ff", sigma)
    soc_tensions = {}
    for deva_info in state.get("devas_state", {}).values():
        c = deva_info.get("center", "")
        e = deva_info.get("energy", 0.0)
        if c and c not in soc_tensions:
            soc_tensions[c] = e

    print(f"\n{ANSI_CYAN}{'═'*60}{ANSI_RESET}")
    print(f"  {ANSI_BOLD}МОНАДА v35.0 ГЕПТАРХИЯ{ANSI_RESET}  |  цикл {cycle}  |  {rune}")
    print(f"  Нота: {note}")
    print(f"  Маркер: {marker}")
    if sigma is not None:
        sc = _sigma_color(float(sigma))
        print(f"  σ = {sc}{sigma:.3f}{ANSI_RESET}")
    print(f"\n  {ANSI_BOLD}Порты:{ANSI_RESET}")
    for name, port in PORTS.items():
        ok  = _check_port(port)
        dot = f"{ANSI_GREEN}●{ANSI_RESET}" if ok else f"{ANSI_RED}○{ANSI_RESET}"
        print(f"    {dot} {name:12s} :{port}")
    print(f"{ANSI_CYAN}{'═'*60}{ANSI_RESET}\n")


def _pralaya() -> None:
    try:
        from core.janus_conductor import glyphogenesis
        state = _load_state()
        mem   = state.get("shared_memory", [])
        n     = glyphogenesis(mem, state.get("cycle", 0))
        print(f"{ANSI_YELLOW}ᛟ Пралайя: глифогенез завершён (+{n} глифов){ANSI_RESET}")
    except Exception as ex:
        print(f"{ANSI_RED}Пралайя: {ex}{ANSI_RESET}")
    try:
        import lipika_writer
        state = _load_state()
        lipika_writer.record("PRALAYA", "terminal",
                             "ручная пралайя из терминала",
                             cycle=state.get("cycle", 0))
    except Exception:
        pass
    if os.path.exists(FIELD_STATE):
        try:
            with open(FIELD_STATE, encoding="utf-8") as f:
                s = json.load(f)
            s["current_note"] = 1
            s.pop("active_task", None)
            s["shock_count"]  = 0
            s["marker"]       = "PRALAYA"
            s["last_pralaya"] = int(time.time())
            with open(FIELD_STATE, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
            print(f"{ANSI_YELLOW}ᛃ Нота сброшена → ДО, active_task очищен{ANSI_RESET}")
        except Exception as ex:
            print(f"{ANSI_RED}Сохранение после пралайи: {ex}{ANSI_RESET}")


HELP_TEXT = f"""
{ANSI_BOLD}Команды:{ANSI_RESET}
  /статус      — текущий SOC, нота, порты
  /пралайя     — кристаллизация + сброс к ДО
  /выход       — выход из терминала
  /помощь      — эта справка
  <любой текст> — такт Монады
"""


# ── Главный цикл ─────────────────────────────────────────────────────────────

def main() -> None:
    _show_status()

    try:
        from core.conductor import Conductor
        conductor = Conductor()
    except Exception as ex:
        print(f"{ANSI_RED}Ошибка загрузки Conductor: {ex}{ANSI_RESET}")
        sys.exit(1)

    print(f"{ANSI_DIM}Введите задачу или команду (/помощь){ANSI_RESET}\n")

    while True:
        try:
            raw = input(f"{ANSI_PURPLE}ᛗ{ANSI_RESET} >>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{ANSI_DIM}Прерывание — выход.{ANSI_RESET}")
            break

        if not raw:
            continue

        if raw in ("/выход", "/exit", "/quit"):
            break
        elif raw in ("/помощь", "/help"):
            print(HELP_TEXT)
        elif raw in ("/статус", "/status"):
            _show_status()
        elif raw in ("/пралайя", "/pralaya"):
            _pralaya()
        else:
            t0 = time.time()
            try:
                result = conductor.run(raw)
            except KeyboardInterrupt:
                print(f"\n{ANSI_YELLOW}[такт прерван]{ANSI_RESET}")
                continue
            except Exception as ex:
                print(f"{ANSI_RED}[ошибка такта: {ex}]{ANSI_RESET}")
                continue
            elapsed = time.time() - t0
            print(f"\n{ANSI_DIM}── такт {elapsed:.1f}с ──────────────────────────{ANSI_RESET}\n")


if __name__ == "__main__":
    main()
