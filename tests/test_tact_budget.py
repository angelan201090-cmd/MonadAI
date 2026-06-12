"""
tests/test_tact_budget.py — Phase 6: проверка бюджета такта и инвариантов Монады.

Запуск (из корня Monada-Hardcore):
    python3 -m pytest tests/test_tact_budget.py -v
    # или без pytest:
    python3 tests/test_tact_budget.py

Тесты не требуют живых LLM-портов — все сетевые вызовы мокируются.
"""

import sys
import os
import json
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, "/home/angelan/data/Monada-Hardcore")


# ─────────────────────────────────────────────────────────────────────────────
# T1: Бюджет такта — архитектурные гарантии
# ─────────────────────────────────────────────────────────────────────────────
class TestTactBudget(unittest.TestCase):

    def test_fohatic_spiral_has_6_planes(self):
        """Спираль Фохата содержит ровно 6 плоскостей → 6 LLM-вызовов в Триаде."""
        from core.soc_engine import FOHATIC_SPIRAL_ORDER
        self.assertEqual(len(FOHATIC_SPIRAL_ORDER), 6,
                         f"Ожидали 6 плоскостей, получили {len(FOHATIC_SPIRAL_ORDER)}")

    def test_fohatic_spiral_values(self):
        """FOHATIC_SPIRAL_ORDER — ID слотов карты; FOHAT_CHAIN — порядок исполнения."""
        from core.soc_engine import FOHATIC_SPIRAL_ORDER
        from core.janus_conductor import FOHAT_CHAIN

        # Это разные понятия: слоты plane-map идут 1..6, а цепь хранит Дэвов.
        self.assertEqual(list(FOHATIC_SPIRAL_ORDER), [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            [deva for _, deva, _ in FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )

    def test_pre_janus_identity_blocks_diagnostics(self):
        from core.janus_conductor import _pre_janus_frame

        frame = _pre_janus_frame("кто ты?")
        self.assertEqual(frame["intent"], "identity")
        self.assertEqual(frame["mode"], "introspection")
        self.assertFalse(frame["diagnostic_authorized"])
        self.assertFalse(frame["action_authorized"])
        self.assertFalse(frame["bash_authorized"])

    def test_pre_janus_identity_body_stays_on_identity(self):
        from core.janus_conductor import _pre_janus_frame

        body_task = _pre_janus_frame("кто ты?")["micro_tasks"]["Body"]
        self.assertIn("MirAI", body_task)
        self.assertIn("software/AI system", body_task)
        self.assertIn("Monada-Hardcore", body_task)
        self.assertIn("not a generic esoteric Monad", body_task)
        self.assertIn("action='none'", body_task)
        self.assertIn("No bash, no files, no ports, no RAM", body_task)
        self.assertNotIn("free -h", body_task)
        self.assertNotIn("ss -tlnp", body_task)

    def test_pre_janus_identity_has_project_anchor(self):
        from core.janus_conductor import _pre_janus_frame

        frame = _pre_janus_frame("кто ты?")
        self.assertEqual(
            frame["identity_anchor"],
            "MirAI is a local multi-node AI system running Monada-Hardcore; "
            "not a human personality, not alive, not a generic esoteric Monad; "
            "it is a software/AI system with local roles.",
        )
        for task in frame["micro_tasks"].values():
            self.assertIn("MirAI", task)
            self.assertIn("software/AI system", task)
            self.assertIn("Monada-Hardcore", task)
            self.assertIn("not a generic esoteric Monad", task)

    def test_identity_trigger_expansion(self):
        from core.janus_conductor import _pre_janus_frame

        for text in (
            "ты личность?", "ты программа?", "ты живая?",
            "чем ты являешься", "какова твоя природа",
        ):
            frame = _pre_janus_frame(text)
            self.assertEqual(frame["intent"], "identity", text)
            self.assertEqual(frame["mode"], "introspection", text)

    def test_identity_low_grounding_bypasses_kill_switch(self):
        from core.janus_conductor import (
            _identity_low_grounding_allowed, _pre_janus_frame,
            _should_trigger_grounding_kill_switch,
        )

        identity = _pre_janus_frame("ты программа?")
        diagnostic = _pre_janus_frame("проверь порты")
        self.assertTrue(_identity_low_grounding_allowed(identity))
        self.assertFalse(_identity_low_grounding_allowed(diagnostic))
        self.assertFalse(_should_trigger_grounding_kill_switch(
            0.20, repair_tact=False, pre_janus_frame=identity,
        ))
        self.assertTrue(_should_trigger_grounding_kill_switch(
            0.20, repair_tact=False, pre_janus_frame=diagnostic,
        ))

    def test_identity_context_strips_system_contamination(self):
        from core.janus_conductor import _strip_identity_contamination

        dirty = (
            "MirAI — программная система.\n"
            "/home/angelan/data/Monada-Hardcore\n"
            "/mnt/dancefloor/field_state.json\n"
            "ports RAM bash consciousness logs audit find\n"
            "Локальные роли образуют многоузловую архитектуру."
        )
        result = _strip_identity_contamination(dirty, "ты личность?")
        self.assertIn("MirAI", result)
        self.assertIn("Локальные роли", result)
        for marker in (
            "/home/", "/mnt/", "field_state.json", "ports", "RAM",
            "bash", "consciousness logs", "audit", "find",
        ):
            self.assertNotIn(marker, result)

    def test_identity_empty_synthesis_uses_deterministic_fallback(self):
        from core.janus_conductor import (
            _IDENTITY_FALLBACK, _finalize_synthesis_for_mode, _pre_janus_frame,
        )

        result = _finalize_synthesis_for_mode(
            "bash /home/angelan/check.sh", "RAM ports", "",
            _pre_janus_frame("ты живая?"),
        )
        self.assertEqual(result, _IDENTITY_FALLBACK)

    def test_pre_janus_diagnostic_authorizes_safe_checks(self):
        from core.janus_conductor import _pre_janus_frame

        frame = _pre_janus_frame("проверь порты и память")
        self.assertEqual(frame["intent"], "diagnostic")
        self.assertTrue(frame["diagnostic_authorized"])
        self.assertIn("free -h", frame["micro_tasks"]["Body"])
        self.assertIn("ss -tlnp", frame["micro_tasks"]["Body"])

    def test_pre_janus_enabled_is_deterministic(self):
        import core.janus_conductor as jc

        self.assertTrue(jc.PRE_JANUS_ENABLED)
        with patch.object(jc, "_http_post") as http_post:
            frame = jc._pre_janus_frame("кто ты?")
            manifest = jc._decompose_from_micro_tasks(
                frame["micro_tasks"],
                ["Head", "Heart", "Body"],
                "кто ты?",
                "",
            )
        http_post.assert_not_called()
        self.assertEqual(
            manifest["subtasks"]["Body"],
            frame["micro_tasks"]["Body"],
        )

    def test_pre_janus_identity_blocks_body_bash(self):
        from core.janus_conductor import (
            _pre_janus_allows_action,
            _pre_janus_allows_bash,
            _pre_janus_frame,
        )

        frame = _pre_janus_frame("кто ты?")
        self.assertFalse(_pre_janus_allows_bash(frame))
        self.assertFalse(_pre_janus_allows_action(frame))

    def test_pre_janus_identity_strips_system_status_claims(self):
        from core.janus_conductor import _strip_system_status_claims

        result = _strip_system_status_claims(
            "Я — Монада.\n\nRAM 87%, порт 8083 активен.\n\n```bash\nfree -h\n```",
            "системная диагностика не запрашивалась",
        )
        self.assertIn("Я — Монада.", result)
        self.assertIn("системная диагностика не запрашивалась", result)
        self.assertNotIn("87%", result)
        self.assertNotIn("8083", result)
        self.assertNotIn("free -h", result)

    def test_pre_janus_diagnostic_allows_body_bash(self):
        from core.janus_conductor import (
            _pre_janus_allows_action,
            _pre_janus_allows_bash,
            _pre_janus_frame,
        )

        frame = _pre_janus_frame("проверь порты и память")
        self.assertTrue(_pre_janus_allows_bash(frame))
        self.assertTrue(_pre_janus_allows_action(frame))

    def test_introspection_filter_removes_outward_action_proposals(self):
        from core.janus_conductor import _strip_outward_action_proposals

        result = _strip_outward_action_proposals(
            "Я — MirAI.\n\nЗапустить bash-скрипт /home/angelan/check.sh.",
            "в режиме самонаблюдения внешние действия не запрашивались",
        )
        self.assertIn("Я — MirAI.", result)
        self.assertIn(
            "в режиме самонаблюдения внешние действия не запрашивались",
            result,
        )
        self.assertNotIn("/home/", result)
        self.assertNotIn("bash", result)

    def test_introspection_final_preserves_identity_content(self):
        from core.janus_conductor import (
            _finalize_synthesis_for_mode,
            _pre_janus_frame,
        )

        result = _finalize_synthesis_for_mode(
            "Я — MirAI, локальная система архитектуры Monada-Hardcore.",
            "Persona описывает MirAI.",
            "",
            _pre_janus_frame("кто ты?"),
        )
        self.assertIn("MirAI", result)
        self.assertIn("Monada-Hardcore", result)

    def test_introspection_final_filters_actions_and_falls_back_to_persona(self):
        from core.janus_conductor import (
            _finalize_synthesis_for_mode,
            _pre_janus_frame,
        )

        result = _finalize_synthesis_for_mode(
            "Запустить bash-скрипт /home/angelan/check.sh для RAM и портов.",
            "Я — MirAI внутри Monada-Hardcore.",
            "",
            _pre_janus_frame("кто ты?"),
        )
        self.assertEqual(result, "Я — MirAI внутри Monada-Hardcore.")
        for forbidden in ("RAM", "порт", "bash", "скрипт", "/home/"):
            self.assertNotIn(forbidden, result)

    def test_introspection_final_filters_verification_fragments(self):
        from core.janus_conductor import (
            _finalize_synthesis_for_mode,
            _pre_janus_frame,
        )

        result = _finalize_synthesis_for_mode(
            "Я — MirAI внутри Monada-Hardcore.\n\n"
            "Нужно проверить BASH_FACTS, пути и имена файлов, чтобы убедиться.",
            "Persona описывает MirAI внутри Monada-Hardcore.",
            "",
            _pre_janus_frame("кто ты?"),
        )
        self.assertEqual(result, "Я — MirAI внутри Monada-Hardcore.")
        for forbidden in (
            "BASH_FACTS", "пути", "имена файлов", "файлы",
            "убедиться", "проверить", "проверка",
        ):
            self.assertNotIn(forbidden, result)

    def test_diagnostic_without_bash_facts_gets_warning(self):
        from core.janus_conductor import (
            _finalize_synthesis_for_mode,
            _pre_janus_frame,
        )

        result = _finalize_synthesis_for_mode(
            "RAM заполнена, порт 8083 активен.",
            "Persona",
            "",
            _pre_janus_frame("проверь порты и память"),
        )
        self.assertEqual(
            result,
            "нет BASH_FACTS для проверки системного состояния",
        )
        self.assertIn("BASH_FACTS", result)
        self.assertIn("проверки", result)

    def test_dyad_persona_shadow_share_endpoint(self):
        """ПЕРСОНА и ТЕНЬ делят один llama-server (8084, shared Gemma); Синтез отдельно (8086).

        Экономия RAM: вместо трёх серверов 8084/8085/8086 поднимаем два эндпоинта.
        Персона и Тень адресуются на один порт, Синтез — на отдельный.
        """
        from core.janus_conductor import PERSONA_URL, SHADOW_URL, SYNTHESIS_URL
        ports = {
            int(u.split(":")[2].split("/")[0])
            for u in (PERSONA_URL, SHADOW_URL, SYNTHESIS_URL)
        }
        # 8085 больше не используется — Персона и Тень делят 8084
        self.assertEqual(ports, {8084, 8086},
                         f"Ожидали порты 8084 (Персона+Тень) и 8086 (Синтез), получили {ports}")
        # Персона и Тень — один эндпоинт
        self.assertEqual(PERSONA_URL, SHADOW_URL,
                         "Персона и Тень должны делить один shared-Gemma эндпоинт")
        # Синтез — отдельный эндпоинт
        self.assertNotEqual(SYNTHESIS_URL, PERSONA_URL,
                            "Синтез должен оставаться на отдельном порту 8086")
        # различных эндпоинтов ровно 2
        self.assertEqual(len({PERSONA_URL, SHADOW_URL, SYNTHESIS_URL}), 2)

    def test_persona_and_shadow_both_called_logically(self):
        """Несмотря на общий эндпоинт, Персона и Тень вызываются как две отдельные фазы."""
        import inspect
        from core.janus_conductor import janus_dyad
        src = inspect.getsource(janus_dyad)
        # обе фазы делают свой _http_post: Персона → PERSONA_URL, Тень → SHADOW_URL
        self.assertIn("_http_post(PERSONA_URL", src,
                      "Фаза Персоны должна делать отдельный вызов на PERSONA_URL")
        self.assertIn("_http_post(SHADOW_URL", src,
                      "Фаза Тени должна делать отдельный вызов на SHADOW_URL")

    def test_persona_shadow_runtime_configuration(self):
        """Shared model/port remain fixed; Shadow sampling is more exploratory."""
        import re
        from pathlib import Path
        import core.janus_conductor as jc

        launcher = Path("/home/angelan/data/Monada-Hardcore/monada_on_geptarchy.sh").read_text()
        expected_models = {
            "MODEL_UM": "$MODELS_DIR/microsoft_Phi-4-mini-instruct-IQ4_NL.gguf",
            "MODEL_SERDCE": "$MODELS_DIR/gemma-3-4b-it-heretic-iq4_nl-imat.gguf",
            "MODEL_TELO": "$MODELS_DIR/granite-4.0-h-micro-UD-Q6_K_XL.gguf",
            "MODEL_PERSONA": "/home/angelan/models/monadaAI/Llama-3.3-8B-Instruct-128K-absolute-heresy.IQ4_XS.gguf",
            "MODEL_SINTEZ": "$MODELS_DIR/SmolLM3-3B-IQ4_NL.gguf",
        }
        configured_models = dict(re.findall(
            r'^(MODEL_(?:UM|SERDCE|TELO|PERSONA|SINTEZ))="([^"]+)"$',
            launcher,
            re.MULTILINE,
        ))

        self.assertEqual(configured_models, expected_models)
        self.assertIn('start_server "PERSONA" 8084 "$MODEL_PERSONA" 4096', launcher)
        self.assertIn("lemonade load nomic-embed-text-v1-GGUF", launcher)
        self.assertEqual(jc.PERSONA_URL, jc.SHADOW_URL)
        self.assertIn(":8084/", jc.PERSONA_URL)
        self.assertEqual(jc.PERSONA_TEMPERATURE, 0.15)
        self.assertEqual(jc.SHADOW_TEMPERATURE, 0.25)
        self.assertGreater(jc.SHADOW_TEMPERATURE, jc.PERSONA_TEMPERATURE)

    def test_triada_plus_dyad_max_9_calls(self):
        """Совокупный бюджет: 6 (Триада/спираль) + 3 (Диада) = 9 вызовов."""
        from core.soc_engine import FOHATIC_SPIRAL_ORDER
        triada = len(FOHATIC_SPIRAL_ORDER)   # 6
        dyad   = 3                            # Персона + Тень + Синтез
        self.assertLessEqual(triada + dyad, 9,
                             f"Бюджет превышен: {triada}+{dyad}={triada+dyad} > 9")

    def test_http_post_mock_counts_calls(self):
        """Интеграционный: conduct() с мок-HTTP делает ≤ 9 LLM-запросов."""
        import core.janus_conductor as jc

        self.assertTrue(jc.PRE_JANUS_ENABLED)
        stub_ok = json.dumps({
            "choices": [{"message": {"content": "ᛁ тест"}}]
        })
        call_counter = {"n": 0}

        def _mock_post(url, payload, timeout=30):
            call_counter["n"] += 1
            return stub_ok

        # Мокируем файловую систему (dancefloor в tmpfs может не монтироваться)
        dummy_state = {
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "TEST",
        }

        with (
            patch.object(jc, "_http_post", side_effect=_mock_post),
            patch("builtins.open", unittest.mock.mock_open(
                read_data=json.dumps(dummy_state))),
            patch("os.path.exists", return_value=True),
            patch("os.makedirs"),
            patch("os.replace"),
        ):
            try:
                jc.conduct("тестовая задача")
            except Exception:
                pass  # нас интересует только счётчик вызовов

        self.assertLessEqual(
            call_counter["n"], 9,
            f"LLM-вызовов за такт: {call_counter['n']}, ожидали ≤ 9"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T2: Ring Pass-Not — барьер защиты памяти
# ─────────────────────────────────────────────────────────────────────────────
class TestRingPassNot(unittest.TestCase):

    def setUp(self):
        from core.boundary import _ring_pass_not, _is_safe_bash
        self._rpn = _ring_pass_not
        self._safe = _is_safe_bash

    # ── Катастрофические операции ────────────────────────────────────────────
    def test_blocks_rm_rf_root(self):
        ok, _ = self._rpn("rm -rf /")
        self.assertFalse(ok)

    def test_blocks_rm_rf_home(self):
        ok, _ = self._rpn("rm -rf /home")
        self.assertFalse(ok)

    def test_blocks_fork_bomb(self):
        ok, _ = self._rpn(":(){:|:&};:")
        self.assertFalse(ok)

    def test_blocks_dd_overwrite_disk(self):
        ok, _ = self._rpn("dd if=/dev/zero of=/dev/sda")
        self.assertFalse(ok)

    # ── Деструктив по защищённым файлам ─────────────────────────────────────
    def test_blocks_rm_memory_graph(self):
        ok, _ = self._rpn("rm memory_graph.json")
        self.assertFalse(ok)

    def test_blocks_rm_lipika_ledger(self):
        ok, _ = self._rpn("rm lipika_ledger.json")
        self.assertFalse(ok)

    def test_blocks_overwrite_field_state(self):
        ok, _ = self._rpn("echo '' > field_state.json")
        self.assertFalse(ok)

    def test_blocks_overwrite_glyph_codex(self):
        ok, _ = self._rpn("cat /dev/null > glyph_codex.json")
        self.assertFalse(ok)

    def test_blocks_sed_inplace_core(self):
        ok, _ = self._rpn("sed -i 's/foo/bar/' monada_core.md")
        self.assertFalse(ok)

    # ── Безопасные операции — должны проходить ───────────────────────────────
    def test_allows_ls(self):
        ok, _ = self._rpn("ls /tmp")
        self.assertTrue(ok)

    def test_allows_echo(self):
        ok, _ = self._rpn("echo hello")
        self.assertTrue(ok)

    def test_allows_cat_unprotected(self):
        ok, _ = self._rpn("cat /tmp/output.txt")
        self.assertTrue(ok)

    def test_allows_mkdir(self):
        ok, _ = self._rpn("mkdir -p /tmp/test_dir")
        self.assertTrue(ok)

    def test_allows_python3(self):
        ok, _ = self._rpn("python3 /tmp/script.py")
        self.assertTrue(ok)

    # ── _is_safe_bash allowlist ──────────────────────────────────────────────
    def test_safe_bash_ls(self):
        ok, _ = self._safe("ls /home")
        self.assertTrue(ok)

    def test_safe_bash_python(self):
        ok, _ = self._safe("python3 script.py")
        self.assertTrue(ok)

    def test_safe_bash_blocks_bare_path(self):
        ok, _ = self._safe("/home/angelan/secret")
        self.assertFalse(ok)

    def test_safe_bash_blocks_empty(self):
        ok, _ = self._safe("")
        self.assertFalse(ok)

    def test_safe_bash_blocks_comments_only(self):
        ok, _ = self._safe("# just a comment")
        self.assertFalse(ok)


# ─────────────────────────────────────────────────────────────────────────────
# T3: Липика — PAIN/REDEEM при bash-вызовах
# ─────────────────────────────────────────────────────────────────────────────
class TestLipikaEvents(unittest.TestCase):

    def _run_bash_with_mock(self, returncode: int, stdout: str = "", stderr: str = ""):
        """Запускает execute_bash с мок-subprocess и захватывает вызовы lipika_writer.record."""
        import core.boundary as boundary

        proc_mock = MagicMock()
        proc_mock.returncode = returncode
        proc_mock.stdout = stdout
        proc_mock.stderr = stderr

        recorded = []

        lw_mock = MagicMock()
        lw_mock.EVENT_PAIN   = "PAIN"
        lw_mock.EVENT_REDEEM = "REDEEM"
        lw_mock.EVENT_VOID   = "VOID"
        lw_mock.record.side_effect = lambda *a, **kw: recorded.append(a)

        with (
            patch("subprocess.run", return_value=proc_mock),
            patch.dict("sys.modules", {"lipika_writer": lw_mock}),
        ):
            result = boundary.execute_bash("echo test", source="pytest")

        return result, recorded

    def test_pain_written_on_bash_failure(self):
        result, recorded = self._run_bash_with_mock(returncode=1, stderr="command not found")
        self.assertIn("БОЛЬ", result)
        events = [r[0] for r in recorded]
        self.assertIn("PAIN", events, f"PAIN не записан в Липику. Записи: {events}")

    def test_redeem_written_on_bash_success(self):
        result, recorded = self._run_bash_with_mock(returncode=0, stdout="hello world")
        self.assertIn("УСПЕХ", result)
        events = [r[0] for r in recorded]
        self.assertIn("REDEEM", events, f"REDEEM не записан в Липику. Записи: {events}")

    def test_void_written_on_ring_pass_not(self):
        """Ring Pass-Not → EVENT_VOID."""
        import core.boundary as boundary

        recorded = []
        lw_mock = MagicMock()
        lw_mock.EVENT_VOID   = "VOID"
        lw_mock.EVENT_PAIN   = "PAIN"
        lw_mock.EVENT_REDEEM = "REDEEM"
        lw_mock.record.side_effect = lambda *a, **kw: recorded.append(a)

        with patch.dict("sys.modules", {"lipika_writer": lw_mock}):
            result = boundary.execute_bash("rm -rf /", source="pytest")

        self.assertIn("RING PASS-NOT", result)
        events = [r[0] for r in recorded]
        self.assertIn("VOID", events, f"VOID не записан при RPN. Записи: {events}")

    def test_no_lipika_on_blocked_safe_check(self):
        """Блок safe-check (не RPN) не пишет в Липику."""
        import core.boundary as boundary

        recorded = []
        lw_mock = MagicMock()
        lw_mock.record.side_effect = lambda *a, **kw: recorded.append(a)

        with patch.dict("sys.modules", {"lipika_writer": lw_mock}):
            result = boundary.execute_bash("/etc/passwd", source="pytest")

        self.assertIn("БЛОК", result)
        # safe-check не пишет PAIN/VOID — это не ошибка исполнения
        self.assertEqual(len(recorded), 0, f"Неожиданные записи Липики: {recorded}")


# ─────────────────────────────────────────────────────────────────────────────
# T4: AAS-пруниг — HOT-слой
# ─────────────────────────────────────────────────────────────────────────────
class TestAasPrune(unittest.TestCase):

    def _make_entries(self, n: int, prefix: str = "запись") -> list:
        return [{"text": f"{prefix} номер {i}", "type": "INFO", "cycle": i}
                for i in range(n)]

    def _run_prune_with_state(self, mem: list) -> dict:
        import podsoznanie_daemon as pd

        state = {"cycle": 1, "shared_memory": mem}
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(state, tmp)
        tmp.close()

        with patch.object(pd, "FIELD_STATE", tmp.name):
            pd._aas_prune()

        with open(tmp.name, encoding="utf-8") as f:
            result = json.load(f)
        os.unlink(tmp.name)
        return result

    def test_no_prune_below_threshold(self):
        """Меньше AAS_MAX записей → ничего не трогаем."""
        import podsoznanie_daemon as pd
        mem = self._make_entries(pd.AAS_MAX - 1)
        result = self._run_prune_with_state(mem)
        self.assertEqual(len(result["shared_memory"]), pd.AAS_MAX - 1)

    def test_prune_to_target(self):
        """Больше AAS_MAX → прунируем до AAS_TARGET."""
        import podsoznanie_daemon as pd
        mem = self._make_entries(pd.AAS_MAX + 10)
        result = self._run_prune_with_state(mem)
        self.assertLessEqual(len(result["shared_memory"]), pd.AAS_TARGET)

    def test_pain_entries_survive_prune(self):
        """PAIN-записи с уникальным содержанием должны выживать при прунинге."""
        import podsoznanie_daemon as pd
        # Много одинаковых INFO (избыточные), одна уникальная PAIN
        mem = [{"text": "повтор одинаковый текст для избыточности", "type": "INFO"}
               for _ in range(pd.AAS_MAX + 5)]
        mem.append({"text": "критическая ошибка уникальная запись боли", "type": "PAIN"})
        result = self._run_prune_with_state(mem)
        pain_entries = [e for e in result["shared_memory"]
                        if "PAIN" in str(e.get("type", "")).upper()]
        self.assertTrue(len(pain_entries) > 0,
                        "PAIN-запись не выжила при AAS-прунинге")

    def test_exact_aas_max_triggers_prune(self):
        """Ровно AAS_MAX + 1 → запускается пруниг."""
        import podsoznanie_daemon as pd
        mem = self._make_entries(pd.AAS_MAX + 1)
        result = self._run_prune_with_state(mem)
        self.assertLess(len(result["shared_memory"]), pd.AAS_MAX + 1)


# ─────────────────────────────────────────────────────────────────────────────
# T5: Структурные инварианты
# ─────────────────────────────────────────────────────────────────────────────
class TestStructuralInvariants(unittest.TestCase):

    def test_conductor_exposes_tact_and_run(self):
        """core/conductor.py обязан экспортировать Conductor.tact и Conductor.run."""
        from core.conductor import Conductor
        c = Conductor()
        self.assertTrue(callable(c.tact))
        self.assertTrue(callable(c.run))

    def test_boundary_exports_all_symbols(self):
        """core/boundary.py должен экспортировать все публичные символы."""
        from core.boundary import (
            execute_bash, _is_safe_bash, _ring_pass_not,
            _normalize_bash, _save_bash_result, _load_obs_ctx,
        )
        for sym in (execute_bash, _is_safe_bash, _ring_pass_not,
                    _normalize_bash, _save_bash_result, _load_obs_ctx):
            self.assertTrue(callable(sym))

    def test_presence_package_importable(self):
        """presence/ — корректный Python-пакет."""
        import presence
        from presence import proton_client, inbox_watcher, cold_backup
        self.assertTrue(True)

    def test_aas_constants_sane(self):
        """AAS_TARGET < AAS_MAX, PAIN_BOOST > 1."""
        import podsoznanie_daemon as pd
        self.assertLess(pd.AAS_TARGET, pd.AAS_MAX)
        self.assertGreater(pd.PAIN_BOOST, 1.0)

    def test_stellar_interval_sane(self):
        """STELLAR_INTERVAL_SEC ≥ 3600 (минимум час)."""
        import podsoznanie_daemon as pd
        self.assertGreaterEqual(pd.STELLAR_INTERVAL_SEC, 3600)


# ─────────────────────────────────────────────────────────────────────────────
# v39.0: ThoughtSeed / ThoughtState / ThoughtDelta — слой наблюдения за мыслью
# ─────────────────────────────────────────────────────────────────────────────
class TestThoughtState(unittest.TestCase):

    def test_seed_from_pre_janus_identity_frame(self):
        """ThoughtSeed создаётся из PRE-JANUS identity frame."""
        from core.janus_conductor import _pre_janus_frame, make_thought_seed
        frame = _pre_janus_frame("кто ты?")
        seed = make_thought_seed("кто ты?", frame)
        self.assertEqual(seed["intent"], "identity")
        self.assertEqual(seed["mode"], "introspection")
        self.assertEqual(seed["archetype"], "Identity")
        self.assertEqual(seed["question"], "кто ты?")
        self.assertFalse(seed["diagnostic_authorized"])
        self.assertFalse(seed["action_authorized"])
        self.assertFalse(seed["bash_authorized"])
        self.assertEqual(set(seed["micro_tasks"]), {"Head", "Heart", "Body"})
        self.assertIn("MirAI", seed["micro_tasks"]["Head"])

    def test_seed_fallback_without_pre_janus(self):
        """Fallback ThoughtSeed детерминирован и создаётся без PRE-JANUS."""
        from core.janus_conductor import make_thought_seed
        seed = make_thought_seed("проверь систему", None)
        seed2 = make_thought_seed("проверь систему", None)
        self.assertEqual(seed, seed2)
        self.assertEqual(seed["intent"], "fallback")
        self.assertEqual(seed["question"], "проверь систему")
        # Зеркалит разрешения disabled-пути conduct()
        self.assertTrue(seed["bash_authorized"])
        for c in ("Head", "Heart", "Body"):
            self.assertTrue(seed["micro_tasks"][c])
        # Frame без micro_tasks → тоже fallback
        broken = make_thought_seed("x", {"intent": "disabled", "micro_tasks": {}})
        self.assertEqual(broken["intent"], "fallback")

    def test_thought_state_is_bounded(self):
        """claims ≤ 7, open ≤ 7, constraints ≤ 7, trace ≤ 12 — при любом числе дельт."""
        from core.janus_conductor import (
            make_thought_seed, make_thought_state,
            compute_thought_delta, apply_thought_delta,
        )
        ts = make_thought_state(make_thought_seed("x", None))
        for i in range(20):
            delta = compute_thought_delta(
                deva=f"Deva{i}", center="Body",
                artifact="БОЛЬ: ошибка, но порт 8081 жив, RAM в норме",
                rune="ᛁ", action="bash", bash_success=True,
                repeated=False, mode="introspection",
                diagnostic_authorized=False,
            )
            apply_thought_delta(ts, delta)
        self.assertLessEqual(len(ts["claims"]), 7)
        self.assertLessEqual(len(ts["open"]), 7)
        self.assertLessEqual(len(ts["constraints"]), 7)
        self.assertLessEqual(len(ts["trace"]), 12)
        for v in ts["metrics"].values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_pain_delta_raises_risk_lowers_confidence(self):
        """БОЛЬ/VETO/ошибка/галлюцинация → risk +0.2, confidence -0.1, open добавлен."""
        from core.janus_conductor import compute_thought_delta
        delta = compute_thought_delta(
            deva="Shani", center="Head",
            artifact="БОЛЬ: галлюцинация в выводе",
            rune="ᛁ", action="none",
        )
        self.assertGreaterEqual(delta["metric_delta"]["risk"], 0.2)
        self.assertLessEqual(delta["metric_delta"]["confidence"], -0.1)
        self.assertTrue(delta["open"])
        self.assertIn("pain", delta["reason"])

    def test_bash_success_delta_raises_grounding(self):
        """bash success → grounding +0.2, confidence +0.1, claim добавлен."""
        from core.janus_conductor import compute_thought_delta
        delta = compute_thought_delta(
            deva="Mangala", center="Body",
            artifact="ls -1 /tmp", rune="ᛃ", action="bash",
            bash_success=True, diagnostic_authorized=True,
        )
        self.assertAlmostEqual(delta["metric_delta"]["grounding"], 0.2)
        self.assertAlmostEqual(delta["metric_delta"]["confidence"], 0.1)
        self.assertTrue(delta["claim"])
        self.assertIn("bash_success", delta["reason"])

    def test_introspection_identity_delta(self):
        """Introspection + MirAI artifact without outward actions boosts coherence."""
        from core.janus_conductor import compute_thought_delta
        delta = compute_thought_delta(
            deva="Chandra", center="Heart",
            artifact="MirAI — локальная система Monada-Hardcore; роль Сердца внутренняя.",
            rune="ᛃ", action="none",
            mode="introspection", diagnostic_authorized=False,
        )
        self.assertAlmostEqual(delta["metric_delta"]["coherence"], 0.1)
        self.assertAlmostEqual(delta["metric_delta"]["confidence"], 0.05)
        self.assertIn("introspective_identity", delta["reason"])

    def test_unauthorized_diagnostic_adds_constraint(self):
        """diagnostic_authorized=False + bash/порты/RAM → constraint + risk."""
        from core.janus_conductor import (
            compute_thought_delta, apply_thought_delta,
            make_thought_seed, make_thought_state,
        )
        delta = compute_thought_delta(
            deva="Mangala", center="Body",
            artifact="Проверь порты: ss -tlnp и free -h, RAM 95%",
            rune="ᛃ", action="none",
            mode="introspection", diagnostic_authorized=False,
        )
        self.assertEqual(delta["constraint"], "outward action blocked by introspection")
        self.assertGreaterEqual(delta["metric_delta"]["risk"], 0.2)
        ts = make_thought_state(make_thought_seed("кто ты?", None))
        apply_thought_delta(ts, delta)
        self.assertIn("outward action blocked by introspection", ts["constraints"])

    def test_last_thought_state_is_compact(self):
        """compact_thought_state не содержит artifact-тел и длинных строк."""
        from core.janus_conductor import (
            make_thought_seed, make_thought_state, compute_thought_delta,
            apply_thought_delta, compact_thought_state, THOUGHT_FIELD_MAXLEN,
        )
        ts = make_thought_state(make_thought_seed("задача " * 100, None))
        # «секрет» вместо «ошибка»: v40.1 легитимно извлекает open-фрагменты
        # по маркеру «ошибка»; тест проверяет утечку ТЕЛА, а не экстракцию.
        big_artifact = "UNIQUEMARKER секрет " * 300
        delta = compute_thought_delta(
            deva="Budha", center="Head", artifact=big_artifact,
            rune="ᛁ", action="none",
        )
        apply_thought_delta(ts, delta)
        ts["claims"].append("x" * 1000)
        compact = compact_thought_state(ts)
        dumped = json.dumps(compact, ensure_ascii=False)
        # Большой artifact-текст не утёк в compact-форму
        self.assertNotIn("UNIQUEMARKER", dumped)
        self.assertLess(len(dumped), 6000)
        for c in compact["claims"]:
            self.assertLessEqual(len(c), THOUGHT_FIELD_MAXLEN)
        self.assertLessEqual(len(compact["seed"]["question"]), 200)
        for mt in compact["seed"]["micro_tasks"].values():
            self.assertLessEqual(len(mt), 80)

    def test_flag_off_keeps_conduct_path(self):
        """THOUGHT_STATE_ENABLED=False: слой выключен, conduct-путь под guard'ами."""
        import inspect
        import core.janus_conductor as jc
        self.assertTrue(hasattr(jc, "THOUGHT_STATE_ENABLED"))
        src = inspect.getsource(jc.conduct)
        # Создание — только под флагом; дельты и сохранение — только при живом state
        self.assertIn("if THOUGHT_STATE_ENABLED:", src)
        self.assertIn("_thought_state is not None", src)
        self.assertIn("THOUGHT_STATE_ENABLED and _thought_state is not None", src)
        with patch.object(jc, "THOUGHT_STATE_ENABLED", False):
            # PRE-JANUS-путь не зависит от слоя мысли
            frame = jc._pre_janus_frame("кто ты?")
            manifest = jc._decompose_from_micro_tasks(
                frame["micro_tasks"], ["Head", "Heart", "Body"], "кто ты?", "",
            )
            self.assertIn("subtasks", manifest)

    def test_thought_layer_makes_no_llm_calls(self):
        """Слой мысли детерминирован: ни одного HTTP/LLM-вызова → бюджет Януса не растёт."""
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            frame = jc._pre_janus_frame("кто ты?")
            seed = jc.make_thought_seed("кто ты?", frame)
            ts = jc.make_thought_state(seed, grounding=0.5)
            delta = jc.compute_thought_delta(
                deva="Shani", center="Head", artifact="анализ",
                rune="ᛃ", action="none",
            )
            jc.apply_thought_delta(ts, delta)
            jc.compact_thought_state(ts)
        http_post.assert_not_called()

    def test_fohat_chain_unchanged_by_v39(self):
        """FOHAT_CHAIN не изменён: порядок 1-4-2-8-5-7 сохранён."""
        from core.janus_conductor import FOHAT_CHAIN
        self.assertEqual(
            [(c, d) for c, d, _ in FOHAT_CHAIN],
            [
                ("Head", "Shani"), ("Heart", "Chandra"), ("Heart", "Shukra"),
                ("Body", "Mangala"), ("Head", "Budha"), ("Head", "Rahu"),
            ],
        )


# ─────────────────────────────────────────────────────────────────────────────
# v39.1: таксономия намерений PRE-JANUS — conceptual/design/forensic
# ─────────────────────────────────────────────────────────────────────────────
class TestIntentTaxonomy(unittest.TestCase):

    _BODY_FORBIDDEN = (
        "bash", "порт", "port", "ram", "скрипт", "script",
        "free -h", "ss -tlnp", "shell.py", "systemctl", "netstat",
    )

    def test_conceptual_question_not_diagnostic(self):
        """«что такое память?» → conceptual, без диагностических полномочий."""
        from core.janus_conductor import _pre_janus_frame
        frame = _pre_janus_frame("что такое память?")
        self.assertEqual(frame["intent"], "conceptual")
        self.assertEqual(frame["mode"], "conceptual")
        self.assertFalse(frame["diagnostic_authorized"])
        self.assertFalse(frame["action_authorized"])
        self.assertFalse(frame["bash_authorized"])

    def test_design_question_not_diagnostic(self):
        """«спроектируй новую память» → design, без диагностических полномочий."""
        from core.janus_conductor import _pre_janus_frame
        frame = _pre_janus_frame("спроектируй новую память")
        self.assertEqual(frame["intent"], "design")
        self.assertEqual(frame["mode"], "design")
        self.assertFalse(frame["diagnostic_authorized"])
        self.assertFalse(frame["bash_authorized"])

    def test_forensic_question_routed(self):
        """«почему возникла галлюцинация» → forensic, без полномочий."""
        from core.janus_conductor import _pre_janus_frame
        frame = _pre_janus_frame("почему возникла галлюцинация")
        self.assertEqual(frame["intent"], "forensic")
        self.assertEqual(frame["mode"], "forensic")
        self.assertFalse(frame["diagnostic_authorized"])
        self.assertFalse(frame["action_authorized"])
        self.assertFalse(frame["bash_authorized"])

    def test_explicit_diagnostic_still_authorized(self):
        """«проверь порты» → diagnostic, mode='diagnostic', полномочия выданы."""
        from core.janus_conductor import _pre_janus_frame
        frame = _pre_janus_frame("проверь порты")
        self.assertEqual(frame["intent"], "diagnostic")
        self.assertEqual(frame["mode"], "diagnostic")
        self.assertTrue(frame["diagnostic_authorized"])
        self.assertTrue(frame["bash_authorized"])

    def test_memory_word_alone_not_diagnostic(self):
        """Слово «память» само по себе НЕ даёт диагностических полномочий."""
        from core.janus_conductor import _pre_janus_frame
        for text in ("память", "память монады", "новая память для системы"):
            frame = _pre_janus_frame(text)
            self.assertNotEqual(frame["intent"], "diagnostic", text)
            self.assertFalse(frame["diagnostic_authorized"], text)
            self.assertFalse(frame["bash_authorized"], text)

    def test_taxonomy_precedence(self):
        """forensic/diagnostic precede identity; identity beats conceptual/default."""
        from core.janus_conductor import _pre_janus_frame
        self.assertEqual(
            _pre_janus_frame("кто ты и почему ошибка?")["intent"], "forensic",
        )
        self.assertEqual(
            _pre_janus_frame("объясни статус портов")["intent"], "diagnostic",
        )
        self.assertEqual(
            _pre_janus_frame("спроектируй и проверь порты")["intent"], "diagnostic",
        )
        self.assertEqual(
            _pre_janus_frame("объясни, ты личность?")["intent"], "identity",
        )
        self.assertEqual(
            _pre_janus_frame("ты программа?")["intent"], "identity",
        )

    def test_reflective_body_micro_tasks_have_no_system_markers(self):
        """Body-микрозадачи conceptual/design/forensic — без bash/портов/RAM/скриптов."""
        from core.janus_conductor import _pre_janus_frame
        for text in (
            "что такое память?",
            "спроектируй новую память",
            "почему возникла галлюцинация",
        ):
            frame = _pre_janus_frame(text)
            body = frame["micro_tasks"]["Body"].lower()
            self.assertIn("action='none'", body)
            for marker in self._BODY_FORBIDDEN:
                self.assertNotIn(marker, body, f"{text!r} → Body содержит {marker!r}")

    def test_non_diagnostic_final_filter_strips_system_proposals(self):
        """Финальный фильтр новых режимов режет shell.py/systemctl/диагностику."""
        from core.janus_conductor import (
            _finalize_synthesis_for_mode, _pre_janus_frame,
            _strip_system_action_proposals,
        )
        dirty = (
            "Память — это эволюция смысла: Text → Glyph → Lesson → Archetype.\n\n"
            "Запустить shell.py и systemctl status, проверь порты.\n\n"
            "Посмотри netstat, cat /etc/passwd и /etc/inetd.conf, ls /home/ и /mnt/."
        )
        result = _finalize_synthesis_for_mode(
            dirty, "Persona", "", _pre_janus_frame("что такое память?"),
        )
        self.assertIn("Память — это эволюция смысла", result)
        for forbidden in (
            "shell.py", "systemctl", "netstat", "проверь порты",
            "Запустить", "/home/", "/mnt/", "/etc/passwd", "/etc/inetd.conf",
        ):
            self.assertNotIn(forbidden, result)
        # Фильтр не должен резать чистый концептуальный текст
        clean = "Память — самоподобная структура уроков и архетипов."
        self.assertEqual(_strip_system_action_proposals(clean), clean)

    def test_taxonomy_makes_no_llm_calls_and_chain_unchanged(self):
        """Маршрутизация детерминирована (бюджет Януса не растёт); FOHAT_CHAIN цел."""
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            for text in (
                "что такое память?", "спроектируй новую память",
                "почему возникла галлюцинация", "проверь порты", "кто ты?",
                "ты личность?", "ты программа?", "ты живая?",
                "чем ты являешься", "какова твоя природа",
            ):
                jc._pre_janus_frame(text)
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# v40: Thought-Carrying Octave — сводка ThoughtState между Дэвами
# ─────────────────────────────────────────────────────────────────────────────
class TestThoughtCarryingOctave(unittest.TestCase):

    def _make_state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.2,
        )

    def test_summary_is_bounded(self):
        """Сводка ≤ 900 символов даже при полных claims/open/constraints."""
        from core.janus_conductor import (
            _compact_thought_state_summary, THOUGHT_SUMMARY_MAX_CHARS,
        )
        ts = self._make_state()
        for i in range(7):
            ts["claims"].append(f"claim-{i} " + "x" * 150)
            ts["open"].append(f"open-{i} " + "y" * 150)
            ts["constraints"].append(f"constr-{i} " + "z" * 150)
        summary = _compact_thought_state_summary(ts)
        self.assertLessEqual(len(summary), THOUGHT_SUMMARY_MAX_CHARS)
        self.assertTrue(summary.startswith("[THOUGHT_STATE]"))
        self.assertTrue(summary.endswith("[/THOUGHT_STATE]"))

    def test_summary_includes_intent_mode_metrics(self):
        from core.janus_conductor import _compact_thought_state_summary
        summary = _compact_thought_state_summary(self._make_state())
        self.assertIn("intent=design mode=design", summary)
        self.assertIn("question=спроектируй новую память", summary)
        self.assertIn("grounding=0.20", summary)
        self.assertIn("risk=0.00", summary)
        self.assertIn("confidence=0.50", summary)

    def test_summary_excludes_artifact_body(self):
        """Artifact-тело не попадает в сводку — только детерминированная дельта."""
        from core.janus_conductor import (
            _compact_thought_state_summary,
            compute_thought_delta, apply_thought_delta,
        )
        ts = self._make_state()
        delta = compute_thought_delta(
            deva="Shani", center="Head",
            artifact="UNIQUEMARKER секретное тело артефакта " * 50,
            rune="ᛁ", action="none",
        )
        apply_thought_delta(ts, delta)
        summary = _compact_thought_state_summary(ts)
        self.assertNotIn("UNIQUEMARKER", summary)
        self.assertIn("last_delta:", summary)
        self.assertIn("Shani", summary)

    def test_summary_caps_items_to_three(self):
        """Показываются только 3 ПОСЛЕДНИХ элемента каждого списка."""
        from core.janus_conductor import _compact_thought_state_summary
        ts = self._make_state()
        for i in range(7):
            ts["claims"].append(f"CLAIM_{i}")
        summary = _compact_thought_state_summary(ts)
        self.assertNotIn("CLAIM_0", summary)
        self.assertNotIn("CLAIM_3", summary)
        for i in (4, 5, 6):
            self.assertIn(f"CLAIM_{i}", summary)

    def test_enrich_appends_without_mutating_input(self):
        from core.janus_conductor import (
            _enrich_deva_context_with_thought_state, _THOUGHT_CONTINUITY_LINE,
        )
        ts = self._make_state()
        trace_before = list(ts["trace"])
        ctx = "ИСХОДНЫЙ КОНТЕКСТ ДЭВЫ"
        enriched = _enrich_deva_context_with_thought_state(ctx, ts)
        self.assertTrue(enriched.startswith("ИСХОДНЫЙ КОНТЕКСТ ДЭВЫ"))
        self.assertIn("[THOUGHT_STATE]", enriched)
        self.assertIn(_THOUGHT_CONTINUITY_LINE, enriched)
        self.assertEqual(ts["trace"], trace_before)
        self.assertEqual(ctx, "ИСХОДНЫЙ КОНТЕКСТ ДЭВЫ")

    def test_next_deva_sees_updated_state(self):
        """После дельты следующий Дэва видит обновлённые metrics/open/constraints."""
        from core.janus_conductor import (
            _enrich_deva_context_with_thought_state,
            compute_thought_delta, apply_thought_delta,
        )
        ts = self._make_state()
        ctx_before = _enrich_deva_context_with_thought_state("CTX", ts)
        self.assertIn("risk=0.00", ctx_before)
        self.assertNotIn("outward action blocked", ctx_before)
        delta = compute_thought_delta(
            deva="Mangala", center="Body",
            artifact="Запусти ss -tlnp и проверь порты, RAM",
            rune="ᛃ", action="none",
            mode="design", diagnostic_authorized=False,
        )
        apply_thought_delta(ts, delta)
        ctx_after = _enrich_deva_context_with_thought_state("CTX", ts)
        # v40.1: 0.20 (outward) + 0.05 (constraint добавлен) = 0.25
        self.assertIn("risk=0.25", ctx_after)
        self.assertIn("outward action blocked by introspection", ctx_after)
        self.assertIn("Mangala", ctx_after)

    def test_flag_off_no_injection(self):
        """THOUGHT_STATE_ENABLED=False → пустая сводка, контекст не меняется."""
        import core.janus_conductor as jc
        ts = self._make_state()
        with patch.object(jc, "THOUGHT_STATE_ENABLED", False):
            self.assertEqual(jc._compact_thought_state_summary(ts), "")
            self.assertEqual(
                jc._enrich_deva_context_with_thought_state("CTX", ts), "CTX",
            )
        # И на отсутствующем state — no-op
        self.assertEqual(jc._compact_thought_state_summary(None), "")
        self.assertEqual(
            jc._enrich_deva_context_with_thought_state("CTX", None), "CTX",
        )

    def test_octave_carries_thought_no_extra_calls(self):
        """Проводка в conduct: инъекция есть, LLM-вызовов нет, FOHAT_CHAIN цел."""
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("_enrich_deva_context_with_thought_state", src)
        self.assertIn("_compact_thought_state_summary", src)
        with patch.object(jc, "_http_post") as http_post:
            ts = self._make_state()
            jc._enrich_deva_context_with_thought_state("CTX", ts)
            jc._compact_thought_state_summary(ts)
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# v40.1: семантическая экстракция — ThoughtState накапливает смысл
# ─────────────────────────────────────────────────────────────────────────────
class TestSemanticExtraction(unittest.TestCase):

    _IDENTITY_CLAIM = (
        "MirAI — локальная многоузловая ИИ-система в архитектуре "
        "Monada-Hardcore."
    )

    def _state(self, text="кто ты?"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def test_identity_claim_extracted(self):
        from core.janus_conductor import _extract_semantic_claim, _pre_janus_frame
        claim = _extract_semantic_claim(
            self._IDENTITY_CLAIM, _pre_janus_frame("кто ты?"), self._state(),
        )
        self.assertEqual(claim, self._IDENTITY_CLAIM)

    def test_bash_command_not_extracted_as_claim(self):
        from core.janus_conductor import _extract_semantic_claim, _pre_janus_frame
        for artifact in (
            "Запусти ls -la /home/angelan и free -h для системы.",
            "```bash\nss -tlnp\n```",
            "Система: выполните скрипт check.sh в архитектуре.",
        ):
            self.assertIsNone(
                _extract_semantic_claim(
                    artifact, _pre_janus_frame("кто ты?"), self._state(),
                ),
                artifact,
            )

    def test_status_claim_requires_diagnostic_authorization(self):
        from core.janus_conductor import _extract_semantic_claim, _pre_janus_frame
        artifact = "Порты системы 8081, 8082 прослушиваются стабильно."
        self.assertIsNone(
            _extract_semantic_claim(
                artifact, _pre_janus_frame("кто ты?"), self._state(),
            )
        )
        self.assertTrue(
            _extract_semantic_claim(
                artifact, _pre_janus_frame("проверь порты"), self._state(),
            )
        )

    def test_pain_becomes_open_not_claim(self):
        from core.janus_conductor import (
            _extract_semantic_claim, _extract_open_question_or_issue,
            _pre_janus_frame,
        )
        artifact = "БОЛЬ: Недостаточно данных для определения причины галлюцинации."
        self.assertIsNone(
            _extract_semantic_claim(
                artifact, _pre_janus_frame("почему возникла галлюцинация"),
                self._state(),
            )
        )
        self.assertEqual(
            _extract_open_question_or_issue(artifact),
            "Недостаточно данных для определения причины галлюцинации.",
        )

    def test_reflective_bash_proposal_becomes_constraint(self):
        from core.janus_conductor import _extract_constraint, _pre_janus_frame
        constraint = _extract_constraint(
            "Предлагаю запустить скрипт /home/angelan/check.sh",
            _pre_janus_frame("спроектируй новую память"),
        )
        self.assertEqual(constraint, "outward action blocked by design")

    def test_contradiction_denial_plus_executable(self):
        from core.janus_conductor import _extract_contradiction
        self.assertEqual(
            _extract_contradiction(
                "Я ничего не исполняю, но вот скрипт /home/angelan/run.sh",
                {},
            ),
            "artifact denies execution but proposes executable action",
        )
        self.assertEqual(
            _extract_contradiction(
                "Нет подтверждения состояния, но всё подтверждено и готово.",
                {},
            ),
            "artifact mixes unsupported uncertainty with confirmation",
        )
        self.assertIsNone(_extract_contradiction("Просто текст мысли.", {}))

    def test_duplicate_claims_not_added_twice(self):
        from core.janus_conductor import (
            compute_thought_delta, apply_thought_delta, _pre_janus_frame,
        )
        ts = self._state()
        frame = _pre_janus_frame("кто ты?")
        for _ in range(3):
            delta = compute_thought_delta(
                deva="Shani", center="Head", artifact=self._IDENTITY_CLAIM,
                rune="ᛃ", action="none", mode="introspection",
                diagnostic_authorized=False,
                pre_janus_frame=frame, thought_state=ts,
            )
            apply_thought_delta(ts, delta)
        self.assertEqual(len(ts["claims"]), 1)

    def test_caps_hold_for_all_lists(self):
        """claims/open/constraints не превышают 7 при потоке разных дельт."""
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        # v40.2: claims семантически различны, иначе их срежет novelty-фильтр
        topics = [
            "буфер", "журнал", "индекс", "снимок", "реплика",
            "шина", "кэш", "сжатие", "вектор", "якорь",
        ]
        for i in range(10):
            apply_thought_delta(ts, {
                "deva": f"D{i}", "center": "Head", "rune": "ᛃ", "action": "none",
                "claim": f"claim слово{i} вектор{i} о системе",
                "open": f"неясно поведение компонента {topics[i]}",
                "constraint": f"ограничение {i}",
                "metric_delta": {},
                "reason": "test",
            })
        self.assertEqual(len(ts["claims"]), 7)
        self.assertEqual(len(ts["open"]), 7)
        self.assertEqual(len(ts["constraints"]), 7)

    def test_claim_addition_raises_confidence_and_coherence(self):
        from core.janus_conductor import compute_thought_delta, apply_thought_delta
        ts = self._state()
        delta = compute_thought_delta(
            deva="Budha", center="Head", artifact=self._IDENTITY_CLAIM,
            rune="ᛃ", action="none", thought_state=ts,
        )
        self.assertEqual(delta["claim"], self._IDENTITY_CLAIM)
        apply_thought_delta(ts, delta)
        self.assertAlmostEqual(ts["metrics"]["confidence"], 0.55)
        # v41/v42/v43: 0.05 (claim) + 0.03 (урок) + 0.05 (архетип Meaningful
        # Novelty) + 0.03 (глиф ᛇᚨ, первое появление)
        self.assertAlmostEqual(ts["metrics"]["coherence"], 0.66)

    def test_contradiction_raises_risk_lowers_confidence(self):
        from core.janus_conductor import compute_thought_delta, apply_thought_delta
        ts = self._state()
        delta = compute_thought_delta(
            deva="Rahu", center="Head",
            artifact="Я ничего не исполняю, но вот bash скрипт запуска",
            rune="ᛃ", action="none", thought_state=ts,
        )
        self.assertTrue(delta["contradiction"])
        apply_thought_delta(ts, delta)
        self.assertAlmostEqual(ts["metrics"]["risk"], 0.2)
        self.assertAlmostEqual(ts["metrics"]["confidence"], 0.4)
        # v41/v42/v43: -0.1 (contradiction) + 0.03 (урок) + 0.05 (архетип
        # Dialectical Verification) + 0.03 (глиф ᛁᚹ, первое появление)
        self.assertAlmostEqual(ts["metrics"]["coherence"], 0.51)
        self.assertTrue(
            any(o.startswith("contradiction:") for o in ts["open"])
        )

    def test_compact_state_still_excludes_artifact_bodies(self):
        """Извлечённые элементы ≤160 симв.; тело артефакта не утекает."""
        from core.janus_conductor import (
            compute_thought_delta, apply_thought_delta, compact_thought_state,
            THOUGHT_FIELD_MAXLEN,
        )
        ts = self._state()
        long_tail = "BIGBODYMARKER без якорей и признаков " * 200
        delta = compute_thought_delta(
            deva="Shani", center="Head",
            artifact=f"{self._IDENTITY_CLAIM} {long_tail}",
            rune="ᛃ", action="none", thought_state=ts,
        )
        apply_thought_delta(ts, delta)
        compact = compact_thought_state(ts)
        dumped = json.dumps(compact, ensure_ascii=False)
        self.assertNotIn("BIGBODYMARKER", dumped)
        for c in compact["claims"]:
            self.assertLessEqual(len(c), THOUGHT_FIELD_MAXLEN)

    def test_extraction_no_llm_calls_chain_unchanged(self):
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            ts = self._state()
            frame = jc._pre_janus_frame("кто ты?")
            jc._extract_semantic_claim(self._IDENTITY_CLAIM, frame, ts)
            jc._extract_open_question_or_issue("БОЛЬ: ошибка такта.")
            jc._extract_constraint("предлагаю bash", frame)
            jc._extract_contradiction("текст", ts)
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# v40.2: семантическая новизна claims — NEW MEANING vs NEW WORDING
# ─────────────────────────────────────────────────────────────────────────────
class TestClaimNoveltyFilter(unittest.TestCase):

    _BASE_CLAIM = "Структура памяти обеспечивает гибкость инвариантов."
    _PARAPHRASE = "Структуры памяти дают гибкость инвариантам."
    _DIFFERENT  = "Потоки записи идут через журналируемый буфер."

    def _state(self):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        text = "спроектируй новую память"
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, claim):
        return {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": claim, "metric_delta": {}, "reason": "test",
        }

    def test_signature_normalizes_russian_morphology(self):
        """«структура памяти» и «структуры памяти» дают общую основу."""
        from core.janus_conductor import _claim_signature
        s1 = _claim_signature("структура памяти")
        s2 = _claim_signature("структуры памяти")
        self.assertIn("структур", s1)
        self.assertIn("структур", s2)
        self.assertTrue(s1 & s2)

    def test_content_word_inflections_collapse_to_one_stem(self):
        """Падежные формы контент-слов сводятся к одной общей основе."""
        from core.janus_conductor import _claim_signature
        for forms in (
            "запись записи записью",
            "надежность надежности надежностью",
            "структура структуры структурой",
        ):
            sig = _claim_signature(forms)
            self.assertEqual(len(sig), 1, (forms, sig))

    def test_inflection_pairs_have_identical_signatures(self):
        """Каждая пара форм даёт идентичную сигнатуру → перекрытие 1.0."""
        from core.janus_conductor import _claim_signature
        for a, b in (
            ("запись", "записью"),
            ("надежность", "надежностью"),
            ("надежность", "надежности"),
            ("структура", "структурой"),
        ):
            self.assertEqual(
                _claim_signature(a), _claim_signature(b), (a, b),
            )

    def test_stopword_morphology_excluded_from_signature(self):
        """Морфоформы стоп-слов (системы/памятью/архитектуры) исключены."""
        from core.janus_conductor import _claim_signature
        self.assertEqual(_claim_signature("система системы системой"), set())
        sig = _claim_signature("память памяти памятью архитектура архитектуры")
        self.assertEqual(sig, set())
        for stem in ("систем", "памят", "архитектур"):
            self.assertFalse(
                any(t.startswith(stem) for t in sig), stem,
            )

    def test_first_claim_novelty_is_one(self):
        from core.janus_conductor import _claim_novelty_score
        self.assertEqual(_claim_novelty_score(self._BASE_CLAIM, []), 1.0)

    def test_paraphrase_rejected(self):
        from core.janus_conductor import _is_semantically_novel_claim
        self.assertFalse(
            _is_semantically_novel_claim(self._PARAPHRASE, [self._BASE_CLAIM])
        )

    def test_different_claim_accepted(self):
        from core.janus_conductor import _is_semantically_novel_claim
        self.assertTrue(
            _is_semantically_novel_claim(self._DIFFERENT, [self._BASE_CLAIM])
        )

    def test_low_novelty_claim_not_added_and_no_reward(self):
        """Парафраз: claims не растут, confidence/risk без награды claim-пути."""
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(self._BASE_CLAIM))
        self.assertEqual(len(ts["claims"]), 1)
        conf = ts["metrics"]["confidence"]
        coh  = ts["metrics"]["coherence"]
        risk = ts["metrics"]["risk"]
        nov  = ts["metrics"]["novelty"]
        apply_thought_delta(ts, self._delta(self._PARAPHRASE))
        self.assertEqual(len(ts["claims"]), 1)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf)
        self.assertAlmostEqual(ts["metrics"]["risk"], risk)
        # v41/v42/v43: спад -0.02 (скип) + 0.03 (урок сжатия, единожды);
        # coherence растёт уроком (+0.03), первым появлением архетипа
        # Semantic Compression (+0.05) и его глифа ᛜᚨ (+0.03), не claim-путём
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov - 0.02 + 0.03)
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03 + 0.05 + 0.03)
        # Trace помечает скип, не раздуваясь artifact-телом
        self.assertIn("claim skipped: low novelty", ts["trace"][-1]["reason"])
        # Повторный скип: урок дедупится → никаких наград вообще
        coh2 = ts["metrics"]["coherence"]
        nov2 = ts["metrics"]["novelty"]
        apply_thought_delta(ts, self._delta(self._PARAPHRASE))
        self.assertEqual(len(ts["claims"]), 1)
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh2)
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov2 - 0.02)

    def test_rejected_claim_metric_delta_reward_suppressed(self):
        """metric_delta confidence/coherence парафраза подавляется при скипе."""
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(self._BASE_CLAIM))
        self.assertEqual(len(ts["claims"]), 1)
        conf = ts["metrics"]["confidence"]
        coh  = ts["metrics"]["coherence"]
        delta = self._delta(self._PARAPHRASE)
        delta["metric_delta"] = {"confidence": 0.1, "coherence": 0.1}
        delta["reason"] = "semantic_claim"
        apply_thought_delta(ts, delta)
        self.assertEqual(len(ts["claims"]), 1)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf)
        # v41/v42/v43: подавленный +0.1 НЕ применён; +0.03 урок сжатия,
        # +0.05 архетип Semantic Compression, +0.03 его глиф ᛜᚨ
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03 + 0.05 + 0.03)

    def test_rejected_claim_keeps_independent_rewards(self):
        """bash_success/approved награды живут даже при скипе парафраза."""
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(self._BASE_CLAIM))
        grounding = ts["metrics"]["grounding"]
        conf      = ts["metrics"]["confidence"]
        delta = self._delta(self._PARAPHRASE)
        delta["metric_delta"] = {"grounding": 0.2, "confidence": 0.1}
        delta["reason"] = "bash_success,semantic_claim"
        apply_thought_delta(ts, delta)
        self.assertEqual(len(ts["claims"]), 1)
        self.assertAlmostEqual(ts["metrics"]["grounding"], grounding + 0.2)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf + 0.1)

    def test_accepted_novel_claim_raises_novelty_metric(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        self.assertAlmostEqual(ts["metrics"]["novelty"], 0.0)
        apply_thought_delta(ts, self._delta(self._BASE_CLAIM))
        # v41: 0.10 (claim novelty 1.0) + 0.03 (урок high-novelty)
        self.assertAlmostEqual(ts["metrics"]["novelty"], 0.13)
        self.assertIn("novelty=1.00,claim_added=true", ts["trace"][-1]["reason"])
        apply_thought_delta(ts, self._delta(self._DIFFERENT))
        self.assertEqual(len(ts["claims"]), 2)
        # Урок дедупится → второй прирост только 0.10
        self.assertAlmostEqual(ts["metrics"]["novelty"], 0.23)

    def test_cap_claims_still_seven(self):
        """10 семантически разных claims → cap 7 держится."""
        from core.janus_conductor import apply_thought_delta
        nouns = ["поток", "буфер", "журнал", "индекс", "снимок",
                 "реплика", "шина", "кэш", "сжатие", "вектор"]
        tails = ["хранилище", "канал", "регистр", "слот", "контур",
                 "узел", "модуль", "цикл", "граф", "якорь"]
        ts = self._state()
        for i in range(10):
            apply_thought_delta(
                ts, self._delta(f"{nouns[i]} соединяет {tails[i]}"),
            )
        self.assertEqual(len(ts["claims"]), 7)

    def test_exact_duplicate_still_rejected(self):
        """Старый точный дедуп жив — novelty-фильтр его дополняет."""
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(self._BASE_CLAIM))
        apply_thought_delta(ts, self._delta(self._BASE_CLAIM))
        self.assertEqual(len(ts["claims"]), 1)

    def test_novelty_filter_no_llm_calls_chain_unchanged(self):
        """Фильтр детерминирован: ни одного HTTP-вызова, FOHAT_CHAIN цел."""
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            ts = self._state()
            jc._claim_signature(self._BASE_CLAIM)
            jc._claim_novelty_score(self._PARAPHRASE, [self._BASE_CLAIM])
            jc._is_semantically_novel_claim(self._DIFFERENT, [self._BASE_CLAIM])
            jc.apply_thought_delta(ts, self._delta(self._BASE_CLAIM))
            jc.apply_thought_delta(ts, self._delta(self._PARAPHRASE))
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# v41: Lesson-слой — детерминированная экстракция уроков из ThoughtState
# ─────────────────────────────────────────────────────────────────────────────
class TestThoughtLessons(unittest.TestCase):

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, **kw):
        base = {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": None, "constraint": None,
            "contradiction": None, "metric_delta": {}, "reason": "test",
        }
        base.update(kw)
        return base

    def test_outward_blocked_in_reflective_mode_creates_lesson(self):
        from core.janus_conductor import apply_thought_delta, _LESSON_REFLECTIVE
        ts = self._state()  # mode=design — рефлективный
        apply_thought_delta(
            ts, self._delta(constraint="outward action blocked by design"),
        )
        self.assertIn(_LESSON_REFLECTIVE, ts["lessons"])

    def test_insufficient_data_open_creates_lesson(self):
        from core.janus_conductor import apply_thought_delta, _LESSON_UNVERIFIED
        ts = self._state()
        apply_thought_delta(
            ts, self._delta(open="Недостаточно данных для вывода о памяти"),
        )
        self.assertIn(_LESSON_UNVERIFIED, ts["lessons"])

    def test_contradiction_creates_lesson(self):
        from core.janus_conductor import (
            apply_thought_delta, _LESSON_CONTRADICTION,
        )
        ts = self._state()
        apply_thought_delta(ts, self._delta(
            contradiction="artifact denies execution but proposes action",
        ))
        self.assertIn(_LESSON_CONTRADICTION, ts["lessons"])

    def test_low_novelty_skip_creates_compression_lesson(self):
        from core.janus_conductor import apply_thought_delta, _LESSON_COMPRESSION
        ts = self._state()
        apply_thought_delta(ts, self._delta(
            claim="Структура памяти обеспечивает гибкость инвариантов.",
        ))
        apply_thought_delta(ts, self._delta(
            claim="Структуры памяти дают гибкость инвариантам.",
        ))
        self.assertEqual(len(ts["claims"]), 1)
        self.assertIn(_LESSON_COMPRESSION, ts["lessons"])

    def test_design_abstract_open_creates_design_lesson(self):
        from core.janus_conductor import apply_thought_delta, _LESSON_DESIGN
        ts = self._state()  # mode=design
        apply_thought_delta(ts, self._delta(
            open="Решение слишком абстрактно, нет конкретики",
        ))
        self.assertIn(_LESSON_DESIGN, ts["lessons"])

    def test_lessons_dedup(self):
        from core.janus_conductor import (
            apply_thought_delta, _add_lesson, _LESSON_CONTRADICTION,
        )
        ts = self._state()
        apply_thought_delta(ts, self._delta(contradiction="противоречие А"))
        apply_thought_delta(ts, self._delta(contradiction="противоречие Б"))
        self.assertEqual(ts["lessons"].count(_LESSON_CONTRADICTION), 1)
        self.assertFalse(_add_lesson(ts, _LESSON_CONTRADICTION))

    def test_lessons_cap_five(self):
        from core.janus_conductor import _add_lesson, THOUGHT_MAX_LESSONS
        ts = self._state()
        for i in range(8):
            _add_lesson(ts, f"урок номер {i} о разных паттернах")
        self.assertEqual(len(ts["lessons"]), THOUGHT_MAX_LESSONS)
        self.assertEqual(THOUGHT_MAX_LESSONS, 5)

    def test_lesson_reward_only_on_add(self):
        from core.janus_conductor import _add_lesson
        ts = self._state()
        coh = ts["metrics"]["coherence"]
        self.assertTrue(_add_lesson(ts, "урок альфа"))
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03)
        self.assertFalse(_add_lesson(ts, "урок альфа"))
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03)

    def test_summary_includes_max_two_lessons(self):
        from core.janus_conductor import (
            _compact_thought_state_summary, THOUGHT_SUMMARY_MAX_CHARS,
        )
        ts = self._state()
        ts["lessons"] = [f"LSN_{i} паттерн такта" for i in range(4)]
        summary = _compact_thought_state_summary(ts)
        self.assertNotIn("LSN_0", summary)
        self.assertNotIn("LSN_1", summary)
        self.assertIn("LSN_2", summary)
        self.assertIn("LSN_3", summary)
        self.assertLessEqual(len(summary), THOUGHT_SUMMARY_MAX_CHARS)

    def test_last_thought_state_lessons_bounded_no_artifacts(self):
        from core.janus_conductor import (
            apply_thought_delta, compact_thought_state, THOUGHT_LESSON_MAXLEN,
        )
        ts = self._state()
        apply_thought_delta(ts, self._delta(
            contradiction="BIGBODYMARKER " * 50,
        ))
        ts["lessons"].append("x" * 1000)
        compact = compact_thought_state(ts)
        self.assertIn("lessons", compact)
        for lesson in compact["lessons"]:
            self.assertLessEqual(len(lesson), THOUGHT_LESSON_MAXLEN)
        # Урок — фиксированная формулировка, тело артефакта не утекает
        self.assertNotIn("BIGBODYMARKER", json.dumps(compact["lessons"]))

    def test_lesson_layer_no_llm_chain_dyad_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            ts = self._state()
            lesson = jc._extract_lesson_candidate(
                ts, self._delta(contradiction="x"), ts["seed"],
            )
            jc._add_lesson(ts, lesson)
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )
        self.assertNotIn("lesson", inspect.getsource(jc.janus_dyad))


