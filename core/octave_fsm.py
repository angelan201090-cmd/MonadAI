"""
Octave FSM — State Machine Закона Семи (Гурджиев).

Узлы графа  = физические инференсы моделей Триады и Януса.
Рёбра       = передача структурированных CognitiveTensor.
Conscious Shock = прерыватель по энтропии контекста.

Используется из janus_conductor.conduct() как скелет управления.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

from core.soc_engine import SIGMA_LOW, SIGMA_HIGH


# ── Состояния Октавы ──────────────────────────────────────────────────────────

class Note(IntEnum):
    DO     = 1
    RE     = 2
    MI     = 3
    FA     = 4
    SOL    = 5
    LA     = 6
    SI     = 7
    FAIL_1 = 8   # Герой Мангала: σ < SIGMA_LOW / стазис
    FAIL_2 = 9   # Трикстер Кету: σ > SIGMA_HIGH / хаос


# Граф переходов (нормальный поток без провалов)
_TRANSITIONS: dict[int, int] = {
    1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 1,  # DO→RE→MI→FA→SOL→LA→SI→DO
    8: 1,  # FAIL_1 → сброс к DO (Герой преодолел стазис)
    9: 5,  # FAIL_2 → прыжок к SOL (Трикстер погасил хаос, переходим к анализу)
}

# Shannon-энтропия выше этого порога = контекст засорён, нужен Shock.
# 4.5 бит = ~22 равновероятных слова — слишком низко для реального shared_ctx.
# Здоровый технический текст на 300 словах ≈ 7–8 бит → порог 8.5.
ENTROPY_SHOCK_THRESHOLD = 8.5
MAX_SHOCK_RESETS        = 3   # больше → перестаём шоковать, принудительно FAIL_1


# ── Тензор когниций ───────────────────────────────────────────────────────────

@dataclass
class CognitiveTensor:
    """
    JSON-структура, передаваемая по рёбрам графа между узлами.
    Каждый узел читает tensor_in, дополняет и возвращает tensor_out.
    """
    task:        str              # исходная задача (неизменна внутри цикла)
    anchor:      str              # якорь цели — переинъектируется при Shock
    context:     str              # shared_experience (накапливается)
    artifacts:   list[str]        = field(default_factory=list)
    persona:     str              = ""
    shadow:      str              = ""
    note:        int              = 1
    sigma:       float            = 1.0
    k_jera:      float            = 0.0
    entropy:     float            = 0.0
    shock_count: int              = 0

    def as_dict(self) -> dict:
        return {
            "task":        self.task,
            "anchor":      self.anchor,
            "context":     self.context,
            "artifacts":   self.artifacts,
            "persona":     self.persona,
            "shadow":      self.shadow,
            "note":        self.note,
            "sigma":       self.sigma,
            "k_jera":      self.k_jera,
            "entropy":     self.entropy,
            "shock_count": self.shock_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CognitiveTensor":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _shannon_entropy(texts: list[str]) -> float:
    """Shannon log2-энтропия слов в списке строк."""
    if not texts:
        return 0.0
    words = " ".join(str(t) for t in texts).lower().split()
    if len(words) < 2:
        return 0.0
    total = len(words)
    cnt   = Counter(words)
    return round(-sum((c / total) * math.log2(c / total) for c in cnt.values()), 4)


# ── Сам FSM ───────────────────────────────────────────────────────────────────

class OctaveFSM:
    """
    Directed graph FSM для Октавы.

    call_node(center, deva, task, rune_ctx, note_name, k_jera,
              current_note, role_prompt, fired_already, prev_artifact) → str
        — вызывает конкретную модель Триады и возвращает артефакт.

    call_janus(task, triad_artifacts, k_jera)
        → (synthesis: str, d_persona: float, s_shadow: float, retry: bool)
        — трёхфазная диалектика Януса (Персона / Тень / Синтез).
    """

    def __init__(
        self,
        call_node:  Callable,
        call_janus: Callable,
    ) -> None:
        self._call_node  = call_node
        self._call_janus = call_janus

    # ── Conscious Shock ───────────────────────────────────────────────────────

    def should_shock(self, tensor: CognitiveTensor) -> bool:
        return (
            tensor.entropy > ENTROPY_SHOCK_THRESHOLD
            and tensor.shock_count < MAX_SHOCK_RESETS
        )

    def apply_shock(self, tensor: CognitiveTensor, log_fn: Callable | None = None) -> CognitiveTensor:
        """
        Conscious Shock: глушим зашумлённый контекст, переинъектируем якорь цели.
        Артефакты обнуляются — только anchor остаётся как стартовая переменная.
        """
        msg = (f"ᚲ CONSCIOUS SHOCK #{tensor.shock_count + 1}: "
               f"entropy={tensor.entropy:.3f} > {ENTROPY_SHOCK_THRESHOLD} "
               f"| контекст очищен, якорь переинъектирован")
        if log_fn:
            log_fn(msg)
        else:
            print(f"[FSM] {msg}")

        return CognitiveTensor(
            task        = tensor.task,
            anchor      = tensor.anchor,
            context     = tensor.anchor,   # сброс к чистому якорю
            artifacts   = [],              # обнуляем зашумлённые артефакты
            persona     = tensor.persona,
            shadow      = tensor.shadow,
            note        = tensor.note,
            sigma       = tensor.sigma,
            k_jera      = tensor.k_jera,
            entropy     = 0.0,
            shock_count = tensor.shock_count + 1,
        )

    # ── Шаг Октавы (один такт Триады) ─────────────────────────────────────────

    def step(
        self,
        tensor:      CognitiveTensor,
        firing_plan: list[dict],
        note_name:   str,
        rune_ctx:    str,
        log_fn:      Callable | None = None,
    ) -> tuple[CognitiveTensor, list[str]]:
        """
        Выполняет один такт: последовательно активирует все узлы из firing_plan,
        передавая обновляемый tensor по рёбрам.

        firing_plan items: {"center": str, "deva": str, "plane": int, "octave": str}

        Возвращает (обновлённый tensor, список новых артефактов).
        """
        # Conscious Shock перед стартом такта
        if self.should_shock(tensor):
            tensor = self.apply_shock(tensor, log_fn)

        new_artifacts:  list[str]  = []
        fired_set:      set[str]   = set()
        prev_artifact:  dict[str, str] = {}

        for unit in firing_plan:
            center       = unit["center"]
            deva         = unit["deva"]
            octave_label = unit.get("octave", "аккорд")
            plane        = unit.get("plane", 0)

            fired_already = center in fired_set
            prev = prev_artifact.get(center, "")

            # Передаём контекст узлу: task = задача + current context snapshot
            node_task = (
                f"{tensor.anchor}"
                f"{tensor.task}\n\n"
                f"<SHARED_EXPERIENCE>\n{tensor.context}\n</SHARED_EXPERIENCE>"
            )
            if fired_already:
                node_task = (
                    "[РЕФИНАЛЬНАЯ ОКТАВА] НЕ повторяй предыдущий артефакт дословно. "
                    "Уточни, проверь или углуби — добавь недостающее. "
                    "Если добавить нечего — верни одну строку: ᛁ\n"
                    f"[ТВОЙ_ПРЕДЫДУЩИЙ_АРТЕФАКТ]: {prev[:400]}\n\n"
                ) + node_task

            artifact = self._call_node(
                center        = center,
                deva          = deva,
                task          = node_task,
                rune_ctx      = rune_ctx,
                note_name     = note_name,
                k_jera        = tensor.k_jera,
                current_note  = tensor.note,
                fired_already = fired_already,
                prev_artifact = prev,
            )

            fired_set.add(center)
            prev_artifact[center] = artifact

            record = f"[{center}/{deva}|пл.{plane}|{octave_label}]: {artifact}"
            new_artifacts.append(record)

            # Рёбра: обновляем контекст после каждого узла (поток тензора)
            tensor = CognitiveTensor(
                task        = tensor.task,
                anchor      = tensor.anchor,
                context     = tensor.context + f"\n{record}",
                artifacts   = tensor.artifacts + [record],
                persona     = tensor.persona,
                shadow      = tensor.shadow,
                note        = tensor.note,
                sigma       = tensor.sigma,
                k_jera      = tensor.k_jera,
                entropy     = _shannon_entropy(tensor.artifacts + [record]),
                shock_count = tensor.shock_count,
            )

        return tensor, new_artifacts

    # ── Янус-фаза (финальная диалектика) ─────────────────────────────────────

    def janus_pass(
        self,
        tensor:       CognitiveTensor,
        all_artifacts: str,
    ) -> tuple[str, CognitiveTensor, bool]:
        """
        Прогоняет финальный синтез через Персону / Тень / Синтез.
        Возвращает (synthesis, updated_tensor, retry_needed).
        """
        synthesis, d_persona, s_shadow, retry = self._call_janus(
            task            = tensor.task,
            triad_artifacts = all_artifacts,
            k_jera          = tensor.k_jera,
        )
        updated = CognitiveTensor(
            task        = tensor.task,
            anchor      = tensor.anchor,
            context     = tensor.context + f"\n[СИНТЕЗ]: {synthesis[:500]}",
            artifacts   = tensor.artifacts,
            persona     = str(d_persona),
            shadow      = str(s_shadow),
            note        = tensor.note,
            sigma       = tensor.sigma,
            k_jera      = tensor.k_jera,
            entropy     = tensor.entropy,
            shock_count = tensor.shock_count,
        )
        return synthesis, updated, retry

    # ── Переход ноты ─────────────────────────────────────────────────────────

    def next_note(
        self,
        current:  int,
        sigma:    float,
        stasis:   bool,
        провал:   int | None = None,
    ) -> int:
        """
        Определяет следующую ноту по состоянию SOC.
        Приоритет: FAIL_1 > FAIL_2 > нормальный переход.
        """
        if stasis or sigma < SIGMA_LOW:
            return int(Note.FAIL_1)
        if sigma > SIGMA_HIGH:
            return int(Note.FAIL_2)
        if провал in (8, 9):
            return провал
        return _TRANSITIONS.get(current, 1)

    # ── Инициализация тензора из conduct() ───────────────────────────────────

    @staticmethod
    def build_tensor(
        task:    str,
        anchor:  str,
        context: str,
        note:    int,
        sigma:   float,
        k_jera:  float,
    ) -> CognitiveTensor:
        return CognitiveTensor(
            task    = task,
            anchor  = anchor,
            context = context,
            note    = note,
            sigma   = sigma,
            k_jera  = k_jera,
            entropy = _shannon_entropy(context.split("\n")),
        )
