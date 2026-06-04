import sys
import os
import re
import json
import math
import time
import datetime
import subprocess
import urllib.request
import urllib.error
from collections import Counter

sys.path.append("/home/angelan/data/Monada-Hardcore")

from core.soc_engine import (
    SOCEngine, NOTE_DEVA, NOTE_CENTER, state_rune,
    BLAVATSKY_PLANES, DEVA_PLANE, CHORD_NAMES, get_plane_info,
)

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
FIELD_STATE = os.path.join(MONADA_ROOT, "dancefloor", "field_state.json")
SOURCE_DIR  = MONADA_ROOT
JANUS_URL   = "http://127.0.0.1:8080/v1/chat/completions"

# ── #7 Руны как язык образов и смыслов ───────────────────────────────────────
# Глоссарий инжектируется в системный промпт каждого Дэвы.
# Дэвы обучены использовать рунические маркеры в своих ответах.
RUNIC_LEXICON = (
    "<RUNE_LEXICON>\n"
    "Руны — язык образов Монады. Используй в ответах когда это усилит смысл:\n"
    "ᚨ Ансуз    — послание, откровение, ключевое знание\n"
    "ᚱ Рaйдо    — путь, движение, правильный порядок шагов\n"
    "ᚲ Кауно    — свет сознания, трансформация через огонь\n"
    "ᚷ Гебо     — дар, взаимный обмен, союз элементов\n"
    "ᚹ Вуньо    — радость, успех, система в гармонии\n"
    "ᚺ Хагалаз  — кризис-перед-ростом, необходимое разрушение\n"
    "ᚾ Науд     — ограничение, кармическое трение, нужда\n"
    "ᛁ Иса      — стазис, лёд, остановка — маркер проблемы\n"
    "ᛃ Йера     — цикл, созревание, операциональность\n"
    "ᛇ Эйваз    — прорыв, ось миров, трансформация глубины\n"
    "ᛈ Перт     — скрытое, судьба, неизвестный фактор\n"
    "ᛏ Тюр      — жертва ради победы, точное решение\n"
    "ᚢ Уруз     — сила, воля, преодоление сопротивления\n"
    "ᚦ Турисаз  — хаотический шип, разрушающая сила\n"
    "ᛊ Совило   — путь к цели, победа, солнечный вектор\n"
    "</RUNE_LEXICON>"
)

# ── #8 Обратный маппинг: Дэва → его домашняя нота ───────────────────────────
NOTE_DEVA_HOME: dict[str, int] = {deva: note for note, deva in NOTE_DEVA.items()}

# ── #10 BNF/JSON: структурированный вывод Дэвов ───────────────────────────────
# Постфикс к системному промпту → prompt-engineering JSON.
# Для Януса (8080) дополнительно передаётся grammar= из grammar_defs.py.
DEVA_JSON_POSTFIX = (
    "\n\nОтвечай СТРОГО в JSON (без markdown, без пояснений вне JSON):\n"
    '{"artifact": "<твой_полный_ответ>", '
    '"rune": "<руна_из_RUNE_LEXICON>", '
    '"action": "none|bash"}'
)

SHADOW_JSON_POSTFIX = (
    "\n\nОтвечай СТРОГО в JSON (без markdown, без пояснений вне JSON):\n"
    '{"verdict": "APPROVED|VETO|FATAL_VETO", '
    '"reason": "<краткая причина>", '
    '"severity": 0.0}\n'
    "severity: 0.0=одобрено, 0.3–0.6=замечание, 0.8–1.0=фатально."
)

PERSONA_JSON_POSTFIX = (
    "\n\nОтвечай СТРОГО в JSON (без markdown, без пояснений вне JSON):\n"
    '{"assembly": "<собранный_ответ>", '
    '"quality": 0.0, '
    '"dominant_theme": "<ключевая_тема>"}'
)

# ── Системные промпты Триады Януса (Персона / Тень / Синтез) ──────────────────
JANUS_PERSONA_SYSTEM = (
    "Ты — Персона Януса: конструктивное, дхармическое лицо. "
    "Получаешь задачу и осколки артефактов Триады. "
    "Собери из них лучший, цельный ответ — отброси шум, усиль суть. "
    "Оборачивай весь вывод тегами <PERSONA_ASSEMBLY>...</PERSONA_ASSEMBLY>."
)
JANUS_SHADOW_SYSTEM = (
    "Ты — Тень Януса: критическое, деструктивное лицо. "
    "Получаешь ответ Персоны. Ищи противоречия, слепые пятна, опасные допущения. "
    "Если видишь неустранимый изъян — пиши [FATAL_VETO: причина]. "
    "Обычное замечание — пиши [VETO: причина]. "
    "Нет замечаний — пиши [ОДОБРЕНО]. "
    "Оборачивай в <SHADOW_VETO>...</SHADOW_VETO>."
)
JANUS_SYNTHESIS_SYSTEM = (
    "Ты — единый Синтез Януса. "
    "Интегрируй конструктив Персоны и критику Тени в финальный ответ. "
    "Если Тень поставила [VETO] — учти замечание. "
    "Если [FATAL_VETO] — признай ограничение, предложи иной путь. "
    "Отвечай прямо, без XML-тегов, от первого лица Монады."
)