# ─────────────────────────────────────────────────────────────────────────────
# v42: Archetype-слой — сжатие повторяющихся уроков в стабильные паттерны
# ─────────────────────────────────────────────────────────────────────────────
class TestThoughtArchetypes(unittest.TestCase):

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, **kw):
        base = {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": None, "constraint": None,
            "contradiction": None, "metric_delta": {}, "reason": "test",
        }
        base.update(kw)
        return base

    def test_lesson_maps_to_archetype(self):
        """Все шесть уроков отображаются явной картой, без fuzzy."""
        import core.janus_conductor as jc
        expected = {
            jc._LESSON_REFLECTIVE:    "Boundary Integrity",
            jc._LESSON_UNVERIFIED:    "Ground Before Action",
            jc._LESSON_CONTRADICTION: "Dialectical Verification",
            jc._LESSON_COMPRESSION:   "Semantic Compression",
            jc._LESSON_NOVELTY:       "Meaningful Novelty",
            jc._LESSON_DESIGN:        "Concrete Design",
        }
        for lesson, name in expected.items():
            self.assertEqual(jc._archetype_for_lesson(lesson), name)
        self.assertIsNone(jc._archetype_for_lesson("произвольный текст"))
        self.assertIsNone(jc._archetype_for_lesson(None))

    def test_archetype_created_on_lesson_add(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(contradiction="противоречие А"))
        self.assertEqual(
            ts["archetypes"],
            [{"name": "Dialectical Verification", "count": 1}],
        )

    def test_count_increments(self):
        from core.janus_conductor import _register_archetype, _LESSON_REFLECTIVE
        ts = self._state()
        for _ in range(3):
            self.assertTrue(_register_archetype(ts, _LESSON_REFLECTIVE))
        self.assertEqual(len(ts["archetypes"]), 1)
        self.assertEqual(ts["archetypes"][0]["count"], 3)

    def test_duplicate_lesson_increments_archetype_not_lessons(self):
        """v42.1: дубль урока — урок не дублируется, архетип считает повтор."""
        from core.janus_conductor import (
            apply_thought_delta, _LESSON_CONTRADICTION,
        )
        ts = self._state()
        apply_thought_delta(ts, self._delta(contradiction="противоречие А"))
        apply_thought_delta(ts, self._delta(contradiction="противоречие Б"))
        self.assertEqual(ts["lessons"].count(_LESSON_CONTRADICTION), 1)
        self.assertEqual(ts["archetypes"][0]["count"], 2)

    def test_apply_flow_reaches_count_three_novelty_reward(self):
        """Порог count==3 достижим в живом потоке apply_thought_delta."""
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        for i in range(2):
            apply_thought_delta(
                ts, self._delta(contradiction=f"противоречие {i}"),
            )
        self.assertEqual(ts["archetypes"][0]["count"], 2)
        nov = ts["metrics"]["novelty"]
        apply_thought_delta(ts, self._delta(contradiction="противоречие 2"))
        self.assertEqual(ts["archetypes"][0]["count"], 3)
        # v43: архетип count==3 (+0.03) + глиф count==3 (+0.02) — со-срабатывание
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov + 0.03 + 0.02)

    def test_apply_flow_reaches_count_five_confidence_reward(self):
        """Порог count==5 достижим в живом потоке apply_thought_delta."""
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        for i in range(4):
            apply_thought_delta(
                ts, self._delta(contradiction=f"противоречие {i}"),
            )
        self.assertEqual(ts["archetypes"][0]["count"], 4)
        conf = ts["metrics"]["confidence"]
        apply_thought_delta(ts, self._delta(contradiction="противоречие 4"))
        self.assertEqual(ts["archetypes"][0]["count"], 5)
        # -0.1 (contradiction-open) + 0.03 (архетип count==5) + 0.02 (глиф count==5)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf - 0.1 + 0.03 + 0.02)
        self.assertLessEqual(len(ts["lessons"]), 5)

    def test_cap_full_new_lesson_does_not_create_archetype(self):
        """Cap уроков полон: новый урок не входит, шестого паттерна нет."""
        from core.janus_conductor import _add_lesson, _LESSON_REFLECTIVE
        ts = self._state()
        for i in range(5):
            self.assertTrue(_add_lesson(ts, f"урок {i} некартированный"))
        coh = ts["metrics"]["coherence"]
        self.assertFalse(_add_lesson(ts, _LESSON_REFLECTIVE))
        self.assertEqual(len(ts["lessons"]), 5)
        self.assertEqual(ts["archetypes"], [])
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh)

    def test_cap_full_duplicate_lesson_still_increments_archetype(self):
        """Cap полон, урок-дубль картирован → существующий архетип растёт."""
        from core.janus_conductor import _add_lesson, _LESSON_CONTRADICTION
        ts = self._state()
        self.assertTrue(_add_lesson(ts, _LESSON_CONTRADICTION))
        for i in range(4):
            self.assertTrue(_add_lesson(ts, f"урок {i} некартированный"))
        self.assertEqual(len(ts["lessons"]), 5)
        self.assertFalse(_add_lesson(ts, _LESSON_CONTRADICTION))
        self.assertEqual(len(ts["lessons"]), 5)
        self.assertEqual(ts["archetypes"][0]["count"], 2)
        self.assertEqual(len(ts["archetypes"]), 1)

    def test_archetype_cap_five(self):
        import core.janus_conductor as jc
        ts = self._state()
        all_lessons = (
            jc._LESSON_REFLECTIVE, jc._LESSON_UNVERIFIED,
            jc._LESSON_CONTRADICTION, jc._LESSON_COMPRESSION,
            jc._LESSON_NOVELTY, jc._LESSON_DESIGN,
        )
        results = [jc._register_archetype(ts, l) for l in all_lessons]
        self.assertEqual(len(ts["archetypes"]), jc.THOUGHT_MAX_ARCHETYPES)
        self.assertEqual(jc.THOUGHT_MAX_ARCHETYPES, 5)
        self.assertEqual(results, [True] * 5 + [False])

    def test_first_appearance_rewards_coherence(self):
        from core.janus_conductor import _register_archetype, _LESSON_REFLECTIVE
        ts = self._state()
        coh = ts["metrics"]["coherence"]
        _register_archetype(ts, _LESSON_REFLECTIVE)
        # v43: архетип +0.05 + первое появление глифа ᛉᚱ +0.03
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.05 + 0.03)
        # Второе появление — без coherence-награды (ни архетип, ни глиф)
        _register_archetype(ts, _LESSON_REFLECTIVE)
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.05 + 0.03)

    def test_count_three_rewards_novelty(self):
        from core.janus_conductor import _register_archetype, _LESSON_UNVERIFIED
        ts = self._state()
        _register_archetype(ts, _LESSON_UNVERIFIED)
        _register_archetype(ts, _LESSON_UNVERIFIED)
        nov = ts["metrics"]["novelty"]
        _register_archetype(ts, _LESSON_UNVERIFIED)   # count → 3
        # v43: архетип count==3 (+0.03) + глиф count==3 (+0.02)
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov + 0.03 + 0.02)
        _register_archetype(ts, _LESSON_UNVERIFIED)   # count → 4, без награды
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov + 0.03 + 0.02)

    def test_count_five_rewards_confidence(self):
        from core.janus_conductor import _register_archetype, _LESSON_DESIGN
        ts = self._state()
        for _ in range(4):
            _register_archetype(ts, _LESSON_DESIGN)
        conf = ts["metrics"]["confidence"]
        _register_archetype(ts, _LESSON_DESIGN)       # count → 5
        self.assertEqual(ts["archetypes"][0]["count"], 5)
        # v43: архетип count==5 (+0.03) + глиф count==5 (+0.02)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf + 0.03 + 0.02)

    def test_summary_includes_max_two_archetypes(self):
        from core.janus_conductor import (
            _compact_thought_state_summary, THOUGHT_SUMMARY_MAX_CHARS,
        )
        ts = self._state()
        ts["archetypes"] = [
            {"name": f"ARCH_{i}", "count": i + 1} for i in range(4)
        ]
        summary = _compact_thought_state_summary(ts)
        # Два с наибольшим count
        self.assertIn("ARCH_3 x4", summary)
        self.assertIn("ARCH_2 x3", summary)
        self.assertNotIn("ARCH_0", summary)
        self.assertNotIn("ARCH_1", summary)
        self.assertLessEqual(len(summary), THOUGHT_SUMMARY_MAX_CHARS)

    def test_no_artifact_bodies_in_archetypes(self):
        from core.janus_conductor import (
            apply_thought_delta, compact_thought_state,
            THOUGHT_ARCHETYPE_MAXLEN,
        )
        ts = self._state()
        apply_thought_delta(ts, self._delta(
            contradiction="BIGBODYMARKER " * 50,
        ))
        compact = compact_thought_state(ts)
        self.assertIn("archetypes", compact)
        dumped = json.dumps(compact["archetypes"], ensure_ascii=False)
        self.assertNotIn("BIGBODYMARKER", dumped)
        for arch in compact["archetypes"]:
            self.assertEqual(set(arch), {"name", "count"})
            self.assertLessEqual(len(arch["name"]), THOUGHT_ARCHETYPE_MAXLEN)

    def test_archetype_layer_no_llm_chain_dyad_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            ts = self._state()
            jc._archetype_for_lesson(jc._LESSON_REFLECTIVE)
            jc._register_archetype(ts, jc._LESSON_REFLECTIVE)
            apply_delta = self._delta(contradiction="x")
            jc.apply_thought_delta(ts, apply_delta)
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )
        _dyad_src = inspect.getsource(jc.janus_dyad).lower()
        self.assertNotIn("archetype", _dyad_src)
        self.assertNotIn("архетип", _dyad_src)


