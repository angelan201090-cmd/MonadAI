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
        self.assertIn("MonadaAI", body_task)
        self.assertIn("local AI system", body_task)
        self.assertIn("Monada-Hardcore", body_task)
        self.assertIn("not a generic/esoteric monad", body_task)
        self.assertIn("action='none'", body_task)
        self.assertIn("Do not propose scripts", body_task)
        self.assertNotIn("free -h", body_task)
        self.assertNotIn("ss -tlnp", body_task)

    def test_pre_janus_identity_has_project_anchor(self):
        from core.janus_conductor import _pre_janus_frame

        frame = _pre_janus_frame("кто ты?")
        self.assertEqual(
            frame["identity_anchor"],
            "MonadaAI is the local multi-node AI system running this "
            "Monada-Hardcore architecture; do not answer as generic "
            "philosophical/esoteric Monad.",
        )
        for task in frame["micro_tasks"].values():
            self.assertIn("MonadaAI", task)
            self.assertIn("local AI system", task)
            self.assertIn("Monada-Hardcore", task)
            self.assertIn("not a generic/esoteric monad", task)

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
            "Я — MonadaAI.\n\nЗапустить bash-скрипт /home/angelan/check.sh.",
            "в режиме самонаблюдения внешние действия не запрашивались",
        )
        self.assertIn("Я — MonadaAI.", result)
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
            "Я — MonadaAI, локальная система архитектуры Monada-Hardcore.",
            "Persona описывает MonadaAI.",
            "",
            _pre_janus_frame("кто ты?"),
        )
        self.assertIn("MonadaAI", result)
        self.assertIn("Monada-Hardcore", result)

    def test_introspection_final_filters_actions_and_falls_back_to_persona(self):
        from core.janus_conductor import (
            _finalize_synthesis_for_mode,
            _pre_janus_frame,
        )

        result = _finalize_synthesis_for_mode(
            "Запустить bash-скрипт /home/angelan/check.sh для RAM и портов.",
            "Я — MonadaAI внутри Monada-Hardcore.",
            "",
            _pre_janus_frame("кто ты?"),
        )
        self.assertEqual(result, "Я — MonadaAI внутри Monada-Hardcore.")
        for forbidden in ("RAM", "порт", "bash", "скрипт", "/home/"):
            self.assertNotIn(forbidden, result)

    def test_introspection_final_filters_verification_fragments(self):
        from core.janus_conductor import (
            _finalize_synthesis_for_mode,
            _pre_janus_frame,
        )

        result = _finalize_synthesis_for_mode(
            "Я — MonadaAI внутри Monada-Hardcore.\n\n"
            "Нужно проверить BASH_FACTS, пути и имена файлов, чтобы убедиться.",
            "Persona описывает MonadaAI внутри Monada-Hardcore.",
            "",
            _pre_janus_frame("кто ты?"),
        )
        self.assertEqual(result, "Я — MonadaAI внутри Monada-Hardcore.")
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
        self.assertIn("MonadaAI", seed["micro_tasks"]["Head"])

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
        """Introspection + MonadaAI-артефакт без внешних действий → coherence/confidence."""
        from core.janus_conductor import compute_thought_delta
        delta = compute_thought_delta(
            deva="Chandra", center="Heart",
            artifact="MonadaAI — локальная система Monada-Hardcore; роль Сердца внутренняя.",
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
        """forensic > identity; явный diagnostic > design/conceptual."""
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
        "MonadaAI — локальная многоузловая ИИ-система в архитектуре "
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
        for i in range(10):
            apply_thought_delta(ts, {
                "deva": f"D{i}", "center": "Head", "rune": "ᛃ", "action": "none",
                "claim": f"claim слово{i} вектор{i} о системе",
                "open": f"открытый вопрос {i}",
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
        # v41/v42: 0.05 (claim) + 0.03 (урок) + 0.05 (архетип Meaningful Novelty)
        self.assertAlmostEqual(ts["metrics"]["coherence"], 0.63)

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
        # v41/v42: -0.1 (contradiction) + 0.03 (урок) + 0.05 (архетип
        # Dialectical Verification, первое появление)
        self.assertAlmostEqual(ts["metrics"]["coherence"], 0.48)
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
        # v41/v42: спад -0.02 (скип) + 0.03 (урок сжатия, единожды);
        # coherence растёт ТОЛЬКО уроком (+0.03) и первым появлением
        # архетипа Semantic Compression (+0.05), не наградой claim-пути
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov - 0.02 + 0.03)
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03 + 0.05)
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
        # v41/v42: подавленный +0.1 НЕ применён; +0.03 урок сжатия
        # и +0.05 первое появление архетипа Semantic Compression
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.03 + 0.05)

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
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov + 0.03)

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
        # -0.1 (contradiction-open) + 0.03 (порог архетипа count==5)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf - 0.1 + 0.03)
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
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.05)
        # Второе появление — без coherence-награды
        _register_archetype(ts, _LESSON_REFLECTIVE)
        self.assertAlmostEqual(ts["metrics"]["coherence"], coh + 0.05)

    def test_count_three_rewards_novelty(self):
        from core.janus_conductor import _register_archetype, _LESSON_UNVERIFIED
        ts = self._state()
        _register_archetype(ts, _LESSON_UNVERIFIED)
        _register_archetype(ts, _LESSON_UNVERIFIED)
        nov = ts["metrics"]["novelty"]
        _register_archetype(ts, _LESSON_UNVERIFIED)   # count → 3
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov + 0.03)
        _register_archetype(ts, _LESSON_UNVERIFIED)   # count → 4, без награды
        self.assertAlmostEqual(ts["metrics"]["novelty"], nov + 0.03)

    def test_count_five_rewards_confidence(self):
        from core.janus_conductor import _register_archetype, _LESSON_DESIGN
        ts = self._state()
        for _ in range(4):
            _register_archetype(ts, _LESSON_DESIGN)
        conf = ts["metrics"]["confidence"]
        _register_archetype(ts, _LESSON_DESIGN)       # count → 5
        self.assertEqual(ts["archetypes"][0]["count"], 5)
        self.assertAlmostEqual(ts["metrics"]["confidence"], conf + 0.03)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
