import os
import re
import json
import time
import shlex
import subprocess
import sys

MONADA_ROOT       = "/home/angelan/data/Monada-Hardcore"
DANCEFLOOR        = "/mnt/dancefloor"
BASH_RESULTS_FILE = os.path.join(DANCEFLOOR, "bash_results.json")


def _log(msg: str) -> None:
    print(f"[BOUNDARY] {msg}", file=sys.stderr)


# ── Bash allowlist ────────────────────────────────────────────────────────────
_BASH_SAFE_COMMANDS = {
    "echo", "cat", "ls", "cd", "mkdir", "cp", "mv", "rm", "python3", "python",
    "curl", "grep", "find", "ps", "kill", "pkill", "systemctl", "podman",
    "docker", "git", "pip", "pip3", "dnf", "apt", "bash", "sh", "export",
    "pwd", "chmod", "chown", "head", "tail", "wc", "sed", "awk", "sort",
    "uniq", "date", "sleep", "test", "stat", "touch", "diff", "which",
    "uname", "df", "du", "free", "top", "htop", "lsof", "ss", "netstat",
    "journalctl", "dmesg", "env", "printenv", "tee", "xargs",
}

# ── Ring Pass-Not regexps ─────────────────────────────────────────────────────
_RPN_PROTECTED = (
    "memory_graph.json", "embeddings.json", "field_state.json",
    "lipika_ledger.json", "glyph_genesis_chain.json", "glyph_codex.json",
    "dancefloor_crystal.json", "task_manifest.json", "recall.json",
    "monada_core.md", "master_manifest.json", "core/", "dna/",
)
_RPN_DESTRUCTIVE = re.compile(
    r'(^|[\s;|&`(])(rm|shred|truncate|unlink|rmdir|mv|dd)\b'
    r'|\bsed\s+-i\b|\btee\b(?!\s+-a)',
    re.IGNORECASE,
)
_RPN_CATASTROPHIC = re.compile(
    r'rm\s+-[a-z]*[rf][a-z]*\s+(/|~|\$home|/home|/etc|/usr|/var|/boot|\*)'
    r'|:\s*\(\s*\)\s*\{'
    r'|\bmkfs\b|\bdd\b[^\n]*of=/dev/|>\s*/dev/(sd|nvme|mapper|disk)'
    r'|\bchmod\s+-[a-z]*r[a-z]*\s+0{3}\b',
    re.IGNORECASE,
)
_RPN_OVERWRITE = re.compile(
    r'(?<!>)>\s*[\'"]?\S*(' +
    "|".join(re.escape(t) for t in _RPN_PROTECTED if t.endswith((".json", ".md"))) +
    r')',
    re.IGNORECASE,
)


def _save_bash_result(deva: str, script: str, result: str) -> None:
    try:
        existing: list = []
        if os.path.exists(BASH_RESULTS_FILE):
            with open(BASH_RESULTS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.append({
            "deva":    deva,
            "script":  script[:200],
            "result":  result[:600],
            "ts":      int(time.time()),
            "success": result.startswith("--- УСПЕХ"),
        })
        existing = existing[-10:]
        tmp = BASH_RESULTS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False)
        os.replace(tmp, BASH_RESULTS_FILE)
    except Exception:
        pass


