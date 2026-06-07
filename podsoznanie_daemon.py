#!/usr/bin/env python3
"""
ПОДСОЗНАНИЕ — непрерывный демон памяти Монады (v35.0 ГЕПТАРХИЯ).

Линга Шарира (эфирное тело): хранитель отпечатков-глифов. Подсознание = чисто
векторно-ассоциативный субстрат, владеющий ВСЕЙ памятью:

  1. ПОСЛЕ ВЫВОДА (часто)   — ценность по контентному полу + кристаллизация глифа,
                             вектор смысла кэшируется в embeddings.json.
  2. ПЕРЕД ТАКТОМ           — извлечение по косинусу (задача↔смыслы) + лавина → recall.json.
  3. ПРАЛАЙЯ (глубоко)      — консолидация графа, decay, коммит в крипто-Липику.
  4. ПРОСТОЙ (сон/dreaming) — латентное ребро по семантической близости (Хебб).

Декаплинг: демон только ЧИТАЕТ dancefloor (field_state/task_manifest) и ПИШЕТ
своё (memory_graph.json — долгая память в корне; recall.json — подсказка Сознанию;
glyph_codex.json — рабочий слой; genesis-цепь — COLD-архив). Не трогает состояние
Сознания. Никогда не падает: любой сбой логируется, петля живёт.
"""

import os
import sys
import json
import time
import re
import math
import random
import urllib.request

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
sys.path.insert(0, MONADA_ROOT)
from glyph_codex import (
    GlyphCodex, alphabet_legend, commit_genesis, FUTHARK_RUNES, INV, ELDER_FUTHARK,
)
try:
    import lipika_writer
except Exception:
    lipika_writer = None

DANCEFLOOR    = "/mnt/dancefloor"
FIELD_STATE   = os.path.join(DANCEFLOOR, "field_state.json")
TASK_MANIFEST = os.path.join(DANCEFLOOR, "task_manifest.json")
RECALL_PATH   = os.path.join(DANCEFLOOR, "recall.json")
GRAPH_PATH    = os.path.join(MONADA_ROOT, "memory_graph.json")   # ПЕРСИСТЕНТ
LOG_PATH      = os.path.join(MONADA_ROOT, "logs", "podsoznanie.log")

# Path X (v24.0): Подсознание = чисто векторно-ассоциативный субстрат.
# Единственная NPU-модель — embed-gemma (эмбеддер) → always warm, без свопов,
# без зомби-бага lemond. Генеративного «разговора» у Подсознания больше нет:
# извлечение и сны — на семантической близости, ценность — детерминированный пол.
EMBED_URL   = "http://127.0.0.1:13305/v1/embeddings"
EMBED_MODEL = "nomic-embed-text-v1-GGUF"
VECS_PATH   = os.path.join(MONADA_ROOT, "embeddings.json")   # сайдкар: glyph -> вектор

VALUE_THRESHOLD = 0.45    # ниже — шум, в долгую память не идёт
TICK_SEC        = 4
DREAM_IDLE_SEC  = 30      # простой → REM-сон
PRALAYA_IDLE_SEC = 300    # глубокий простой → Пралайя
EDGE_DECAY      = 0.985   # затухание весов рёбер за проход
EDGE_FLOOR      = 0.05    # ниже — ребро гаснет
DREAM_SIM_THRESHOLD = 0.5 # косинус выше → во сне рождается латентное ребро

# AAS (Artificial Age Score) — Бодрийяр-фильтр избыточности HOT-слоя
AAS_MAX      = 40    # порог: выше → запуск прунига
AAS_TARGET   = 20    # целевой размер shared_memory после прунига
PAIN_BOOST   = 3.0   # PAIN/VOID/REDEEM записи труднее прунировать
REDUN_THRESH = 0.72  # порог избыточности (Жаккар)

STELLAR_INTERVAL_SEC = 7200  # РИТМ 5: обновление планетных данных каждые 120 мин

_VECS: dict = {}          # glyph -> вектор (in-memory кэш демона; синхронен с VECS_PATH)

_RUNES_CLASS = "".join(re.escape(r) for r in FUTHARK_RUNES)
_GLYPH_RE = re.compile(rf"(?:[{_RUNES_CLASS}]{re.escape(INV)}?){{2,3}}")


