#!/usr/bin/env python3
"""
Glyph Codex — система глифогенеза и компактизации памяти Монады.

Алфавит: Старший Футарк (24 руны) × 2 состояния (прямое/перевёрнутое merkstave)
= 48 базовых глифов. Глифы КОМПОНУЮТСЯ в глиф-слова (как нуклеотиды ДНК),
давая 48² = 2304 / 48³ = 110592 смыслов.

Разделение для устранения коллизии с маркерами состояния SOC:
  - ОДНА руна (ᛁ)           → маркер состояния SOC (не трогаем)
  - глиф-СЛОВО 2-3 руны (ᚱᚠ) → запись кодекса (глифогенез)

Трёхслойная память:
  HOT   shared_memory (полный текст)
  WARM  глиф-кодированная (модели видят глифы + легенду)
  COLD  крипто-цепочка генезиса (неизменный архив расшифровок)
"""

import json
import os
import hashlib
import time
import re

CODEX_PATH   = "/mnt/dancefloor/glyph_codex.json"
GENESIS_PATH = "/home/angelan/data/Monada-Hardcore/glyph_genesis_chain.json"

# Метка перевёрнутого состояния (merkstave) — комбинирующий макрон U+0304.
# ᚱ̄ = теневой/провальный аспект руны ᚱ.
INV = "̄"

# ── Старший Футарк: руна → традиционный смысловой сид ─────────────────────────
# Сиды помогают Янусу подбирать резонансные руны под смысловые кластеры.
ELDER_FUTHARK = {
    "ᚠ": "ресурс/богатство/энергия",
    "ᚢ": "сила/воля/первичная мощь",
    "ᚦ": "хаос/разрушение/защитная сила",
    "ᚨ": "сигнал/инсайт/коммуникация",
    "ᚱ": "путь/движение/исполнение",
    "ᚲ": "знание/раскрытие/факел",
    "ᚷ": "дар/обмен/симбиоз",
    "ᚹ": "радость/успех/гармония",
    "ᚺ": "кризис/град/очищающее разрушение",
    "ᚾ": "нужда/ограничение/принуждение",
    "ᛁ": "стазис/лёд/заморозка",
    "ᛃ": "урожай/цикл/результат",
    "ᛇ": "ось/трансформация/глубина",
    "ᛈ": "жребий/тайна/неизвестное",
    "ᛉ": "защита/щит/граница",
    "ᛊ": "победа/солнце/энергия воли",
    "ᛏ": "воля/жертва/направленный удар",
    "ᛒ": "рост/рождение/становление",
    "ᛖ": "движение-в-паре/прогресс/доверие",
    "ᛗ": "самость/я/человек-узел",
    "ᛚ": "поток/интуиция/вода",
    "ᛜ": "семя/потенциал/завершённый цикл",
    "ᛞ": "прорыв/пробуждение/день",
    "ᛟ": "наследие/корень/дом",
}

FUTHARK_RUNES = list(ELDER_FUTHARK.keys())

# Руны, зарезервированные как маркеры состояния SOC — НЕ используются
# как одиночные глиф-слова (но могут входить в состав глиф-слов 2+ рун).
STATE_RUNES = {"ᛁ", "ᛃ", "ᚦ", "ᚹ", "ᛇ"}


def _rune_meaning(rune: str) -> str:
    """Смысл руны с учётом перевёрнутого состояния."""
    if rune.endswith(INV):
        base = rune[:-len(INV)]
        return f"теневой/провальный аспект «{ELDER_FUTHARK.get(base, '?')}»"
    return ELDER_FUTHARK.get(rune, "?")


def alphabet_legend() -> str:
    """Полная легенда алфавита Футарка для затравки Януса при глифогенезе."""
    lines = ["АЛФАВИТ ГЛИФОВ (Старший Футарк, прямое значение):"]
    for r, m in ELDER_FUTHARK.items():
        lines.append(f"  {r} = {m}")
    lines.append(f"Перевёрнутая руна (с {INV}) = теневой/провальный аспект.")
    return "\n".join(lines)


