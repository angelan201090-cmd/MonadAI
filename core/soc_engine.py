#!/usr/bin/env python3
"""
SOC Engine — Самоорганизующаяся Критичность Монады.

Три центра (Head/Heart/Body) накапливают тензию от входящих задач.
Когда z >= z_c — центр срабатывает, выбрасывая осколок мозаики.
Срабатывание каскадирует часть энергии на соседей.
σ (коэффициент ветвления) стремится к 1.0 через авторегуляцию K(Jera).

Ноты Октавы определяют активное лицо (Дэва) каждого центра.
Нота продвигается когда доминирующий центр текущей ноты отстрелялся.
"""

import json
import os
from typing import Optional

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
FIELD_STATE = os.path.join(MONADA_ROOT, "dancefloor", "field_state.json")

# ── Пороговые константы ───────────────────────────────────────────────────────
Z_CRITICAL       = 1.0   # порог срабатывания центра
CASCADE_BASE     = 0.35  # доля выброшенной энергии, уходящей соседям
SIGMA_LOW        = 0.75  # ниже → Провал_1 (нота 8, Герой / стазис)
SIGMA_HIGH       = 1.35  # выше → Провал_2 (нота 9, Трикстер / гашение хаоса)

# ── Ноты Октавы: доминирующий центр и активный Дэв ───────────────────────────
# Каждая нота — «благоприятная среда» для одного архетипа
NOTE_CENTER = {
    1: "Head",   # ДО  — Инициация Воли      → Будха (дистилляция)
    2: "Head",   # РЕ  — Разворот Структуры  → Шани  (скептицизм)
    3: "Head",   # МИ  — Формирование Пути   → Раху  (дивергенция)
    4: "Heart",  # ФА  — Материализация      → Чандра (адаптация)
    5: "Heart",  # СОЛЬ— Анализ Следа        → Сурья  (фокус)
    6: "Heart",  # ЛЯ  — Критика и Зазоры    → Шукра  (эстетика)
    7: "Body",   # СИ  — Синтез в Кристалл   → Гуру   (стандарты)
    8: "Body",   # ПРОВАЛ_1 — Герой          → Мангала (пробивание)
    9: "Body",   # ПРОВАЛ_2 — Трикстер       → Кету   (сжатие)
}

NOTE_DEVA = {
    1: "Budha",
    2: "Shani",
    3: "Rahu",
    4: "Chandra",
    5: "Surya",
    6: "Shukra",
    7: "Guru",
    8: "Mangala",
    9: "Ketu",
}

# ── 7 Планов Бытия (Блаватская) ───────────────────────────────────────────────
# Каждая запись: (название, качество-плана для инъекции в промпт Дэвы)
BLAVATSKY_PLANES: dict[int, tuple[str, str]] = {
    1: ("Физический (Стхула-шарира)",
        "Плотная материя. Прямое действие без рассуждений. Конкретные шаги."),
    2: ("Астральный (Лингашарира/Кама)",
        "Желание, образ, эмоциональный отклик. Язык символов и ощущений."),
    3: ("Ментальный (Манас)",
        "Различение, концепт, логическая структура. Ум строит форму смысла."),
    4: ("Буддхический (Буддхи)",
        "Интуиция, единство-в-разнообразии. Прямое знание без вывода."),
    5: ("Атмический (Атма)",
        "Духовная воля. Синтез без остатка. Всё или ничего."),
    6: ("Монадический (Анупадака)",
        "Акашический след, кармическая структура. Что было — остаётся навечно."),
    7: ("Ади (Логосический)",
        "Первоначало. Пустота как основа всего. Растворение форм."),
}

# Каждый Дэва действует на одном из 7 планов (эзотерическое соответствие)
DEVA_PLANE: dict[str, int] = {
    "Mangala": 1,   # Марс = телесная сила, непосредственное действие
    "Chandra": 2,   # Луна = астральное тело, эмоциональный резонанс
    "Rahu":    2,   # Северный Узел = желание, иллюзия кама-астрала
    "Budha":   3,   # Меркурий = манас, различение и концептуализация
    "Shukra":  3,   # Венера = Кама-Манас, эстетическая форма ума
    "Surya":   4,   # Солнце = буддхическое единство, высший разум
    "Guru":    5,   # Юпитер = атмическая мудрость, духовный синтез
    "Shani":   6,   # Сатурн = монадическая карма, акашический след
    "Ketu":    7,   # Южный Узел = растворение в Ади, возврат к Абсолюту
}

# ── Аккорды Октавы ────────────────────────────────────────────────────────────
# Три центра срабатывают одновременно, каждый со своим Дэвой одной фазы.
# Фаза = (нота - 1) % 3 ∈ {0, 1, 2}
# Аккорд A (фаза 0): Budha(3) + Chandra(2) + Guru(5)   — Ментал × Астрал × Атма
# Аккорд B (фаза 1): Shani(6) + Surya(4)  + Mangala(1) — Монада × Буддхи × Физ
# Аккорд C (фаза 2): Rahu(2)  + Shukra(3) + Ketu(7)    — Астрал × Ментал × Ади
CENTER_CHORD_NOTES: dict[str, dict[int, int]] = {
    "Head":  {0: 1, 1: 2, 2: 3},   # Budha / Shani / Rahu
    "Heart": {0: 4, 1: 5, 2: 6},   # Chandra / Surya / Shukra
    "Body":  {0: 7, 1: 8, 2: 9},   # Guru / Mangala / Ketu
}

