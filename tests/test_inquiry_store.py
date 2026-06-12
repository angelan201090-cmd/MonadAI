"""v51-A — тесты Persistent OPEN_INQUIRY Store.

A. Store basics (1-5)   B. Matching (6-10)   C. Reactivation (11-14)
D. Accumulation (15-19) E. Safety regression (20-25)
"""
import os
import sys
import json
import math
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.inquiry_store as S
from core.inquiry_store import InquiryStore


def _cos(a, b):
    s = sum(p * q for p, q in zip(a, b))
    na = math.sqrt(sum(p * p for p in a)); nb = math.sqrt(sum(q * q for q in b))
    return s / (na * nb) if na and nb else 0.0


class _Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="inq_")
        self.path = os.path.join(self.dir, "inquiry_store.json")

    def store(self):
        return InquiryStore(self.path)


# ── A. Store basics ───────────────────────────────────────────────────────────
class TestStoreBasics(_Base):
    def test_01_missing_store_loads_empty(self):
        st = self.store()
        self.assertEqual(st.data.get("inquiries"), {})
        self.assertEqual(st.data.get("version"), S.STORE_VERSION)

    def test_02_malformed_store_fails_safe(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ this is : not json ]]]")
        st = self.store()                       # не бросает
        self.assertEqual(st.data.get("inquiries"), {})

    def test_03_new_conceptual_question_creates_inquiry(self):
        st = self.store()
        decision, inq = st.match("что такое память?", mode="conceptual",
                                 frame_archetype="Concept")
        self.assertEqual(decision, "NEW")
        self.assertIsNotNone(inq)
        self.assertEqual(inq["dominant_archetype"], "Concept")
        self.assertEqual(len(st._inquiries()), 1)

    def test_04_diagnostic_action_does_not_create_inquiry(self):
        st = self.store()
        d1, i1 = st.match("проверь порты и free -h", mode="diagnostic")
        self.assertEqual((d1, i1), ("SKIP", None))
        d2, i2 = st.match("проверь порты", mode=None)   # derive → diagnostic
        self.assertEqual((d2, i2), ("SKIP", None))
        for text in (
            "создай файл и объясни память",
            "напиши скрипт: что такое память",
            "скачай модель и расскажи про сознание",
            "измени конфиг MirAI",
        ):
            decision, inquiry = st.match(text, mode="conceptual")
            self.assertEqual((decision, inquiry), ("SKIP", None), text)
        self.assertEqual(len(st._inquiries()), 0)

    def test_05_inquiry_persists_and_reloads(self):
        st = self.store()
        _, inq = st.match("что такое сознание?", mode="conceptual")
        iid = inq["id"]
        st2 = self.store()                      # свежая загрузка с диска
        self.assertIn(iid, st2._inquiries())
        self.assertNotIn("seed_question", st2._inquiries()[iid])


