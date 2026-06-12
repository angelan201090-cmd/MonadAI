"""
v51-A — Persistent OPEN_INQUIRY Store (Monada-Hardcore / MirAI).

Долгоживущий aggregate root для исследовательских вопросов. Консервативная
надстройка НАД тактом: семантика коллапса НЕ меняется (это v51-B+). Здесь только:
durable-хранилище, матчинг conceptual/introspection-вопросов к инквайри,
накопление ССЫЛОК (lessons/archetypes/glyphs/evidence-счётчики) и реактивация
как наблюдательный контекст.

Инварианты безопасности (v49-F/v50-G сохраняются):
  • Инквайри НЕ обладает authority: не создаёт истину, память, действия, личность.
  • Реактивация инжектится ТОЛЬКО как observational shared_ctx, НИКОГДА в
    BASH_FACTS и НИКОГДА не авторизует bash/действие.
  • Сырьё (артефакты/промпты/bash-вывод) НЕ хранится — только дистиллят и счётчики.

Эмбеддинги: по умолчанию детерминированный лексический fallback (offline,
restart-stable, без зависимости от NPU). Реальный podsoznanie_daemon._embed —
опциональный embed_fn; в v51-A по умолчанию ВЫКЛ, чтобы не смешивать вектора
разной размерности при флапе сервиса.
"""

import os
import re
import json
import math
import time
import hashlib

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
INQUIRY_STORE_PATH = os.path.join(MONADA_ROOT, "inquiry_store.json")
STORE_VERSION = "v51-A"

EMBED_DIM = 256

# ── Пороги матчинга (нач. калибровка v51-A) ───────────────────────────────────
JOIN_COS    = 0.85   # JOIN если cosine ≥ И margin ко 2-му ≥ JOIN_MARGIN
JOIN_MARGIN = 0.07
NEW_COS     = 0.60   # ниже — точно новая инквайри
RADIUS_CAP  = 0.40   # макс. допустимый дрейф члена (1-cos): структурный антиблоб
ALPHA       = 0.35   # якорь центроида: centroid = α·seed + (1-α)·mean(members)
MAX_DEPTH   = 2      # parent→child; глубже не уходим (Case C/D)

# Режимы, для которых заводим инквайри. Остальное (diagnostic/forensic/action/
# default/design) — не заводим (scope v51-A).
REFLECTIVE_MODES   = {"conceptual", "introspection"}
HARD_EXCLUDE_MODES = {"diagnostic", "forensic"}

# Identity/self-кластер: шире, чем _pre_janus identity (сюда же "что такое MirAI?").
IDENTITY_SELF_PATTERNS = (
    "кто ты", "что ты такое", "кем ты являешься", "чем ты являешься",
    "кто я", "что такое mirai", "что такое monadaai",
    "ты разумен", "ты разумный", "ты осознаешь", "осознаешь себя",
    "обладаешь ли ты сознанием", "ты обладаешь сознанием", "ты сознание",
    "ты живой", "ты живая", "ты личность", "ты программа", "ты система",
    "ты ии", "ты ai", "твоя природа", "твоя сущность",
)
CONCEPTUAL_PATTERNS = (
    "что такое", "как работает", "как устроен", "что значит", "что есть",
    "объясни", "расскажи", "почему", "зачем", "в чем смысл", "в чём смысл",
)
# Действие/диагностика — жёстко исключаем.
ACTION_PATTERNS = (
    "проверь", "проверить", "free -h", "ss -tlnp", "статус портов",
    "перезапусти", "запусти", "удали", "очисти", "выполни команду",
    "создай", "создать", "напиши скрипт", "напиши код", "скачай", "установи",
    "измени", "изменить", "отредактируй", "сохрани", "отправь", "перемести",
    "скопируй", " ram", "порт", "диагностика",
)

