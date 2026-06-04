"""
Lipika Ledger — append-only кармический реестр Монады.

Каждое событие (боль, ошибка, стазис) записывается с SHA-256 хэшем
и меткой времени. Накопленный нерешённый долг блокирует μ (сверхусилие)
в тензорном движке до искупления когерентными вычислениями.

v2: улучшена детекция REDEEM — качественный синтез >300 символов без маркеров боли
автоматически засчитывается как искупление.
"""

import json
import hashlib
import time
import os
import sys

LEDGER_PATH = "/home/angelan/data/Monada-Hardcore/lipika_ledger.json"

EVENT_PAIN    = "PAIN"
EVENT_STASIS  = "STASIS"
EVENT_HALLUC  = "HALLUC"
EVENT_REDEEM  = "REDEEM"

DEBT_WEIGHTS = {
    EVENT_PAIN:   1.0,
    EVENT_STASIS: 0.5,
    EVENT_HALLUC: 2.0,
    EVENT_REDEEM: -1.5,
}

# Порог длины для автоматического засчёта REDEEM
REDEEM_MIN_LEN = 300

# Маркеры боли — наличие хотя бы одного = не REDEEM
PAIN_MARKERS = ("БОЛЬ", "--- БОЛЬ", "returncode", "ᛁ", "ISA", "СТАЗИС",
                "fallback", "вне сети", "Ошибка", "СБОЙ", "CRITICAL")


def _load() -> dict:
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"karma_debt": 0.0, "history": []}


def _save(ledger: dict) -> None:
    tmp = LEDGER_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
    os.replace(tmp, LEDGER_PATH)


def record(event_type: str, role: str, content: str, cycle: int = 0) -> dict:
    ledger  = _load()
    payload = f"{event_type}:{role}:{cycle}:{content}"
    sha     = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    entry = {
        "id":        sha[:16],
        "sha256":    sha,
        "timestamp": int(time.time()),
        "event":     event_type,
        "role":      role,
        "cycle":     cycle,
        "resolved":  event_type == EVENT_REDEEM,
        "excerpt":   content[:120],
    }

    ledger["history"].append(entry)
    weight = DEBT_WEIGHTS.get(event_type, 0.0)
    ledger["karma_debt"] = max(0.0, round(ledger["karma_debt"] + weight, 3))

    _save(ledger)
    print(f"[LIPIKA] {event_type} by {role} | debt={ledger['karma_debt']:.2f} | sha={sha[:10]}",
          file=sys.stderr)
    return entry


def get_debt() -> float:
    return _load().get("karma_debt", 0.0)


def is_debt_critical(threshold: float = 5.0) -> bool:
    return get_debt() >= threshold


def _is_clean(artifact: str) -> bool:
    """Артефакт без маркеров боли и достаточной длины → кандидат на REDEEM."""
    return (
        len(artifact.strip()) >= REDEEM_MIN_LEN
        and not any(k in artifact for k in PAIN_MARKERS)
    )


def auto_record_from_artifact(role: str, artifact: str, cycle: int = 0) -> None:
    """
    Автоматически определяет тип события и записывает в реестр.

    Иерархия детекции:
    1. PAIN   — маркеры БОЛЬ/returncode
    2. STASIS — маркеры ᛁ/ISA/СТАЗИС/fallback
    3. HALLUC — артефакт < 10 символов (галлюцинация)
    4. REDEEM — явный успех ИЛИ качественный синтез >300 символов без боли
    (Если ни одно условие — событие не записывается.)
    """
    art = artifact.strip()
    if any(k in artifact for k in ("БОЛЬ", "--- БОЛЬ", "returncode")):
        record(EVENT_PAIN, role, artifact, cycle)
    elif any(k in artifact for k in ("ᛁ", "ISA", "СТАЗИС", "fallback")):
        record(EVENT_STASIS, role, artifact, cycle)
    elif len(art) < 10:
        record(EVENT_HALLUC, role, artifact, cycle)
    elif (
        "успех" in art.lower()
        or "--- успех" in art.lower()
        or _is_clean(artifact)
    ):
        record(EVENT_REDEEM, role, artifact, cycle)


if __name__ == "__main__":
    record(EVENT_PAIN,   "Builder",   "bash: command not found: nonexistent", cycle=1)
    record(EVENT_STASIS, "Navigator", "ᛁ система скована", cycle=2)
    record(EVENT_REDEEM, "Critic",    "Код проверен, логика корректна.", cycle=3)
    print(f"Current debt: {get_debt()}")
    print(f"Critical: {is_debt_critical()}")