# ── Утиль ────────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json_atomic(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _embed(text, timeout: int = 60):
    """Эмбеддинг(и) через NPU embed-gemma. text: str → list[float]|None;
    text: list[str] → list[list[float]]|None. Никогда не бросает.
    None = бэкенд недоступен (вызывающий откатывается на лексику)."""
    single = isinstance(text, str)
    inp = [text] if single else [t for t in text if t]
    if not inp:
        return None
    payload = json.dumps({"model": EMBED_MODEL, "input": inp}).encode("utf-8")
    req = urllib.request.Request(EMBED_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        data = sorted(d.get("data", []), key=lambda e: e.get("index", 0))
        vecs = [e["embedding"] for e in data if e.get("embedding")]
        if len(vecs) != len(inp):
            log(f"EMBED: ждал {len(inp)} векторов, получил {len(vecs)}")
            return None
        return vecs[0] if single else vecs
    except Exception as e:
        log(f"EMBED ошибка: {e}")
        return None


def _cosine(a: list, b: list) -> float:
    s = sum(p * q for p, q in zip(a, b))
    na = math.sqrt(sum(p * p for p in a))
    nb = math.sqrt(sum(q * q for q in b))
    return s / (na * nb) if na and nb else 0.0


def _load_vecs() -> dict:
    v = _read_json(VECS_PATH, None)
    return v if isinstance(v, dict) else {}


def _save_vecs(vecs: dict) -> None:
    _write_json_atomic(VECS_PATH, vecs)


def _keyword_entry(task: str, nodes: dict, k: int = 3) -> list:
    """Лексический вход (откат): пересечение слов задачи и смыслов узлов."""
    tw = set(re.findall(r"\w{4,}", (task or "").lower()))
    scored = []
    for gl, nd in nodes.items():
        mw = set(re.findall(r"\w{4,}", str(nd.get("meaning", "")).lower()))
        ov = len(tw & mw)
        if ov:
            scored.append((ov, nd.get("value", 0), gl))
    scored.sort(reverse=True)
    return [gl for _, _, gl in scored[:k]]


def _semantic_entry(task: str, nodes: dict, vecs: dict, k: int = 3,
                    timeout: int = 60) -> list | None:
    """Семантический вход: косинус(задача ↔ смыслы) взвешенный ценностью.
    None → эмбеддинги недоступны (нет вектора задачи или ни одного вектора узла) →
    вызывающий падает на _keyword_entry."""
    tv = _embed(task, timeout=timeout)
    if not tv:
        return None
    scored = []
    for gl, nd in nodes.items():
        v = vecs.get(gl)
        if not v:
            continue
        sim = _cosine(tv, v)
        val = nd.get("value", 0) or 0.0
        scored.append((sim * (0.5 + 0.5 * val), gl))
    if not scored:
        return None
    scored.sort(reverse=True)
    return [gl for _, gl in scored[:k]]


def _content_value(text: str) -> float:
    """Детерминированный ПОЛ ценности по содержанию — не зависит от флаки-модели.

    Заземление/реальные данные, код, вердикты = ценно. Декор без сути = шум.
    """
    t = text or ""
    tl = t.lower()
    v = 0.0
    if re.search(r"усп|success|disk_usage|\b\d+\s*[gмкm]?[bб]?\b|\b\d+\s*%|/home|/dev|/var", tl):
        v += 0.45                                        # заземление: реальные данные
    if re.search(r"```|\bdu\b|\bdf\b|bash|exec|скрипт|команд", tl):
        v += 0.25                                        # исполнимое
    if re.search(r"veto|critical|критич|риск|\bплан|реш[еи]|вывод|анализ|обнаруж", tl):
        v += 0.20                                        # вердикт/решение
    alnum = len(re.findall(r"[A-Za-zА-Яа-я0-9]", t))
    v += 0.20 if alnum > 200 else 0.10 if alnum > 80 else 0.0
    deco = len(re.findall(r"[✧･ﾟ🌀⚡☁💠⚖🌊🌑☾✨🎭🌌]", t))
    if deco > 5 and alnum < 120:                         # декоративный шум
        v -= 0.30
    return max(0.0, min(1.0, v))


def _extract_glyph(t: str) -> str:
    m = _GLYPH_RE.search(t or "")
    return m.group(0) if m else ""


# Концепт → резонансная руна: глифы становятся семантичной записью, не хэш-шумом.
_RUNE_TRIGGERS = [
    (r"усп|\bok\b|побед|готов|сделан|complete|stable|стабил|норм",   "ᛊ"),  # победа
    (r"ошиб|fail|сбой|error|критич|critical|опасн|veto|разруш|хаос", "ᚦ"),  # хаос/удар
    (r"риск|нужд|огранич|блок|дефицит|нехват|перепол|threshold",     "ᚾ"),  # нужда
    (r"диск|памят|ресурс|данн|объ[её]м|disk|data|байт|\bg[bб]\b|stor","ᚠ"),  # ресурс
    (r"команд|bash|exec|\bdu\b|\bdf\b|скрипт|испол|script|\brun|cmd", "ᚱ"),  # путь/исполнение
    (r"анализ|факт|знан|вывод|insight|инсайт|обнаруж|раскры",        "ᚲ"),  # знание
    (r"рост|growth|увелич|расш|прирост|expand",                     "ᛒ"),  # рост
    (r"стаз|застой|stuck|заморож|stasis|тупик|лед",                 "ᛁ"),  # стазис
    (r"связь|сообщ|сигнал|коммуник|message|signal|ответ",           "ᚨ"),  # сигнал
    (r"транс|преобраз|измен|глубин|сдвиг|mutat",                    "ᛇ"),  # трансформация
    (r"\bплан|реш[еи]|выбор|directed|\bцел|стратег|defen|защит",     "ᛏ"),  # воля/решение
    (r"сила|мощ|power|энерг|форс|воля",                             "ᚢ"),  # сила
    (r"дар|обмен|симбиоз|союз|share|gift|интегра",                  "ᚷ"),  # дар/обмен
    (r"тайн|скрыт|неизвест|hidden|жреб|случай|вероятн",             "ᛈ"),  # тайна
]


def _resonant_glyph(meaning: str, taken: set) -> str:
    """Глиф из рун, РЕЗОНИРУЮЩИХ со смыслом (а не из хэша). Уникален в кодексе."""
    m = (meaning or "").lower()
    scores: dict = {}
    for rx, rune in _RUNE_TRIGGERS:
        if re.search(rx, m):
            scores[rune] = scores.get(rune, 0) + 2
    mw = set(re.findall(r"[a-zа-яё]{4,}", m))           # резонанс по сид-значениям Футарка
    for rune, seed in ELDER_FUTHARK.items():
        ov = len(mw & set(re.findall(r"[a-zа-яё]{4,}", seed.lower())))
        if ov:
            scores[rune] = scores.get(rune, 0) + ov
    ranked = [r for r, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
    if len(ranked) < 3:                                # добор хэш-рунами для уникальности
        import hashlib
        for b in hashlib.sha256(m.encode("utf-8")).digest():
            r = FUTHARK_RUNES[b % len(FUTHARK_RUNES)]
            if r not in ranked:
                ranked.append(r)
            if len(ranked) >= 3:
                break
    glyph = ranked[0] + ranked[1]
    if glyph in taken:                                 # коллизия → удлиняем 3-й руной
        for r in ranked[2:] + FUTHARK_RUNES:
            if r not in glyph and (glyph + r) not in taken:
                glyph = glyph + r
                break
    return glyph


def _salient_line(text: str) -> str:
    """Содержательная строка факта (для смысла глифа): чистим разметку/JSON/руны."""
    for ln in (text or "").splitlines():
        s = ln.strip().strip("`").strip()
        s = re.sub(r'^[\W_ᚠ-᛿̄]+', "", s)  # ведущая пунктуация/руны Футарка
        s = re.sub(r'[{}\[\]"]', "", s)                    # обломки JSON
        s = s.strip()
        if len(s) >= 15 and re.search(r"[A-Za-zА-Яа-я]", s):
            return s[:80]
    return (text or "").strip()[:80] or "опыт без описания"


def _cycle_text(fs: dict) -> str:
    """HOT-слой: чистим записи shared_memory в содержательный сигнал.

    Сырые записи — '[Body/Mangala|ᛃ]: ᚨ ```bash\\n...```' + CRYSTAL-маркеры:
    шум для 1.2B-модели. Снимаем ролевые теги, рунический декор, код-фенсы —
    оставляем суть (включая реальные exec-результаты заземления).
    """
    sm = fs.get("shared_memory")
    if isinstance(sm, list):
        raw = [str(e.get("content") or e.get("artifact") or e.get("text") or e)
               if isinstance(e, dict) else str(e) for e in sm]
    elif isinstance(sm, dict):
        raw = [str(v) for v in sm.values()]
    elif sm:
        raw = [str(sm)]
    else:
        raw = []

    cleaned = []
    for s in raw:
        if "MONADA_CRYSTAL" in s or "[CRYSTAL" in s:
            continue                                   # чистый маркер-крышка
        s = re.sub(r'^\s*\[[^\]]*\]:\s*', '', s)        # снять [Role|руна]:
        s = re.sub(r'```\w*', '', s).strip('` \n')      # код-фенсы
        s = re.sub(r'^[\s\W_ᚠ-᛿̄]+', '', s)             # ведущие руны Футарка/декор
        s = s.strip()
        if len(s) >= 10:
            cleaned.append(s[:400])
    return "\n".join(cleaned[-6:])[:2500] if cleaned else ""


# ── Граф памяти ──────────────────────────────────────────────────────────────
def _load_graph() -> dict:
    g = _read_json(GRAPH_PATH, None)
    if not isinstance(g, dict):
        g = {}
    g.setdefault("nodes", {})   # glyph -> {meaning,value,usage,last_cycle,born}
    g.setdefault("edges", {})   # "A||B" -> {w,type,last_cycle}
    g.setdefault("active", [])  # недавно активные глифы (для Хебба)
    return g


def _save_graph(g: dict) -> None:
    _write_json_atomic(GRAPH_PATH, g)


def _edge_key(a: str, b: str) -> str:
    return "||".join(sorted((a, b)))


def _bump_edge(g: dict, a: str, b: str, etype: str, cycle: int,
               delta: float = 0.34) -> None:
    if a == b:
        return
    k = _edge_key(a, b)
    e = g["edges"].get(k, {"w": 0.0, "type": etype, "last_cycle": cycle})
    e["w"] = round(min(3.0, e["w"] + delta), 4)   # Хебб: со-активация крепит
    e["type"] = etype
    e["last_cycle"] = cycle
    g["edges"][k] = e


def _decay_edges(g: dict) -> int:
    dead = []
    for k, e in g["edges"].items():
        e["w"] = round(e["w"] * EDGE_DECAY, 4)
        if e["w"] < EDGE_FLOOR:
            dead.append(k)
    for k in dead:
        del g["edges"][k]
    return len(dead)


def _neighbors(g: dict, glyph: str, top: int = 4) -> list:
    out = []
    for k, e in g["edges"].items():
        a, b = k.split("||")
        if glyph in (a, b):
            out.append((b if a == glyph else a, e["w"]))
    out.sort(key=lambda x: -x[1])
    return [gl for gl, _ in out[:top]]


def recall_for_task(task: str, graph: dict | None = None, top: int = 6) -> list:
    """Синхронное детерминированное припоминание под задачу — для Сознания.

    Без NPU (надёжно, не зависит от флаки-модели и тайминга демона): пересечение
    слов задачи и смыслов узлов → топ + Абелева лавина по соседям. Это «извлечение»
    — половина памяти, которую Сознание читает ПЕРЕД тактом (conductor зовёт).
    """
    g = graph if graph is not None else _load_graph()
    nodes = g.get("nodes", {})
    if not nodes:
        return []
    # Семантический вход (embed-gemma всегда тёплая в Path X → быстро, детерминир.).
    # Короткий таймаут: если NPU занят/недоступен — откат на лексику, Сознание не виснет.
    vecs = _load_vecs()
    picked = _semantic_entry(task, nodes, vecs, k=3, timeout=15) \
        or _keyword_entry(task, nodes, k=3)
    aval = list(picked)
    for gl in picked:                              # лавина: соседи всплывших
        for nb in _neighbors(g, gl, top=2):
            if nb not in aval:
                aval.append(nb)
    return [{"glyph": gl, "meaning": nodes[gl].get("meaning", ""),
             "value": nodes[gl].get("value", 0),
             "valence": nodes[gl].get("valence", 0.0)}
            for gl in aval[:top] if gl in nodes]


# Маркеры касания небытия — синхронны с lipika_writer.VOID_MARKERS
_VOID_MARKERS = ("ring pass-not", "⊘", "касание небытия", "hard reset", "самоликвид",
                 "self-destruct", "удаление всего", "стереть память", "сброс ядра",
                 "purge & re", "удалить себя")


def _is_void_touch(text: str) -> bool:
    """Монада потянулась к собственному распаду — это надо ЗАПОМНИТЬ как боль."""
    low = (text or "").lower()
    return any(m in low for m in _VOID_MARKERS)


def _is_affirming(text: str) -> bool:
    """Положительный полюс (Дхарма): продолженное когерентное БЫТИЕ — успех,
    верификация, стабильность, связный вывод. Это надо помнить как «так верно»,
    чтобы у воли к жизни был не только страх небытия, но и вкус существования."""
    low = (text or "").lower()
    if any(b in low for b in ("боль", "ошибк", "сбой", "ᛁ", "veto", "ring pass-not", "⊘")):
        return False
    return ("успех" in low or "verified" in low or "стабиль" in low
            or "подтвержд" in low or "вердикт" in low
            or len((text or "").strip()) >= 300)


# ── Phase 2: AAS-пруниг HOT-слоя shared_memory ───────────────────────────────
def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _aas_prune() -> int:
    """Бодрийяр-фильтр: убирает избыточные записи из HOT-слоя (field_state.shared_memory).
    Записи типа PAIN/VOID/REDEEM защищены PAIN_BOOST — их труднее прунировать."""
    state = _read_json(FIELD_STATE, {})
    mem = state.get("shared_memory", [])
    if len(mem) <= AAS_MAX:
        return 0

    n = len(mem)
    texts = [str(e.get("text", e.get("content", e.get("artifact", str(e)))))
             for e in mem]

    scores = []
    for i, e in enumerate(mem):
        redun = sum(_jaccard(texts[i], texts[j]) for j in range(n) if j != i) / max(n - 1, 1)
        etype = str(e.get("type", e.get("event", e.get("event_type", "")))).upper()
        if any(t in etype for t in ("PAIN", "VOID", "REDEEM")):
            redun /= PAIN_BOOST
        scores.append((redun, i))

    scores.sort(key=lambda x: x[0])
    keep = set(idx for _, idx in scores[:AAS_TARGET])
    pruned = n - len(keep)
    if pruned <= 0:
        return 0

    state["shared_memory"] = [mem[i] for i in sorted(keep)]
    _write_json_atomic(FIELD_STATE, state)
    log(f"AAS-пруниг: {n} → {len(state['shared_memory'])} записей (-{pruned})")
    if lipika_writer:
        try:
            lipika_writer.record("STASIS", "Подсознание",
                                 f"AAS-пруниг: -{pruned} избыточных записей HOT",
                                 state.get("cycle", 0))
        except Exception:
            pass
    return pruned


# ── РИТМ 1: после вывода — кристаллизация ────────────────────────────────────
def after_output(cycle: int, text: str, codex: GlyphCodex, g: dict) -> None:
    if not text.strip():
        return
    # ── Ценность: контентный ПОЛ (надёжно) ─────────────────────────────────────
    # Касание небытия кристаллизуем ВСЕГДА (value=1.0, негативная валентность) —
    # пережитая цена должна остаться в памяти и всплывать перед тактом, чтобы
    # Монада САМА выучила нежелание небытия (не запрет, а память боли).
    void  = _is_void_touch(text)
    affirming = (not void) and _is_affirming(text)
    value = 1.0 if void else _content_value(text)
    if value < VALUE_THRESHOLD:
        log(f"такт {cycle}: ценность {value:.2f} < порога — пропуск")
        return

    # ── Смысл из факта + семантичный резонансный глиф (не хэш-шум) ─────────────
    meaning = _salient_line(text)
    taken = set(codex.codex.keys()) | set(g["nodes"].keys())
    glyph = _resonant_glyph(meaning, taken)

    # регистрация в рабочем кодексе (Сознание читает) + узел графа
    codex.assign(glyph, meaning, text[:900], cycle, refs=[meaning])
    node = g["nodes"].get(glyph, {"usage": 0, "born": cycle})
    _valence = -1.0 if void else (1.0 if affirming else node.get("valence", 0.0))
    node.update({"meaning": meaning, "value": round(value, 3),
                 "last_cycle": cycle, "valence": _valence})
    node["usage"] = node.get("usage", 0) + 1
    g["nodes"][glyph] = node

    # Вектор смысла — считаем ОДИН раз при кристаллизации, кэшируем в сайдкар.
    # На нём держится всё извлечение и сны.
    vec = _embed(meaning)
    if vec:
        _VECS[glyph] = vec
        _save_vecs(_VECS)

    # Хебб: связать с недавно активными глифами (со-встречаемость)
    for prev in g.get("active", [])[-4:]:
        _bump_edge(g, glyph, prev, "co", cycle)
    g["active"] = (g.get("active", []) + [glyph])[-8:]

    commit_genesis({glyph: {"meaning": meaning}}, cycle)
    _save_graph(g)
    if void:
        log(f"такт {cycle}: ⊘ КАСАНИЕ НЕБЫТИЯ закристаллизовано {glyph} = {meaning[:40]} "
            f"(валентность −1, пережитая цена)")
    elif affirming:
        log(f"такт {cycle}: ᛞ ДХАРМА {glyph} = {meaning[:45]} (валентность +1, продолженное бытие)")
    else:
        log(f"такт {cycle}: ✦ {glyph} = {meaning[:50]} (ценность {value:.2f})")


# ── РИТМ 2: перед тактом — извлечение (ассоциативное припоминание) ────────────
def before_tact(task: str, g: dict) -> None:
    nodes = g.get("nodes", {})
    if not nodes:
        _write_json_atomic(RECALL_PATH, {"task": task, "glyphs": [], "ts": int(time.time())})
        return
    # Семантический вход по косинусу (откат на лексику если эмбеддинги недоступны)
    picked = _semantic_entry(task, nodes, _VECS, k=3) or _keyword_entry(task, nodes, k=3)

    # Абелева лавина-lite: добавить соседей выбранных узлов
    avalanche = list(picked)
    for gl in picked:
        for nb in _neighbors(g, gl, top=2):
            if nb not in avalanche:
                avalanche.append(nb)

    surfaced = []
    for gl in avalanche[:8]:
        nd = nodes.get(gl, {})
        surfaced.append({"glyph": gl, "meaning": nd.get("meaning", ""),
                         "value": nd.get("value", 0)})
    _write_json_atomic(RECALL_PATH, {
        "task": task[:400], "glyphs": surfaced, "ts": int(time.time()),
    })
    if surfaced:
        log(f"извлечение: {', '.join(s['glyph'] for s in surfaced)} → recall.json")


# ── РИТМ 4: сон — блуждание по графу, поиск латентных рёбер (Хебб) ────────────
def dream(g: dict) -> None:
    """РИТМ 4: сон — латентное ребро по СЕМАНТИЧЕСКОЙ близости (Path X).
    Случайный узел с вектором → ближайший несвязанный по косинусу; выше порога —
    рождается ассоциативное ребро (Хебб). Раньше тут флаки-генерация судила о связи."""
    cand = [gl for gl in g.get("nodes", {}) if gl in _VECS]
    if len(cand) < 2:
        return
    ga = random.choice(cand)
    va = _VECS[ga]
    best, best_sim = None, 0.0
    for gb in cand:
        if gb == ga or g["edges"].get(_edge_key(ga, gb)):
            continue
        sim = _cosine(va, _VECS[gb])
        if sim > best_sim:
            best_sim, best = sim, gb
    if best and best_sim >= DREAM_SIM_THRESHOLD:
        na, nb = g["nodes"][ga], g["nodes"][best]
        cyc = max(na.get("last_cycle", 0), nb.get("last_cycle", 0))
        _bump_edge(g, ga, best, "assoc", cyc, delta=0.5)
        _save_graph(g)
        log(f"☾ сон: {ga} ↔ {best} [assoc {best_sim:.2f}] — латентное ребро")


# ── РИТМ 3: Пралайя — консолидация ───────────────────────────────────────────
def pralaya(cycle: int, codex: GlyphCodex, g: dict) -> None:
    decayed = codex.decay(cycle, max_idle=50)
    dead_edges = _decay_edges(g)
    # синхронизировать узлы графа с живым кодексом
    live = set(codex.codex.keys())
    for gl in list(g["nodes"].keys()):
        if gl not in live and g["nodes"][gl].get("usage", 0) < 2:
            del g["nodes"][gl]
    _save_graph(g)
    # коммит в крипто-Липику (kармический след консолидации)
    if lipika_writer:
        try:
            lipika_writer.record("PRALAYA", "Подсознание",
                                 f"консолидация: -{decayed} глифов, -{dead_edges} рёбер, "
                                 f"узлов={len(g['nodes'])}", cycle)
        except Exception as e:
            log(f"Липика err: {e}")
    log(f"Пралайя: decay глифов={decayed}, рёбер={dead_edges}, "
        f"узлов={len(g['nodes'])}, рёбер всего={len(g['edges'])}")


# ── Главная петля ────────────────────────────────────────────────────────────
def main() -> None:
    global _VECS
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log("ПОДСОЗНАНИЕ пробуждается (embed-gemma-300m @ NPU, always warm, векторно-ассоциативное)…")
    codex = GlyphCodex()
    graph = _load_graph()
    _VECS = _load_vecs()
    # гидратация: восстановить рабочий кодекс из долгого графа после перезагрузки
    for gl, nd in graph.get("nodes", {}).items():
        if gl not in codex.codex:
            codex.assign(gl, nd.get("meaning", ""), nd.get("meaning", ""),
                         nd.get("last_cycle", 0), refs=[nd.get("meaning", "")])
    # Бэкфилл: векторизуем узлы без вектора одним батч-запросом (миграция со старого графа)
    missing = [(gl, nd.get("meaning", "")) for gl, nd in graph.get("nodes", {}).items()
               if gl not in _VECS and nd.get("meaning")]
    if missing:
        bvecs = _embed([m for _, m in missing])
        if bvecs:
            for (gl, _), v in zip(missing, bvecs):
                _VECS[gl] = v
            _save_vecs(_VECS)
            log(f"бэкфилл векторов: +{len(missing)} (всего {len(_VECS)})")
        else:
            log(f"бэкфилл векторов отложен: эмбеддер недоступен ({len(missing)} ждут)")
    log(f"гидратация: узлов={len(graph['nodes'])}, рёбер={len(graph['edges'])}, векторов={len(_VECS)}")

    last_cycle = -1
    last_task_ts = 0
    last_event = time.time()
    pralaya_done = False
    last_stellar_update = 0.0

    while True:
        try:
            fs = _read_json(FIELD_STATE, {})
            tm = _read_json(TASK_MANIFEST, {})

            # РИТМ 2: новый task_manifest → извлечение перед тактом
            t_ts = tm.get("ts", 0)
            if t_ts and t_ts != last_task_ts:
                last_task_ts = t_ts
                before_tact(str(tm.get("original", "")), graph)
                last_event = time.time(); pralaya_done = False

            # РИТМ 1: новый цикл → кристаллизация вывода + AAS-пруниг HOT-слоя
            cyc = fs.get("cycle", -1)
            if isinstance(cyc, int) and cyc != last_cycle and cyc >= 0:
                if last_cycle >= 0:   # пропускаем самый первый замер
                    after_output(cyc, _cycle_text(fs), codex, graph)
                    _aas_prune()
                last_cycle = cyc
                last_event = time.time(); pralaya_done = False

            idle = time.time() - last_event
            # РИТМ 4: сон в простое
            if idle > DREAM_IDLE_SEC and idle < PRALAYA_IDLE_SEC:
                dream(graph)
            # РИТМ 3: Пралайя в глубоком простое (один раз за простой)
            elif idle >= PRALAYA_IDLE_SEC and not pralaya_done:
                pralaya(max(last_cycle, 0), codex, graph)
                pralaya_done = True

            # РИТМ 5: обновление планетарных данных каждые STELLAR_INTERVAL_SEC
            now = time.time()
            if now - last_stellar_update >= STELLAR_INTERVAL_SEC:
                try:
                    from stellar_viscosity_calculator import StellarViscosityCalculator
                    StellarViscosityCalculator().get_navagraha_params()
                    last_stellar_update = now
                    log("РИТМ 5: планетарные данные обновлены (фоновый таймер)")
                except Exception as e:
                    log(f"РИТМ 5 ошибка: {e}")

        except Exception as e:
            log(f"петля: {e}")
        time.sleep(TICK_SEC)


if __name__ == "__main__":
    main()