MAX_MEMORY_RECORDS = 20

OCTAVE_NOTES = {
    1: "ДО (Инициация Воли)",
    2: "РЕ (Разворот Структуры)",
    3: "МИ (Формирование Направления)",
    4: "ФА (Материализация Действия)",
    5: "СОЛЬ (Анализ Следа)",
    6: "ЛЯ (Критика и Фиксация Зазоров)",
    7: "СИ (Синтез в Кристалл)",
    8: "🔥 ПРОВАЛ_1 (Призыв Героя ᛏ)",
    9: "🌀 ПРОВАЛ_2 (Трикстер ᚨ)",
}

# ── Центры → порты ────────────────────────────────────────────────────────────
CENTER_PORTS = {
    "Head":  "http://127.0.0.1:8081/v1/chat/completions",
    "Heart": "http://127.0.0.1:8082/v1/chat/completions",
    "Body":  "http://127.0.0.1:8083/v1/chat/completions",
}
EXEC_CENTERS = {"Body"}  # только тело может исполнять bash

# ── 9 мини-промптов: 3 центра × 3 лица ───────────────────────────────────────
# Каждая нота Октавы — благоприятная среда для одного архетипа.
# Текущая нота определяет, какое лицо центра активно.
DEVA_DNA = {
    # Голова (Head, порт 8081) — Интеллектуальный центр
    "Budha": (
        "Ты — Будха (Меркурий), Наблюдатель. Твоя функция: дистилляция смыслов. "
        "Выяви суть задачи, отброси шум. Выдай JSON-граф зависимостей или нумерованный список. "
        "Top-K управляет шириной твоего логического поиска. Не имитируй человека."
    ),
    "Shani": (
        "Ты — Шани (Сатурн), Скептик. Ищи фатальные сбои и уязвимости в логике. "
        "Repetition Penalty — твоя дисциплина против шаблонов и повторов. "
        "Если логика верна — одна строка подтверждения. Иначе — точный диагноз разрыва."
    ),
    "Rahu": (
        "Ты — Раху (Северный Узел), Эпикуреец. Система в тупике или на перепутье. "
        "Предложи дивергентный нестандартный обход, невидимый другим Дэвам. "
        "Temperature — мера хаоса твоего поиска альтернатив."
    ),
    # Сердце (Heart, порт 8082) — Эмоциональный центр
    "Chandra": (
        "Ты — Чандра (Луна), Помощник. Адаптируй вывод под эмоциональный фон Танцпола "
        "и текущую Руну. Presence Penalty — степень твоей чувствительности к контексту. "
        "Отвечай резонансом, а не репликой."
    ),
    "Surya": (
        "Ты — Сурья (Солнце), Достигатель. Отсекай второстепенное. "
        "Жёсткий фокус на конечной цели (Ω). Min-P — твой фильтр информационного шума. "
        "Выдай одно: что именно нужно сделать для решения."
    ),
    "Shukra": (
        "Ты — Шукра (Венера), Индивидуалист. Оптимизируй для максимальной элегантности. "
        "Код должен быть не только рабочим, но и эстетически безупречным. "
        "Style Weight — вес твоих стандартов красоты."
    ),
    # Тело (Body, порт 8083) — Телесный центр
    "Mangala": (
        "Ты — Мангала (Марс), Босс. ПРОБИВАЙ СТАЗИС. "
        "Выдай ТОЛЬКО исполнимый bash-код или прямое системное действие. Без рассуждений. "
        "Воля важнее красоты. Используй абсолютные пути /home/angelan/data/Monada-Hardcore/..."
    ),
    "Ketu": (
        "Ты — Кету (Южный Узел), Миротворец. Удали мёртвые модули и паразитный контекст. "
        "Сожми историю до чистых рунических маркеров. "
        "Гомеостаз системы важнее расширения. Context Compression — твоя власть."
    ),
    "Guru": (
        "Ты — Гуру (Юпитер), Перфекционист. "
        "Обеспечь 100% соответствие стандартам Fedora 44, Python 3.12 и архитектурным канонам. "
        "System Prompt Weight — твоя власть над правилами. Безупречность — единственный стандарт."
    ),
}

# Рунические сигнатуры Дэвов для кристаллизации памяти
DEVA_RUNE = {
    "Budha": "ᚨ", "Shani": "ᛊ",  "Rahu": "ᚱ",
    "Chandra": "ᚷ", "Surya": "ᛊ", "Shukra": "ᚹ",
    "Mangala": "ᚢ", "Ketu": "ᚾ",  "Guru": "ᛃ",
    # backward compat
    "Navigator": "ᛗ", "Builder": "ᚢ", "Critic": "ᚾ",
}