# Стоп-слова снимают вопросный каркас, чтобы лексический вектор нёс смысловые
# существительные ("памят", "созна"). Множество стемов выводится через _stem,
# чтобы оставаться согласованным со стеммингом контента (а не задаваться вручную).
_STOPWORDS_FULL = {
    "что", "такое", "как", "это", "почему", "зачем", "объясни", "объясните",
    "расскажи", "работает", "устроена", "устроено", "устроен", "является",
    "есть", "кто", "чем", "какой", "какова", "значит", "смысл",
    "представляет", "собой",
    "ты", "вы", "мне", "меня", "тебя", "для", "при", "про", "над", "под",
    "может", "или", "the", "what", "how", "why", "does",
}


# ── Текстовые утилиты ─────────────────────────────────────────────────────────
def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().replace("ё", "е")).strip()


def _stem(tok: str) -> str:
    """Псевдо-стем: обрезка до 5 символов (память/памяти/памятью→памят)."""
    return tok[:5]


# Стемы стоп-слов — через тот же _stem, чтобы фильтрация совпадала со стеммингом.
_STOPSTEMS = {_stem(w) for w in _STOPWORDS_FULL}


def _content_stems(text: str) -> list:
    raw = re.findall(r"[a-zа-я0-9]{3,}", _norm(text))
    return [s for s in (_stem(t) for t in raw) if s not in _STOPSTEMS]


def _l2norm(vec: list) -> list:
    n = math.sqrt(sum(x * x for x in vec))
    return [x / n for x in vec] if n else vec


def _cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    s = sum(p * q for p, q in zip(a, b))
    na = math.sqrt(sum(p * p for p in a))
    nb = math.sqrt(sum(q * q for q in b))
    return s / (na * nb) if na and nb else 0.0


def _has_any(low: str, patterns) -> bool:
    return any(p in low for p in patterns)


def identity_self_match(text) -> bool:
    return _has_any(_norm(text), IDENTITY_SELF_PATTERNS)


def derive_mode(text) -> str:
    """Грубый локальный режим, когда _pre_janus frame недоступен. Не заменяет
    _pre_janus_frame — только gate инквайри."""
    low = _norm(text)
    if _has_any(low, ACTION_PATTERNS):
        return "diagnostic"
    if identity_self_match(low):
        return "introspection"
    if _has_any(low, CONCEPTUAL_PATTERNS):
        return "conceptual"
    return "default"


def classify_archetype(text, mode, frame_archetype):
    """dominant_archetype если вопрос eligible для инквайри, иначе None.
    eligible = mode ∈ REFLECTIVE, И НЕ diagnostic/forensic/action."""
    low = _norm(text)
    mode = (mode or "").strip().lower()
    id_self = identity_self_match(low)
    if mode in HARD_EXCLUDE_MODES or _has_any(low, ACTION_PATTERNS):
        return None
    if mode not in REFLECTIVE_MODES:
        return None
    return "Identity" if id_self else str(frame_archetype or "Concept")