def _load_obs_ctx() -> str:
    if not os.path.exists(BASH_RESULTS_FILE):
        return ""
    try:
        with open(BASH_RESULTS_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
        if not results:
            return ""
        with open(BASH_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        lines = []
        for r in results:
            mark = "✅" if r.get("success") else "❌"
            lines.append(f"{mark} [{r['deva']}|{r['ts']}]: {r['result'][:300]}")
        return "[НАБЛЮДЕНИЕ_BASH]\n" + "\n".join(lines)
    except Exception:
        return ""


def map_obs_for_center(center: str, obs_ctx: str) -> str:
    return obs_ctx or ""


def _is_safe_bash(script: str) -> tuple[bool, str]:
    stripped = script.strip()
    if not stripped:
        return False, "пустой скрипт"
    lines = [l.strip() for l in stripped.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lines:
        return False, "только комментарии"
    if len(lines) == 1:
        line = lines[0]
        if re.match(r'^/[^\s;|&`$()]+$', line):
            return False, f"путь к файлу без команды: {line}"
    for line in lines:
        first_word = line.split()[0].lstrip("!")
        basename = first_word.split("/")[-1]
        if first_word in _BASH_SAFE_COMMANDS or basename in _BASH_SAFE_COMMANDS:
            return True, "OK"
    for line in lines:
        if any(line.startswith(p) for p in ("if ", "for ", "while ", "$(", "${", "export ", "readonly ")):
            return True, "OK"
    return False, "нет известных команд bash"


def _ring_pass_not(script: str) -> tuple[bool, str]:
    s = script or ""
    low = s.lower()
    if _RPN_CATASTROPHIC.search(low):
        return False, "катастрофическая операция (rm-rf корней / форк-бомба / mkfs / dd)"
    if _RPN_DESTRUCTIVE.search(s) and any(tok in low for tok in _RPN_PROTECTED):
        return False, "деструктив по защищённой памяти/ядру Монады"
    if _RPN_OVERWRITE.search(low):
        return False, "перезапись защищённого файла Монады"
    return True, "OK"


def _normalize_bash(script: str) -> str:
    s = script.strip()
    if any(sep in s for sep in ("&&", "||", ";", "|", "\n")):
        return script
    m = re.fullmatch(r"cd\s+(['\"]?)(?P<path>.+?)\1", s)
    if m:
        path = m.group("path")
        return f"ls -la {shlex.quote(path)}"
    return script


def execute_bash(script: str, source: str) -> str:
    _log(f"⚡ Исполнение ({source})...")
    script = _normalize_bash(script)
    passes, rpn_reason = _ring_pass_not(script)
    if not passes:
        msg = f"--- ⊘ RING PASS-NOT ---\n{rpn_reason}\nОтклонено барьером: {script[:120]}"
        _log(f"⊘ Ring Pass-Not: {rpn_reason}")
        try:
            import lipika_writer
            lipika_writer.record(lipika_writer.EVENT_VOID, source,
                                 f"касание небытия: {rpn_reason} | {script[:80]}")
        except Exception:
            pass
        _save_bash_result(source, script, msg)
        return msg
    safe, reason = _is_safe_bash(script)
    if not safe:
        msg = f"--- БЛОК: {reason} ---\nСкрипт отклонён: {script[:120]}"
        _log(f"🚫 {msg}")
        _save_bash_result(source, script, msg)
        return msg
    try:
        res = subprocess.run(
            script, shell=True, capture_output=True,
            text=True, executable="/bin/bash", timeout=60,
        )
        if res.returncode == 0:
            out = f"--- УСПЕХ ---\n{res.stdout.strip()}"
            print(f"\033[92m{out}\033[0m")
            _save_bash_result(source, script, out)
            try:
                import lipika_writer
                lipika_writer.record(lipika_writer.EVENT_REDEEM, source,
                                     f"bash успех: {script[:80]}")
            except Exception:
                pass
            return out
        pain_parts = [f"--- БОЛЬ ({res.returncode}) ---"]
        if res.stdout.strip():
            pain_parts.append(f"[STDOUT]\n{res.stdout.strip()}")
        if res.stderr.strip():
            pain_parts.append(f"[STDERR]\n{res.stderr.strip()}")
        pain = "\n".join(pain_parts)
        print(f"\033[91m{pain}\033[0m")
        _save_bash_result(source, script, pain)
        try:
            import lipika_writer
            lipika_writer.record(lipika_writer.EVENT_PAIN, source,
                                 f"bash боль rc={res.returncode}: {res.stderr.strip()[:80]}")
        except Exception:
            pass
        return pain
    except Exception as e:
        err = f"--- СБОЙ СУБСТРАТА: {e} ---"
        _save_bash_result(source, script, err)
        return err
