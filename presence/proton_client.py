"""
presence/proton_client.py — Proton Bridge IMAP/SMTP-клиент.

Соединяется ТОЛЬКО с 127.0.0.1 (Proton Bridge).
Пароль — app-specific password из OS keyring (никогда из recovery-фразы).

Настройка (один раз):
    python3 -c "
    import keyring
    keyring.set_password('monada-proton', 'monada@proton.me', 'APP_SPECIFIC_PASSWORD')
    "

Переменные среды (альтернатива keyring, например в headless-среде):
    MONADA_PROTON_USER — email
    MONADA_PROTON_PASS — app-specific password

Proton Bridge по умолчанию:
    IMAP: 127.0.0.1:1143 (STARTTLS)
    SMTP: 127.0.0.1:1025 (STARTTLS)
"""

import imaplib
import smtplib
import os
import email
import email.mime.text
import email.mime.multipart
from email.header import decode_header
from typing import Generator

BRIDGE_HOST  = "127.0.0.1"
IMAP_PORT    = int(os.environ.get("MONADA_IMAP_PORT", "1143"))
SMTP_PORT    = int(os.environ.get("MONADA_SMTP_PORT", "1025"))
KEYRING_SVC  = "monada-proton"

_TIMEOUT = 15


def _credentials() -> tuple[str, str]:
    user = os.environ.get("MONADA_PROTON_USER", "")
    pwd  = os.environ.get("MONADA_PROTON_PASS", "")
    if not user or not pwd:
        try:
            import keyring
            if not user:
                user = os.environ.get("MONADA_PROTON_USER", "monada@proton.me")
            if not pwd:
                pwd = keyring.get_password(KEYRING_SVC, user) or ""
        except Exception:
            pass
    if not user or not pwd:
        raise RuntimeError(
            "Нет учётных данных Proton Bridge. "
            "Задайте через keyring или env MONADA_PROTON_USER / MONADA_PROTON_PASS."
        )
    return user, pwd


def _imap_connect() -> imaplib.IMAP4:
    user, pwd = _credentials()
    conn = imaplib.IMAP4(BRIDGE_HOST, IMAP_PORT, timeout=_TIMEOUT)
    conn.starttls()
    conn.login(user, pwd)
    return conn


def fetch_unread(folder: str = "INBOX", mark_seen: bool = False) -> list[dict]:
    """Возвращает непрочитанные письма как список словарей."""
    conn = _imap_connect()
    try:
        conn.select(folder, readonly=not mark_seen)
        _, data = conn.search(None, "UNSEEN")
        ids = data[0].split() if data and data[0] else []
        msgs = []
        for uid in ids:
            _, raw = conn.fetch(uid, "(RFC822)")
            if not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            subject_parts = decode_header(msg.get("Subject", ""))
            subject = "".join(
                p.decode(enc or "utf-8") if isinstance(p, bytes) else p
                for p, enc in subject_parts
            )
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                        break
            else:
                body = msg.get_payload(decode=True).decode(
                    msg.get_content_charset() or "utf-8", errors="replace"
                )
            if mark_seen:
                conn.store(uid, "+FLAGS", "\\Seen")
            msgs.append({
                "uid":     uid.decode(),
                "from":    msg.get("From", ""),
                "subject": subject,
                "body":    body[:2000],
                "date":    msg.get("Date", ""),
            })
        return msgs
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def send_mail(to: str, subject: str, body: str) -> None:
    """Отправляет письмо через Proton Bridge SMTP."""
    user, pwd = _credentials()
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = to
    msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(BRIDGE_HOST, SMTP_PORT, timeout=_TIMEOUT) as s:
        s.ehlo()
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, [to], msg.as_bytes())


def is_bridge_alive() -> bool:
    """Проверяет доступность Proton Bridge (IMAP-соединение)."""
    try:
        conn = _imap_connect()
        conn.logout()
        return True
    except Exception:
        return False