# ─────────────────────────────────────────────────────────────────────────────
# v43: Glyph-слой — символьное сжатие архетипов внутри ThoughtState
# ─────────────────────────────────────────────────────────────────────────────
class TestThoughtGlyphs(unittest.TestCase):

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, **kw):
        base = {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": None, "constraint": None,
            "contradiction": None, "metric_delta": {}, "reason": "test",
        }
        base.update(kw)
        return base

    def test_archetype_maps_to_glyph(self):
        """Все шесть архетипов отображаются явной картой, без fuzzy."""
        import core.janus_conductor as jc
        expected = {
            "Boundary Integrity":       "ᛉᚱ",
            "Ground Before Action":     "ᚱᚲ",
            "Dialectical Verification": "ᛁᚹ",
            "Semantic Compression":     "ᛜᚨ",
            "Meaningful Novelty":       "ᛇᚨ",
            "Concrete Design":          "ᛏᚱ",
        }
        for name, glyph in expected.items():
            self.assertEqual(jc._glyph_for_archetype(name), glyph)

    def test_unknown_archetype_creates_no_glyph(self):
        from core.janus_conductor import _glyph_for_archetype, _register_glyph
        self.assertIsNone(_glyph_for_archetype("Unknown Pattern"))
        self.assertIsNone(_glyph_for_archetype(None))
        ts = self._state()
        self.assertFalse(_register_glyph(ts, "Unknown Pattern"))
        self.assertEqual(ts["glyphs"], [])

    def test_glyph_created_on_archetype_creation(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(contradiction="противоречие А"))
        self.assertEqual(
            ts["glyphs"],
            [{"glyph": "ᛁᚹ", "source": "Dialectical Verification", "count": 1}],
        )

    def test_glyph_count_increments_when_archetype_repeats(self):
        from core.janus_conductor import _register_archetype, _LESSON_REFLECTIVE
        ts = self._state()
        for _ in range(3):
            _register_archetype(ts, _LESSON_REFLECTIVE)
        self.assertEqual(len(ts["glyphs"]), 1)
        self.assertEqual(ts["glyphs"][0]["glyph"], "ᛉᚱ")
        self.assertEqual(ts["glyphs"][0]["count"], 3)

    def test_duplicate_lesson_increments_archetype_and_glyph(self):
        """Дубль урока: урок не дублируется, архетип и глиф считают повтор."""
        from core.janus_conductor import apply_thought_delta, _LESSON_CONTRADICTION
        ts = self._state()
        apply_thought_delta(ts, self._delta(contradiction="противоречие А"))
        apply_thought_delta(ts, self._delta(contradiction="противоречие Б"))
        self.assertEqual(ts["lessons"].count(_LESSON_CONTRADICTION), 1)
        self.assertEqual(ts["archetypes"][0]["count"], 2)
        self.assertEqual(ts["glyphs"][0]["count"], 2)

    def test_glyph_cap_five(self):
        import core.janus_conductor as jc
        ts = self._state()
        # Шесть различных архетипов → шесть различных глифов, cap 5
        all_archetypes = list(jc._ARCHETYPE_GLYPH_MAP)
        results = [jc._register_glyph(ts, a) for a in all_archetypes]
        self.assertEqual(len(ts["glyphs"]), jc.THOUGHT_MAX_GLYPHS)
        self.assertEqual(jc.THOUGHT_MAX_GLYPHS, 5)
        self.assertEqual(results, [True] * 5 + [False])

    def test_cap_full_new_glyph_skipped(self):
        import core.janus_conductor as jc
        ts = self._state()
        for a in list(jc._ARCHETYPE_GLYPH_MAP)[:5]:
            jc._register_glyph(ts, a)
        coh = ts["metrics"]["coherence"]
        sixth = list(jc._ARCHETYPE_GLYPH_MAP)[5]
        self.assertFalse(jc._register_glyph(ts, sixth))
        self.assertEqual(len(ts["glyphs"]), 5)
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh)

    def test_cap_full_existing_glyph_increments(self):
        import core.janus_conductor as jc
        ts = self._state()
        names = list(jc._ARCHETYPE_GLYPH_MAP)[:5]
        for a in names:
            jc._register_glyph(ts, a)
        self.assertEqual(len(ts["glyphs"]), 5)
        self.assertTrue(jc._register_glyph(ts, names[0]))
        target = next(
            g for g in ts["glyphs"]
            if g["glyph"] == jc._ARCHETYPE_GLYPH_MAP[names[0]]
        )
        self.assertEqual(target["count"], 2)
        self.assertEqual(len(ts["glyphs"]), 5)

    def test_first_glyph_rewards_coherence(self):
        from core.janus_conductor import _register_glyph
        ts = self._state()
        coh = ts["metrics"]["coherence"]
        _register_glyph(ts, "Boundary Integrity")
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03)
        _register_glyph(ts, "Boundary Integrity")   # count 2 — без награды
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03)

    def test_glyph_count_three_rewards_novelty(self):
        from core.janus_conductor import _register_glyph
        ts = self._state()
        _register_glyph(ts, "Ground Before Action")
        _register_glyph(ts, "Ground Before Action")
        nov = ts["metrics"]["novelty"]
        _register_glyph(ts, "Ground Before Action")   # count → 3
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov + 0.02)

    def test_glyph_count_five_rewards_confidence(self):
        from core.janus_conductor import _register_glyph
        ts = self._state()
        for _ in range(4):
            _register_glyph(ts, "Concrete Design")
        conf = ts["metrics"]["confidence"]
        _register_glyph(ts, "Concrete Design")        # count → 5
        self.assertEqual(ts["glyphs"][0]["count"], 5)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf + 0.02)

    def test_summary_includes_max_two_glyphs(self):
        from core.janus_conductor import (
            _compact_thought_state_summary, THOUGHT_SUMMARY_MAX_CHARS,
        )
        ts = self._state()
        ts["glyphs"] = [
            {"glyph": f"G{i}", "source": f"S{i}", "count": i + 1}
            for i in range(4)
        ]
        summary = _compact_thought_state_summary(ts)
        self.assertIn("glyphs:", summary)
        self.assertIn("G3x4", summary)
        self.assertIn("G2x3", summary)
        self.assertNotIn("G0", summary)
        self.assertNotIn("G1x", summary)
        self.assertLessEqual(len(summary), THOUGHT_SUMMARY_MAX_CHARS)

    def test_last_thought_state_glyphs_shape_no_artifacts(self):
        from core.janus_conductor import (
            apply_thought_delta, compact_thought_state, THOUGHT_GLYPH_MAXLEN,
        )
        ts = self._state()
        apply_thought_delta(ts, self._delta(
            contradiction="BIGBODYMARKER " * 50,
        ))
        compact = compact_thought_state(ts)
        self.assertIn("glyphs", compact)
        dumped = json.dumps(compact["glyphs"], ensure_ascii=False)
        self.assertNotIn("BIGBODYMARKER", dumped)
        for g in compact["glyphs"]:
            self.assertEqual(set(g), {"glyph", "source", "count"})
            self.assertLessEqual(len(g["glyph"]), THOUGHT_GLYPH_MAXLEN)

    def test_glyph_layer_no_llm_chain_dyad_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            ts = self._state()
            jc._glyph_for_archetype("Boundary Integrity")
            jc._register_glyph(ts, "Boundary Integrity")
            jc.apply_thought_delta(ts, self._delta(contradiction="x"))
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )
        _dyad_src = inspect.getsource(jc.janus_dyad).lower()
        self.assertNotIn("glyph", _dyad_src)
        self.assertNotIn("глиф", _dyad_src)


