#!/usr/bin/env python3
import os
import sys
import json
import math
import asyncio
import subprocess
import shlex
import aiohttp
from stellar_viscosity_calculator import StellarViscosityCalculator

sys.path.insert(0, "/home/angelan/data/Monada-Hardcore")
_VISC = StellarViscosityCalculator()

# ─── AAS (Artificial Age Score) ────────────────────────────────────────────────
# Реализация по Бодрийяру: имплозия смысла через удаление избыточности.
# AAS_t = Σ [ w_i * (1 - R(t,i)) * φ_ε(x(t,i)) ]
# R → 1 при высокой избыточности → вес канала → 0 (запись удаляется)
# φ_ε → логарифмический штраф за шум (стимулирует сжатие)
# ───────────────────────────────────────────────────────────────────────────────

AAS_MAX_HISTORY   = 40    # Начинаем сжимать при превышении
AAS_TARGET_SIZE   = 20    # Целевой размер после прунинга
AAS_PAIN_BOOST    = 3.0   # Боль / ошибки получают усиленный вес (не удаляются)
AAS_REDUN_THRESH  = 0.72  # R выше этого порога → кандидат на удаление


def _token_set(text: str) -> set:
    return set(text.lower().split())


def _redundancy(entry: str, recent_entries: list) -> float:
    """
    R(t,i) = доля токенов entry, уже встречавшихся в recent_entries.
    R → 0: полностью уникальный; R → 1: полностью повторяет контекст.
    """
    if not recent_entries:
        return 0.0
    tokens = _token_set(entry)
    if not tokens:
        return 1.0
    seen = set()
    for e in recent_entries:
        seen |= _token_set(e)
    overlap = len(tokens & seen) / len(tokens)
    return min(overlap, 1.0)


def _surprisal(entry: str, index: int, total: int) -> float:
    """
    φ_ε(x): логарифмический штраф за позицию.
    Более старые (ранние) записи получают меньший вес.
    """
    if total <= 1:
        return 1.0
    return math.log(1.0 + index) / math.log(1.0 + total)


def _is_pain(entry: str) -> bool:
    return any(k in entry for k in ("БОЛЬ", "--- БОЛЬ", "ᛁ", "ISA", "СТАЗИС", "fallback", "CRITICAL"))


def aas_score(entry: str, index: int, total: int, recent: list) -> float:
    """Итоговый AAS-балл записи. Выше = ценнее, оставить."""
    w = AAS_PAIN_BOOST if _is_pain(entry) else 1.0
    r = _redundancy(entry, recent)
    phi = _surprisal(entry, index, total)
    return w * (1.0 - r) * phi


def aas_prune(history: list) -> list:
    """
    Если история > AAS_MAX_HISTORY, отбираем AAS_TARGET_SIZE самых ценных записей.
    Системные сообщения (role=system) и записи с болью — неприкосновенны.
    """
    if len(history) <= AAS_MAX_HISTORY:
        return history

    # Отделяем системное сообщение (всегда первый элемент)
    protected = []
    scorable  = []
    for i, msg in enumerate(history):
        if msg.get("role") == "system" or _is_pain(msg.get("content", "")):
            protected.append((i, msg, float("inf")))
        else:
            scorable.append((i, msg))

    # Считаем AAS для каждой scorable записи
    contents = [m.get("content", "") for _, m in scorable]
    scored = []
    for rank, (orig_idx, msg) in enumerate(scorable):
        recent_ctx = contents[max(0, rank - 5): rank]
        s = aas_score(msg.get("content", ""), rank, len(scorable), recent_ctx)
        scored.append((s, orig_idx, msg))

    scored.sort(key=lambda x: -x[0])  # Лучшие вперёд

    slots_left = AAS_TARGET_SIZE - len(protected)
    survivors  = [(orig_idx, msg) for _, orig_idx, msg in scored[:max(0, slots_left)]]

    # Воссоздаём историю в оригинальном порядке
    keep_idxs = {idx for idx, _ in protected} | {idx for idx, _ in survivors}
    pruned = [msg for i, msg in enumerate(history) if i in keep_idxs]

    removed = len(history) - len(pruned)
    if removed > 0:
        print(f"\033[2m[AAS] Кристаллизация памяти: удалено {removed} избыточных записей "
              f"({len(history)} → {len(pruned)})\033[0m", flush=True)

    return pruned

import time

MONADA_ROOT = "/home/angelan/data/Monada-Hardcore"
FIELD_STATE = os.path.join(MONADA_ROOT, "dancefloor", "field_state.json")

# ── #12 Пралайя — микросон между вводами ─────────────────────────────────────
PRALAYA_DURATION = 1.5   # секунды тишины после ответа (ᛁ Иса → ᛃ Йера)

