"""
presence/inbox_watcher.py — непрерывный наблюдатель входящих писем.

Опрашивает Proton Bridge IMAP каждые POLL_SEC секунд.
Новые письма превращает в «Впечатления» и дописывает в task_manifest.json
(Подсознание читает TASK_MANIFEST → before_tact → recall).

Запуск: python3 -m presence.inbox_watcher
Или как фоновый процесс из monada_on_geptarchy.sh.
"""

import os
import sys
import json
import time

sys.path.insert(0, "/home/angelan/data/Monada-Hardcore")

from presence.proton_client import fetch_unread, is_bridge_alive

MONADA_ROOT   = "/home/angelan/data/Monada-Hardcore"
DANCEFLOOR    = "/mnt/dancefloor"
TASK_MANIFEST = os.path.join(DANCEFLOOR, "task_manifest.json")
LOG_PATH      = os.path.join(MONADA_ROOT, "logs", "inbox_watcher.log")

POLL_SEC      = 120   # проверять каждые 2 минуты
MAX_INBOX_Q   = 10    # максимум непрочитанных задач в очереди

try:
    import lipika_writer
except Exception:
    lipika_writer = None


def _log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] [INBOX] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _read_manifest() -> dict:
    try:
        with open(TASK_MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_manifest(obj: dict) -> None:
    tmp = TASK_MANIFEST + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TASK_MANIFEST)


def _mail_to_task(msg: dict) -> str:
    sender  = msg.get("from", "неизвестный")
    subject = msg.get("subject", "(без темы)")
    body    = msg.get("body", "").strip()[:800]
    return (
        f"[ПИСЬМО от {sender}]\n"
        f"Тема: {subject}\n"
        f"{body}"
    )


def _enqueue(task_text: str, source: str) -> None:
    manifest = _read_manifest()
    queue: list = manifest.get("inbox_queue", [])
    if len(queue) >= MAX_INBOX_Q:
        _log(f"очередь полна ({MAX_INBOX_Q}), письмо пропущено: {source[:60]}")
        return
    queue.append({
        "original": task_text[:1200],
        "source":   source,
        "ts":       int(time.time()),
        "type":     "mail",
    })
    manifest["inbox_queue"] = queue
    manifest["ts"] = int(time.time())
    _write_manifest(manifest)
    _log(f"+1 в очередь: {source[:80]}")
    if lipika_writer:
        try:
            lipika_writer.record("REDEEM", "inbox_watcher",
                                 f"новое письмо: {source[:60]}")
        except Exception:
            pass


def poll_once() -> int:
    try:
        msgs = fetch_unread(mark_seen=True)
    except Exception as e:
        _log(f"IMAP ошибка: {e}")
        return 0
    for msg in msgs:
        task = _mail_to_task(msg)
        src  = f"{msg.get('from','')} / {msg.get('subject','')}"
        _enqueue(task, src)
    return len(msgs)


def main() -> None:
    os.makedirs(DANCEFLOOR, exist_ok=True)
    _log("inbox_watcher запущен")

    while True:
        if is_bridge_alive():
            n = poll_once()
            if n:
                _log(f"получено писем: {n}")
        else:
            _log("Proton Bridge недоступен, пропускаю такт")
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