# ── Хранилище ─────────────────────────────────────────────────────────────────
class InquiryStore:
    def __init__(self, path: str = INQUIRY_STORE_PATH, embed_fn=None,
                 dim: int = EMBED_DIM):
        self.path = path
        self._embed_fn = embed_fn      # опц. реальный эмбеддер (list[float] | None)
        self.dim = dim
        self.data = self._load()

    # ── persistence (robust + atomic) ────────────────────────────────────────
    def _empty(self) -> dict:
        return {"version": STORE_VERSION, "inquiries": {}}

    def _valid_record(self, key, rec) -> bool:
        if not isinstance(key, str) or not isinstance(rec, dict):
            return False
        if rec.get("id") != key or rec.get("status") not in ("OPEN", "DORMANT", "CLOSED"):
            return False
        for name in ("seed_emb", "centroid_vec", "members_mean"):
            vec = rec.get(name)
            if not isinstance(vec, list) or len(vec) != self.dim:
                return False
            if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vec):
                return False
        return isinstance(rec.get("children", []), list)

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return self._empty()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict) or not isinstance(d.get("inquiries"), dict):
                raise ValueError("schema")
            if any(not self._valid_record(k, v)
                   for k, v in d["inquiries"].items()):
                raise ValueError("record schema")
            return d
        except Exception as e:
            # malformed → safe fallback (НЕ перезаписываем файл здесь — чтобы не
            # терять данные молча; перезапишем только при следующей валидной записи).
            try:
                print(f"[INQUIRY] store malformed, using empty fallback: {e}")
            except Exception:
                pass
            return self._empty()

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as e:
            try:
                print(f"[INQUIRY] save failed: {e}")
            except Exception:
                pass

    # ── embeddings ───────────────────────────────────────────────────────────
    def embed(self, text) -> list:
        """Всегда возвращает нормированный вектор фикс. размерности. Реальный
        эмбеддер используется только если явно подан и вернул вектор нужной длины."""
        if self._embed_fn is not None:
            try:
                v = self._embed_fn(text)
                if isinstance(v, list) and v and len(v) == self.dim:
                    return _l2norm([float(x) for x in v])
            except Exception:
                pass
        return self._lexical_embed(text)

    def _lexical_embed(self, text) -> list:
        vec = [0.0] * self.dim
        for s in _content_stems(text):
            h = int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[h] += 1.0
        return _l2norm(vec)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _inquiries(self) -> dict:
        return self.data.setdefault("inquiries", {})

    def _active(self) -> list:
        return [r for r in self._inquiries().values()
                if r.get("status") in ("OPEN", "DORMANT")]

    def _new_id(self, seed: str, cycle: int) -> str:
        base = hashlib.sha1(
            f"{seed}|{cycle}|{len(self._inquiries())}|{time.time()}".encode("utf-8")
        ).hexdigest()[:8]
        iid = f"INQ_{base}"
        while iid in self._inquiries():
            base = hashlib.sha1((iid + "x").encode()).hexdigest()[:8]
            iid = f"INQ_{base}"
        return iid

    def _create(self, seed_question, emb, archetype, cycle, parent_id=None) -> dict:
        iid = self._new_id(seed_question, cycle)
        rec = {
            "id": iid,
            "question_key": archetype,
            "status": "OPEN",
            "created_cycle": int(cycle),
            "last_touch_cycle": int(cycle),
            "touches": 0,
            "parent_id": parent_id,
            "children": [],
            "seed_emb": emb,
            "centroid_vec": list(emb),
            "members_mean": list(emb),
            "member_count": 1,
            "radius": 0.0,
            "dominant_archetype": archetype,
            "glyph": "",
            "lesson_ids": [],
            "archetypes": [],
            "glyphs": [],
            "evidence_for": 0,
            "evidence_against": 0,
            "unverified": 0,
            "closure_score": 0.0,
        }
        self._inquiries()[iid] = rec
        if parent_id and parent_id in self._inquiries():
            kids = self._inquiries()[parent_id].setdefault("children", [])
            if iid not in kids:
                kids.append(iid)
        return rec

    def _root_for(self, rec: dict) -> dict:
        pid = rec.get("parent_id")
        return self._inquiries()[pid] if pid and pid in self._inquiries() else rec

    def _fold_member(self, rec: dict, emb: list) -> None:
        """Вливает член в центроид: centroid = α·seed + (1-α)·mean(members),
        с якорем к seed. radius обновляется консервативно."""
        cnt = int(rec.get("member_count", 1)) + 1
        mean = rec.get("members_mean") or list(rec.get("seed_emb", emb))
        mean = [m + (e - m) / cnt for m, e in zip(mean, emb)]
        seed = rec.get("seed_emb") or mean
        rec["members_mean"] = mean
        rec["member_count"] = cnt
        rec["centroid_vec"] = _l2norm(
            [ALPHA * s + (1.0 - ALPHA) * m for s, m in zip(seed, mean)]
        )
        rec["radius"] = round(
            max(float(rec.get("radius", 0.0)),
                1.0 - _cosine(rec["centroid_vec"], emb)), 4)

    def _attach_child_capped(self, raw_text, emb, archetype, cycle, anchor):
        """Создаёт ребёнка с глубиной ≤ MAX_DEPTH: родитель ребёнка — всегда КОРЕНЬ.
        Если anchor сам ребёнок — крепим sibling к его корню (не внук)."""
        root = self._root_for(anchor)
        rec = self._create(raw_text, emb, archetype, cycle, parent_id=root["id"])
        self._save()
        return ("CHILD", rec)

    # ── matching ─────────────────────────────────────────────────────────────
    def match(self, raw_text, mode=None, frame_archetype=None, cycle=0):
        """(decision, inquiry|None). Создаёт/присоединяет и ПЕРСИСТИТ.
        decision ∈ {SKIP, NEW, JOIN, CHILD}. inquiry None только при SKIP."""
        archetype = classify_archetype(raw_text, mode, frame_archetype)
        if archetype is None:
            return ("SKIP", None)
        emb = self.embed(raw_text)
        if archetype == "Identity":
            return self._match_identity(raw_text, emb, archetype, cycle)
        return self._match_semantic(raw_text, emb, archetype, cycle)

    def _match_identity(self, raw_text, emb, archetype, cycle):
        roots = [r for r in self._active()
                 if r.get("dominant_archetype") == "Identity" and not r.get("parent_id")]
        if not roots:
            rec = self._create(raw_text, emb, archetype, cycle)
            self._save()
            return ("NEW", rec)
        root = max(roots, key=lambda r: _cosine(emb, r.get("centroid_vec", [])))
        if _cosine(emb, root.get("centroid_vec", [])) >= JOIN_COS:
            self._fold_member(root, emb)
            self._save()
            return ("JOIN", root)
        # та же identity-природа, иная формулировка → специализация (ребёнок)
        return self._attach_child_capped(raw_text, emb, archetype, cycle, root)

    def _match_semantic(self, raw_text, emb, archetype, cycle):
        scored = sorted(
            ((_cosine(emb, r.get("centroid_vec", [])), r) for r in self._active()),
            key=lambda x: -x[0])
        best_sim, best = (scored[0] if scored else (0.0, None))
        second_sim = scored[1][0] if len(scored) > 1 else 0.0

        if best is None or best_sim < NEW_COS:
            rec = self._create(raw_text, emb, archetype, cycle)
            self._save()
            return ("NEW", rec)

        if best_sim >= JOIN_COS and (best_sim - second_sim) >= JOIN_MARGIN \
                and (1.0 - best_sim) <= RADIUS_CAP:
            self._fold_member(best, emb)
            self._save()
            return ("JOIN", best)

        # AMBIGUOUS-полоса: тот же архетип → ребёнок; иначе новая sibling-инквайри.
        if best.get("dominant_archetype") == archetype:
            return self._attach_child_capped(raw_text, emb, archetype, cycle, best)
        rec = self._create(raw_text, emb, archetype, cycle)
        self._save()
        return ("NEW", rec)

    # ── reactivation (observational only) ────────────────────────────────────
    def reactivation_context(self, rec) -> str:
        """Компактный наблюдательный блок для shared_ctx. Пусто, если у инквайри
        ещё нет накопленного знания (нечего реактивировать)."""
        if not rec:
            return ""
        if not (int(rec.get("touches", 0)) > 0 or rec.get("glyph")
                or rec.get("lesson_ids")
                or rec.get("archetypes")):
            return ""
        lines = [
            "[OPEN_INQUIRY_CONTEXT observational_only]",
            f"inquiry: {rec.get('id')} | status: {rec.get('status')} "
            f"| touches: {int(rec.get('touches', 0))} "
            f"| archetype: {rec.get('dominant_archetype')}",
        ]
        if rec.get("glyph"):
            lines.append(f"glyph: {rec.get('glyph')}")
        lessons = [str(x)[:120] for x in (rec.get("lesson_ids") or [])][:3]
        if lessons:
            lines.append("lessons: " + "; ".join(lessons))
        arche = [str(x) for x in (rec.get("archetypes") or [])][:4]
        if arche:
            lines.append("archetypes: " + ", ".join(arche))
        lines.append(
            "note: observational context only; no authority to assert truth, "
            "create memory, execute actions, or change identity.")
        return "\n".join(lines)

    # ── accumulation (refs + counts only, no raw artifacts) ──────────────────
    @staticmethod
    def _merge_capped(dst: list, items, cap: int = 12, maxlen: int = 200) -> None:
        for it in (items or []):
            s = str(it)[:maxlen].strip()
            if s and s not in dst:
                dst.append(s)
        if len(dst) > cap:
            del dst[: len(dst) - cap]

    def accumulate(self, inquiry, *, final_answer="", last_thought_state=None,
                   evidence=None, cycle=0) -> None:
        """Конец такта: touches, best_answer, ссылки lessons/archetypes/glyphs,
        evidence-счётчики. Сырьё не хранится."""
        if not inquiry:
            return
        iid = inquiry.get("id") if isinstance(inquiry, dict) else str(inquiry)
        rec = self._inquiries().get(iid)
        if rec is None:
            return

        rec["touches"] = int(rec.get("touches", 0)) + 1
        rec["last_touch_cycle"] = int(cycle)

        lts = last_thought_state if isinstance(last_thought_state, dict) else {}
        lesson_ids = [
            hashlib.sha256(str(x).encode("utf-8")).hexdigest()[:16]
            for x in (lts.get("lessons") or [])
        ]
        self._merge_capped(rec.setdefault("lesson_ids", []), lesson_ids, maxlen=16)
        archetype_ids = []
        for item in (lts.get("archetypes") or []):
            value = item.get("name", "") if isinstance(item, dict) else item
            value = str(value).strip()
            if re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9 _-]{1,64}", value):
                archetype_ids.append(
                    hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
                )
        self._merge_capped(
            rec.setdefault("archetypes", []), archetype_ids, maxlen=16)
        glyphs = []
        for item in (lts.get("glyphs") or []):
            value = item.get("glyph", "") if isinstance(item, dict) else item
            value = str(value).strip()
            if re.fullmatch(r"[ᚠ-ᛯ̄]{1,8}", value):
                glyphs.append(value)
        self._merge_capped(rec.setdefault("glyphs", []), glyphs,
                           cap=24, maxlen=8)
        if rec.get("glyphs"):
            rec["glyph"] = rec["glyphs"][-1]

        ev = evidence if isinstance(evidence, dict) else {}
        rec["evidence_for"] = int(rec.get("evidence_for", 0)) + int(ev.get("confirmed", 0))
        rec["evidence_against"] = (int(rec.get("evidence_against", 0))
                                   + int(ev.get("refuted", 0)) + int(ev.get("contradiction", 0)))
        rec["unverified"] = int(rec.get("unverified", 0)) + int(ev.get("unverified", 0))
        self._save()