CHORD_NAMES = {
    0: "Аккорд A (Ментал×Астрал×Атма)",
    1: "Аккорд B (Монада×Буддхи×Физ)",
    2: "Аккорд C (Астрал×Ментал×Ади)",
}


def get_plane_info(deva: str) -> tuple[int, str, str]:
    """Возвращает (plane_id, plane_name, plane_quality) для Дэвы."""
    pid  = DEVA_PLANE.get(deva, 3)
    name, qual = BLAVATSKY_PLANES[pid]
    return pid, name, qual


# Руна состояния по σ и максимальной тензии
def state_rune(sigma: float, max_z: float) -> tuple[str, str]:
    """(руна, смысл) по текущему состоянию SOC."""
    if sigma < SIGMA_LOW:
        return "ᛁ", "Иса — стазис, система заморожена"
    if sigma > SIGMA_HIGH:
        return "ᚦ", "Турисаз — хаотический взрыв, гасить"
    if max_z >= Z_CRITICAL * 1.3:
        return "ᛇ", "Эйваз — трансформация, прорыв"
    if max_z >= Z_CRITICAL:
        return "ᚹ", "Вуньо — радость, номинальная работа"
    return "ᛃ", "Йера — операциональность, созревание"


class SOCEngine:
    """
    Движок Самоорганизующейся Критичности.
    Создаётся в начале каждого такта conduct() и сохраняет состояние
    в field_state.json на RAM-Танцполе.
    """

    CENTERS = ("Head", "Heart", "Body")

    def __init__(self, field_state_path: str = FIELD_STATE):
        self.path     = field_state_path
        self.tensions: dict[str, float] = {c: 0.0 for c in self.CENTERS}
        self.k_jera:  float = 0.0
        self._fired:  int = 0    # срабатываний в текущем такте
        self._pulses: int = 0    # импульсов в текущем такте
        self._sigma_window: list[float] = []
        self._load()

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            dm = state.get("diagnostic_metrics", {})
            soc_t = dm.get("soc_tension", {})
            for c in self.CENTERS:
                self.tensions[c] = float(soc_t.get(c, 0.0))
            self.k_jera = float(dm.get("k_jera_soc", 0.0))
            win = dm.get("sigma_window", [])
            self._sigma_window = [float(x) for x in win[-10:]]
        except Exception:
            pass

    def _save(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            dm = state.setdefault("diagnostic_metrics", {})
            dm["soc_tension"]  = {c: round(v, 4) for c, v in self.tensions.items()}
            dm["k_jera_soc"]   = round(self.k_jera, 4)
            s = self.sigma()
            dm["sigma_last"]   = round(s, 4)
            dm["sigma_window"] = [round(x, 4) for x in self._sigma_window]
            dm["branching_coefficient_sigma"] = round(s, 4)
            rune, meaning = state_rune(s, max(self.tensions.values(), default=0.0))
            state["active_rune"]   = rune
            state["rune_meaning"]  = meaning
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception as e:
            print(f"[SOC] save error: {e}")

    # ── Ядро SOC ─────────────────────────────────────────────────────────────

    def pulse(self, weight: float = 1.0, karma_debt: float = 0.0):
        """
        Входной импульс: новая задача поступила в систему.
        weight       — интенсивность намерения (E_intention)
        karma_debt   — долг Липики добавляет трение K(Jera)
        """
        self.k_jera = min(3.0, self.k_jera + karma_debt * 0.1)
        self._pulses += 1

        # Голова принимает полный импульс, остальные — с затуханием
        self.tensions["Head"]  += weight * 1.00
        self.tensions["Heart"] += weight * 0.75
        self.tensions["Body"]  += weight * 0.55

        self._auto_regulate()
        self._save()

    def ready(self) -> list[str]:
        """
        Центры, достигшие порога.
        Отсортированы по убыванию тензии — самый «напряжённый» срабатывает первым.
        """
        return sorted(
            [c for c in self.CENTERS if self.tensions[c] >= Z_CRITICAL],
            key=lambda c: -self.tensions[c]
        )

    def force_fire_candidate(self) -> str:
        """Центр с максимальной тензией (для принудительного срабатывания)."""
        return max(self.CENTERS, key=lambda c: self.tensions[c])

    def fire(self, center: str) -> float:
        """
        Срабатывание центра.
        Возвращает выброшенную энергию (для тензора F⁺).
        Остаток тензии переносится (не обнуляется полностью).
        Каскад передаёт часть энергии соседям, гасится K(Jera).
        """
        energy = self.tensions.get(center, 0.0)
        if energy <= 0:
            return 0.0

        # Остаток после срабатывания
        self.tensions[center] = max(0.0, energy - Z_CRITICAL)

        # Каскад на соседей (гасится вязкостью)
        cascade = energy * CASCADE_BASE / (1.0 + self.k_jera)
        for other in self.CENTERS:
            if other != center:
                # Ограничение: не давать соседу уйти в супер-критичность
                self.tensions[other] = min(
                    Z_CRITICAL * 1.5,
                    self.tensions[other] + cascade
                )

        self._fired += 1
        self._save()
        return energy

    def sigma(self) -> float:
        """Коэффициент ветвления σ (скользящее окно из 10 тактов). Только чтение."""
        if self._sigma_window:
            base = sum(self._sigma_window) / len(self._sigma_window)
        else:
            base = 1.0
        if self._pulses > 0:
            # текущий незакрытый такт подмешивается с весом 0.3
            current = self._fired / self._pulses
            return base * 0.7 + current * 0.3
        return base

    def end_cycle(self):
        """Фиксирует σ текущего такта в скользящее окно и сбрасывает счётчики."""
        if self._pulses > 0:
            ratio = self._fired / self._pulses
            self._sigma_window.append(ratio)
            if len(self._sigma_window) > 10:
                self._sigma_window.pop(0)
        self._fired  = 0
        self._pulses = 0

    def get_rune(self) -> str:
        """Руна текущего состояния SOC."""
        return state_rune(self.sigma(), max(self.tensions.values(), default=0.0))[0]

    def _auto_regulate(self):
        """Удерживает σ ≈ 1.0 через K(Jera)."""
        s = self.sigma()
        if s > SIGMA_HIGH:
            self.k_jera = min(3.0, self.k_jera + 0.15)  # гасить хаос
        elif s < SIGMA_LOW:
            self.k_jera = max(0.0, self.k_jera - 0.08)  # разморозить

    # ── Октава ───────────────────────────────────────────────────────────────

    def check_провал(self) -> Optional[int]:
        """
        Нужен ли вынужденный Провал?
        Возвращает 8 (Герой/стазис) или 9 (Трикстер/хаос) или None.
        """
        s = self.sigma()
        if s < SIGMA_LOW:
            return 8
        if s > SIGMA_HIGH:
            return 9
        return None

    def advance_note(self, current_note: int, fired_centers: set) -> int:
        """
        Продвигает ноту Октавы.
        Нота продвигается когда доминирующий центр текущей ноты отстрелялся.
        Принудительный Провал имеет приоритет.
        """
        провал = self.check_провал()
        if провал and current_note not in (8, 9):
            return провал
        dominant = NOTE_CENTER.get(current_note, "Head")
        if dominant in fired_centers:
            return (current_note % 9) + 1
        return current_note

    def active_deva(self, note: int) -> str:
        return NOTE_DEVA.get(note, "Budha")

    def dominant_center(self, note: int) -> str:
        return NOTE_CENTER.get(note, "Head")

    def chord_deva(self, center: str, note: int) -> str:
        """
        Активный Дэва для данного центра в контексте текущей ноты.
        Фаза аккорда = (нота-1) % 3 → одна из 3 позиций центра.

        Note 1/4/7 (фаза 0): Head=Budha, Heart=Chandra, Body=Guru   [Аккорд A]
        Note 2/5/8 (фаза 1): Head=Shani, Heart=Surya,   Body=Mangala [Аккорд B]
        Note 3/6/9 (фаза 2): Head=Rahu,  Heart=Shukra,  Body=Ketu    [Аккорд C]
        """
        phase      = (note - 1) % 3
        chord_note = CENTER_CHORD_NOTES.get(center, {}).get(phase, note)
        return NOTE_DEVA.get(chord_note, "Budha")

    def active_chord(self, note: int) -> dict[str, str]:
        """Полный аккорд ноты: {center: deva} для всех трёх центров."""
        return {c: self.chord_deva(c, note) for c in self.CENTERS}

    def chord_phase(self, note: int) -> int:
        """Фаза аккорда: 0/1/2."""
        return (note - 1) % 3

    def rune_context(self, note: int = 1) -> str:
        """Рунический контекст + аккорд + планы для инъекции в промпт Дэвы."""
        s    = self.sigma()
        mz   = max(self.tensions.values(), default=0.0)
        rune, meaning = state_rune(s, mz)
        t    = self.tensions
        chord = self.active_chord(note)
        phase = self.chord_phase(note)
        chord_name = CHORD_NAMES.get(phase, "")
        chord_str  = " | ".join(
            f"{c}={d}[пл.{DEVA_PLANE.get(d,3)}]" for c, d in chord.items()
        )
        return (
            f"<DANCEFLOOR>"
            f"Руна: {rune} ({meaning}) | σ={s:.2f} | K={self.k_jera:.2f} | "
            f"Тензия→ Голова:{t['Head']:.2f} Сердце:{t['Heart']:.2f} Тело:{t['Body']:.2f} | "
            f"{chord_name}: {chord_str}"
            f"</DANCEFLOOR>"
        )