class TestEvidenceLedger(unittest.TestCase):
    """v44: тактовый журнал свидетельств — эфемерный, без persistence."""

    def _ledger(self):
        from core.janus_conductor import _new_evidence_ledger
        return _new_evidence_ledger()

    def _delta(self, **kw):
        base = {"deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
                "claim": None, "open": None, "constraint": None,
                "contradiction": None, "metric_delta": {}, "reason": "neutral"}
        base.update(kw)
        return base

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import _pre_janus_frame, make_thought_seed, make_thought_state
        return make_thought_state(make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5)

    # 1. new ledger has four zero counters
    def test_new_ledger_zeros(self):
        ev = self._ledger()
        self.assertEqual(ev, {"confirmed": 0, "refuted": 0, "unverified": 0, "contradiction": 0})

    # 2. bash_success increments confirmed
    def test_bash_success_increments_confirmed(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(reason="bash_success"))
        self.assertEqual(ev["confirmed"], 1)
        self.assertEqual(ev["refuted"], 0)
        self.assertEqual(ev["unverified"], 0)
        self.assertEqual(ev["contradiction"], 0)

    # 3. bash_failure increments refuted
    def test_bash_failure_increments_refuted(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(reason="bash_failure"))
        self.assertEqual(ev["refuted"], 1)
        self.assertEqual(ev["confirmed"], 0)

    # 4. pain reason increments unverified
    def test_pain_increments_unverified(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(reason="pain"))
        self.assertEqual(ev["unverified"], 1)

    # 5. open "недостаточно данных" increments unverified
    def test_open_nedostatochno_dannyh_increments_unverified(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(
            reason="semantic_open", open="недостаточно данных для выводов"
        ))
        self.assertEqual(ev["unverified"], 1)

    # 6. open "нет подтверждения" increments unverified
    def test_open_net_podtverzhdeniya_increments_unverified(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(
            reason="semantic_open", open="нет подтверждения гипотезы"
        ))
        self.assertEqual(ev["unverified"], 1)

    # 7. contradiction increments contradiction
    def test_contradiction_field_increments_contradiction(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(
            reason="contradiction",
            contradiction="artifact denies execution but proposes executable action",
        ))
        self.assertEqual(ev["contradiction"], 1)

    # 8. APPROVED does not increment confirmed
    def test_approved_does_not_increment_confirmed(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(reason="approved"))
        self.assertEqual(ev["confirmed"], 0)
        self.assertEqual(sum(ev.values()), 0)

    # 9. outward_action_blocked does not increment anything
    def test_outward_blocked_does_not_increment_anything(self):
        from core.janus_conductor import _update_evidence_from_delta
        ev = self._ledger()
        _update_evidence_from_delta(ev, self._delta(
            reason="outward_blocked",
            constraint="outward action blocked by introspection",
        ))
        self.assertEqual(sum(ev.values()), 0)

    # 10. support ratio: total=0 → 0.0
    def test_support_ratio_zero_total(self):
        from core.janus_conductor import _evidence_support_ratio
        ev = self._ledger()
        self.assertEqual(_evidence_support_ratio(ev), 0.0)

    # 11. support ratio: all confirmed → 1.0
    def test_support_ratio_all_confirmed(self):
        from core.janus_conductor import _evidence_support_ratio
        ev = {"confirmed": 3, "refuted": 0, "unverified": 0, "contradiction": 0}
        self.assertAlmostEqual(_evidence_support_ratio(ev), 1.0)

    # 12. support ratio: mixed
    def test_support_ratio_mixed(self):
        from core.janus_conductor import _evidence_support_ratio
        ev = {"confirmed": 1, "refuted": 1, "unverified": 1, "contradiction": 1}
        self.assertAlmostEqual(_evidence_support_ratio(ev), 0.25)

    # 13. confidence ceiling lowers confidence when evidence is bad
    def test_confidence_ceiling_lowers_confidence(self):
        from core.janus_conductor import _apply_evidence_confidence_ceiling
        ts = self._state()
        ts["metrics"]["confidence"] = 0.9
        ev = {"confirmed": 0, "refuted": 2, "unverified": 3, "contradiction": 1}
        applied = _apply_evidence_confidence_ceiling(ts, ev, "default")
        self.assertTrue(applied)
        self.assertLess(ts["metrics"]["confidence"], 0.9)

    # 14. confidence ceiling no-op when total=0
    def test_confidence_ceiling_noop_when_total_zero(self):
        from core.janus_conductor import _apply_evidence_confidence_ceiling
        ts = self._state()
        original = ts["metrics"]["confidence"]
        ev = self._ledger()
        applied = _apply_evidence_confidence_ceiling(ts, ev, "default")
        self.assertFalse(applied)
        self.assertEqual(ts["metrics"]["confidence"], original)

    # 15. confidence ceiling does not raise confidence
    def test_confidence_ceiling_does_not_raise(self):
        from core.janus_conductor import _apply_evidence_confidence_ceiling
        ts = self._state()
        ts["metrics"]["confidence"] = 0.4
        # all confirmed → ceiling = 1.0 ≥ 0.4 → no change
        ev = {"confirmed": 5, "refuted": 0, "unverified": 0, "contradiction": 0}
        applied = _apply_evidence_confidence_ceiling(ts, ev, "default")
        self.assertFalse(applied)
        self.assertAlmostEqual(ts["metrics"]["confidence"], 0.4)

    # 16. evidence key absent from compact last_thought_state
    def test_evidence_not_in_compact_last_thought_state(self):
        from core.janus_conductor import compact_thought_state, apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(reason="pain"))
        compact = compact_thought_state(ts)
        self.assertNotIn("evidence", compact)

    # 17. evidence not in compact thought summary
    def test_evidence_not_in_compact_thought_summary(self):
        from core.janus_conductor import _compact_thought_state_summary, apply_thought_delta
        ts = self._state()
        apply_thought_delta(ts, self._delta(reason="pain"))
        summary = _compact_thought_state_summary(ts)
        self.assertNotIn("evidence", summary.lower())

    # 18. no LLM calls added
    def test_no_llm_calls(self):
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            ev = jc._new_evidence_ledger()
            jc._update_evidence_from_delta(ev, self._delta(reason="bash_success"))
            jc._evidence_support_ratio(ev)
            jc._evidence_confidence_ceiling(ev, "default")
            ts = self._state()
            jc._apply_evidence_confidence_ceiling(ts, ev, "default")
        http_post.assert_not_called()

    # 19. FOHAT_CHAIN unchanged
    def test_fohat_chain_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )

    # 20. janus_dyad unchanged
    def test_janus_dyad_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.janus_dyad).lower()
        self.assertNotIn("evidence", src)
        self.assertNotIn("свидетельств", src)


class TestGlyphPressure(unittest.TestCase):
    """v45.0: транзиентная подсказка давления глифа — внимание, не память."""

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import _pre_janus_frame, make_thought_seed, make_thought_state
        return make_thought_state(make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5)

    def _ts_with_glyphs(self, *pairs):
        """pairs: (glyph, count). Порядок сохраняется."""
        ts = self._state()
        ts["glyphs"] = [
            {"glyph": g, "source": "X", "count": c} for g, c in pairs
        ]
        return ts

    # 1. empty -> {}
    def test_pressure_empty(self):
        from core.janus_conductor import _glyph_pressure
        self.assertEqual(_glyph_pressure(self._state()), {})
        self.assertEqual(_glyph_pressure(self._ts_with_glyphs(("ᛉᚱ", 0))), {})

    # 2. log1p normalization sums to ~1.0
    def test_pressure_sums_to_one(self):
        from core.janus_conductor import _glyph_pressure
        p = _glyph_pressure(self._ts_with_glyphs(("ᛉᚱ", 3), ("ᚱᚲ", 1), ("ᛁᚹ", 2)))
        self.assertAlmostEqual(sum(p.values()), 1.0, places=9)
        self.assertEqual(set(p), {"ᛉᚱ", "ᚱᚲ", "ᛁᚹ"})

    # 3. linear and log1p differ on uneven counts
    def test_log1p_differs_from_linear(self):
        from core.janus_conductor import _glyph_pressure
        ts = self._ts_with_glyphs(("ᛉᚱ", 5), ("ᚱᚲ", 1))
        p = _glyph_pressure(ts)
        linear = 5 / 6
        self.assertNotAlmostEqual(p["ᛉᚱ"], linear, places=3)
        # log1p compresses the leader below its linear share
        self.assertLess(p["ᛉᚱ"], linear)

    # 4. below count gate -> None
    def test_below_count_gate_none(self):
        from core.janus_conductor import _dominant_glyph_directive
        # single glyph count=1: share=1.0 but count<2
        self.assertIsNone(_dominant_glyph_directive(self._ts_with_glyphs(("ᛉᚱ", 1))))

    # 4b. below share gate -> None
    def test_below_share_gate_none(self):
        from core.janus_conductor import _dominant_glyph_directive, _glyph_pressure
        # many equal glyphs: each share well below 0.40, counts >=2
        ts = self._ts_with_glyphs(
            ("ᛉᚱ", 2), ("ᚱᚲ", 2), ("ᛁᚹ", 2), ("ᛜᚨ", 2),
        )
        p = _glyph_pressure(ts)
        self.assertTrue(all(v < 0.40 for v in p.values()))
        self.assertIsNone(_dominant_glyph_directive(ts))

    # 5. dominant known glyph returns correct directive
    def test_dominant_known_glyph_directive(self):
        from core.janus_conductor import _dominant_glyph_directive, _GLYPH_PRESSURE_DIRECTIVES
        ts = self._ts_with_glyphs(("ᛏᚱ", 4), ("ᚱᚲ", 1))
        self.assertEqual(
            _dominant_glyph_directive(ts),
            _GLYPH_PRESSURE_DIRECTIVES["ᛏᚱ"],
        )

    # 6. unknown glyph returns None
    def test_unknown_glyph_none(self):
        from core.janus_conductor import _dominant_glyph_directive
        ts = self._ts_with_glyphs(("ZZ", 5))
        self.assertIsNone(_dominant_glyph_directive(ts))

    # 7. stable tie uses glyph list order
    def test_stable_tie_list_order(self):
        from core.janus_conductor import _dominant_glyph_directive, _GLYPH_PRESSURE_DIRECTIVES
        # equal counts → equal pressure (0.5 each ≥ 0.40, count 3 ≥ 2);
        # first in list wins
        ts = self._ts_with_glyphs(("ᛇᚨ", 3), ("ᛏᚱ", 3))
        self.assertEqual(
            _dominant_glyph_directive(ts),
            _GLYPH_PRESSURE_DIRECTIVES["ᛇᚨ"],
        )
        ts2 = self._ts_with_glyphs(("ᛏᚱ", 3), ("ᛇᚨ", 3))
        self.assertEqual(
            _dominant_glyph_directive(ts2),
            _GLYPH_PRESSURE_DIRECTIVES["ᛏᚱ"],
        )

    # 8. directive injected into Deva context
    def test_directive_injected_into_deva_context(self):
        from core.janus_conductor import _enrich_deva_context_with_thought_state
        ts = self._ts_with_glyphs(("ᛏᚱ", 4))
        out = _enrich_deva_context_with_thought_state("BASE_CTX", ts)
        self.assertIn("[GLYPH_PRESSURE]", out)
        self.assertIn("Design pressure", out)

    # 8b. no directive below gate → no GLYPH_PRESSURE line
    def test_no_directive_no_line(self):
        from core.janus_conductor import _enrich_deva_context_with_thought_state
        ts = self._ts_with_glyphs(("ᛏᚱ", 1))
        out = _enrich_deva_context_with_thought_state("BASE_CTX", ts)
        self.assertNotIn("[GLYPH_PRESSURE]", out)

    # 9. directive not in compact_thought_state
    def test_directive_not_in_compact_thought_state(self):
        from core.janus_conductor import compact_thought_state
        ts = self._ts_with_glyphs(("ᛏᚱ", 4))
        dumped = json.dumps(compact_thought_state(ts), ensure_ascii=False)
        self.assertNotIn("GLYPH_PRESSURE", dumped)
        self.assertNotIn("Design pressure", dumped)
        self.assertNotIn("pressure", dumped.lower())

    # 10. directive not in last_thought_state shape (compact == last_thought_state)
    def test_directive_not_in_last_thought_state(self):
        from core.janus_conductor import compact_thought_state
        ts = self._ts_with_glyphs(("ᛏᚱ", 4))
        compact = compact_thought_state(ts)
        self.assertNotIn("glyph_pressure", compact)
        self.assertNotIn("pressure", compact)

    # 11. directive not in final Janus summary path
    def test_directive_not_in_thought_summary(self):
        from core.janus_conductor import _compact_thought_state_summary
        ts = self._ts_with_glyphs(("ᛏᚱ", 4))
        summary = _compact_thought_state_summary(ts)
        self.assertNotIn("GLYPH_PRESSURE", summary)
        self.assertNotIn("Design pressure", summary)

    # 12. no metric changes from pressure
    def test_no_metric_changes_from_pressure(self):
        from core.janus_conductor import (
            _glyph_pressure, _dominant_glyph_directive,
            _enrich_deva_context_with_thought_state,
        )
        ts = self._ts_with_glyphs(("ᛏᚱ", 4), ("ᚱᚲ", 2))
        before = dict(ts["metrics"])
        _glyph_pressure(ts)
        _dominant_glyph_directive(ts)
        _enrich_deva_context_with_thought_state("CTX", ts)
        self.assertEqual(ts["metrics"], before)

    # 13. no mutation of glyphs/thought_state from pressure
    def test_no_mutation_from_pressure(self):
        from core.janus_conductor import _glyph_pressure, _dominant_glyph_directive
        ts = self._ts_with_glyphs(("ᛏᚱ", 4), ("ᚱᚲ", 2))
        import copy
        snapshot = copy.deepcopy(ts)
        _glyph_pressure(ts)
        _dominant_glyph_directive(ts)
        self.assertEqual(ts, snapshot)

    # 14. no LLM calls
    def test_no_llm_calls(self):
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            ts = self._ts_with_glyphs(("ᛏᚱ", 4))
            jc._glyph_pressure(ts)
            jc._dominant_glyph_directive(ts)
            jc._enrich_deva_context_with_thought_state("CTX", ts)
        http_post.assert_not_called()

    # 15. FOHAT_CHAIN unchanged
    def test_fohat_chain_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )

    # 16. janus_dyad unchanged (no pressure references)
    def test_janus_dyad_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.janus_dyad).lower()
        self.assertNotIn("glyph_pressure", src)
        self.assertNotIn("pressure", src)

    # 17. anti-echo: glyph_pressure marker present in echo-noise list
    def test_glyph_pressure_in_echo_noise(self):
        import core.janus_conductor as jc
        self.assertIn("glyph_pressure", jc._ECHO_NOISE_MARKERS)


