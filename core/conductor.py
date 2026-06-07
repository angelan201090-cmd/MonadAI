"""
core/conductor.py — FSM-вход Монады v35.0 ГЕПТАРХИЯ

Публичный API: Conductor.tact() / Conductor.run()
Внутренняя логика живёт в janus_conductor.py.
Этапы одного такта:
  Boundary → Triada (спираль 6 вызовов) → Dyad (3 вызова) → Crystallize
"""
from core.janus_conductor import conduct as _conduct


class Conductor:
    def tact(self, raw_text: str) -> str:
        return _conduct(raw_text)

    def run(self, raw_text: str) -> str:
        result = self.tact(raw_text)
        while isinstance(result, str) and result.startswith("__CONTINUE__:"):
            result = self.tact(result[len("__CONTINUE__:"):])
        return result or ""


def conduct(raw_text: str) -> str:
    return _conduct(raw_text)