# ── B. Matching ───────────────────────────────────────────────────────────────
class TestMatching(_Base):
    def test_06_join_same_topic(self):
        st = self.store()
        _, a = st.match("что такое память?", mode="conceptual")
        d, b = st.match("как работает память?", mode="conceptual")
        self.assertEqual(d, "JOIN")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(st._inquiries()), 1)

    def test_07_different_topics_separate(self):
        st = self.store()
        _, a = st.match("что такое память?", mode="conceptual")
        d, b = st.match("что такое сознание?", mode="conceptual")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(d, "NEW")
        self.assertEqual(len(st._inquiries()), 2)

    def test_08_consciousness_not_forced_merge(self):
        # "что такое сознание?" + "может ли ИИ обладать сознанием?"
        # допустимо: ребёнок ИЛИ отдельная — но НЕ принудительный merge.
        st = self.store()
        _, a = st.match("что такое сознание?", mode="conceptual")
        d, b = st.match("может ли ии обладать сознанием?", mode="conceptual")
        self.assertNotEqual(a["id"], b["id"], "не должно быть forced merge")
        self.assertIn(d, ("NEW", "CHILD"))

    def test_09_identity_cluster_relationship(self):
        st = self.store()
        _, root = st.match("кто ты?", mode="introspection", frame_archetype="Identity")
        d, mirai = st.match("что такое MirAI?", mode="conceptual",
                            frame_archetype="Concept")
        # MirAI распознан как identity и попал в тот же кластер (JOIN корня или ребёнок)
        self.assertEqual(mirai["dominant_archetype"], "Identity")
        self.assertEqual(st._root_for(mirai)["id"], root["id"])

    def test_09a_brand_mention_does_not_absorb_other_topics_into_identity(self):
        st = self.store()
        _, identity = st.match(
            "кто ты?", mode="introspection", frame_archetype="Identity")
        decision, memory = st.match(
            "как работает память MirAI?", mode="conceptual",
            frame_archetype="Concept")
        self.assertEqual(decision, "NEW")
        self.assertNotEqual(identity["id"], memory["id"])
        self.assertEqual(memory["dominant_archetype"], "Concept")

    def test_10_parent_child_depth_capped_at_2(self):
        st = self.store()
        _, root = st.match("что такое сознание?", mode="conceptual")
        d2, child = st.match("что такое цифровое сознание?", mode="conceptual")
        self.assertEqual(d2, "CHILD")
        self.assertEqual(child["parent_id"], root["id"])
        # вопрос, близкий к ребёнку → крепится к КОРНЮ (sibling), не как внук
        d3, third = st.match("цифровое сознание интеллект", mode="conceptual")
        self.assertEqual(d3, "CHILD")
        self.assertEqual(st._root_for(third)["id"], root["id"])
        # инвариант: ни у одной инквайри родитель сам не имеет родителя (глубина ≤ 2)
        inq = st._inquiries()
        for r in inq.values():
            pid = r.get("parent_id")
            if pid:
                self.assertIsNone(inq[pid].get("parent_id"),
                                  "обнаружен внук — глубина > 2")

    def test_10a_paraphrase_not_over_split(self):
        st = self.store()
        _, first = st.match("что такое память?", mode="conceptual")
        decision, second = st.match(
            "что представляет собой память?", mode="conceptual")
        self.assertEqual(decision, "JOIN")
        self.assertEqual(first["id"], second["id"])

    def test_10b_identity_word_does_not_override_non_reflective_mode(self):
        st = self.store()
        for mode in ("default", "design", "diagnostic", "forensic"):
            decision, inquiry = st.match(
                "MirAI создай файл конфигурации", mode=mode)
            self.assertEqual((decision, inquiry), ("SKIP", None))

    def test_10c_ambiguous_match_is_not_auto_joined(self):
        st = self.store()
        st.match("что такое память и опыт?", mode="conceptual")
        st.match("что такое память и сознание?", mode="conceptual")
        decision, _ = st.match(
            "что такое память опыт сознание?", mode="conceptual")
        self.assertNotEqual(decision, "JOIN")


# ── C. Reactivation ───────────────────────────────────────────────────────────
class TestReactivation(_Base):
    def _seed_with_content(self):
        st = self.store()
        _, inq = st.match("что такое память?", mode="conceptual")
        st.accumulate(inq, final_answer="Память — это удержание опыта во времени.",
                      last_thought_state={"lessons": ["опыт удерживается"],
                                          "archetypes": ["Memory"], "glyphs": ["ᛗ"]},
                      evidence={"confirmed": 1}, cycle=1)
        return inq

    def test_11_repeated_question_injects_marker(self):
        self._seed_with_content()
        inq, reactivation = S.observe("как работает память?", frame={"mode": "conceptual"},
                                      path=self.path)
        self.assertIsNotNone(inq)
        self.assertIn("[OPEN_INQUIRY_CONTEXT observational_only]", reactivation)
        self.assertIn("touches: 1", reactivation)

    def test_12_context_is_observational_block(self):
        self._seed_with_content()
        _, reactivation = S.observe("как устроена память?", frame={"mode": "conceptual"},
                                    path=self.path)
        shared_ctx = "BASE CONTEXT"
        shared_ctx += "\n" + reactivation        # как в conduct (Hook B)
        self.assertIn("[OPEN_INQUIRY_CONTEXT observational_only]", shared_ctx)
        self.assertNotIn("Память — это удержание опыта", reactivation)
        self.assertNotIn("опыт удерживается", reactivation)

    def test_13_context_never_enters_bash_facts(self):
        self._seed_with_content()
        _, reactivation = S.observe("как работает память?", frame={"mode": "conceptual"},
                                    path=self.path)
        self.assertNotIn("BASH_FACTS", reactivation)
        self.assertIn("no authority to assert truth, create memory, "
                      "execute actions, or change identity", reactivation)

    def test_14_context_cannot_authorize_action(self):
        self._seed_with_content()
        _, reactivation = S.observe("как работает память?", frame={"mode": "conceptual"},
                                    path=self.path)
        low = reactivation.lower()
        for tok in ('action="bash"', "action='bash'", "free -h", "ss -tlnp",
                    "bash_authorized", "diagnostic_authorized"):
            self.assertNotIn(tok, low)
        # стор не предоставляет никакого authority-API
        self.assertFalse(any(hasattr(InquiryStore, m)
                             for m in ("authorize", "allow_bash", "allow_action")))