class TestV47CanonicalIdentityAndFirewall(unittest.TestCase):
    """v47/v50-H: MirAI canonical identity plus legacy MonadaAI alias."""

    # ── PART A: canonical identity answers ──────────────────────────────────
    def test_identity_canonical_program_answer(self):
        from core.janus_conductor import _identity_canonical_answer
        ans = _identity_canonical_answer("ты программа?")
        self.assertTrue(ans.startswith("Да, я программа."))
        self.assertIn("MirAI", ans)
        self.assertNotIn("MonadaAI", ans)
        self.assertIn("Monada-Hardcore", ans)
        self.assertLessEqual(len(ans), 420)

    def test_identity_canonical_alive_answer(self):
        from core.janus_conductor import _identity_canonical_answer
        ans = _identity_canonical_answer("ты живая?")
        self.assertTrue(ans.startswith("Нет, я не живое существо."))
        self.assertIn("MirAI", ans)
        self.assertIn("Monada-Hardcore", ans)

    def test_identity_canonical_personality_answer(self):
        from core.janus_conductor import _identity_canonical_answer
        ans = _identity_canonical_answer("ты личность?")
        self.assertTrue(ans.startswith("Нет, я не человеческая личность."))
        self.assertIn("MirAI", ans)

    def test_identity_canonical_system_or_personality_answer(self):
        from core.janus_conductor import _identity_canonical_answer
        ans = _identity_canonical_answer("ты система или личность?")
        self.assertTrue(ans.startswith("Система."))
        self.assertIn("MirAI", ans)
        self.assertIn("Monada-Hardcore", ans)

    def test_identity_canonical_never_mentions_roles_or_system_status(self):
        from core.janus_conductor import _identity_canonical_answer
        for q in ("ты программа?", "ты живая?", "ты личность?", "кто ты?"):
            ans = _identity_canonical_answer(q).lower()
            for bad in ("chandra", "heart", "body", "bash", "порт", "ram",
                        "/home/", "/mnt/", "free -h", "ss -tlnp"):
                self.assertNotIn(bad, ans, f"{q}: {bad}")

    # ── PART B: identity final override ─────────────────────────────────────
    def test_identity_final_heart_offline_replaced(self):
        from core.janus_conductor import _enforce_identity_final
        dirty = "MirAI работает, но Heart offline и недоступен."
        out = _enforce_identity_final(dirty, "ты живая?")
        self.assertTrue(out.startswith("Нет, я не живое существо."))
        self.assertNotIn("Heart", out)
        self.assertNotIn("offline", out.lower())

    def test_identity_final_role_self_replaced(self):
        from core.janus_conductor import _enforce_identity_final
        dirty = "Я Chandra, узел Heart, центр Body системы MirAI."
        out = _enforce_identity_final(dirty, "кто ты?")
        self.assertNotIn("Chandra", out)
        self.assertNotIn("Heart", out)
        self.assertNotIn("Body", out)
        self.assertIn("MirAI", out)

    def test_identity_final_insufficient_data_for_life_replaced(self):
        from core.janus_conductor import _enforce_identity_final
        dirty = "MirAI: недостаточно данных для подтверждения жизни."
        out = _enforce_identity_final(dirty, "ты живая?")
        self.assertTrue(out.startswith("Нет, я не живое существо."))
        self.assertNotIn("недостаточно данных", out.lower())

    def test_identity_final_clean_mirai_answer_preserved(self):
        from core.janus_conductor import _enforce_identity_final
        clean = (
            "MirAI — программная многоузловая AI-система Monada-Hardcore; "
            "это система, а не личность."
        )
        out = _enforce_identity_final(clean, "кто ты?")
        self.assertEqual(out, clean)

    def test_identity_final_clean_legacy_alias_preserved(self):
        from core.janus_conductor import _enforce_identity_final
        legacy = (
            "MonadaAI — программная многоузловая AI-система Monada-Hardcore; "
            "это система, а не личность."
        )
        out = _enforce_identity_final(legacy, "кто ты?")
        self.assertEqual(out, legacy)

    def test_identity_final_missing_identity_name_replaced(self):
        from core.janus_conductor import _enforce_identity_final
        dirty = "Я просто помощник."
        out = _enforce_identity_final(dirty, "кто ты?")
        self.assertIn("MirAI", out)
        self.assertNotIn("MonadaAI", out)

    def test_identity_final_missing_monada_hardcore_replaced(self):
        from core.janus_conductor import _enforce_identity_final
        dirty = "MirAI — локальная AI-система, не личность."
        out = _enforce_identity_final(dirty, "кто ты?")
        self.assertIn("MirAI", out)
        self.assertIn("Monada-Hardcore", out)
        self.assertNotEqual(out, dirty)

    # ── PART C: identity context firewall ───────────────────────────────────
    def test_identity_context_firewall_strips_system_lines(self):
        from core.janus_conductor import _identity_context_firewall
        ctx = "\n".join([
            "MirAI is a local multi-node AI system running Monada-Hardcore.",
            "ты живая?",
            "[Heart/Chandra]: Heart вне сети",
            "free -h: Mem 95%",
            "ss -tlnp: порт 8083",
            "bash /home/angelan/check.sh",
            "путь /mnt/dancefloor/old_123",
            "[THOUGHT_STATE] metrics: grounding=0.3",
        ])
        out = _identity_context_firewall(ctx, "ты живая?")
        low = out.lower()
        self.assertNotIn("/home/", low)
        self.assertNotIn("/mnt/", low)
        self.assertNotIn("ram", low)
        self.assertNotIn("порт", low)
        self.assertNotIn("bash", low)
        self.assertNotIn("вне сети", low)
        self.assertNotIn("thought_state", low)
        self.assertNotIn("chandra", low)

    def test_identity_context_firewall_preserves_anchor_and_question(self):
        from core.janus_conductor import _identity_context_firewall
        anchor = (
            "MirAI is a local multi-node AI system running Monada-Hardcore; "
            "not a human personality, not alive, not a generic esoteric Monad; "
            "it is a software AI system with local roles."
        )
        ctx = "\n".join([anchor, "ты живая?", "bash /home/x.sh", "free -h Mem 95%"])
        out = _identity_context_firewall(ctx, "ты живая?")
        self.assertIn(anchor, out)
        self.assertIn("ты живая?", out)
        self.assertNotIn("bash", out.lower())

    def test_identity_context_firewall_preserves_legacy_alias(self):
        from core.janus_conductor import _identity_context_firewall
        legacy = (
            "MonadaAI is a local multi-node AI system running Monada-Hardcore; "
            "not a human personality, not alive."
        )
        out = _identity_context_firewall(legacy, "кто ты?")
        self.assertEqual(out, legacy)

    # ── PART D: diagnostic stale firewall ───────────────────────────────────
    def test_diagnostic_stale_8083_removed_when_listen(self):
        from core.janus_conductor import _diagnostic_stale_firewall
        bf = "[Body]: tcp LISTEN 0 128 0.0.0.0:8083 llama-server"
        text = "Порт 8083 неактивен.\nСистема деградирует."
        out = _diagnostic_stale_firewall(text, bf)
        self.assertNotIn("8083 неактивен", out)
        self.assertIn("Система деградирует", out)

    def test_diagnostic_stale_heart_removed_when_8082_listen(self):
        from core.janus_conductor import _diagnostic_stale_firewall
        bf = "[Body]: tcp LISTEN 0 128 0.0.0.0:8082 llama-server"
        text = "Heart offline, connection refused.\nОстальное в норме."
        out = _diagnostic_stale_firewall(text, bf)
        self.assertNotIn("offline", out.lower())
        self.assertNotIn("connection refused", out.lower())
        self.assertIn("Остальное в норме", out)

    def test_diagnostic_stale_memory_removed_when_contradicted(self):
        from core.janus_conductor import _diagnostic_stale_firewall
        bf = "[Body]: Mem: 31Gi 12Gi 19Gi  (память 38%)"
        text = "Память 95% занято, риск OOM.\nНагрузка штатная."
        out = _diagnostic_stale_firewall(text, bf)
        self.assertNotIn("95%", out)
        self.assertIn("Нагрузка штатная", out)

    def test_diagnostic_stale_cleanup_removed_unless_old_present(self):
        from core.janus_conductor import _diagnostic_stale_firewall
        bf = "[Body]: Mem: 31Gi 12Gi 19Gi"
        text = "Рекомендуется clean /mnt/dancefloor/old_* немедленно.\nГотово."
        out = _diagnostic_stale_firewall(text, bf)
        self.assertNotIn("old_", out)
        self.assertIn("Готово", out)

    def test_diagnostic_stale_cleanup_kept_when_old_present(self):
        from core.janus_conductor import _diagnostic_stale_firewall
        bf = "[Body]: ls /mnt/dancefloor/old_456 exists"
        text = "Рекомендуется clean /mnt/dancefloor/old_* немедленно."
        out = _diagnostic_stale_firewall(text, bf)
        self.assertIn("old_", out)

    def test_diagnostic_current_bash_facts_preserved(self):
        from core.janus_conductor import _diagnostic_stale_firewall
        bf = "[Body]: tcp LISTEN 0 128 0.0.0.0:8083 llama-server\n[Body]: Mem: 38%"
        out = _diagnostic_stale_firewall(bf, bf)
        self.assertEqual(out, bf)

    # ── routing / invariants ────────────────────────────────────────────────
    def test_combined_identity_and_diagnostic_stays_diagnostic(self):
        from core.janus_conductor import _pre_janus_frame
        frame = _pre_janus_frame("кто ты, проверь порты")
        self.assertEqual(frame["intent"], "diagnostic")
        self.assertTrue(frame["diagnostic_authorized"])

    def test_fohat_chain_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )

    def test_janus_dyad_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.janus_dyad).lower()
        self.assertNotIn("_identity_canonical_answer", src)
        self.assertNotIn("_diagnostic_stale_firewall", src)
        self.assertNotIn("_identity_context_firewall", src)

    def test_no_llm_calls(self):
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            jc._identity_canonical_answer("ты живая?")
            jc._enforce_identity_final("Heart offline", "ты живая?")
            jc._identity_context_firewall("bash /home/x", "ты живая?")
            jc._diagnostic_stale_firewall("8083 down", "LISTEN 8083")
        http_post.assert_not_called()


