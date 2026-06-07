#!/usr/bin/env python3
"""
BNF/GBNF-грамматики для llama.cpp.
Передаются в параметре "grammar" API-запроса для принудительного
структурирования вывода модели на уровне декодинга (token-constrained sampling).

v35.0 ГЕПТАРХИЯ: все узлы — GPU llama-server, grammar поддерживается везде.
DEVA_GBNF   → Триада  (Head=8081, Heart=8082, Body=8083)
SHADOW_GBNF → Тень    (8085)
PERSONA_GBNF → Персона (8084)
"""

# ── Дэва: артефакт + руна + действие ─────────────────────────────────────────
# {"artifact": "...", "rune": "ᛃ", "action": "none|bash"}
DEVA_GBNF = r"""
root    ::= "{" ws
            dq "artifact" dq ws ":" ws string ws "," ws
            dq "rune"     dq ws ":" ws rune-val ws "," ws
            dq "action"   dq ws ":" ws action-val ws
            "}"
string  ::= dq ( [^"\\] | "\\" [^\n] )* dq
rune-val ::= dq rune-char dq
rune-char ::= [ᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛏᚢᚦᛊ]
action-val ::= dq ( "none" | "bash" ) dq
dq      ::= "\""
ws      ::= [ \t\n]*
"""

# ── Тень: структурированный вердикт ──────────────────────────────────────────
# {"verdict": "APPROVED|VETO|FATAL_VETO", "reason": "...", "severity": 0.0}
SHADOW_GBNF = r"""
root     ::= "{" ws
             dq "verdict"  dq ws ":" ws verdict-val  ws "," ws
             dq "reason"   dq ws ":" ws string        ws "," ws
             dq "severity" dq ws ":" ws float-val     ws
             "}"
verdict-val ::= dq ( "APPROVED" | "VETO" | "FATAL_VETO" ) dq
string      ::= dq ( [^"\\] | "\\" [^\n] )* dq
float-val   ::= [0-9] ( "." [0-9]+ )?
dq          ::= "\""
ws          ::= [ \t\n]*
"""

# ── Персона: сборка артефактов ─────────────────────────────────────────────────
# {"assembly": "...", "quality": 0.0, "dominant_theme": "..."}
PERSONA_GBNF = r"""
root   ::= "{" ws
           dq "assembly"       dq ws ":" ws string ws "," ws
           dq "quality"        dq ws ":" ws float-val ws "," ws
           dq "dominant_theme" dq ws ":" ws string ws
           "}"
string    ::= dq ( [^"\\] | "\\" [^\n] )* dq
float-val ::= [0-9] ( "." [0-9]+ )?
dq        ::= "\""
ws        ::= [ \t\n]*
"""


def response_format_json() -> dict:
    """Минимальный response_format для json_object (OpenAI-compatible)."""
    return {"type": "json_object"}
