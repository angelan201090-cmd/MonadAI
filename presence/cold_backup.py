"""
presence/cold_backup.py — зашифрованный холодный бэкап.

Бэкапит:
  - memory_graph.json (COLD-граф, долгосрочная память)
  - lipika_ledger.json (SHA-256 karma-цепочка)

Шифрование: AES-256-GCM через стандартную библиотеку secrets + пакет
`cryptography`. Ключ берётся из OS keyring (сервис «monada-backup»).

Настройка ключа (один раз):
    python3 -c "
    import keyring, secrets, base64
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    keyring.set_password('monada-backup', 'backup-key', key)
    print('ключ установлен:', key[:8], '...')
    "

Запуск:
    python3 -m presence.cold_backup               # создать бэкап
    python3 -m presence.cold_backup --restore <файл>  # восстановить
"""

import os
import sys
import json
import time
import base64
import struct
import argparse
import secrets as _secrets

sys.path.insert(0, "/home/angelan/data/Monada-Hardcore")

MONADA_ROOT  = "/home/angelan/data/Monada-Hardcore"
BACKUP_DIR   = os.path.join(MONADA_ROOT, "backups")
KEYRING_SVC  = "monada-backup"
KEYRING_USER = "backup-key"

SOURCES = {
    "memory_graph":   os.path.join(MONADA_ROOT, "memory_graph.json"),
    "lipika_ledger":  os.path.join(MONADA_ROOT, "lipika_ledger.json"),
}


def _get_key() -> bytes:
    raw = os.environ.get("MONADA_BACKUP_KEY", "")
    if not raw:
        try:
            import keyring
            raw = keyring.get_password(KEYRING_SVC, KEYRING_USER) or ""
        except Exception:
            pass
    if not raw:
        raise RuntimeError(
            "Нет ключа бэкапа. Задайте через keyring (monada-backup/backup-key) "
            "или env MONADA_BACKUP_KEY."
        )
    return base64.urlsafe_b64decode(raw.encode())


def _encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-256-GCM через пакет cryptography."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise RuntimeError("pip install cryptography")
    nonce = _secrets.token_bytes(12)
    ct    = AESGCM(key).encrypt(nonce, plaintext, None)
    # формат: 4-байтовая длина nonce | nonce | ciphertext+tag
    return struct.pack(">I", len(nonce)) + nonce + ct


def _decrypt(blob: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nlen  = struct.unpack(">I", blob[:4])[0]
    nonce = blob[4:4 + nlen]
    ct    = blob[4 + nlen:]
    return AESGCM(key).decrypt(nonce, ct, None)


def create_backup() -> str:
    key = _get_key()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts   = int(time.time())
    pkg  = {}
    for name, path in SOURCES.items():
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                pkg[name] = f.read()
        else:
            pkg[name] = None

    raw_json = json.dumps({
        "ts":      ts,
        "sources": list(SOURCES.keys()),
        "data":    pkg,
    }, ensure_ascii=False).encode("utf-8")

    blob = _encrypt(raw_json, key)
    out  = os.path.join(BACKUP_DIR, f"monada_backup_{ts}.enc")
    with open(out, "wb") as f:
        f.write(blob)

    print(f"[BACKUP] создан: {out} ({len(blob)} байт)")
    return out


def restore_backup(path: str) -> None:
    key = _get_key()
    with open(path, "rb") as f:
        blob = f.read()
    raw  = _decrypt(blob, key)
    pkg  = json.loads(raw.decode("utf-8"))
    data = pkg.get("data", {})
    for name, content in data.items():
        dest = SOURCES.get(name)
        if not dest or content is None:
            continue
        backup_of = dest + f".pre_restore_{int(time.time())}"
        if os.path.exists(dest):
            os.rename(dest, backup_of)
            print(f"[BACKUP] предыдущий {name} → {backup_of}")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[BACKUP] восстановлен: {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Monada холодный бэкап")
    ap.add_argument("--restore", metavar="FILE", help="восстановить из файла .enc")
    args = ap.parse_args()

    if args.restore:
        restore_backup(args.restore)
    else:
        create_backup()


if __name__ == "__main__":
    main()