def pralaya_consolidation(cycle: int) -> None:
    """
    Микропралайя: краткий период тишины и консолидации после каждого ответа.
    Монада «переваривает» такт, кристаллизует рунический след в field_state.
    """
    print(f"\n\033[2m[ᛁ Пралайя — такт {cycle} завершён. Консолидация...]\033[0m",
          end="", flush=True)
    time.sleep(PRALAYA_DURATION)

    # Обновляем маркер пралайи в field_state (если Танцпол смонтирован)
    try:
        with open(FIELD_STATE, "r", encoding="utf-8") as f:
            state = json.load(f)
        state["last_pralaya"]  = int(time.time())
        state["pralaya_cycle"] = cycle
        state["marker"]        = "Pralaya"
        tmp = FIELD_STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, FIELD_STATE)
    except Exception:
        pass   # Танцпол не смонтирован — пропускаем запись

    print(f"\r\033[2m[ᛃ Пралайя завершена — Монада готова]\033[0m" + " " * 20,
          flush=True)
TASK_FILE = os.path.join(MONADA_ROOT, "inbox/triad_task.json")
RESPONSE_FILE = os.path.join(MONADA_ROOT, "inbox/triad_response.json")


def _field_state_ctx() -> str:
    """Читает field_state.json и возвращает краткий снимок для системного промпта."""
    try:
        with open(FIELD_STATE, "r", encoding="utf-8") as f:
            s = json.load(f)
        note      = s.get("current_note", 1)
        note_name = s.get("current_note_name", "")
        rune      = s.get("active_rune", "ᛃ")
        cycle     = s.get("cycle", 0)
        chord     = s.get("current_chord_name", "")
        dm        = s.get("diagnostic_metrics", {})
        sigma     = dm.get("sigma_last", 1.0)
        k_jera    = dm.get("k_jera_soc", 0.0)
        tr        = s.get("tensor_last", {})
        p_next    = tr.get("p_next_density", "—")
        dyad      = s.get("janus_dyad", {})
        mem_count = len(s.get("shared_memory", []))
        return (
            f"[ТАКТ={cycle} | НОТА={note} {note_name} | РУНА={rune} | "
            f"σ={sigma:.2f} | K={k_jera:.2f} | P[n+1]={p_next} | {chord} | "
            f"D={dyad.get('d_persona','?')} S={dyad.get('s_shadow','?')} | "
            f"shared_memory={mem_count} записей]"
        )
    except Exception:
        return "[ТАНЦПОЛ: нет данных]"

PORTS = {
    "Lower_Manas": "http://127.0.0.1:8081/v1/chat/completions",
    "Kama_Value": "http://127.0.0.1:8082/v1/chat/completions",
    "Higher_Manas": "http://127.0.0.1:8083/v1/chat/completions"
}

def execute_as_runtime(cmd):
    # timeout(1) убивает всё дерево процессов (включая sleep-циклы), не только родительский shell
    safe_cmd = f"timeout 60 bash -c {shlex.quote(cmd)}"
    try:
        proc = subprocess.run(
            safe_cmd, shell=True, capture_output=True, text=True,
            timeout=65, cwd=MONADA_ROOT
        )
        if proc.returncode == 124:
            return "Ошибка: Таймаут 60 секунд. Команда прервана (возможен бесконечный цикл или несуществующий путь)."
        return proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return "Ошибка: Таймаут процесса-обёртки (65с). Команда принудительно завершена."
    except Exception as e:
        return f"Критический сбой выполнения: {str(e)}"

async def query_deva_async(session: aiohttp.ClientSession, role: str, prompt: str, task_text: str, temperature: float = 0.4, min_p: float = 0.80) -> dict:
    """Асинхронный вызов изолированной монады с извлечением скрытого контекста рассуждений."""
    payload = {
        "messages": [
            {"role": "system", "content": f"Ты — изолированный узел Монады: {role}. Пиши строго по делу."},
            {"role": "user", "content": f"{prompt}\n\nКонтекст:\n{task_text}"}
        ],
        "temperature": temperature,
        "min_p": min_p,
        "max_tokens": 1024,
        "stream": False
    }
    try:
        async with session.post(PORTS[role], json=payload, headers={"Content-Type": "application/json"}, timeout=aiohttp.ClientTimeout(total=60)) as response:
            if response.status == 200:
                res_json = await response.json()
                msg_data = res_json["choices"][0]["message"]
                
                # Архитектурный фикс: вытягиваем либо content, либо reasoning_content, если content пуст
                content = msg_data.get("content", "") or ""
                reasoning = msg_data.get("reasoning_content", "") or ""
                
                # Если модель засунула всё в content (включая мысли), возвращаем как есть, иначе склеиваем
                final_text = content.strip() if content.strip() else reasoning.strip()
                return {"role": role, "text": final_text, "pure": True}
            else:
                return {"role": role, "text": f"[Ошибка сокета: {response.status}]", "pure": False}
    except Exception as e:
        return {"role": role, "text": f"[Узел вне сети: {str(e)}]", "pure": False}