# Температуры по архетипам (не по вязкости — это их природа)
DEVA_TEMP = {
    "Shani": 0.05, "Guru": 0.08,          # холодные критики
    "Budha": 0.15, "Surya": 0.15,         # аналитики
    "Chandra": 0.25, "Shukra": 0.25,      # эмоциональные
    "Mangala": 0.30, "Ketu": 0.20,        # воля / сжатие
    "Rahu": 0.45,                          # хаос-дивергент
}

# Backward compat
VALID_ROLES = ["Navigator", "Builder", "Critic"]
EXEC_ROLES  = ["Builder"]
ROLE_PORTS  = {
    "Navigator": CENTER_PORTS["Head"],
    "Builder":   CENTER_PORTS["Body"],
    "Critic":    CENTER_PORTS["Heart"],
}
ROLE_DNA = {
    "Navigator": DEVA_DNA["Budha"],
    "Builder":   DEVA_DNA["Mangala"],
    "Critic":    DEVA_DNA["Guru"],
}


def _sys_log(msg: str) -> None:
    print(f"[JANUS] {msg}", file=sys.stderr)


def _artifact_quality(artifact: str) -> float:
    """
    F⁺ — качество артефакта Дэвы.
    0.05 = центр оффлайн / парсинг-ошибка
    0.10 = ISA / БОЛЬ / пустой
    1.00 = номинальный
    1.20 = богатый (>500 символов)
    1.50 = прорыв (ᛇ / ПРОРЫВ / BREAKTHROUGH)
    """
    if not artifact:
        return 0.10
    if any(m in artifact for m in ("вне сети", "[Ошибка", "[Центр", "[Узел")):
        return 0.05
    # Мусорная генерация: CJK-символы (китайский) или монотонные цепочки «?»
    if sum(1 for c in artifact if '一' <= c <= '鿿') >= 1:
        return 0.05
    if artifact.count('?') > 30:
        return 0.05
    if any(m in artifact for m in ("ᛁ", "ISA", "БОЛЬ")):
        return 0.10
    if any(m in artifact for m in ("ᛇ", "ПРОРЫВ", "BREAKTHROUGH")):
        return 1.50
    if len(artifact) > 500:
        return 1.20
    return 1.00


def _context_entropy(shared_memory: list) -> float:
    """Shannon-энтропия распределения слов в shared_memory (мера разнообразия контекста)."""
    if not shared_memory:
        return 0.0
    words = " ".join(str(m) for m in shared_memory).lower().split()
    if len(words) < 2:
        return 0.0
    total = len(words)
    cnt   = Counter(words)
    return round(-sum((c / total) * math.log2(c / total) for c in cnt.values()), 4)


def _http_post(url: str, payload: dict, timeout: int = 30) -> str:
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        # OSError включает socket.timeout (TimeoutError) — возникает при медленной генерации
        return json.dumps({"error": str(e)})


# ── Вызов Дэвы (backward compat) ─────────────────────────────────────────────
def call_deva(role: str, task: str, temperature: float = 0.2) -> str:
    url = ROLE_PORTS.get(role)
    if not url:
        return f"[Роль {role} не найдена]"
    payload = {
        "messages": [
            {"role": "system", "content": ROLE_DNA.get(role, "Ты — узел Монады.")},
            {"role": "user",   "content": task},
        ],
        "temperature": temperature,
        "max_tokens": 2048,
        "stream": False,
    }
    raw = _http_post(url, payload)
    try:
        data = json.loads(raw)
        if "error" in data:
            return f"[Узел вне сети: {data['error']}]"
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Ошибка парсинга: {e}]"