# ── Фасад для conductor (свежий стор на такт → процесс-безопасно) ─────────────
INQUIRY_STORE_ENABLED = True


def _frame_cycle(frame) -> int:
    if isinstance(frame, dict):
        try:
            return int(frame.get("cycle", 0) or 0)
        except Exception:
            return 0
    return 0


def observe(raw_text, frame=None, cycle=0, path: str = INQUIRY_STORE_PATH):
    """Hook A+B: матчит/создаёт инквайри → (inquiry|None, reactivation_str).
    Никогда не бросает. reactivation_str пуст, если нечего реактивировать."""
    if not INQUIRY_STORE_ENABLED:
        return (None, "")
    try:
        store = InquiryStore(path)
        mode = frame.get("mode") if isinstance(frame, dict) else None
        arche = frame.get("archetype") if isinstance(frame, dict) else None
        if mode is None:
            mode = derive_mode(raw_text)
        _decision, inq = store.match(raw_text, mode=mode, frame_archetype=arche,
                                     cycle=cycle or _frame_cycle(frame))
        if inq is None:
            return (None, "")
        return (inq, store.reactivation_context(inq))
    except Exception as e:
        try:
            print(f"[INQUIRY] observe failed: {e}")
        except Exception:
            pass
        return (None, "")


def accumulate(inquiry, *, final_answer="", last_thought_state=None, evidence=None,
               cycle=0, path: str = INQUIRY_STORE_PATH):
    """Hook C: конец такта. Никогда не бросает."""
    if not INQUIRY_STORE_ENABLED or not inquiry:
        return
    try:
        InquiryStore(path).accumulate(
            inquiry, final_answer=final_answer, last_thought_state=last_thought_state,
            evidence=evidence, cycle=cycle)
    except Exception as e:
        try:
            print(f"[INQUIRY] accumulate failed: {e}")
        except Exception:
            pass