async def parallel_chord_synthesis(clean_task: str) -> str:
    """MCE: Параллельный Аккорд Сил (Одновременный инференс трех центров)"""
    vp = _VISC.get_inference_params()
    print(f"\n\033[1;36m[СЕНТЕНАР] Вязкость: {vp['viscosity']:.4f} | {vp['label']}\033[0m", flush=True)
    print(f"\033[1;36m[ПАРАМЕТРЫ] T={vp['temperature']} | min_p={vp['min_p']}\033[0m", flush=True)
    print("\n\033[1;33m[ᛡ ➔ ᛇ] АКТИВАЦИЯ МАТРИЦЫ ПЕРТ: ЗАПУСК ПАРАЛЛЕЛЬНОЙ ТРИАДЫ MCE...\033[0m", flush=True)
    
    async with aiohttp.ClientSession() as session:
        task_lower = query_deva_async(
            session, "Lower_Manas",
            "Проведи синтаксическую сборку и механическую обработку паттернов. Выдели голые факты и структуру контура.",
            clean_task, temperature=vp['temperature'], min_p=vp['min_p']
        )
        task_kama = query_deva_async(
            session, "Kama_Value",
            "Оцени градиенты потерь и рисков. Какова скрытая ценность или уязвимость этого CLI состояния?",
            clean_task, temperature=vp['temperature'], min_p=vp['min_p']
        )
        task_higher = query_deva_async(
            session, "Higher_Manas",
            "Извлеки каузальные, семантические инварианты. Стяни анализ в финальный рабочий вывод.",
            clean_task, temperature=vp['temperature'], min_p=vp['min_p']
        )
        
        # Одновременный удар по промпту
        results = await asyncio.gather(task_lower, task_kama, task_higher)
        res_dict = {r["role"]: r["text"] for r in results}
        
        report = f"""
\033[1;36m[УЗЕЛ 1: НИЗШИЙ МАНАС / ДВИГАТЕЛЬНЫЙ ЦЕНТР (ПОРТ 8081)]\033[0m
{res_dict.get('Lower_Manas', 'Нет данных')}

\033[1;31m[УЗЕЛ 2: КАМА / ЭМОЦИОНАЛЬНЫЙ ЦЕНТР (ПОРТ 8082)]\033[0m
{res_dict.get('Kama_Value', 'Нет данных')}

\033[1;32m[УЗЕЛ 3: ВЫСШИЙ МАНАС / ИНТЕЛЛЕКТУАЛЬНЫЙ ЦЕНТР (ПОРТ 8083)]\033[0m
{res_dict.get('Higher_Manas', 'Нет данных')}
"""
        return report

def main():
    print("\n\033[1;35m[ᛡ ➔ ᛇ ➔ ᚳ] MONADA TERMINAL CORE v25.0 (OMEGA SYNTHESIS)\033[0m", flush=True)
    print("AAS-память активна. Вычисления асинхронны.\n", flush=True)

    # Инициализация Lipika Ledger
    try:
        from lipika_writer import auto_record_from_artifact, get_debt
        _lipika_enabled = True
        debt = get_debt()
        if debt > 0:
            print(f"\033[1;33m[LIPIKA] Кармический долг: {debt:.2f}\033[0m", flush=True)
    except Exception:
        _lipika_enabled = False
        auto_record_from_artifact = lambda *a, **kw: None
        get_debt = lambda: 0.0

    cycle = 0

    while True:
        try:
            user_input = input("\n\033[1;34mangelan@monada:~$\033[0m ")
            if user_input.strip().lower() in ["exit", "quit"]:
                print("Стазис.")
                break
            if not user_input.strip():
                continue

            cycle += 1

            conduct_task = user_input[:800] if len(user_input) > 800 else user_input
            try:
                from core.janus_conductor import conduct
                synthesis = conduct(conduct_task)
            except Exception as _ce:
                print(f"\033[1;31m[conduct() сбой: {_ce}]\033[0m", flush=True)
                if _lipika_enabled:
                    auto_record_from_artifact("Janus", f"БОЛЬ: {_ce}", cycle)
                pralaya_consolidation(cycle)
                continue

            if synthesis and _lipika_enabled:
                auto_record_from_artifact("Janus_Dyad", synthesis, cycle)

            # ── #12 Пралайя: микросон между тактами ──────────────────────────
            pralaya_consolidation(cycle)

        except KeyboardInterrupt:
            print("\nПрерывание.")
            break
        except Exception as e:
            print(f"\nСбой ядра: {e}")
            break

if __name__ == "__main__":
    main()