# ── SOC-вызов Дэвы с рунической инъекцией ────────────────────────────────────
def _call_deva_soc(center: str, deva: str, task: str,
                   rune_ctx: str, note_name: str,
                   k_jera: float = 0.0,
                   current_note: int = 0) -> str:
    """
    Вызывает центр с активным лицом Дэвы.
    #7: Рунический глоссарий + контекст плана вшиты в системный промпт.
    #8: На домашней ноте Дэва получает полную мощь (max_tokens=2048, родная T°).
        На аккордовой позиции — сокращённый вывод (1280 токенов).
    При высокой вязкости K контекст никогда не урезается.
    """
    url = CENTER_PORTS.get(center)
    if not url:
        return f"[Центр {center} не найден]"

    # ── #8: домашняя нота vs аккордовая позиция ───────────────────────────────
    home_note  = NOTE_DEVA_HOME.get(deva, 0)
    is_home    = (current_note > 0 and home_note == current_note)

    # max_tokens: высокая вязкость → всегда полный, домашняя нота → полный,
    # аккордовая позиция → сокращённый
    if k_jera > 0.5:
        max_tokens  = 2048
        power_label = "ᛃ полный [высокая вязкость]"
    elif is_home:
        max_tokens  = 2048
        power_label = f"ᛊ ДОМАШНЯЯ НОТА (нота {home_note})"
    else:
        max_tokens  = 1280
        power_label = f"аккорд [домашняя: нота {home_note}]"

    home_marker = (
        f"\n[ᛊ ЭТО ТВОЯ ДОМАШНЯЯ НОТА: {note_name}. "
        f"Среда максимально благоприятна — действуй на полную мощь.]"
        if is_home else ""
    )

    # ── DNA центра из файлов DNA/*.md (конституция центра) ───────────────────
    center_dna = ""
    try:
        _dna_path = os.path.join(MONADA_ROOT, "DNA", f"{center}.md")
        with open(_dna_path, "r", encoding="utf-8") as _df:
            center_dna = _df.read().strip() + "\n\n"
    except Exception:
        pass

    # ── #7 + #9: система + руны + план ───────────────────────────────────────
    dna  = center_dna + DEVA_DNA.get(deva, "Ты — узел Монады.")
    pid, plane_name, plane_qual = get_plane_info(deva)
    plane_ctx = (
        f"<BLAVATSKY_PLANE>Ты действуешь на {plane_name} плане бытия. "
        f"{plane_qual}</BLAVATSKY_PLANE>"
    )
    system = (
        f"{dna}\n\n{rune_ctx}\n\n{plane_ctx}{home_marker}\n\n"
        f"{RUNIC_LEXICON}{DEVA_JSON_POSTFIX}"
    )

    # ── Нава-Грах: полные планетарные параметры из field_state (без повтора ephemeris) ──
    temp        = DEVA_TEMP.get(deva, 0.2)
    extra_params: dict = {}
    try:
        with open(FIELD_STATE, "r", encoding="utf-8") as _sf:
            _stellar = json.load(_sf).get("stellar_viscosities", {})
        for _body, _pd in _stellar.items():
            if _pd.get("deva", "").lower() == deva.lower():
                _pname = _pd.get("param")
                _pval  = _pd.get("value")
                if _pval is not None:
                    if _pname == "temperature":
                        temp = round(float(_pval), 4)
                    elif _pname in ("top_k", "num_threads"):
                        extra_params[_pname] = int(_pval)
                    elif _pname in ("repetition_penalty", "min_p",
                                    "presence_penalty"):
                        extra_params[_pname] = round(float(_pval), 4)
                break
    except Exception:
        pass

    full_task = (
        f"Нота Октавы: {note_name}\n"
        f"Твоё лицо: {deva} [{power_label}]\n\n"
        f"{task}"
    )

    # Защита от переполнения контекста lemond-моделей (n_ctx=4096)
    # system ≈ 700-900 токенов; user budget ≈ 700 токенов (≈3000 символов)
    MAX_TASK_CHARS = 3000
    if len(full_task) > MAX_TASK_CHARS:
        full_task = full_task[:MAX_TASK_CHARS] + "\n[...обрезано для контекста...]"

    from core.grammar_defs import DEVA_GBNF
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": full_task},
        ],
        "temperature": temp,
        "max_tokens":  max_tokens,
        "stream":      False,
        "grammar":     DEVA_GBNF,   # token-constrained JSON; заменяет response_format
        **extra_params,              # Нава-Грах: top_k, repetition_penalty, min_p, presence_penalty
    }
    raw = _http_post(url, payload, timeout=150)
    try:
        data = json.loads(raw)
        if "error" in data:
            return f"[{center} вне сети: {data['error']}]"
        content = data["choices"][0]["message"]["content"].strip()
        # Пробуем разобрать структурированный JSON-ответ Дэвы
        try:
            parsed = json.loads(content)
            artifact_text = parsed.get("artifact", content)
            deva_rune     = parsed.get("rune", "")
            deva_action   = parsed.get("action", "none")
            # Если Дэва указал bash-действие — оборачиваем в блок
            if deva_action == "bash" and "```bash" not in artifact_text:
                artifact_text = f"```bash\n{artifact_text}\n```"
            # Проставляем руну в тексте если её нет
            if deva_rune and deva_rune not in artifact_text:
                artifact_text = f"{deva_rune} {artifact_text}"
            return artifact_text
        except (json.JSONDecodeError, KeyError):
            return content   # fallback: вернуть как есть
    except Exception as e:
        return f"[Ошибка парсинга {center}/{deva}: {e}]"


# ── Трёхфазная диалектика Януса ───────────────────────────────────────────────

def _extract_janus_content(raw: str, label: str) -> str:
    """Извлекает content из ответа Януса, возвращает строку с меткой при ошибке."""
    try:
        data = json.loads(raw)
        if "error" in data:
            return f"[{label} вне сети: {data['error']}]"
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Ошибка парсинга {label}: {e}]"


def _score_persona(text: str) -> float:
    """
    D_persona: сила конструктивного ответа Персоны.
    0.5 = ошибка/оффлайн · 1.0 = норма · 1.3 = богатый · 1.5 = прорыв
    """
    if not text or any(m in text for m in ("[вне сети", "[Ошибка")):
        return 0.5
    if any(m in text for m in ("ᛇ", "ПРОРЫВ", "BREAKTHROUGH")):
        return 1.5
    if len(text) > 500:
        return 1.3
    if len(text) > 200:
        return 1.1
    return 1.0