class GlyphCodex:
    """Хранилище глиф-слов с usage-учётом и SHA-цепочкой генезиса."""

    def __init__(self, path: str = CODEX_PATH):
        self.path = path
        self.codex: dict = {}     # glyph_word -> {meaning, expansion, refs, birth_cycle, usage, last_used}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.codex = json.load(f)
            except Exception:
                self.codex = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.codex, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ── Назначение глифа ─────────────────────────────────────────────────────
    def assign(self, glyph: str, meaning: str, expansion: str,
               cycle: int, refs: list | None = None) -> bool:
        """Регистрирует новое глиф-слово. Возвращает False если уже занято."""
        if glyph in self.codex:
            return False
        self.codex[glyph] = {
            "meaning":     meaning,
            "expansion":   expansion[:1000],
            "refs":        refs or [],
            "birth_cycle": cycle,
            "usage":       0,
            "last_used":   cycle,
        }
        self._save()
        return True

    def is_valid_glyph_word(self, glyph: str) -> bool:
        """Глиф-слово = 2+ руны Футарка (с учётом INV-меток)."""
        runes = re.findall(rf"[{''.join(FUTHARK_RUNES)}]{INV}?", glyph)
        return len(runes) >= 2

    # ── Развёртка ────────────────────────────────────────────────────────────
    def expand(self, glyph: str, cycle: int = 0) -> str:
        """Разворачивает глиф в полный смысл. Инкрементит usage."""
        entry = self.codex.get(glyph)
        if not entry:
            return f"[глиф {glyph} не найден]"
        entry["usage"] += 1
        entry["last_used"] = cycle or entry["last_used"]
        self._save()
        return f"{glyph} = {entry['meaning']}: {entry['expansion']}"

    # ── Кодирование текста ───────────────────────────────────────────────────
    def encode(self, text: str, cycle: int = 0) -> str:
        """Заменяет в тексте известные смыслы их глифами (компактизация).

        Сопоставление по ключевым refs-фразам каждого глифа.
        """
        result = text
        # Сортируем по длине refs-фраз (длинные раньше — точнее)
        items = sorted(
            self.codex.items(),
            key=lambda kv: -max((len(r) for r in kv[1].get("refs", [])), default=0),
        )
        for glyph, entry in items:
            for phrase in entry.get("refs", []):
                if phrase and phrase in result:
                    result = result.replace(phrase, glyph)
                    entry["usage"] += 1
                    entry["last_used"] = cycle or entry["last_used"]
        self._save()
        return result

    # ── Легенда для промпта (гибрид: топ-N частых) ───────────────────────────
    def legend(self, top_n: int = 10) -> str:
        """Компактная легенда самых используемых глифов для system-промпта."""
        if not self.codex:
            return ""
        top = sorted(self.codex.items(), key=lambda kv: -kv[1].get("usage", 0))[:top_n]
        lines = ["ГЛИФ-КОДЕКС (частые, разворачивай редкие через expand_glyph):"]
        for glyph, entry in top:
            lines.append(f"  {glyph} = {entry['meaning']}")
        return "\n".join(lines)

    # ── Decay: сброс мёртвой кожи (Хагалаз) ──────────────────────────────────
    def decay(self, current_cycle: int, max_idle: int = 50) -> int:
        """Удаляет глиф-слова, не использованные max_idle тактов. Возвращает кол-во."""
        dead = [
            g for g, e in self.codex.items()
            if current_cycle - e.get("last_used", 0) > max_idle and e.get("usage", 0) < 2
        ]
        for g in dead:
            del self.codex[g]
        if dead:
            self._save()
        return len(dead)

    def stats(self) -> dict:
        return {
            "total_glyphs": len(self.codex),
            "total_usage":  sum(e.get("usage", 0) for e in self.codex.values()),
        }


# ── Крипто-цепочка генезиса (неизменный архив, COLD-слой) ────────────────────
def commit_genesis(new_glyphs: dict, cycle: int, state_hash: str = "") -> str:
    """Добавляет блок в SHA-цепочку генезиса кодекса (tamper-evident).

    Каждый блок: {prev_hash, cycle, glyphs, ts, hash}. Цепочка неизменна —
    переписать историю эволюции языка Монады нельзя без разрыва хэшей.
    """
    chain = []
    if os.path.exists(GENESIS_PATH):
        try:
            with open(GENESIS_PATH, "r", encoding="utf-8") as f:
                chain = json.load(f)
        except Exception:
            chain = []
    prev_hash = chain[-1]["hash"] if chain else "0" * 64
    block = {
        "index":     len(chain),
        "prev_hash": prev_hash,
        "cycle":     cycle,
        "glyphs":    {g: e.get("meaning", "") for g, e in new_glyphs.items()},
        "state_hash": state_hash,
        "ts":        int(time.time()),
    }
    payload = json.dumps(block, ensure_ascii=False, sort_keys=True)
    block["hash"] = hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()
    chain.append(block)
    tmp = GENESIS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(chain, f, ensure_ascii=False, indent=2)
    os.replace(tmp, GENESIS_PATH)
    return block["hash"]


def verify_genesis_chain() -> tuple[bool, int]:
    """Проверяет целостность цепочки. Возвращает (валидна, длина)."""
    if not os.path.exists(GENESIS_PATH):
        return True, 0
    try:
        with open(GENESIS_PATH, "r", encoding="utf-8") as f:
            chain = json.load(f)
    except Exception:
        return False, 0
    prev = "0" * 64
    for block in chain:
        if block["prev_hash"] != prev:
            return False, len(chain)
        b = {k: block[k] for k in block if k != "hash"}
        payload = json.dumps(b, ensure_ascii=False, sort_keys=True)
        h = hashlib.sha256((block["prev_hash"] + payload).encode("utf-8")).hexdigest()
        if h != block["hash"]:
            return False, len(chain)
        prev = block["hash"]
    return True, len(chain)


if __name__ == "__main__":
    # Самотест
    c = GlyphCodex("/tmp/test_codex.json")
    print(alphabet_legend()[:200])
    c.assign("ᚱᚠ", "успешная проверка ресурсов",
             "Body выполнил check_disk, место в норме", cycle=1,
             refs=["успешная проверка ресурсов диска"])
    c.assign("ᚱ" + INV + "ᚾ", "заблокированный путь из-за нужды",
             "путь исполнения заблокирован ограничением", cycle=1)
    print("\nЛегенда:", c.legend())
    print("Encode:", c.encode("Была успешная проверка ресурсов диска вчера"))
    print("Expand:", c.expand("ᚱᚠ"))
    h = commit_genesis(c.codex, cycle=1)
    print("Genesis hash:", h[:16])
    print("Chain valid:", verify_genesis_chain())
    os.remove("/tmp/test_codex.json")
