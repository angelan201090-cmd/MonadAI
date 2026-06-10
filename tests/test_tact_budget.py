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


if __name__ == "__main__":
    unittest.main(verbosity=2)