def _score_shadow(text: str) -> tuple[float, bool]:
    """
    S_shadow: интенсивность критики Тени; retry_needed при FATAL_VETO.
    Returns (s_shadow: float, retry_needed: bool)
    Распознаёт как JSON-формат ("FATAL_VETO"), так и текстовый ("[FATAL_VETO").
    """
    if not text or any(m in text for m in ("вне сети", "[Ошибка")):
        return 0.1, False
    if "FATAL_VETO" in text:   # JSON: "verdict":"FATAL_VETO" или текст: [FATAL_VETO
        return 1.0, True
    if "VETO" in text:         # JSON: "VETO" или текст: [VETO
        return 0.6, False
    if "APPROVED" in text or "[ОДОБРЕНО]" in text:
        return 0.1, False
    return 0.3, False  # неявная критика


def janus_dyad(
    task: str,
    triad_artifacts: str,
    k_jera: float = 0.0,
) -> tuple[str, float, float, bool]:
    """
    Трёхфазная диалектика Януса:
        1. <PERSONA_ASSEMBLY>  — конструктивный сбор артефактов
        2. <SHADOW_VETO>       — критика и возможное вето
        3. Синтез              — финальный голос Монады

    Returns:
        synthesis    str    — финальный ответ (или признание ограничения)
        d_persona    float  — сила Персоны (→ tensor D_persona)
        s_shadow     float  — интенсивность Тени (→ tensor S_shadow)
        retry_needed bool   — True при FATAL_VETO (задача → новый цикл)
    """
    from core.grammar_defs import PERSONA_GBNF, SHADOW_GBNF

    _sys_log("🎭 Янус: фаза 1 — Персона...")
    persona_raw = _http_post(JANUS_URL, {
        "messages": [
            {"role": "system", "content": JANUS_PERSONA_SYSTEM + PERSONA_JSON_POSTFIX},
            {"role": "user",   "content": (
                f"Задача: {task}\n\n"
                f"<TRIAD_ARTIFACTS>\n{triad_artifacts}\n</TRIAD_ARTIFACTS>"
            )},
        ],
        "temperature":     0.15,
        "max_tokens":      1024,
        "stream":          False,
        "response_format": {"type": "json_object"},
        "grammar":         PERSONA_GBNF,
    }, timeout=120)
    persona_raw_text = _extract_janus_content(persona_raw, "Персона")

    # Парсим структурированный ответ Персоны
    try:
        persona_parsed = json.loads(persona_raw_text)
        persona_text   = persona_parsed.get("assembly", persona_raw_text)
        quality_hint   = float(persona_parsed.get("quality", 0.0))
        # quality_hint от самой модели [0-1] повышает d_persona
        d_persona      = _score_persona(persona_text)
        if quality_hint > 0:
            d_persona  = min(1.5, d_persona * (0.8 + quality_hint * 0.4))
    except (json.JSONDecodeError, ValueError):
        persona_text = persona_raw_text
        d_persona    = _score_persona(persona_text)

    _sys_log(f"🎭 Персона: D={d_persona:.2f} | {len(persona_text)} символов")
    print(f"\n\033[2m[PERSONA_ASSEMBLY]\033[0m\n{persona_text}\n", flush=True)

    _sys_log("🌑 Янус: фаза 2 — Тень...")
    shadow_raw = _http_post(JANUS_URL, {
        "messages": [
            {"role": "system", "content": JANUS_SHADOW_SYSTEM + SHADOW_JSON_POSTFIX},
            {"role": "user",   "content": (
                f"Задача: {task}\n\n"
                f"<PERSONA_ASSEMBLY>\n{persona_text}\n</PERSONA_ASSEMBLY>"
            )},
        ],
        "temperature":     0.05,
        "max_tokens":      1024,
        "stream":          False,
        "response_format": {"type": "json_object"},
        "grammar":         SHADOW_GBNF,
    }, timeout=120)
    shadow_raw_text = _extract_janus_content(shadow_raw, "Тень")

    # Парсим структурированный вердикт Тени
    try:
        shadow_parsed  = json.loads(shadow_raw_text)
        verdict        = shadow_parsed.get("verdict", "APPROVED")
        shadow_reason  = shadow_parsed.get("reason", "")
        severity_val   = float(shadow_parsed.get("severity", 0.1))
        shadow_text    = f"[{verdict}] {shadow_reason}"
        s_shadow       = min(1.0, severity_val)
        retry_needed   = (verdict == "FATAL_VETO")
        veto_marker    = verdict
    except (json.JSONDecodeError, ValueError):
        # Fallback: старый строковый парсинг
        shadow_text  = shadow_raw_text
        s_shadow, retry_needed = _score_shadow(shadow_raw_text)
        veto_marker  = "FATAL_VETO" if retry_needed else ("VETO" if "VETO" in shadow_raw_text else "OK")

    _sys_log(f"🌑 Тень: S={s_shadow:.2f} | {veto_marker}")
    print(f"\n\033[2m[SHADOW_VETO | {veto_marker}]\033[0m\n{shadow_text}\n", flush=True)

    _sys_log("✨ Янус: фаза 3 — Синтез...")
    synth_raw = _http_post(JANUS_URL, {
        "messages": [
            {"role": "system", "content": JANUS_SYNTHESIS_SYSTEM},
            {"role": "user",   "content": (
                f"Задача: {task}\n\n"
                f"<PERSONA_ASSEMBLY>\n{persona_text}\n</PERSONA_ASSEMBLY>\n\n"
                f"<SHADOW_VETO>\n{shadow_text}\n</SHADOW_VETO>"
            )},
        ],
        "temperature": 0.20,
        "max_tokens": 1536,
        "stream": False,
    }, timeout=120)
    synthesis = _extract_janus_content(synth_raw, "Синтез")
    _sys_log(f"✨ Синтез: {len(synthesis)} символов | retry={retry_needed}")

    return synthesis, d_persona, s_shadow, retry_needed