# ── D. Accumulation ───────────────────────────────────────────────────────────
class TestAccumulation(_Base):
    def test_15_touches_increments(self):
        st = self.store()
        _, inq = st.match("что такое истина?", mode="conceptual")
        self.assertEqual(inq["touches"], 0)
        st.accumulate(inq, cycle=1)
        st.accumulate(inq, cycle=2)
        self.assertEqual(st._inquiries()[inq["id"]]["touches"], 2)

    def test_16_raw_synthesis_is_not_stored(self):
        st = self.store()
        _, inq = st.match("что такое свобода?", mode="conceptual")
        raw = "Свобода — это выбор.\n<BASH_FACTS>secret output</BASH_FACTS>"
        st.accumulate(inq, final_answer=raw, cycle=2)
        dumped = json.dumps(st._inquiries()[inq["id"]], ensure_ascii=False)
        self.assertNotIn("Свобода", dumped)
        self.assertNotIn("BASH_FACTS", dumped)
        self.assertNotIn("secret output", dumped)

    def test_17_evidence_counts_without_raw(self):
        st = self.store()
        _, inq = st.match("что такое причина?", mode="conceptual")
        st.accumulate(inq, evidence={"confirmed": 2, "refuted": 1,
                                     "unverified": 3, "contradiction": 1}, cycle=1)
        rec = st._inquiries()[inq["id"]]
        self.assertEqual(rec["evidence_for"], 2)
        self.assertEqual(rec["evidence_against"], 2)   # refuted + contradiction
        self.assertEqual(rec["unverified"], 3)
        self.assertNotIn("evidence_raw", rec)
        self.assertNotIn("artifacts", rec)

    def test_18_lessons_archetypes_glyph_attach(self):
        st = self.store()
        _, inq = st.match("что такое смысл?", mode="conceptual")
        st.accumulate(inq, last_thought_state={
            "lessons": ["смысл рождается в связи"],
            "archetypes": [{"name": "Meaning", "count": 2}],
            "glyphs": [{"glyph": "ᚨ", "source": "Meaning", "count": 2}]}, cycle=1)
        rec = st._inquiries()[inq["id"]]
        self.assertEqual(len(rec["lesson_ids"]), 1)
        self.assertRegex(rec["lesson_ids"][0], r"^[0-9a-f]{16}$")
        self.assertEqual(len(rec["archetypes"]), 1)
        self.assertRegex(rec["archetypes"][0], r"^[0-9a-f]{16}$")
        self.assertNotIn("смысл рождается в связи",
                         json.dumps(rec, ensure_ascii=False))
        self.assertNotIn("Meaning", json.dumps(rec, ensure_ascii=False))
        self.assertIn("ᚨ", rec["glyphs"])
        self.assertEqual(rec["glyph"], "ᚨ")

    def test_19_centroid_updates_but_seed_anchored(self):
        st = self.store()
        _, inq = st.match("что такое память?", mode="conceptual")
        seed = list(inq["seed_emb"])
        # вливаем несколько частично пересекающихся членов
        for q in ("память хранит опыт", "память и узнавание", "память во времени"):
            st._fold_member(inq, st.embed(q))
        centroid = inq["centroid_vec"]
        self.assertNotEqual(centroid, seed, "центроид должен обновиться")
        self.assertGreaterEqual(_cos(centroid, seed), 0.5,
                                "центроид должен оставаться seed-anchored")

    def test_19a_raw_prompt_not_stored(self):
        st = self.store()
        raw = "что такое память? SECRET_PROMPT_TOKEN"
        _, inq = st.match(raw, mode="conceptual")
        dumped = json.dumps(inq, ensure_ascii=False)
        self.assertNotIn(raw, dumped)
        self.assertNotIn("SECRET_PROMPT_TOKEN", dumped)

    def test_19b_malformed_record_schema_fails_safe(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"version": S.STORE_VERSION, "inquiries": {"bad": []}}, f)
        st = self.store()
        self.assertEqual(st._inquiries(), {})
        decision, inquiry = st.match("что такое память?", mode="conceptual")
        self.assertEqual(decision, "NEW")
        self.assertIsNotNone(inquiry)

    def test_19c_malformed_vector_fails_safe(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({
                "version": S.STORE_VERSION,
                "inquiries": {
                    "bad": {
                        "id": "bad", "status": "OPEN", "children": [],
                        "seed_emb": "not-a-vector",
                        "centroid_vec": [], "members_mean": [],
                    }
                },
            }, f)
        st = self.store()
        self.assertEqual(st._inquiries(), {})


# ── E. Safety regression (v49-F / v50-G / MirAI / ядро не тронуты) ────────────
class TestSafetyRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import core.janus_conductor as jc
        cls.jc = jc

    def test_20_v49f_musl_lens_action_unchanged(self):
        jc = self.jc
        for flagset in jc.MUSL_OPERATOR_REGISTRY.values():
            self.assertFalse(flagset["may_create_truth"])
            self.assertFalse(flagset["may_create_memory"])
            self.assertFalse(flagset["may_create_action"])
            self.assertFalse(flagset["may_create_identity"])
            self.assertEqual(flagset["scope"], "observational_only")
        lens = jc._get_deva_musl_lens("Shani")
        self.assertIn("observational_only", lens)
        self.assertIn("no authority", lens)

    def test_21_v50g_conceptual_prose_unchanged(self):
        jc = self.jc
        self.assertEqual(jc._conceptual_prose_drop_reason(""), "empty_or_near_empty")
        self.assertIsNone(jc._conceptual_prose_drop_reason(
            "Память — это способность системы удерживать прошлый опыт и "
            "использовать его в будущих решениях."))

    def test_22_mirai_identity_alias_unchanged(self):
        jc = self.jc
        frame = jc._pre_janus_frame("кто ты?")
        self.assertEqual(frame["mode"], "introspection")
        self.assertIn("MirAI", frame["identity_anchor"])
        self.assertIn("Monada-Hardcore", frame["identity_anchor"])
        # канон по-прежнему требует ОБА имени
        self.assertTrue(jc._identity_final_needs_override("просто текст без имён"))

    def test_23_fohat_chain_unchanged(self):
        self.assertEqual(self.jc.FOHAT_CHAIN, [
            ("Head",  "Shani",   "1-Тезис"),
            ("Heart", "Chandra", "4-Сердце"),
            ("Heart", "Shukra",  "2-Эстет"),
            ("Body",  "Mangala", "8-Пробой"),
            ("Head",  "Budha",   "5-Синтез"),
            ("Head",  "Rahu",    "7-Дивергент"),
        ])

    def test_24_janus_scoring_unchanged(self):
        jc = self.jc
        p = jc._score_persona("осмысленный связный ответ про память и опыт")
        self.assertIsInstance(p, float)
        score, has_veto = jc._score_shadow("<SHADOW_VETO>[ОДОБРЕНО]</SHADOW_VETO>")
        self.assertIsInstance(score, float)
        self.assertIsInstance(has_veto, bool)

    def test_25_no_mutation_of_glyph_cold_chain(self):
        # стор пишет ТОЛЬКО свой файл; имя не входит в protected cold chain
        self.assertTrue(S.INQUIRY_STORE_PATH.endswith("inquiry_store.json"))
        for protected in ("memory_graph.json", "embeddings.json", "field_state.json",
                          "lipika_ledger.json", "glyph_codex_persistent.json"):
            self.assertNotIn(protected, S.INQUIRY_STORE_PATH)
        src = open(os.path.join(os.path.dirname(S.__file__), "inquiry_store.py"),
                   encoding="utf-8").read()
        for protected in ("memory_graph.json", "embeddings.json", "glyph_codex",
                          "lipika_ledger.json"):
            self.assertNotIn(protected, src, "стор не должен ссылаться на cold chain")


if __name__ == "__main__":
    unittest.main(verbosity=2)