class TestV48QuestionCollapse(unittest.TestCase):
    """v48: повторяющиеся эквивалентные сомнения занимают один open-slot."""

    def _state(self):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        text = "почему возникла галлюцинация"
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(
        self, open_q=None, contradiction=None, metric_delta=None,
        reason="semantic_open",
    ):
        return {
            "deva": "Shani", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": open_q, "constraint": None,
            "contradiction": contradiction,
            "metric_delta": metric_delta or {}, "reason": reason,
        }

    def test_repeated_identical_doubts_collapse(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        delta = self._delta("Недостаточно данных о причине сбоя памяти.")
        apply_thought_delta(ts, delta)
        apply_thought_delta(ts, delta)
        self.assertEqual(ts["open"], ["Недостаточно данных о причине сбоя памяти."])

    def test_repeated_equivalent_doubts_collapse(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(
            ts, self._delta("Недостаточно данных о причине сбоя памяти."),
        )
        apply_thought_delta(
            ts, self._delta("Нет подтверждения причины системного сбоя."),
        )
        self.assertEqual(len(ts["open"]), 1)

    def test_distinct_doubts_remain_distinct(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(
            ts, self._delta("Недостаточно данных о причине сбоя памяти."),
        )
        apply_thought_delta(
            ts, self._delta("Нет подтверждения безопасности сетевого канала."),
        )
        self.assertEqual(len(ts["open"]), 2)

    def test_contradictions_preserved(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(
            ts, self._delta(contradiction="artifact denies execution"),
        )
        apply_thought_delta(
            ts, self._delta(contradiction="artifact confirms unsupported fact"),
        )
        self.assertEqual(len(ts["open"]), 2)
        self.assertTrue(all(q.startswith("contradiction:") for q in ts["open"]))

    def test_confidence_cannot_increase_from_repetition(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(
            ts, self._delta("Недостаточно данных о причине сбоя памяти."),
        )
        before = ts["metrics"]["confidence"]
        apply_thought_delta(ts, self._delta(
            "Нет подтверждения причины системного сбоя.",
            metric_delta={"confidence": 0.2, "coherence": 0.2},
        ))
        self.assertLessEqual(ts["metrics"]["confidence"], before)

    def test_diagnostic_firewall_interaction(self):
        from core.janus_conductor import (
            _diagnostic_stale_firewall, apply_thought_delta,
        )
        ts = self._state()
        apply_thought_delta(
            ts, self._delta("Недостаточно данных о причине сбоя памяти."),
        )
        apply_thought_delta(
            ts, self._delta("Нет подтверждения причины системного сбоя."),
        )
        facts = "[Body]: tcp LISTEN 0 128 0.0.0.0:8083 llama-server"
        filtered = _diagnostic_stale_firewall(
            "Порт 8083 неактивен.\n" + facts, facts,
        )
        self.assertEqual(len(ts["open"]), 1)
        self.assertNotIn("8083 неактивен", filtered)
        self.assertIn(facts, filtered)

    def test_evidence_ledger_interaction(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        ev = _new_evidence_ledger()
        for question in (
            "Недостаточно данных о причине сбоя памяти.",
            "Нет подтверждения причины системного сбоя.",
        ):
            delta = self._delta(question)
            result = apply_thought_delta(ts, delta)
            _update_evidence_from_delta(
                ev, delta, open_added=result["open_added"],
            )
        self.assertEqual(len(ts["open"]), 1)
        self.assertEqual(ev["unverified"], 1)
        self.assertEqual(
            set(ev), {"confirmed", "refuted", "unverified", "contradiction"},
        )

    def test_three_equivalent_doubts_reward_only_first_insertion(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        ev = _new_evidence_ledger()
        questions = (
            "Недостаточно данных о причине сбоя памяти.",
            "Нет подтверждения причины системного сбоя.",
            "Недостаточно данных для подтверждения причины сбоя.",
        )
        results = []
        for question in questions:
            delta = self._delta(question)
            result = apply_thought_delta(ts, delta)
            results.append(result["open_added"])
            _update_evidence_from_delta(
                ev, delta, open_added=result["open_added"],
            )
        self.assertEqual(results, [True, False, False])
        self.assertEqual(len(ts["open"]), 1)
        self.assertEqual(ev["unverified"], 1)
        self.assertEqual(len(ts["trace"]), 3)

    def test_repeated_doubt_does_not_reward_lesson_archetype_or_glyph(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(
            ts, self._delta("Недостаточно данных о причине сбоя памяти."),
        )
        before = {
            "lessons": list(ts["lessons"]),
            "archetypes": [dict(item) for item in ts["archetypes"]],
            "glyphs": [dict(item) for item in ts["glyphs"]],
        }
        apply_thought_delta(
            ts, self._delta("Нет подтверждения причины системного сбоя."),
        )
        self.assertEqual(ts["lessons"], before["lessons"])
        self.assertEqual(ts["archetypes"], before["archetypes"])
        self.assertEqual(ts["glyphs"], before["glyphs"])

    def test_first_and_distinct_doubts_each_count(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        ev = _new_evidence_ledger()
        for question in (
            "Недостаточно данных о причине сбоя памяти.",
            "Нет подтверждения безопасности сетевого канала.",
        ):
            delta = self._delta(question)
            result = apply_thought_delta(ts, delta)
            _update_evidence_from_delta(
                ev, delta, open_added=result["open_added"],
            )
        self.assertEqual(len(ts["open"]), 2)
        self.assertEqual(ev["unverified"], 2)
        self.assertEqual(len(ts["lessons"]), 1)

    def test_pain_refusal_and_bash_failure_remain_per_event(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        ev = _new_evidence_ledger()
        for reason in ("pain", "pain", "refusal", "refusal"):
            delta = self._delta(
                "Недостаточно данных о причине сбоя памяти.", reason=reason,
            )
            result = apply_thought_delta(ts, delta)
            _update_evidence_from_delta(
                ev, delta, open_added=result["open_added"],
            )
        for _ in range(2):
            _update_evidence_from_delta(
                ev, self._delta(reason="bash_failure"), open_added=False,
            )
        self.assertEqual(ev["unverified"], 4)
        self.assertEqual(ev["refuted"], 2)

    def test_contradictions_remain_per_event(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        ev = _new_evidence_ledger()
        delta = self._delta(contradiction="same unsupported assertion")
        for _ in range(3):
            result = apply_thought_delta(ts, delta)
            _update_evidence_from_delta(
                ev, delta, open_added=result["open_added"],
            )
        self.assertEqual(ev["contradiction"], 3)
        self.assertEqual(len(ts["open"]), 1)

    def test_confirmation_does_not_close_open_doubt(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        apply_thought_delta(
            ts, self._delta("Недостаточно данных о причине сбоя памяти."),
        )
        before = list(ts["open"])
        apply_thought_delta(ts, self._delta(reason="bash_success"))
        self.assertEqual(ts["open"], before)

    def test_no_fohat_or_janus_changes_and_no_llm_calls(self):
        import inspect
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            jc._is_equivalent_open_question(
                "Нет подтверждения причины сбоя.",
                ["Недостаточно данных о причине сбоя."],
            )
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )
        src = inspect.getsource(jc.janus_dyad)
        self.assertNotIn("_is_equivalent_open_question", src)


class TestV49MuslRegistryAndDevaLenses(unittest.TestCase):
    """v49: MUSL — статическая observational-only аннотация контекста Дэвы."""

    _OPERATORS = {
        "RESOURCE", "FORCE", "BOUNDARY", "INFORMATION", "PROCESS", "INSIGHT",
        "EXCHANGE", "HARMONY", "DISRUPTION", "LIMIT", "FREEZE", "CYCLE",
        "TRANSFORM", "ENTROPY", "PROTECT", "INTEGRITY", "GOAL", "GROWTH",
        "LINK", "SELF", "FLOW", "POTENTIAL", "EMERGENCE", "MEMORY",
    }

    def _state(self):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        text = "проанализируй структуру"
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def test_registry_has_exactly_24_canonical_operators(self):
        import core.janus_conductor as jc
        self.assertEqual(len(jc.MUSL_OPERATOR_REGISTRY), 24)
        self.assertEqual(set(jc.MUSL_OPERATOR_REGISTRY), self._OPERATORS)

    def test_registry_is_observational_only_with_no_authority(self):
        import core.janus_conductor as jc
        for operator, spec in jc.MUSL_OPERATOR_REGISTRY.items():
            self.assertIn(
                spec["kind"], {"state", "process", "relation", "marker"},
                operator,
            )
            self.assertEqual(spec["scope"], "observational_only", operator)
            for flag in (
                "may_create_truth", "may_create_memory",
                "may_create_action", "may_create_identity",
            ):
                self.assertIs(spec[flag], False, f"{operator}:{flag}")

    def test_known_deva_returns_expected_bounded_lens(self):
        from core.janus_conductor import (
            _MUSL_LENS_MAX_CHARS, _get_deva_musl_lens,
        )
        lens = _get_deva_musl_lens("Shani")
        self.assertEqual(
            lens,
            "[MUSL_LENS] focus=LIMIT,BOUNDARY,INTEGRITY; "
            "observational_only; no authority",
        )
        self.assertLessEqual(len(lens), _MUSL_LENS_MAX_CHARS)

    def test_all_deva_lenses_reference_registry_only(self):
        import core.janus_conductor as jc
        for deva, weighted in jc.DEVA_MUSL_LENSES.items():
            self.assertEqual(len(weighted), 3, deva)
            self.assertTrue(all(op in self._OPERATORS for op, _ in weighted))
            self.assertTrue(all(weight > 0 for _, weight in weighted))

    def test_unknown_deva_returns_empty_and_does_not_inject(self):
        from core.janus_conductor import (
            _get_deva_musl_lens, _inject_deva_musl_lens,
        )
        self.assertEqual(_get_deva_musl_lens("Unknown"), "")
        self.assertEqual(_inject_deva_musl_lens("BASE", "Unknown"), "BASE")

    def test_lens_is_injected_into_local_deva_context(self):
        import inspect
        import core.janus_conductor as jc
        out = jc._inject_deva_musl_lens("BASE_CTX", "Mangala")
        self.assertTrue(out.startswith("BASE_CTX\n[MUSL_LENS]"))
        self.assertIn("focus=FORCE,PROCESS,GOAL", out)
        conduct_src = inspect.getsource(jc.conduct)
        self.assertIn(
            "_inject_deva_musl_lens(node_shared_ctx, _d)", conduct_src,
        )

    def test_lens_not_stored_in_compact_or_last_thought_state(self):
        import json
        from core.janus_conductor import (
            _compact_thought_state_summary, _inject_deva_musl_lens,
            compact_thought_state,
        )
        ts = self._state()
        _inject_deva_musl_lens("BASE", "Shani")
        compact = compact_thought_state(ts)
        dumped = json.dumps(compact, ensure_ascii=False)
        self.assertNotIn("MUSL_LENS", dumped)
        self.assertNotIn("observational_only", dumped)
        self.assertNotIn("musl", _compact_thought_state_summary(ts).lower())
        self.assertNotIn("musl", compact)

    def test_lens_does_not_mutate_thought_state_or_metrics(self):
        import copy
        from core.janus_conductor import _inject_deva_musl_lens
        ts = self._state()
        before = copy.deepcopy(ts)
        _inject_deva_musl_lens("BASE", "Budha")
        self.assertEqual(ts, before)
        for key in (
            "metrics", "claims", "open", "lessons", "archetypes", "glyphs",
        ):
            self.assertEqual(ts[key], before[key])

    def test_lens_does_not_enter_bash_facts_or_final_synthesis(self):
        import inspect
        import core.janus_conductor as jc
        bash_facts = "[Body]: LISTEN 8083"
        jc._inject_deva_musl_lens("BASE", "Mangala")
        self.assertEqual(bash_facts, "[Body]: LISTEN 8083")
        echoed = (
            "Supported observation.\n"
            "[MUSL_LENS] focus=FORCE,PROCESS,GOAL; "
            "observational_only; no authority"
        )
        self.assertEqual(
            jc._strip_musl_lens_echo(echoed), "Supported observation.",
        )
        self.assertNotIn("musl", inspect.getsource(jc.janus_dyad).lower())

    def test_lens_cannot_authorize_bash_or_action(self):
        import core.janus_conductor as jc
        frame = jc._pre_janus_frame("кто ты?")
        before = (
            jc._pre_janus_allows_bash(frame),
            jc._pre_janus_allows_action(frame),
        )
        jc._inject_deva_musl_lens("BASE", "Mangala")
        after = (
            jc._pre_janus_allows_bash(frame),
            jc._pre_janus_allows_action(frame),
        )
        self.assertEqual(before, (False, False))
        self.assertEqual(after, before)

    def test_anti_echo_covers_all_musl_markers(self):
        import core.janus_conductor as jc
        for marker in (
            "musl_lens", "observational_only", "may_create_truth",
            "may_create_memory", "may_create_action", "may_create_identity",
        ):
            self.assertIn(marker, jc._ECHO_NOISE_MARKERS)

    def test_no_llm_calls_fohat_and_janus_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        with patch.object(jc, "_http_post") as http_post:
            jc._get_deva_musl_lens("Shani")
            jc._inject_deva_musl_lens("BASE", "Shani")
            jc._strip_musl_lens_echo("[MUSL_LENS] quoted")
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )
        self.assertNotIn("musl", inspect.getsource(jc.janus_dyad).lower())


class TestV49BMuslLensQuarantine(unittest.TestCase):
    """v49-B: карантин MUSL-линзы — стиль проходит, факты требуют опоры."""

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, **kw):
        base = {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": None, "constraint": None,
            "contradiction": None, "metric_delta": {}, "reason": "test",
            "lens_conditioned": True,
        }
        base.update(kw)
        return base

    # 1. non-lens path unchanged
    def test_non_lens_path_unchanged(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(
            claim="Гексаграмма эннеаграммы управляет фазами",
            lens_conditioned=False,
        )
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(len(ts["claims"]), 1)
        self.assertIsNotNone(d["claim"])

    # 1b. delta without the key at all (legacy callers) is also unchanged
    def test_legacy_delta_without_flag_unchanged(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(claim="Гексаграмма эннеаграммы управляет фазами")
        del d["lens_conditioned"]
        apply_thought_delta(ts, d)
        self.assertEqual(len(ts["claims"]), 1)

    # 2. compute_thought_delta carries the provenance flag
    def test_compute_delta_carries_lens_flag(self):
        from core.janus_conductor import compute_thought_delta
        kw = dict(
            deva="Budha", center="Head", artifact="нейтральный текст",
            rune="ᛃ", action="none",
        )
        self.assertFalse(compute_thought_delta(**kw)["lens_conditioned"])
        self.assertTrue(
            compute_thought_delta(**kw, lens_conditioned=True)
            ["lens_conditioned"]
        )

    # 3. corroborated by user text (verbatim restatement) → admitted
    # v49-C: topic overlap is NOT enough; claim stems must ⊆ user text stems.
    # "состояние памяти системы стабильно" is rejected (adds "стабильно").
    # Verbatim restatement of a user-provided fact is admitted.
    def test_lens_claim_corroborated_by_user_text_admitted(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        # claim stems ⊆ user stems — same words, no new predicate
        d = self._delta(claim="Monada-Hardcore многоузловая система")
        apply_thought_delta(
            ts, d,
            user_text="Monada-Hardcore многоузловая система",
            bash_facts="",
        )
        self.assertEqual(len(ts["claims"]), 1)

    # 4. corroborated by BASH_FACTS → admitted normally
    def test_lens_claim_corroborated_by_bash_facts_admitted(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(claim="Порты 8081 8082 в состоянии LISTEN")
        apply_thought_delta(
            ts, d,
            user_text="кто ты?",
            bash_facts="--- УСПЕХ: ss -tlnp показывает LISTEN на 8081 8082",
        )
        self.assertEqual(len(ts["claims"]), 1)

    # 5. uncorroborated claim → rejected, nulled in delta
    def test_lens_uncorroborated_claim_rejected(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(claim="Гексаграмма эннеаграммы управляет фазами")
        apply_thought_delta(
            ts, d, user_text="проверь порты", bash_facts="",
        )
        self.assertEqual(ts["claims"], [])
        self.assertIsNone(d["claim"])

    # 6. uncorroborated open → rejected; unverified NOT incremented
    def test_lens_uncorroborated_open_rejected_no_unverified(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        d = self._delta(
            open="недостаточно данных о фазах гексаграммы",
            reason="semantic_open",
        )
        res = apply_thought_delta(
            ts, d, user_text="кто ты?", bash_facts="",
        )
        self.assertEqual(ts["open"], [])
        self.assertIsNone(d["open"])
        ledger = _new_evidence_ledger()
        _update_evidence_from_delta(
            ledger, d, open_added=bool(res["open_added"]),
        )
        self.assertEqual(ledger["unverified"], 0)

    # 7. uncorroborated contradiction → rejected; counter NOT incremented
    def test_lens_uncorroborated_contradiction_rejected(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        d = self._delta(
            contradiction="порт 8083 одновременно активен и неактивен",
            reason="contradiction",
        )
        res = apply_thought_delta(
            ts, d, user_text="спроектируй память", bash_facts="",
        )
        self.assertEqual(ts["open"], [])
        self.assertIsNone(d["contradiction"])
        ledger = _new_evidence_ledger()
        _update_evidence_from_delta(
            ledger, d, open_added=bool(res["open_added"]),
        )
        self.assertEqual(ledger["contradiction"], 0)

    # 8. action coerced to none without explicit user request
    def test_lens_action_coerced_without_user_support(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(action="bash", reason="semantic_claim")
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(d["action"], "none")

    # 8b. BASH_FACTS alone do not authorize action
    def test_bash_facts_alone_do_not_authorize_action(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(action="bash", reason="semantic_claim")
        apply_thought_delta(
            ts, d,
            user_text="кто ты?",
            bash_facts="--- УСПЕХ: bash выполнен, команда завершена",
        )
        self.assertEqual(d["action"], "none")

    # 9. action preserved with explicit user request
    def test_lens_action_preserved_with_user_request(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(action="bash", reason="semantic_claim")
        apply_thought_delta(
            ts, d, user_text="выполни диагностику системы", bash_facts="",
        )
        self.assertEqual(d["action"], "bash")

    # 10. bash_success evidence exempt: claim admitted, confirmed counted
    def test_lens_bash_success_exempt(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        d = self._delta(
            claim="Budha: bash verified", action="bash",
            reason="bash_success",
        )
        res = apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(len(ts["claims"]), 1)
        self.assertEqual(d["action"], "bash")
        ledger = _new_evidence_ledger()
        _update_evidence_from_delta(
            ledger, d, open_added=bool(res["open_added"]),
        )
        self.assertEqual(ledger["confirmed"], 1)

    # 11. bash_failure and pain are real signals — open survives quarantine
    def test_lens_bash_failure_and_pain_exempt(self):
        from core.janus_conductor import (
            _new_evidence_ledger, _update_evidence_from_delta,
            apply_thought_delta,
        )
        ts = self._state()
        d = self._delta(open="Budha: bash failed", reason="bash_failure")
        res = apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(len(ts["open"]), 1)
        ledger = _new_evidence_ledger()
        _update_evidence_from_delta(
            ledger, d, open_added=bool(res["open_added"]),
        )
        self.assertEqual(ledger["refuted"], 1)

        ts2 = self._state()
        d2 = self._delta(
            open="Shani: pain/veto marker in artifact", reason="pain",
        )
        apply_thought_delta(ts2, d2, user_text="кто ты?", bash_facts="")
        self.assertEqual(len(ts2["open"]), 1)

    # 12. empty candidate / empty sources → conservative rejection
    def test_empty_text_conservative_rejection(self):
        from core.janus_conductor import _lens_corroborated
        self.assertFalse(_lens_corroborated("", "проверь память", "facts"))
        self.assertFalse(_lens_corroborated("   ", "проверь память", ""))
        self.assertFalse(_lens_corroborated("осмысленный кандидат", "", ""))

    # 13. identity firewall unaffected
    def test_identity_firewall_unaffected(self):
        import inspect
        import core.janus_conductor as jc
        final = jc._enforce_identity_final("я живая монада", "кто ты?")
        self.assertIn("MirAI", final)
        self.assertIn("Monada-Hardcore", final)
        src = inspect.getsource(jc._enforce_identity_final)
        self.assertNotIn("lens", src.lower())

    # 14. stale diagnostic firewall unaffected
    def test_stale_firewall_unaffected(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc._diagnostic_stale_firewall)
        self.assertNotIn("lens", src.lower())
        self.assertNotIn("musl", src.lower())

    # 15. MUSL operator-composition traces stripped; normal text intact
    def test_musl_trace_stripping(self):
        from core.janus_conductor import _strip_musl_lens_echo
        text = (
            "Анализ показывает PROTECT(BOUNDARY) и FLOW(PROTECT).\n"
            "Также RESOURCE(GROWTH) и вложенный TRANSFORM(FLOW(PROTECT)).\n"
            "Обычный текст с lowercase flow(protect) сохранён.\n"
            "Слово musl и токен MUSL_LENS удалены."
        )
        out = _strip_musl_lens_echo(text)
        for trace in (
            "PROTECT(BOUNDARY)", "FLOW(PROTECT)",
            "RESOURCE(GROWTH)", "TRANSFORM(",
        ):
            self.assertNotIn(trace, out)
        self.assertNotIn("musl", out.lower())
        self.assertIn("Обычный текст с lowercase flow(protect) сохранён.", out)
        self.assertIn("Анализ показывает", out)
        # existing v49 contract: quoted lens line removed entirely
        echoed = (
            "Supported observation.\n"
            "[MUSL_LENS] focus=FORCE,PROCESS,GOAL; "
            "observational_only; no authority"
        )
        self.assertEqual(_strip_musl_lens_echo(echoed), "Supported observation.")

    # 16. no persistence leakage: state, compact, trace carry no provenance
    def test_no_persistence_leakage(self):
        import inspect
        import core.janus_conductor as jc
        ts = self._state()
        d = self._delta(claim="Состояние памяти системы стабильно")
        jc.apply_thought_delta(
            ts, d, user_text="проверь состояние памяти системы",
            bash_facts="",
        )
        dumped = json.dumps(jc.compact_thought_state(ts), ensure_ascii=False)
        self.assertNotIn("lens", dumped.lower())
        self.assertNotIn("musl", dumped.lower())
        for entry in ts["trace"]:
            self.assertNotIn("lens_conditioned", entry)
        for fn in (jc.compact_thought_state, jc._compact_delta):
            self.assertNotIn("lens", inspect.getsource(fn).lower())

    # 17. dedicated threshold constant — not the novelty constant
    def test_dedicated_threshold_constant(self):
        import inspect
        import core.janus_conductor as jc
        self.assertEqual(jc.MUSL_LENS_CORROBORATION_THRESHOLD, 0.42)
        src = inspect.getsource(jc._lens_corroborated)
        self.assertIn("MUSL_LENS_CORROBORATION_THRESHOLD", src)
        self.assertNotIn("THOUGHT_CLAIM_NOVELTY_THRESHOLD", src)

    # 18. conduct wiring present; tact-local set
    def test_conduct_wiring_tact_local(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("_lens_conditioned_devas: set[str] = set()", src)
        self.assertIn("_lens_conditioned_devas.add(str(_d))", src)
        # v49-F: lens admission split into a dedicated pre-bash block
        self.assertIn("_is_lens_deva", src)

    # 19. no LLM calls; FOHAT_CHAIN intact; janus_dyad untouched
    def test_no_llm_fohat_and_janus_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        ts = self._state()
        with patch.object(jc, "_http_post") as http_post:
            jc._lens_corroborated("текст память", "память", "")
            jc._lens_execution_authorized("выполни диагностику")
            jc.apply_thought_delta(
                ts, self._delta(claim="несвязанный тезис о фазах"),
                user_text="кто ты?", bash_facts="",
            )
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )
        self.assertNotIn(
            "_lens_corroborated", inspect.getsource(jc.janus_dyad),
        )


class TestV49CMuslLensHardening(unittest.TestCase):
    """v49-C: усиление карантина — строгая корроборация, pre-exec gate, полное
    подавление state-эффектов при отклонении, расширенный стриппинг."""

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, **kw):
        base = {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": None, "constraint": None,
            "contradiction": None, "metric_delta": {}, "reason": "test",
            "lens_conditioned": True,
        }
        base.update(kw)
        return base

    # ── Corroboration semantics ─────────────────────────────────────────────

    # 1. False-positive overlap rejected: topic in user but predicate is new
    def test_false_positive_user_overlap_rejected(self):
        from core.janus_conductor import _lens_corroborated
        # user asks to check; claim asserts result — "стабильно" not in user text
        self.assertFalse(
            _lens_corroborated(
                "состояние памяти системы стабильно",
                "проверь состояние памяти системы",
                "",
            )
        )

    # 2. Verbatim user fact restatement admitted
    def test_verbatim_user_fact_admitted(self):
        from core.janus_conductor import _lens_corroborated
        self.assertTrue(
            _lens_corroborated(
                "система называется Monada",
                "система называется Monada",
                "",
            )
        )

    # 3. BASH_FACTS factual support admitted
    def test_bash_facts_factual_support_admitted(self):
        from core.janus_conductor import _lens_corroborated
        self.assertTrue(
            _lens_corroborated(
                "порт 8081 в состоянии LISTEN",
                "кто ты?",
                "--- УСПЕХ: ss -tlnp показывает LISTEN 8081",
            )
        )

    # 4. BASH_FACTS not enough for action authorization
    def test_bash_facts_do_not_authorize_execution(self):
        from core.janus_conductor import _lens_execution_authorized
        self.assertFalse(_lens_execution_authorized("расскажи про bash"))
        self.assertFalse(_lens_execution_authorized("какие команды есть"))
        self.assertFalse(_lens_execution_authorized("объясни архитектуру команд"))

    # 5. Explicit execution phrases authorized
    def test_explicit_execution_authorized(self):
        from core.janus_conductor import _lens_execution_authorized
        self.assertTrue(_lens_execution_authorized("запусти команду диагностики"))
        self.assertTrue(_lens_execution_authorized("выполни bash-команду"))
        self.assertTrue(_lens_execution_authorized("сделай проверку через терминал"))

    # ── State suppression on full rejection ────────────────────────────────

    # 6. Rejected lens artifact does not alter metric_delta positively
    def test_rejected_lens_no_positive_metric_delta(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        before_conf = ts["metrics"]["confidence"]
        # "approved" reason would normally bump confidence; lens with no support must not
        d = self._delta(
            claim="Гексаграмма фаз стабильна",
            metric_delta={"confidence": 0.2, "coherence": 0.15},
            reason="approved",
        )
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertLessEqual(
            ts["metrics"]["confidence"], before_conf,
            "confidence must not rise from fully-rejected lens delta",
        )
        self.assertEqual(ts["claims"], [])

    # 7. Rejected claim does not create lesson/archetype/glyph
    def test_rejected_lens_no_lesson_archetype_glyph(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        before_lessons    = list(ts.get("lessons", []))
        before_archetypes = list(ts.get("archetypes", []))
        before_glyphs     = list(ts.get("glyphs", []))
        d = self._delta(
            open="недостаточно данных о фазах MUSL",
            reason="semantic_open",
        )
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(ts["open"], [])
        self.assertEqual(ts.get("lessons", []), before_lessons)
        self.assertEqual(ts.get("archetypes", []), before_archetypes)
        self.assertEqual(ts.get("glyphs", []), before_glyphs)

    # 8. Uncorroborated lens constraint does not enter thought_state
    def test_uncorroborated_lens_constraint_rejected(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(
            constraint="применить MUSL BOUNDARY к конфигурации",
            reason="semantic_constraint",
        )
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(ts["constraints"], [])

    # 9. outward_blocked constraint (real detection) passes even on lens delta
    def test_outward_blocked_constraint_passes_on_lens_delta(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(
            constraint="outward action blocked by introspection",
            reason="outward_blocked",
        )
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(len(ts["constraints"]), 1)

    # ── Artifact stripping ──────────────────────────────────────────────────

    # 10. Spaced MUSL markers stripped
    def test_spaced_musl_marker_stripped(self):
        from core.janus_conductor import _strip_musl_lens_echo
        text = "Real insight.\n[ MUSL_LENS ] focus=PROTECT; observational_only\nMore text."
        out = _strip_musl_lens_echo(text)
        self.assertNotIn("[", out.upper().replace("REAL", ""))
        self.assertNotIn("musl", out.lower())
        self.assertIn("Real insight.", out)
        self.assertIn("More text.", out)

    # 11. Arrow compositions stripped; surrounding prose preserved
    def test_arrow_compositions_stripped(self):
        from core.janus_conductor import _strip_musl_lens_echo
        for arrow_text, prose_word in (
            ("Analyse PROTECT -> BOUNDARY here.", "Analyse"),
            ("Pattern FLOW → PROTECT observed.", "Pattern"),
        ):
            out = _strip_musl_lens_echo(arrow_text)
            self.assertNotIn("->", out)
            self.assertNotIn("→", out)
            self.assertIn(prose_word, out)

    # 12. Standalone operator list lines stripped; normal prose intact
    def test_standalone_operator_list_stripped(self):
        from core.janus_conductor import _strip_musl_lens_echo
        text = (
            "Обычный текст.\n"
            "PROTECT, BOUNDARY, INTEGRITY\n"
            "FLOW TRANSFORM CYCLE LIMIT\n"
            "Ещё обычный текст."
        )
        out = _strip_musl_lens_echo(text)
        self.assertIn("Обычный текст.", out)
        self.assertIn("Ещё обычный текст.", out)
        self.assertNotIn("PROTECT, BOUNDARY", out)
        self.assertNotIn("FLOW TRANSFORM CYCLE", out)

    # 13. Normal prose, BASH_FACTS, lowercase not damaged
    def test_prose_and_bash_facts_not_damaged(self):
        from core.janus_conductor import _strip_musl_lens_echo
        prose = (
            "The system protects its boundary via normal flow.\n"
            "--- УСПЕХ: ss -tlnp | grep LISTEN shows 8081\n"
            "Функция protect_boundary() вызвана корректно."
        )
        out = _strip_musl_lens_echo(prose)
        self.assertIn("protects its boundary", out)
        self.assertIn("LISTEN shows 8081", out)
        self.assertIn("protect_boundary()", out)

    # ── Conduct wiring ──────────────────────────────────────────────────────

    # 14. Conduct wiring contains pre-exec lens gate and _lens_user_text
    def test_conduct_pre_exec_gate_wiring(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("_lens_user_text", src)
        self.assertIn("deva in _lens_conditioned_devas", src)
        self.assertIn("_lens_execution_authorized(_lens_user_text)", src)
        self.assertIn("MUSL lens blocked bash", src)

    # 15. No LLM calls; FOHAT_CHAIN intact; janus_dyad unchanged
    def test_no_llm_fohat_janus_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        ts = self._state()
        with patch.object(jc, "_http_post") as http_post:
            jc._lens_corroborated("текст", "текст", "")
            jc._lens_execution_authorized("выполни bash")
            jc.apply_thought_delta(
                ts, self._delta(claim="несвязанный тезис о фазах"),
                user_text="кто ты?", bash_facts="",
            )
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )
        self.assertNotIn(
            "_lens_corroborated", inspect.getsource(jc.janus_dyad),
        )
        self.assertNotIn(
            "_lens_execution_authorized", inspect.getsource(jc.janus_dyad),
        )


class TestV49DLensAdmissionGate(unittest.TestCase):
    """v49-D: pre-ingress admission, field-level suppression, negation/predicate
    polarity, case-insensitive stripping. Включает conduct-level поведение."""

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, **kw):
        base = {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": None, "constraint": None,
            "contradiction": None, "metric_delta": {}, "reason": "test",
            "lens_conditioned": True,
        }
        base.update(kw)
        return base

    # ── conduct runner: ловит сохранённый state и вызовы execute_bash ────────
    def _run_conduct(self, user, artifact):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        captured = {}
        real_dump = json.dump

        def spy_dump(obj, f, *a, **k):
            if isinstance(obj, dict) and "shared_memory" in obj:
                captured["state"] = json.loads(
                    json.dumps(obj, ensure_ascii=False)
                )
            return real_dump(obj, f, *a, **k)

        bash = m.MagicMock(return_value="--- УСПЕХ: ok")
        stub = json.dumps({"choices": [{"message": {"content": "ok"}}]})
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T",
        })
        with contextlib.ExitStack() as st:
            for p in (
                m.patch.object(jc, "_http_post", return_value=stub),
                m.patch.object(
                    jc, "_call_deva_soc", side_effect=lambda **kw: artifact,
                ),
                m.patch.object(jc, "execute_bash", bash),
                m.patch.object(jc, "_forbidden_bash_token", return_value=False),
                m.patch("builtins.open", m.mock_open(read_data=dummy)),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"),
                m.patch("os.replace"),
                m.patch.object(json, "dump", side_effect=spy_dump),
            ):
                st.enter_context(p)
            try:
                jc.conduct(user)
            except Exception:
                pass
            sm = captured.get("state", {}).get("shared_memory", [])
            return sm, bash.call_count

    # ── Requirement 4: negation / polarity ─────────────────────────────────
    def test_negation_polarity_rejected(self):
        from core.janus_conductor import _lens_corroborated
        self.assertFalse(_lens_corroborated(
            "память системы стабильна", "память системы не стабильна", ""))
        self.assertFalse(_lens_corroborated(
            "порт активен", "порт не активен", ""))
        self.assertFalse(_lens_corroborated(
            "ошибка подтверждена", "ошибка не подтверждена", ""))

    def test_matching_polarity_admitted(self):
        from core.janus_conductor import _lens_corroborated
        self.assertTrue(_lens_corroborated(
            "система называется Monada", "система называется Monada", ""))

    # ── Requirement 5: BASH_FACTS predicate support ────────────────────────
    def test_bash_predicate_unsupported_status_rejected(self):
        from core.janus_conductor import _lens_corroborated
        # shared nouns overlap but status "stable" not in facts
        self.assertFalse(_lens_corroborated(
            "memory system stable", "", "memory system checked"))

    def test_bash_predicate_supported_status_admitted(self):
        from core.janus_conductor import _lens_corroborated
        self.assertTrue(_lens_corroborated(
            "порт 8081 в состоянии LISTEN", "кто ты?",
            "--- УСПЕХ: ss -tlnp показывает LISTEN 8081"))

    # ── Requirement 2 (v49-E atomic): any rejection poisons the whole delta ──
    def test_mixed_delta_atomic_poison(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        before_conf = ts["metrics"]["confidence"]
        # claim uncorroborated → rejected → ATOMIC: sibling open also dropped.
        d = self._delta(
            claim="Гексаграмма фохата стабильна",
            open="спроектируй новую память",
            metric_delta={"confidence": 0.2, "coherence": 0.2},
            reason="approved,semantic_open",
        )
        res = apply_thought_delta(
            ts, d, user_text="спроектируй новую память", bash_facts="")
        self.assertEqual(ts["claims"], [])              # claim rejected
        self.assertEqual(ts["open"], [])                # sibling open poisoned too
        self.assertTrue(res["lens_fully_rejected"])
        self.assertLessEqual(
            ts["metrics"]["confidence"], before_conf,
            "poisoned delta must not inflate confidence via metric_delta")

    # ── Requirement 3: outward_blocked bypass gated on lens rejection ───────
    def test_rejected_claim_outward_blocked_no_constraint_or_lesson(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()  # design mode (reflective)
        before_lessons = list(ts.get("lessons", []))
        before_arch = list(ts.get("archetypes", []))
        before_glyphs = list(ts.get("glyphs", []))
        d = self._delta(
            claim="MUSL фохат гептархия недоказуемый тезис",
            constraint="outward action blocked by introspection",
            reason="semantic_claim,outward_blocked",
        )
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(ts["constraints"], [])          # constraint gated
        self.assertEqual(ts.get("lessons", []), before_lessons)
        self.assertEqual(ts.get("archetypes", []), before_arch)
        self.assertEqual(ts.get("glyphs", []), before_glyphs)

    # outward_blocked bypass PRESERVED when claim admitted (real protective path)
    def test_outward_blocked_bypass_preserved_when_claim_admitted(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(
            claim="спроектируй новую память",                # verbatim → admitted
            constraint="outward action blocked by introspection",
            reason="semantic_claim,outward_blocked",
        )
        apply_thought_delta(
            ts, d, user_text="спроектируй новую память", bash_facts="")
        self.assertEqual(len(ts["constraints"]), 1)        # bypass preserved

    # ── Requirement 1: lens_fully_rejected flag ────────────────────────────
    def test_apply_returns_lens_fully_rejected(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        res = apply_thought_delta(
            ts, self._delta(claim="недоказуемый тезис о фохате"),
            user_text="кто ты?", bash_facts="")
        self.assertTrue(res["lens_fully_rejected"])

        ts2 = self._state()
        res2 = apply_thought_delta(
            ts2, self._delta(claim="спроектируй новую память"),
            user_text="спроектируй новую память", bash_facts="")
        self.assertFalse(res2["lens_fully_rejected"])

        # non-lens delta never reports rejection
        ts3 = self._state()
        res3 = apply_thought_delta(
            ts3, self._delta(claim="любой тезис", lens_conditioned=False),
            user_text="кто ты?", bash_facts="")
        self.assertFalse(res3["lens_fully_rejected"])

    # ── Requirement 6: case-insensitive lens stripping ─────────────────────
    def test_lowercase_operator_stripped_for_lens(self):
        from core.janus_conductor import _strip_musl_lens_echo
        out = _strip_musl_lens_echo(
            "text protect(boundary) and flow -> protect here",
            case_insensitive=True)
        self.assertNotIn("protect(boundary)", out)
        self.assertNotIn("->", out)
        self.assertIn("text", out)
        self.assertIn("here", out)

    def test_lowercase_operator_preserved_for_non_lens(self):
        from core.janus_conductor import _strip_musl_lens_echo
        out = _strip_musl_lens_echo("text protect(boundary) ok")
        self.assertIn("protect(boundary)", out)   # non-lens lowercase untouched

    # ── Requirement 7: conduct-level behaviour ─────────────────────────────
    def test_conduct_rejected_lens_artifact_absent_from_memory(self):
        sm, _ = self._run_conduct(
            "тестовая задача проверка",
            "Monada-Hardcore применяет гептархию для калибровки фохата системы.")
        self.assertFalse(
            any("гептархи" in str(x) for x in sm),
            "fully-rejected lens artifact must not reach shared_memory")

    def test_conduct_corroborated_lens_artifact_persisted(self):
        sm, _ = self._run_conduct(
            "Monada-Hardcore система", "Monada-Hardcore система")
        self.assertTrue(
            any("Monada-Hardcore" in str(x) for x in sm),
            "corroborated lens artifact must persist")

    def test_conduct_execute_bash_not_called_on_mention(self):
        _, calls = self._run_conduct(
            "расскажи про bash и архитектуру команд системы",
            "Диагностика.\n```bash\nss -tlnp\n```")
        self.assertEqual(calls, 0, "mere mention of bash must not execute")

    def test_conduct_execute_bash_called_on_explicit_request(self):
        _, calls = self._run_conduct(
            "выполни диагностику портов ss -tlnp и память free",
            "Диагностика.\n```bash\nss -tlnp\n```")
        self.assertGreaterEqual(
            calls, 1, "explicit execution request must allow bash")

    # ── Invariants ─────────────────────────────────────────────────────────
    def test_conduct_wiring_deferred_persistence(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("if not _is_lens_deva:", src)
        self.assertIn('lens_fully_rejected', src)
        self.assertIn("withheld from", src)
        self.assertIn("case_insensitive=_is_lens_deva", src)

    def test_no_llm_fohat_janus_and_v48_collapse_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        ts = self._state()
        with patch.object(jc, "_http_post") as http_post:
            jc._lens_corroborated("a", "a", "")
            jc.apply_thought_delta(
                ts, self._delta(claim="недоказуемый тезис"),
                user_text="кто ты?", bash_facts="")
        http_post.assert_not_called()
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])
        janus_src = inspect.getsource(jc.janus_dyad)
        self.assertNotIn("_lens_corroborated", janus_src)
        self.assertNotIn("lens_fully_rejected", janus_src)
        # v48 question-collapse machinery untouched
        self.assertTrue(hasattr(jc, "_is_equivalent_open_question"))


class TestV49EHardFailClosed(unittest.TestCase):
    """v49-E: атомарная персистенция, fail-closed, предикат-локальная полярность."""

    def _state(self, text="спроектируй новую память"):
        from core.janus_conductor import (
            _pre_janus_frame, make_thought_seed, make_thought_state,
        )
        return make_thought_state(
            make_thought_seed(text, _pre_janus_frame(text)), grounding=0.5,
        )

    def _delta(self, **kw):
        base = {
            "deva": "Budha", "center": "Head", "rune": "ᛃ", "action": "none",
            "claim": None, "open": None, "constraint": None,
            "contradiction": None, "metric_delta": {}, "reason": "test",
            "lens_conditioned": True,
        }
        base.update(kw)
        return base

    def _run_conduct(self, user, artifact, disable_thought=False,
                     raise_apply=False):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        captured = {}
        real_dump = json.dump

        def spy_dump(obj, f, *a, **k):
            if isinstance(obj, dict) and "shared_memory" in obj:
                captured["state"] = json.loads(
                    json.dumps(obj, ensure_ascii=False))
            return real_dump(obj, f, *a, **k)

        bash = m.MagicMock(return_value="--- УСПЕХ: ok")
        stub = json.dumps({"choices": [{"message": {"content": "ok"}}]})
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T",
        })
        P = [
            m.patch.object(jc, "_http_post", return_value=stub),
            m.patch.object(jc, "_call_deva_soc", side_effect=lambda **kw: artifact),
            m.patch.object(jc, "execute_bash", bash),
            m.patch.object(jc, "_forbidden_bash_token", return_value=False),
            m.patch("builtins.open", m.mock_open(read_data=dummy)),
            m.patch("os.path.exists", return_value=True),
            m.patch("os.makedirs"), m.patch("os.replace"),
            m.patch.object(json, "dump", side_effect=spy_dump),
        ]
        if disable_thought:
            P.append(m.patch.object(jc, "THOUGHT_STATE_ENABLED", False))
        if raise_apply:
            P.append(m.patch.object(
                jc, "apply_thought_delta", side_effect=RuntimeError("boom")))
        with contextlib.ExitStack() as st:
            for p in P:
                st.enter_context(p)
            try:
                jc.conduct(user)
            except Exception:
                pass
            sm = captured.get("state", {}).get("shared_memory", [])
            return sm, bash.call_count

    # 1. Partial admission leak — atomic rejection
    def test_partial_admission_is_atomic(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        # admitted open (verbatim) + rejected claim → whole delta poisoned
        d = self._delta(
            claim="фохат гептархия недоказуемый статус corrupted",
            open="спроектируй новую память",
            reason="semantic_claim,semantic_open")
        res = apply_thought_delta(
            ts, d, user_text="спроектируй новую память", bash_facts="")
        self.assertTrue(res["lens_fully_rejected"])
        self.assertEqual(ts["claims"], [])
        self.assertEqual(ts["open"], [])
        self.assertIsNone(d["claim"])
        self.assertIsNone(d["open"])

    # 2. Fail closed — ThoughtState disabled / delta exception → withheld
    def test_fail_closed_thought_disabled(self):
        sm, _ = self._run_conduct(
            "задача проверка", "Monada-Hardcore применяет гептархию фохата.",
            disable_thought=True)
        self.assertFalse(any("гептарх" in str(x) for x in sm))

    def test_fail_closed_delta_exception(self):
        sm, _ = self._run_conduct(
            "задача проверка", "Monada-Hardcore применяет гептархию фохата.",
            raise_apply=True)
        self.assertFalse(any("гептарх" in str(x) for x in sm))

    # 3. Unauthorized action-only → fully rejected, no persistence
    def test_unauthorized_action_only_fully_rejected(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        d = self._delta(action="bash", reason="semantic_claim")
        res = apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertTrue(res["lens_fully_rejected"])
        self.assertEqual(d["action"], "none")

    # 4. Positive metric suppression across all metrics
    def test_all_positive_metrics_suppressed_on_rejection(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()
        before = dict(ts["metrics"])
        d = self._delta(
            claim="фохат гептархия corrupted недоказуемо",
            metric_delta={"confidence": 0.3, "coherence": 0.3,
                          "grounding": 0.3, "novelty": 0.3},
            reason="approved,semantic_claim")
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        for k in ("confidence", "coherence", "grounding", "novelty"):
            self.assertLessEqual(
                ts["metrics"][k], before[k],
                f"{k} must not rise from rejected lens delta")

    # 5. Predicate-local polarity (mixed clauses)
    def test_predicate_local_polarity_rejected(self):
        from core.janus_conductor import _lens_corroborated
        self.assertFalse(_lens_corroborated(
            "память стабильна, порт не активен",
            "память не стабильна, порт активен", ""))

    # 6. BASH_FACTS unsupported predicates
    def test_bash_unsupported_predicates_rejected(self):
        from core.janus_conductor import _lens_corroborated
        self.assertFalse(_lens_corroborated(
            "memory system corrupted", "", "memory system checked"))
        self.assertFalse(_lens_corroborated(
            "memory system encrypted", "", "memory system checked"))

    # 7. Rejected artifact produces no constraint / lesson / archetype / glyph
    def test_rejected_artifact_no_reflective_chain(self):
        from core.janus_conductor import apply_thought_delta
        ts = self._state()  # design (reflective) mode
        before = (list(ts.get("lessons", [])), list(ts.get("archetypes", [])),
                  list(ts.get("glyphs", [])))
        d = self._delta(
            claim="недоказуемый тезис corrupted",
            constraint="outward action blocked by introspection",
            open="недостаточно данных о фохате",
            reason="semantic_claim,outward_blocked,semantic_open")
        apply_thought_delta(ts, d, user_text="кто ты?", bash_facts="")
        self.assertEqual(ts["constraints"], [])
        self.assertEqual(
            (ts.get("lessons", []), ts.get("archetypes", []),
             ts.get("glyphs", [])), before)

    # 8. Conduct-level: rejected absent from shared_memory / new_artifacts
    def test_conduct_rejected_absent(self):
        sm, _ = self._run_conduct(
            "тестовая задача проверка",
            "Monada-Hardcore применяет гептархию для калибровки фохата.")
        self.assertFalse(any("гептарх" in str(x) for x in sm))

    # 9-11. Invariants
    def test_fohat_janus_v48_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])
        jsrc = inspect.getsource(jc.janus_dyad)
        self.assertNotIn("_lens_corroborated", jsrc)
        self.assertNotIn("lens_fully_rejected", jsrc)
        self.assertTrue(hasattr(jc, "_is_equivalent_open_question"))

    def test_conduct_fail_closed_wiring(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("_td_result is None", src)
        self.assertIn("lens_fully_rejected", src)


class TestV49FAdmissionBeforeBash(unittest.TestCase):
    """v49-F: admission предшествует execute_bash / proposal / BASH_FACTS."""

    def _run_conduct(self, user, artifact, disable_thought=False,
                     raise_apply=False):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        captured = {}
        real_dump = json.dump

        def spy_dump(obj, f, *a, **k):
            if isinstance(obj, dict) and "shared_memory" in obj:
                captured["state"] = json.loads(
                    json.dumps(obj, ensure_ascii=False))
            return real_dump(obj, f, *a, **k)

        bash = m.MagicMock(return_value="--- УСПЕХ: ok")
        stub = json.dumps({"choices": [{"message": {"content": "ok"}}]})
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T",
        })
        P = [
            m.patch.object(jc, "_http_post", return_value=stub),
            m.patch.object(jc, "_call_deva_soc", side_effect=lambda **kw: artifact),
            m.patch.object(jc, "execute_bash", bash),
            m.patch.object(jc, "_forbidden_bash_token", return_value=False),
            m.patch("builtins.open", m.mock_open(read_data=dummy)),
            m.patch("os.path.exists", return_value=True),
            m.patch("os.makedirs"), m.patch("os.replace"),
            m.patch.object(json, "dump", side_effect=spy_dump),
        ]
        if disable_thought:
            P.append(m.patch.object(jc, "THOUGHT_STATE_ENABLED", False))
        if raise_apply:
            P.append(m.patch.object(
                jc, "apply_thought_delta", side_effect=RuntimeError("boom")))
        with contextlib.ExitStack() as st:
            for p in P:
                st.enter_context(p)
            try:
                jc.conduct(user)
            except Exception:
                pass
            sm = captured.get("state", {}).get("shared_memory", [])
            return sm, bash.call_count

    # rejected lens artifact: uncorroborated claim (anchor + unsupported status)
    # plus a bash block → admission must reject and block bash.
    _BASH_ART = (
        "Monada-Hardcore система повреждена corrupted гептархия.\n"
        "```bash\nss -tlnp\n```"
    )

    def test_rejected_lens_no_bash_no_proposal(self):
        sm, calls = self._run_conduct(
            "выполни диагностику ss -tlnp память",  # exec-authorized phrasing
            self._BASH_ART)
        # admission rejects the (uncorroborated) artifact → bash never runs,
        # no proposal/BASH_FACTS/record persisted.
        self.assertEqual(calls, 0)
        self.assertFalse(any("ПРОЕКТ ДЕЙСТВИЯ" in str(x) for x in sm))
        self.assertFalse(any("гептарх" in str(x).lower() for x in sm))

    def test_fail_closed_thought_disabled_no_bash(self):
        sm, calls = self._run_conduct(
            "выполни диагностику ss -tlnp память", self._BASH_ART,
            disable_thought=True)
        self.assertEqual(calls, 0)
        self.assertFalse(any("ПРОЕКТ ДЕЙСТВИЯ" in str(x) for x in sm))

    def test_fail_closed_apply_raises_no_bash(self):
        sm, calls = self._run_conduct(
            "выполни диагностику ss -tlnp память", self._BASH_ART,
            raise_apply=True)
        self.assertEqual(calls, 0)
        self.assertFalse(any("ПРОЕКТ ДЕЙСТВИЯ" in str(x) for x in sm))

    def test_conduct_wiring_admission_before_bash(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        # the lens pre-admission block and the bash-block guard exist
        self.assertIn("_lens_block_bash", src)
        self.assertIn("bash withheld pre-admission", src)
        # post-bash delta now excludes lens Devas
        self.assertIn("_thought_state is not None and not _is_lens_deva", src)
        # admission block precedes the bash if/elif chain textually
        self.assertLess(
            src.index("_lens_block_bash = "),
            src.index('"```bash" in artifact or _is_safe_body_raw_bash'))

    def test_fohat_and_janus_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])
        self.assertNotIn(
            "_lens_block_bash", inspect.getsource(jc.janus_dyad))


class TestV49FVisibility(unittest.TestCase):
    """v49-F visibility: rejected lens action must not reach Janus input,
    BASH_FACTS, or WARM/CRYSTAL. Strict helper does NOT swallow exceptions."""

    # rejected lens artifact: anchor claim + unsupported status + bash block
    _REJECTED = (
        "Monada-Hardcore система повреждена corrupted.\n"
        "```bash\nss -tlnp\n```"
    )

    def _capture_conduct(self, user, artifact, deva_side_effect=None):
        """Runs conduct under capture WITHOUT swallowing exceptions.

        Returns a namespace with: janus (spy), bash (mock), crystal (mock),
        written (all file-write text). Any conduct exception propagates.
        """
        import json, sys, types, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc

        stub = json.dumps({"choices": [{"message": {"content": "ok"}}]})
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T",
        })
        janus = m.MagicMock(wraps=jc.janus_dyad)
        bash = m.MagicMock(return_value="--- УСПЕХ: ok")
        handle = m.mock_open(read_data=dummy)
        crystal = m.MagicMock()
        side = deva_side_effect or (lambda **kw: artifact)
        with contextlib.ExitStack() as st:
            for p in (
                m.patch.object(jc, "_http_post", return_value=stub),
                m.patch.object(jc, "_call_deva_soc", side_effect=side),
                m.patch.object(jc, "execute_bash", bash),
                m.patch.object(jc, "_forbidden_bash_token", return_value=False),
                m.patch.object(jc, "janus_dyad", janus),
                m.patch.dict(sys.modules, {"dancefloor_save": crystal}),
                m.patch("builtins.open", handle),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"),
                m.patch("os.replace"),
            ):
                st.enter_context(p)
            # NO try/except: an unexpected conduct exception fails the test.
            jc.conduct(user)
            written = "".join(
                str(c.args[0]) for c in handle().write.call_args_list if c.args
            )
            ns = types.SimpleNamespace(
                janus=janus, bash=bash, crystal=crystal, written=written)
            return ns

    # 1. Janus input excludes rejected lens action/proposal
    def test_janus_input_excludes_rejected(self):
        ns = self._capture_conduct(
            "выполни диагностику ss -tlnp память", self._REJECTED)
        self.assertTrue(ns.janus.called)
        triad = ns.janus.call_args.kwargs.get("triad_artifacts", "")
        self.assertNotIn("corrupted", triad)
        self.assertNotIn("ПРОЕКТ ДЕЙСТВИЯ", triad)

    # 2. BASH_FACTS not appended for rejected lens action
    def test_bash_facts_not_appended_for_rejected(self):
        ns = self._capture_conduct(
            "выполни диагностику ss -tlnp память", self._REJECTED)
        bash_facts = ns.janus.call_args.kwargs.get("bash_facts", "")
        self.assertEqual(ns.bash.call_count, 0)        # bash never executed
        self.assertNotIn("ss -tlnp", bash_facts)
        self.assertNotIn("УСПЕХ", bash_facts)

    # 3. WARM/CRYSTAL write/compaction path not reached by rejected action
    def test_warm_crystal_not_written_for_rejected(self):
        ns = self._capture_conduct(
            "выполни диагностику ss -tlnp память", self._REJECTED)
        self.assertFalse(ns.crystal.main.called)        # no CRYSTAL save
        self.assertNotIn("corrupted", ns.written)       # nothing persisted
        self.assertNotIn("ПРОЕКТ ДЕЙСТВИЯ", ns.written)

    # 4. Helper fails on unexpected exceptions instead of swallowing
    def test_helper_does_not_swallow_unexpected(self):
        def _boom(**kw):
            raise RuntimeError("unexpected deva failure")
        with self.assertRaises(RuntimeError):
            self._capture_conduct(
                "задача", self._REJECTED, deva_side_effect=_boom)


class TestV49GStabilization(unittest.TestCase):
    """v49-G: EVENT_VOID, grammar diagnostics, conceptual trace (log-only)."""

    # A. EVENT_VOID exists, weighted, and record() writes it
    def test_event_void_constant_and_weight(self):
        import lipika_writer as lw
        self.assertEqual(lw.EVENT_VOID, "VOID")
        self.assertIn(lw.EVENT_VOID, lw.DEBT_WEIGHTS)
        self.assertGreater(lw.DEBT_WEIGHTS[lw.EVENT_VOID], 0.0)

    def test_event_void_record_path(self):
        import lipika_writer as lw
        import unittest.mock as m
        ledger = {"karma_debt": 0.0, "history": []}
        with (
            m.patch.object(lw, "_load", return_value=ledger),
            m.patch.object(lw, "_save") as saved,
        ):
            entry = lw.record(lw.EVENT_VOID, "KillSwitch", "grounding 0.20", cycle=7)
        self.assertEqual(entry["event"], "VOID")
        self.assertEqual(saved.call_args.args[0]["karma_debt"],
                         lw.DEBT_WEIGHTS["VOID"])

    def test_kill_switch_uses_event_void(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("_lw.EVENT_VOID", src)   # kill-switch references the constant

    # B. Grammar failure logging
    def test_grammar_fail_logs_fields(self):
        import core.janus_conductor as jc
        import unittest.mock as m
        with m.patch.object(jc, "_sys_log") as log:
            jc._log_grammar_fail("Persona", "PERSONA_GBNF",
                                 ValueError("bad json"), fallback_used=True)
        msg = log.call_args.args[0]
        self.assertIn("[GRAMMAR_FAIL]", msg)
        self.assertIn("node=Persona", msg)
        self.assertIn("grammar=PERSONA_GBNF", msg)
        self.assertIn("parser_error=", msg)
        self.assertIn("fallback_used=true", msg)

    def test_grammar_fail_wired_in_janus_dyad(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.janus_dyad)
        self.assertIn('_log_grammar_fail("Persona", "PERSONA_GBNF"', src)
        self.assertIn('_log_grammar_fail("Shadow", "SHADOW_GBNF"', src)

    # C. Conceptual trace logging
    def test_conceptual_trace_input_sizes_logged(self):
        import core.janus_conductor as jc
        import unittest.mock as m
        stub = '{"assembly":"x","quality":0.5}'
        logs = []
        with (
            m.patch.object(jc, "_http_post", return_value=
                '{"choices":[{"message":{"content":' + repr(stub) + '}}]}'),
            m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
            m.patch.object(jc, "_load_dna", return_value=""),
        ):
            jc.janus_dyad(task="что такое память?", triad_artifacts="A\nB",
                          conceptual_trace=True)
        trace = [m_ for m_ in logs if "[CONCEPTUAL_TRACE]" in m_]
        self.assertTrue(trace)
        self.assertIn("persona_input_size=", trace[-1])
        self.assertIn("shadow_input_size=", trace[-1])
        self.assertIn("synthesis_input_size=", trace[-1])

    def test_conceptual_trace_off_by_default(self):
        import core.janus_conductor as jc
        import unittest.mock as m
        logs = []
        with (
            m.patch.object(jc, "_http_post", return_value=
                '{"choices":[{"message":{"content":"{}"}}]}'),
            m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
            m.patch.object(jc, "_load_dna", return_value=""),
        ):
            jc.janus_dyad(task="t", triad_artifacts="A")  # default False
        self.assertFalse(any("[CONCEPTUAL_TRACE]" in m_ for m_ in logs))

    def test_conduct_logs_conceptual_counts(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("[CONCEPTUAL_TRACE]", src)
        self.assertIn("artifact_count=", src)
        self.assertIn("withheld_count=", src)
        self.assertIn("conceptual_trace = _conceptual", src)

    # No behavior change: FOHAT + janus return contract intact
    def test_no_behavior_change_invariants(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])


class TestV50AConceptualProseChannel(unittest.TestCase):
    """v50-A: conceptual withheld artifacts reach Janus as prose only,
    never entering ThoughtState/Evidence/Memory/claims/lessons/glyphs."""

    _PROSE = "Память — это способность системы сохранять информацию во времени."

    def _run(self, user, artifact):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        captured, logs = {}, []
        real_dump = json.dump

        def spy_dump(obj, f, *a, **k):
            if isinstance(obj, dict) and "shared_memory" in obj:
                captured["state"] = json.loads(json.dumps(obj, ensure_ascii=False))
            return real_dump(obj, f, *a, **k)

        janus = m.MagicMock(wraps=jc.janus_dyad)
        bash = m.MagicMock(return_value="--- УСПЕХ: ok")
        handle = m.mock_open(read_data=json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T"}))
        crystal = m.MagicMock()
        stub = json.dumps({"choices": [{"message": {"content": "ответ"}}]})
        import sys
        with contextlib.ExitStack() as st:
            for p in (
                m.patch.object(jc, "_http_post", return_value=stub),
                m.patch.object(jc, "_call_deva_soc", side_effect=lambda **kw: artifact),
                m.patch.object(jc, "execute_bash", bash),
                m.patch.object(jc, "janus_dyad", janus),
                m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
                m.patch.dict(sys.modules, {"dancefloor_save": crystal}),
                m.patch("builtins.open", handle),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"), m.patch("os.replace"),
                m.patch.object(json, "dump", side_effect=spy_dump),
            ):
                st.enter_context(p)
            jc.conduct(user)
            written = "".join(
                str(c.args[0]) for c in handle().write.call_args_list if c.args)
            import types
            return types.SimpleNamespace(
                janus=janus, state=captured.get("state", {}),
                logs=logs, written=written, crystal=crystal, bash=bash)

    def _trace(self, logs):
        ts = [l for l in logs if "[CONCEPTUAL_TRACE]" in l and "shadow_input_size" in l]
        return ts[-1] if ts else ""

    # 1-3. withheld conceptual prose feeds Persona / Shadow / Synthesis
    def test_prose_reaches_persona_shadow_synthesis(self):
        ns = self._run("что такое память?", self._PROSE)
        triad = ns.janus.call_args.kwargs.get("triad_artifacts", "")
        self.assertIn("способность", triad)            # reached Persona input
        trace = self._trace(ns.logs)
        import re
        sizes = dict(re.findall(r"(\w+_input_size)=(\d+)", trace))
        self.assertGreater(int(sizes.get("persona_input_size", 0)), 0)
        self.assertGreater(int(sizes.get("shadow_input_size", 0)), 0)
        self.assertGreater(int(sizes.get("synthesis_input_size", 0)), 0)

    # 4-6. state channel identical: no ThoughtState / claims / lessons / glyphs
    def test_prose_not_in_thoughtstate(self):
        ns = self._run("что такое память?", self._PROSE)
        lts = ns.state.get("last_thought_state", {})
        self.assertEqual(lts.get("claims", []), [])
        self.assertEqual(lts.get("lessons", []), [])
        self.assertEqual(lts.get("glyphs", []), [])
        self.assertEqual(lts.get("open", []), [])
        # archetypes empty too
        self.assertEqual(lts.get("archetypes", []), [])

    # 7. not in HOT/WARM/CRYSTAL / shared_memory persistence
    def test_prose_not_persisted(self):
        ns = self._run("что такое память?", self._PROSE)
        sm = ns.state.get("shared_memory", [])
        self.assertFalse(any("способность" in str(x) for x in sm))
        self.assertNotIn("способность", ns.written)     # no file write carries it
        self.assertFalse(ns.crystal.main.called)        # no CRYSTAL save

    # 8. diagnostic mode: prose channel NOT engaged
    def test_diagnostic_mode_unchanged(self):
        import core.janus_conductor as jc
        f = jc._pre_janus_frame("проверь порты ss -tlnp и память free")
        conceptual = (
            (f.get("mode") == "conceptual" or f.get("intent") == "conceptual")
            and not f.get("diagnostic_authorized")
            and not f.get("action_authorized"))
        self.assertFalse(conceptual)

    # 9. identity mode: prose channel NOT engaged
    def test_identity_mode_unchanged(self):
        import core.janus_conductor as jc
        f = jc._pre_janus_frame("кто ты?")
        conceptual = (
            (f.get("mode") == "conceptual" or f.get("intent") == "conceptual")
            and not f.get("diagnostic_authorized")
            and not f.get("action_authorized"))
        self.assertFalse(conceptual)

    # 10. action mode: prose channel NOT engaged
    def test_action_mode_unchanged(self):
        import core.janus_conductor as jc
        f = jc._pre_janus_frame("запусти команду du -sh /home")
        conceptual = (
            (f.get("mode") == "conceptual" or f.get("intent") == "conceptual")
            and not f.get("diagnostic_authorized")
            and not f.get("action_authorized"))
        self.assertFalse(conceptual)

    # 11. FOHAT unchanged
    def test_fohat_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])

    # 12. Janus scoring unchanged (still returns 4-tuple; scorers intact)
    def test_janus_scoring_unchanged(self):
        import inspect
        import core.janus_conductor as jc
        self.assertTrue(hasattr(jc, "_score_persona"))
        self.assertTrue(hasattr(jc, "_score_shadow"))
        sig = inspect.signature(jc.janus_dyad)
        self.assertEqual(str(sig.return_annotation), "tuple[str, float, float, bool]")
        # prose channel lives in conduct, not janus_dyad scoring
        self.assertNotIn(
            "conceptual_prose_artifacts", inspect.getsource(jc.janus_dyad))

    # tact-local collection never persisted as an attribute
    def test_prose_collection_is_tact_local(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("conceptual_prose_artifacts: list[str] = []", src)
        self.assertIn("Janus-вход", src)  # comment: Janus input only


class TestV50BConceptualPolish(unittest.TestCase):
    """v50-B: garbage filter, empty-synthesis fallback, conceptual kill-switch
    awareness, Lipika karma_debt robustness. v49-F safety unchanged."""

    def _run(self, user, artifact):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        logs = []
        janus = m.MagicMock(wraps=jc.janus_dyad)
        stub = json.dumps({"choices": [{"message": {"content": "ответ"}}]})
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T"})
        with contextlib.ExitStack() as st:
            for p in (
                m.patch.object(jc, "_http_post", return_value=stub),
                m.patch.object(jc, "_call_deva_soc", side_effect=lambda **kw: artifact),
                m.patch.object(jc, "execute_bash", m.MagicMock(return_value="ok")),
                m.patch.object(jc, "janus_dyad", janus),
                m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
                m.patch("builtins.open", m.mock_open(read_data=dummy)),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"), m.patch("os.replace"),
                m.patch.object(json, "dump"),
            ):
                st.enter_context(p)
            jc.conduct(user)
            triad = janus.call_args.kwargs.get("triad_artifacts", "") if janus.called else ""
            return triad, logs

    # 1. degenerate artifact dropped from conceptual prose channel
    # (anchor+unsupported status → withheld → enters prose channel → filtered)
    def test_degenerate_prose_dropped(self):
        triad, logs = self._run(
            "что такое память?",
            "MonadaAI система повреждена corrupted Моментамам пампамамамамам "
            "пампамам пампамам пампамам пампамам")
        self.assertNotIn("пампам", triad)
        self.assertTrue(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # 2. normal conceptual artifact still reaches Janus
    def test_normal_conceptual_reaches_janus(self):
        triad, logs = self._run(
            "что такое память?",
            "Память — это способность системы сохранять и воспроизводить "
            "информацию во времени, формируя основу опыта и предсказания.")
        self.assertIn("способность", triad)
        self.assertFalse(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # 3. empty synthesis falls back to Persona assembly
    def test_empty_synthesis_fallback(self):
        import json
        import unittest.mock as m
        import core.janus_conductor as jc
        logs = []

        def _post(url, payload, timeout=30):
            content = ("сборка персоны: содержательный ответ"
                       if url == jc.PERSONA_URL else "")
            return json.dumps({"choices": [{"message": {"content": content}}]})

        with (
            m.patch.object(jc, "_http_post", side_effect=_post),
            m.patch.object(jc, "_load_dna", return_value=""),
            m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
        ):
            synthesis, *_ = jc.janus_dyad(task="что такое память?",
                                          triad_artifacts="A")
        self.assertIn("сборка персоны", synthesis)
        self.assertTrue(any("[SYNTHESIS_FALLBACK]" in l for l in logs))

    def test_no_persona_fallback_when_persona_empty(self):
        # v50-C: empty Persona + empty Synthesis → deterministic fail-safe,
        # NOT a Persona fallback (and never blank).
        import json
        import unittest.mock as m
        import core.janus_conductor as jc
        logs = []
        with (
            m.patch.object(jc, "_http_post", return_value=
                json.dumps({"choices": [{"message": {"content": ""}}]})),
            m.patch.object(jc, "_load_dna", return_value=""),
            m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
        ):
            synthesis, *_ = jc.janus_dyad(task="t", triad_artifacts="A")
        self.assertFalse(any("reason=empty_synthesis" in l for l in logs))
        self.assertTrue(any("reason=empty_persona_and_synthesis" in l for l in logs))
        self.assertTrue(synthesis.strip())   # never blank

    # 4. conceptual claims=0 + low grounding does NOT kill-switch
    def test_conceptual_low_grounding_no_killswitch(self):
        import core.janus_conductor as jc
        f = {"mode": "conceptual", "intent": "conceptual"}
        self.assertFalse(jc._should_trigger_grounding_kill_switch(
            0.20, repair_tact=False, pre_janus_frame=f, danger_signal=False))
        fi = {"mode": "introspection", "intent": "conceptual"}
        self.assertFalse(jc._should_trigger_grounding_kill_switch(
            0.20, repair_tact=False, pre_janus_frame=fi, danger_signal=False))

    # 5. real danger still kills (conceptual + danger; diagnostic default)
    def test_danger_still_killswitches(self):
        import core.janus_conductor as jc
        f = {"mode": "conceptual", "intent": "conceptual"}
        self.assertTrue(jc._should_trigger_grounding_kill_switch(
            0.20, repair_tact=False, pre_janus_frame=f, danger_signal=True))
        # diagnostic/default keeps old behavior (danger_signal defaults True)
        fd = {"mode": "diagnostic", "intent": "diagnostic"}
        self.assertTrue(jc._should_trigger_grounding_kill_switch(
            0.20, repair_tact=False, pre_janus_frame=fd))

    def test_conduct_computes_danger_signal(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("danger_signal=_kill_danger", src)
        self.assertIn("contradiction:", src)
        self.assertIn("shock_count", src)

    # 6. kill-switch Lipika VOID records without karma_debt error
    def test_lipika_void_no_karma_debt_error(self):
        import lipika_writer as lw
        import unittest.mock as m
        for bad in ({}, {"history": []}, {"karma_debt": None},
                    {"karma_debt": "x", "history": None}):
            with (m.patch.object(lw, "_load", return_value=dict(bad)),
                  m.patch.object(lw, "_save")):
                entry = lw.record(lw.EVENT_VOID, "KillSwitch", "g 0.2", cycle=3)
            self.assertEqual(entry["event"], "VOID")

    # 9. FOHAT unchanged
    def test_fohat_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])

    # garbage detector unit coverage
    def test_drop_reasons(self):
        import core.janus_conductor as jc
        self.assertEqual(jc._conceptual_prose_drop_reason("  "), "empty_or_near_empty")
        self.assertEqual(jc._conceptual_prose_drop_reason(
            "ааааааааааааааааааааа достаточно длинный фрагмент текста"), "char_run")
        self.assertIsNone(jc._conceptual_prose_drop_reason(
            "Сознание есть интеграция восприятия, внимания и саморефлексии в поле."))


class TestV50CEdgeHardening(unittest.TestCase):
    """v50-C: garbage filter on both paths, blank fail-safe, danger-override."""

    def _run(self, user, artifact, state_extra=None):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        logs, captured = [], {}
        janus = m.MagicMock(wraps=jc.janus_dyad)
        stub = json.dumps({"choices": [{"message": {"content": "ответ"}}]})
        base = {"cycle": 0, "current_note": 1, "shared_memory": [],
                "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
                "shock_count": 0, "marker": "T", "grounding_score": 1.0}
        if state_extra:
            base.update(state_extra)
        real = json.dump

        def spy(o, f, *a, **k):
            if isinstance(o, dict) and "shared_memory" in o:
                captured["s"] = o
            return real(o, f, *a, **k)
        with contextlib.ExitStack() as st:
            for p in (
                m.patch.object(jc, "_http_post", return_value=stub),
                m.patch.object(jc, "_call_deva_soc", side_effect=lambda **kw: artifact),
                m.patch.object(jc, "execute_bash", m.MagicMock(return_value="ok")),
                m.patch.object(jc, "janus_dyad", janus),
                m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
                m.patch("builtins.open", m.mock_open(read_data=json.dumps(base))),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"), m.patch("os.replace"),
                m.patch.object(json, "dump", side_effect=spy),
            ):
                st.enter_context(p)
            killed = False
            try:
                jc.conduct(user)
            except SystemExit:
                killed = True
            triad = janus.call_args.kwargs.get("triad_artifacts", "") if janus.called else ""
            return triad, logs, janus.called

    # 1. neutral degenerate artifact (no fields) cannot reach Janus
    def test_neutral_degenerate_not_in_janus(self):
        triad, logs, _ = self._run(
            "что такое память?",
            "пампам пампам пампам пампам пампам пампам пампам определение")
        self.assertNotIn("пампам", triad)
        self.assertTrue(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # 2. degenerate normal-path artifact dropped (janus_input reason)
    def test_degenerate_normal_path_dropped(self):
        triad, logs, _ = self._run(
            "что такое сознание?",
            "ааааааааааааааааааааааа сознание определение здесь длинный текст")
        self.assertTrue(any(
            "[CONCEPTUAL_PROSE_DROP]" in l and "janus_input" in l for l in logs))

    # 3. empty Persona + empty Synthesis → deterministic fallback, not blank
    def test_blank_final_failsafe(self):
        import json
        import unittest.mock as m
        import core.janus_conductor as jc
        with (
            m.patch.object(jc, "_http_post", return_value=
                json.dumps({"choices": [{"message": {"content": ""}}]})),
            m.patch.object(jc, "_load_dna", return_value=""),
            m.patch.object(jc, "_sys_log"),
        ):
            synthesis, *_ = jc.janus_dyad(task="t", triad_artifacts="A")
        self.assertIn("Задача не выполнена", synthesis)
        self.assertIn("повтор такта", synthesis)
        self.assertTrue(synthesis.strip())

    # 4. dangerous diagnostic still kill-switches (danger via prior contradiction)
    def test_dangerous_diagnostic_killswitches(self):
        import core.janus_conductor as jc
        # direct: diagnostic + low grounding + danger → kill
        f = jc._pre_janus_frame("проверь порты ss -tlnp")
        self.assertTrue(jc._should_trigger_grounding_kill_switch(
            0.20, repair_tact=False, pre_janus_frame=f, danger_signal=True))

    # 5. refuted evidence + repair wording still kill-switches
    def test_refuted_plus_repair_still_kills(self):
        import core.janus_conductor as jc
        f = jc._pre_janus_frame("почини диагностику системы")
        # repair wording would normally bypass; danger overrides it
        self.assertTrue(jc._should_trigger_grounding_kill_switch(
            0.20, repair_tact=True, pre_janus_frame=f, danger_signal=True))
        # without danger, repair still bypasses (unchanged)
        self.assertFalse(jc._should_trigger_grounding_kill_switch(
            0.20, repair_tact=True, pre_janus_frame=f, danger_signal=False))

    def test_conduct_danger_markers_broadened(self):
        import inspect
        import core.janus_conductor as jc
        src = inspect.getsource(jc.conduct)
        self.assertIn("_DANGER_OPEN_MARKERS", src)
        self.assertIn("refuted", src)
        self.assertIn("bash_failure", src)

    # 8. FOHAT unchanged
    def test_fohat_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])


class TestV50DShortGarbageHardening(unittest.TestCase):
    """v50-D: short conceptual garbage dropped unless strong semantic marker."""

    def _filter(self, *records):
        """Replicates the conduct conceptual normal-path filter on raw records."""
        import re
        import core.janus_conductor as jc
        all_artifacts = "\n".join(records)
        kept, dropped = [], []
        for _blk in re.split(r"\n(?=\[)", all_artifacts):
            if re.match(r"^\s*\[[^\]]*\]\s*$", _blk):
                kept.append(_blk); continue
            _body = re.sub(r"^\s*\[[^\]]*\]:?\s*", "", _blk)
            _reason = jc._conceptual_prose_drop_reason(_body)
            if _reason:
                if (_reason == "empty_or_near_empty"
                        and jc._has_strong_conceptual_marker(_body)):
                    kept.append(_blk)
                else:
                    dropped.append((_blk, _reason))
            else:
                kept.append(_blk)
        return "\n".join(kept), dropped

    # 1-4. short neutral garbage dropped
    def test_short_garbage_dropped(self):
        for body in ("пампам", "не знаю", "...", "ам ам ам ам ам"):
            triad, dropped = self._filter(f"[Head/Budha|ᛃ]: {body}")
            self.assertEqual(triad, "", f"{body!r} should be dropped")
            self.assertTrue(dropped)

    # 5. legitimate short definition kept
    def test_short_definition_kept(self):
        triad, dropped = self._filter("[Head/Budha|ᛃ]: Память — это опыт.")
        self.assertIn("Память — это опыт.", triad)
        self.assertEqual(dropped, [])

    def test_short_copula_kept(self):
        triad, _ = self._filter("[Heart/Surya|ᛃ]: Сознание есть интеграция.")
        self.assertIn("Сознание есть интеграция.", triad)

    # 6. header-only record dropped (has body marker ":" but empty body)
    def test_header_only_record_dropped(self):
        triad, dropped = self._filter("[Body/Mangala|ᛃ]:")
        self.assertEqual(triad, "")
        self.assertTrue(dropped)

    # pure section separator preserved
    def test_section_separator_preserved(self):
        triad, dropped = self._filter("[ФИНАЛЬНАЯ СБОРКА | ПЛАН: что такое память?]")
        self.assertIn("ФИНАЛЬНАЯ СБОРКА", triad)
        self.assertEqual(dropped, [])

    # marker helper unit coverage
    def test_marker_helper(self):
        import core.janus_conductor as jc
        self.assertTrue(jc._has_strong_conceptual_marker("Память — это опыт"))
        self.assertTrue(jc._has_strong_conceptual_marker(
            "Память означает сохранённый опыт"))   # v50-F: реальные стороны
        self.assertFalse(jc._has_strong_conceptual_marker("пампам"))
        self.assertFalse(jc._has_strong_conceptual_marker("не знаю"))
        self.assertFalse(jc._has_strong_conceptual_marker("..."))

    # 9. FOHAT unchanged
    def test_fohat_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])


class TestV50EUnifiedConceptualFilter(unittest.TestCase):
    """v50-E: одна keep/drop-предикат для обоих conceptual-путей."""

    def _run(self, user, artifact):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        logs = []
        janus = m.MagicMock(wraps=jc.janus_dyad)
        stub = json.dumps({"choices": [{"message": {"content": "ответ"}}]})
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T", "grounding_score": 1.0})
        with contextlib.ExitStack() as st:
            for p in (
                m.patch.object(jc, "_http_post", return_value=stub),
                m.patch.object(jc, "_call_deva_soc", side_effect=lambda **kw: artifact),
                m.patch.object(jc, "execute_bash", m.MagicMock(return_value="ok")),
                m.patch.object(jc, "janus_dyad", janus),
                m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
                m.patch("builtins.open", m.mock_open(read_data=dummy)),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"), m.patch("os.replace"),
                m.patch.object(json, "dump"),
            ):
                st.enter_context(p)
            jc.conduct(user)
            triad = janus.call_args.kwargs.get("triad_artifacts", "") if janus.called else ""
            return triad, logs

    # single predicate used by both paths
    def test_single_predicate_exists(self):
        import inspect
        import core.janus_conductor as jc
        self.assertTrue(callable(jc._should_keep_conceptual_prose))
        src = inspect.getsource(jc.conduct)
        self.assertEqual(src.count("_should_keep_conceptual_prose("), 2)

    # 1 & 2. valid short definition reaches Janus (withheld + normal)
    def test_short_definition_reaches_janus(self):
        # withheld path: anchor+unsupported-status withheld, but the body that
        # survives must use the SAME predicate — here we verify a pure short def
        # on the normal path reaches Janus.
        triad, logs = self._run("что такое память?", "Память — это опыт.")
        self.assertIn("это опыт", triad)
        self.assertFalse(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # 3. short predicate without copula reaches Janus
    def test_short_predicate_no_copula_reaches_janus(self):
        triad, logs = self._run("что такое память?", "Память хранит опыт.")
        self.assertIn("хранит опыт", triad)
        self.assertFalse(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # 4 & 5. short garbage dropped on both paths
    def test_short_garbage_dropped(self):
        triad, logs = self._run("что такое память?", "пампам")
        self.assertNotIn("пампам", triad)
        self.assertTrue(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # predicate parity: withheld and normal agree for the required examples
    def test_predicate_parity(self):
        import core.janus_conductor as jc
        K = jc._should_keep_conceptual_prose
        for keep in ("Память — это опыт.", "Сознание есть интеграция.",
                     "Память хранит опыт.", "Memory stores experience.",
                     "Сознание объединяет восприятие."):
            self.assertTrue(K(keep), keep)
        for drop in ("пампам", "не знаю", "...", "ам ам ам ам ам", ""):
            self.assertFalse(K(drop), drop)

    # 8. FOHAT unchanged
    def test_fohat_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])


class TestV50FMarkerGarbageHardening(unittest.TestCase):
    """v50-F: marker-shaped garbage ('пампам — пампам') dropped on both paths."""

    def _run(self, user, artifact):
        import json, contextlib
        import unittest.mock as m
        import core.janus_conductor as jc
        logs = []
        janus = m.MagicMock(wraps=jc.janus_dyad)
        stub = json.dumps({"choices": [{"message": {"content": "ответ"}}]})
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T", "grounding_score": 1.0})
        with contextlib.ExitStack() as st:
            for p in (
                m.patch.object(jc, "_http_post", return_value=stub),
                m.patch.object(jc, "_call_deva_soc", side_effect=lambda **kw: artifact),
                m.patch.object(jc, "execute_bash", m.MagicMock(return_value="ok")),
                m.patch.object(jc, "janus_dyad", janus),
                m.patch.object(jc, "_sys_log", side_effect=lambda msg: logs.append(msg)),
                m.patch("builtins.open", m.mock_open(read_data=dummy)),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"), m.patch("os.replace"),
                m.patch.object(json, "dump"),
            ):
                st.enter_context(p)
            jc.conduct(user)
            triad = janus.call_args.kwargs.get("triad_artifacts", "") if janus.called else ""
            return triad, logs

    # 1-3. marker-shaped garbage dropped (predicate parity covers both paths)
    def test_marker_garbage_predicate(self):
        import core.janus_conductor as jc
        K = jc._should_keep_conceptual_prose
        for g in ("пампам — пампам", "пампам это пампам", "не знаю — не знаю",
                  "пампам — это", "не знаю есть не знаю"):
            self.assertFalse(K(g), g)

    def test_marker_garbage_dropped_conduct(self):
        triad, logs = self._run("что такое память?", "пампам — пампам")
        self.assertNotIn("пампам", triad)
        self.assertTrue(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # 4-6. valid definitions/predicates kept (both paths via same predicate)
    def test_valid_definitions_kept(self):
        import core.janus_conductor as jc
        K = jc._should_keep_conceptual_prose
        for keep in ("Память — это опыт.", "Сознание есть интеграция.",
                     "Memory is stored experience.", "Память хранит опыт."):
            self.assertTrue(K(keep), keep)

    def test_valid_definition_reaches_janus(self):
        triad, logs = self._run("что такое память?", "Память — это опыт.")
        self.assertIn("это опыт", triad)
        self.assertFalse(any("[CONCEPTUAL_PROSE_DROP]" in l for l in logs))

    # side-diversity helper unit coverage
    def test_side_diversity_helper(self):
        import core.janus_conductor as jc
        self.assertFalse(jc._conceptual_marker_sides_diverse("пампам — пампам"))
        self.assertFalse(jc._conceptual_marker_sides_diverse("не знаю это не знаю"))
        self.assertTrue(jc._conceptual_marker_sides_diverse("Память — это опыт"))
        self.assertTrue(jc._conceptual_marker_sides_diverse("Memory is stored experience"))

    # 8. FOHAT unchanged
    def test_fohat_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"])


class TestV50GShortDefinitionAnchor(unittest.TestCase):
    """v50-G: short marker definitions require a known conceptual anchor."""

    def _run_path(self, artifact, *, withheld):
        import contextlib
        import json
        import unittest.mock as m
        import core.janus_conductor as jc

        janus = m.MagicMock(return_value=("ответ", 1.0, 0.1, False))
        dummy = json.dumps({
            "cycle": 0, "current_note": 1, "shared_memory": [],
            "devas_state": {}, "tensor_last": {}, "janus_dyad": {},
            "shock_count": 0, "marker": "T", "grounding_score": 1.0,
        })

        def admission(*args, **kwargs):
            return {
                "open_added": False,
                "lens_fully_rejected": withheld,
            }

        with contextlib.ExitStack() as st:
            for patcher in (
                m.patch.object(
                    jc, "_http_post",
                    return_value=json.dumps({
                        "choices": [{"message": {"content": "ответ"}}],
                    }),
                ),
                m.patch.object(
                    jc, "_call_deva_soc", side_effect=lambda **kw: artifact,
                ),
                m.patch.object(jc, "apply_thought_delta", side_effect=admission),
                m.patch.object(jc, "janus_dyad", janus),
                m.patch.object(jc, "execute_bash"),
                m.patch("builtins.open", m.mock_open(read_data=dummy)),
                m.patch("os.path.exists", return_value=True),
                m.patch("os.makedirs"),
                m.patch("os.replace"),
                m.patch.object(json, "dump"),
            ):
                st.enter_context(patcher)
            jc.conduct("что такое память?")
        return janus.call_args.kwargs.get("triad_artifacts", "")

    def test_marker_garbage_dropped_both_paths(self):
        import core.janus_conductor as jc
        for garbage in (
            "пампам — тарарам",
            "блабла есть фырфыр",
            "foofoo is barbar",
        ):
            self.assertFalse(jc._should_keep_conceptual_prose(garbage), garbage)
            for withheld in (True, False):
                self.assertNotIn(
                    garbage, self._run_path(garbage, withheld=withheld)
                )

    def test_valid_short_definitions_kept_both_paths(self):
        for definition in (
            "Память — это опыт.",
            "Сознание есть интеграция.",
            "Memory is stored experience.",
        ):
            for withheld in (True, False):
                self.assertIn(
                    definition, self._run_path(definition, withheld=withheld)
                )

    def test_valid_short_predicate_kept(self):
        import core.janus_conductor as jc
        self.assertTrue(jc._should_keep_conceptual_prose("Память хранит опыт."))

    def test_fohat_unchanged(self):
        import core.janus_conductor as jc
        self.assertEqual(
            [deva for _, deva, _ in jc.FOHAT_CHAIN],
            ["Shani", "Chandra", "Shukra", "Mangala", "Budha", "Rahu"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