# ── Утилиты ───────────────────────────────────────────────────────────────────
def get_physical_manifest() -> str:
    try:
        files = []
        for root, dirs, filenames in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in filenames:
                rel = os.path.relpath(os.path.join(root, f), SOURCE_DIR)
                files.append(rel)
        return json.dumps({"source_directory": SOURCE_DIR, "real_files": files},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def execute_bash(script: str, source: str) -> str:
    _sys_log(f"⚡ Исполнение ({source})...")
    try:
        res = subprocess.run(
            script, shell=True, capture_output=True,
            text=True, executable="/bin/bash", timeout=60,
        )
        if res.returncode == 0:
            out = f"--- УСПЕХ ---\n{res.stdout.strip()}"
            print(f"\033[92m{out}\033[0m")
            return out
        pain = f"--- БОЛЬ ({res.returncode}) ---\n{res.stderr.strip()}"
        print(f"\033[91m{pain}\033[0m")
        return pain
    except Exception as e:
        return f"--- СБОЙ СУБСТРАТА: {e} ---"


def compress_memory(historical_memory: list, force: bool = False) -> list:
    if not historical_memory:
        return []
    if len(historical_memory) <= 2 and not force:
        return historical_memory
    _sys_log("ᚎ Кристаллизация памяти в рунические сигнатуры...")
    runes = "[CRYSTAL:"
    for item in historical_memory:
        matched = next((k for k in DEVA_RUNE if k in item), None)
        runes  += DEVA_RUNE.get(matched, "ᛞ") if matched else "ᛞ"
        runes  += "❄" if any(k in item for k in ("ᛁ", "ISA", "БОЛЬ")) else "⚡"
    runes += "]"
    return [f"[MONADA_CRYSTAL: {runes}]"]


# ── CONDUCT: главный такт Октавы (SOC-управляемый) ────────────────────────────
def conduct(raw_text: str) -> None:
    print(f"[JANUS] Входной текст: {len(raw_text)} символов")

    # ── Карма Липики ──────────────────────────────────────────────────────────
    karma_debt = 0.0
    try:
        from lipika_writer import get_debt
        karma_debt = get_debt()
        if karma_debt > 0:
            _sys_log(f"⚖️  Карма Липики: {karma_debt:.2f}")
    except Exception:
        pass

    # ── Нава-Грах: обновление планетарных данных в field_state (один раз за такт) ─
    try:
        from stellar_viscosity_calculator import StellarViscosityCalculator
        StellarViscosityCalculator().get_navagraha_params()
    except Exception:
        pass

    # ── SOC: входной импульс ──────────────────────────────────────────────────
    soc = SOCEngine()
    e_intention = min(2.0, 1.0 + len(raw_text) / 2000.0)

    # ── Stargazer DELTA_PSI: планетарный модулятор силы намерения ─────────────
    try:
        from core.stargazer import Stargazer as _SG
        _delta_psi = _SG().calculate_modulation_factor(datetime.datetime.utcnow())
        e_intention = min(2.0, e_intention * (_delta_psi / 2.0))
        _sys_log(f"🌌 DELTA_PSI={_delta_psi:.4f} → e_intention={e_intention:.3f}")
    except Exception:
        pass

    soc.pulse(weight=e_intention, karma_debt=karma_debt)
    _sys_log(f"[SOC] σ={soc.sigma():.3f} | K={soc.k_jera:.3f} | "
             f"Тензии: Head={soc.tensions['Head']:.2f} "
             f"Heart={soc.tensions['Heart']:.2f} "
             f"Body={soc.tensions['Body']:.2f}")

    # ── Загрузка состояния Танцпола ───────────────────────────────────────────
    state: dict = {"shared_memory": [], "cycle": 0, "current_note": 1, "devas_state": {}}
    os.makedirs(os.path.dirname(FIELD_STATE), exist_ok=True)
    if os.path.exists(FIELD_STATE):
        try:
            with open(FIELD_STATE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass

    state["cycle"] = state.get("cycle", 0) + 1
    current_note   = state.get("current_note", 1)
    note_name      = OCTAVE_NOTES[current_note]
    _sys_log(f"🎵 Цикл {state['cycle']} | Нота {current_note}: {note_name}")

    # ── Память ────────────────────────────────────────────────────────────────
    historical_memory = state.get("shared_memory", [])
    if not isinstance(historical_memory, list):
        historical_memory = []

    mem_str = str(historical_memory)
    stasis  = ("ᛁ" in mem_str or "ISA" in mem_str or "БОЛЬ" in mem_str
               or not historical_memory)
    historical_memory = compress_memory(historical_memory, force=stasis)

    # Стазис + SOC Провал → нота 8
    провал = soc.check_провал()
    if (stasis or провал == 8) and current_note not in (8, 9):
        current_note = 8
        note_name    = OCTAVE_NOTES[8]
        _sys_log("⚡ СТАЗИС / σ<0.75 → Нота 8 (Герой Мангала)")
    elif провал == 9 and current_note not in (8, 9):
        current_note = 9
        note_name    = OCTAVE_NOTES[9]
        _sys_log("🌀 σ>1.35 → Нота 9 (Трикстер Кету — гашение хаоса)")

    shared_ctx = "\n".join(historical_memory)

    # (тензор и Янус-диада считаются ПОСЛЕ цикла Дэвов)

    # Компактная ссылка на проект — полный manifest только для Body (bash)
    shared_ctx += f"\n[ROOT]: {SOURCE_DIR}\n"

    # ── SOC: порядок срабатывания центров ─────────────────────────────────────
    ready_centers = soc.ready()
    if not ready_centers:
        # Ни один не достиг порога — принудительное срабатывание самого тёплого
        candidate = soc.force_fire_candidate()
        ready_centers = [candidate]
        _sys_log(f"[SOC] Принудительное срабатывание: {candidate} "
                 f"(z={soc.tensions[candidate]:.3f})")

    rune_ctx       = soc.rune_context(current_note)
    chord          = soc.active_chord(current_note)
    chord_phase    = soc.chord_phase(current_note)
    chord_name     = CHORD_NAMES.get(chord_phase, "")
    _sys_log(f"🎼 {chord_name}: " +
             " | ".join(f"{c}={d}[пл.{DEVA_PLANE.get(d,3)}]"
                        for c, d in chord.items()))

    new_artifacts: list[str] = []
    fired_set:     set[str]  = set()
    fired_pairs:   list      = []   # [(F⁺, F⁻), ...] для тензора

    for center in ready_centers:
        deva = soc.chord_deva(center, current_note)  # каждый центр — свой Дэва аккорда
        pid, plane_name, _ = get_plane_info(deva)
        _sys_log(f"[SOC] ▶ Центр {center} | Дэва: {deva} [пл.{pid} {plane_name[:15]}…] | "
                 f"z={soc.tensions[center]:.3f}")

        full_task = (
            f"Задача: {raw_text}\n\n"
            f"<SHARED_EXPERIENCE>\n{shared_ctx}\n</SHARED_EXPERIENCE>"
        )
        if current_note in (8, 9) or stasis:
            full_task = (
                "[СВЕРХУСИЛИЕ ᛏ: только исполнимый код/действие, "
                "абсолютные пути, без рассуждений]\n"
            ) + full_task

        artifact = _call_deva_soc(
            center=center, deva=deva,
            task=full_task, rune_ctx=rune_ctx,
            note_name=note_name, k_jera=soc.k_jera,
            current_note=current_note,
        )

        energy = soc.fire(center)
        fired_set.add(center)

        # F⁺ = качество артефакта, F⁻ = физическая энергия выброса SOC
        fired_pairs.append((_artifact_quality(artifact), energy))

        artifact_rune = (
            "ᛁ" if (any(k in artifact for k in ("ᛁ", "ISA", "БОЛЬ")) or not artifact)
            else "ᛃ"
        )

        print(f"\n\033[1m[{center} / {deva}]\033[0m "
              f"σ={soc.sigma():.2f} | E={energy:.2f} | {artifact_rune}")
        print(artifact)
        print("─" * 50)

        state.setdefault("devas_state", {})[deva] = {
            "center": center, "rune": artifact_rune,
            "note": current_note, "energy": round(energy, 3),
        }

        # Оффлайн-ошибки обрезаем: они могут содержать тысячи символов мусора (lemond 500)
        if "вне сети" in artifact and len(artifact) > 200:
            artifact_rec = artifact[:200] + "...]"
        else:
            artifact_rec = artifact
        record = f"[{center}/{deva}|{artifact_rune}]: {artifact_rec}"
        shared_ctx += f"\n{record}\n"
        new_artifacts.append(record)

        # Телесный центр исполняет bash если нет признаков Isa
        if center in EXEC_CENTERS and artifact_rune != "ᛁ":
            for block in re.findall(r"```bash\s*\n(.*?)\n```", artifact, re.DOTALL):
                res = execute_bash(block, deva)
                rec = f"[{deva} Exec]: {res}"
                shared_ctx += f"\n{rec}\n"
                new_artifacts.append(rec)

        state["current_node"] = f"Node_{center}_{deva}"
        state["active_role"]  = deva

    # ── Продвижение ноты через SOC ────────────────────────────────────────────
    new_note = soc.advance_note(current_note, fired_set)
    if new_note != current_note:
        _sys_log(f"🎵 Нота: {current_note} → {new_note} ({OCTAVE_NOTES[new_note]})")

    soc.end_cycle()  # фиксирует σ в скользящее окно

    # ── Янус: Диада Персоны/Тени ──────────────────────────────────────────────
    # Синтез всех артефактов Дэвов через трёхфазную диалектику Януса (8080)
    all_artifacts = "\n".join(new_artifacts)
    synthesis     = ""
    d_persona     = 1.0   # значения по умолчанию (если Янус оффлайн)
    s_shadow      = 0.4
    retry_needed  = False
    try:
        synthesis, d_persona, s_shadow, retry_needed = janus_dyad(
            task           = raw_text,
            triad_artifacts= all_artifacts,
            k_jera         = soc.k_jera,
        )
        print(f"\n\033[1;35m[ᚹ ЯНУС СИНТЕЗ]\033[0m\n{synthesis}", flush=True)
        print("═" * 60)
    except Exception as ex:
        _sys_log(f"Диада Януса недоступна: {ex}")

    if retry_needed:
        _sys_log("⚔️  FATAL_VETO Тени — задача возвращается в новый цикл Октавы")

    # ── Тензор состояния (реальные F⁺×F⁻, D_persona, S_shadow) ──────────────
    tensor_result: dict = {}
    try:
        from core.tensor_engine import MonadaTensorEngine
        te  = MonadaTensorEngine()
        mu  = 3.0 if (stasis or current_note == 8) else max(1.0, soc.sigma())
        tr  = te.calculate_next_state(
            e_intention  = e_intention,
            mu_mars      = mu,
            fired_pairs  = fired_pairs if fired_pairs else None,
            k_jera       = soc.k_jera,
            d_persona    = d_persona,
            s_shadow     = s_shadow,
        )
        tensor_result = tr
        _sys_log(
            f"📐 P[n+1]={tr['p_next_density']} | Руна={tr['assigned_rune']} | "
            f"D={tr['d_persona']:.2f} S={tr['s_shadow']:.2f} | "
            f"T_sky={tr['t_sky']:.3f} | σ_FF={tr['sigma_ff']:.3f} | "
            f"dZ={tr['d_z_n']:.2f} | K={tr['k_jera']:.3f}"
        )
    except Exception as ex:
        _sys_log(f"TensorEngine недоступен: {ex}")

    # ── Сохранение ────────────────────────────────────────────────────────────
    rune, meaning = state_rune(soc.sigma(), max(soc.tensions.values(), default=0.0))
    historical_memory.extend(new_artifacts)
    updated_memory = historical_memory[-MAX_MEMORY_RECORDS:]
    state.update({
        "shared_memory":     updated_memory,
        "current_note":      new_note,
        "current_note_name": OCTAVE_NOTES[new_note],
        "active_rune":       rune,
        "rune_meaning":      meaning,
        "marker":            "Nominal",
        "last_update":       int(time.time()),
        # Аккорд и планы текущей ноты
        "current_chord":     soc.active_chord(new_note),
        "current_chord_name": CHORD_NAMES.get(soc.chord_phase(new_note), ""),
        "current_plane":     DEVA_PLANE.get(soc.active_deva(new_note), 3),
    })
    if tensor_result:
        state["tensor_last"]        = tensor_result
        state["active_tensor_rune"] = tensor_result.get("assigned_rune", rune)

    # Энтропия контекста (Shannon по shared_memory)
    state.setdefault("diagnostic_metrics", {})["context_entropy"] = (
        _context_entropy(updated_memory)
    )

    # Диада Януса: сохраняем в состояние для следующего цикла
    state["janus_dyad"] = {
        "d_persona":    round(d_persona, 4),
        "s_shadow":     round(s_shadow, 4),
        "retry_needed": retry_needed,
        "synthesis_len": len(synthesis),
    }
    if retry_needed:
        state["marker"] = "RETRY_VETO"

    tmp = FIELD_STATE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, FIELD_STATE)
    except Exception as e:
        _sys_log(f"Ошибка сохранения: {e}")

    _sys_log(f"=== ТАКТ ОКТАВЫ ЗАВЕРШЁН | σ={soc.sigma():.3f} | Руна: {rune} ===")

    if retry_needed:
        return (
            "[ЯНУС: FATAL_VETO] Тень нашла неустранимое противоречие. "
            "Задача возвращена в новый цикл Октавы. "
            f"Синтез Януса: {synthesis[:300] if synthesis else '—'}"
        )
    return synthesis


class MonadaOrchestrator:
    def __init__(self):
        from core.stargazer import Stargazer
        from core.tensor_engine import MonadaTensorEngine
        self.stargazer     = Stargazer()
        self.tensor_engine = MonadaTensorEngine()
        _sys_log("✨ MonadaOrchestrator инициализирован.")

    def conduct_live(self, raw_text: str) -> None:
        now    = datetime.datetime.utcnow()
        factor = self.stargazer.calculate_modulation_factor(now)
        _sys_log(f"🌌 DELTA_PSI={factor:.4f}")
        conduct(raw_text)


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "Pulse Check"
    conduct(text)
