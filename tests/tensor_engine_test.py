import unittest
import json
import os
import datetime
import tempfile
import sys

sys.path.insert(0, "/home/angelan/data/Monada-Hardcore")
from core.tensor_engine import MonadaTensorEngine, compute_omega_density


class MockStargazer:
    def __init__(self, factor: float = 1.0):
        self._factor = factor

    def calculate_modulation_factor(self, dt):
        return self._factor


class TestMonadaTensorEngine(unittest.TestCase):

    def _make_engine(self, history=None, stargazer_factor=1.0):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        state = {"shared_memory": history or [], "cycle": 1}
        json.dump(state, tmp)
        tmp.close()
        engine = MonadaTensorEngine(state_path=tmp.name)
        engine.stargazer = MockStargazer(stargazer_factor)
        self._tmpfile = tmp.name
        return engine

    def tearDown(self):
        if hasattr(self, "_tmpfile") and os.path.exists(self._tmpfile):
            os.remove(self._tmpfile)

    # ── calculate_next_state ───────────────────────────────

    def test_nominal_state_empty_history(self):
        """Пустая история → d_z_n=1.0, k_jera=0.0."""
        engine = self._make_engine()
        r = engine.calculate_next_state(e_intention=1.0, t_sky_factor=1.0, mu_mars=1.0)
        # psi = min(1.0, 1.0 / (1.0 + 1e-5)) ≈ 1.0
        # base_core = (1.0 + 0.4) / 1.0 = 1.4;  chronos = 1.4^1 = 1.4
        # p_next = 1.0 * 1.0 * 1.4 * 3.0 * 1.0 + 1.0 = 5.2
        self.assertAlmostEqual(r["p_next_density"], 5.2, places=1)
        self.assertEqual(r["assigned_rune"], "ᚹ")  # > 3.0; ᛇ требует > 6.0

    def test_mars_supereffort(self):
        """mu_mars=3.0 резко поднимает плотность."""
        engine = self._make_engine()
        r_nom  = engine.calculate_next_state(mu_mars=1.0)
        r_mars = engine.calculate_next_state(e_intention=2.0, mu_mars=3.0)
        self.assertGreater(r_mars["p_next_density"], r_nom["p_next_density"])

    def test_stasis_with_pain_in_history(self):
        """k_jera > 0 снижает base_core и итоговую плотность."""
        engine = self._make_engine()
        r_nominal = engine.calculate_next_state(k_jera=0.0)
        r_trauma  = engine.calculate_next_state(k_jera=2.0)
        self.assertEqual(r_nominal["k_jera"], 0.0)
        self.assertLess(r_trauma["p_next_density"], r_nominal["p_next_density"])

    def test_assigned_rune_thresholds(self):
        """Правильная руна по порогам: >5→ᛇ, >3→ᚹ, ≤3→ᛁ."""
        engine = self._make_engine()
        # Принудительно задаём t_sky_factor = 0.01 → очень низкая плотность
        r_low = engine.calculate_next_state(e_intention=0.001, t_sky_factor=0.01, mu_mars=0.1)
        self.assertEqual(r_low["assigned_rune"], "ᛁ")

    # ── calculate_p_next ──────────────────────────────────

    def test_calculate_p_next_returns_float(self):
        engine = self._make_engine()
        p = engine.calculate_p_next(datetime.datetime.utcnow())
        self.assertIsInstance(p, float)
        self.assertGreater(p, 0.0)

    def test_t_sky_scales_p_next(self):
        """Более высокий t_sky_factor → более высокий P[n+1]."""
        engine = self._make_engine()
        p_low  = engine.calculate_next_state(t_sky_factor=1.0)["p_next_density"]
        p_high = engine.calculate_next_state(t_sky_factor=3.0)["p_next_density"]
        self.assertGreater(p_high, p_low)

    # ── compute_omega_density (функциональный API) ─────────

    def test_omega_density_nominal(self):
        metrics = {
            "Psi_Atma_Buddhi": 0.9, "D_align": 0.8, "S_shadow": 0.2,
            "Lambda_SOC": 1.0, "L_lipika": 0.5, "Sigma": 2.0, "Sum_MCE": 1.5,
        }
        sky = [0.5] * 9
        density = compute_omega_density(metrics, sky)
        self.assertGreater(density, L_0 := 1.0)

    def test_omega_density_high_debt_decay(self):
        """Высокий L_lipika обрушивает плотность."""
        metrics_ok  = {"Psi_Atma_Buddhi": 0.9, "D_align": 0.8, "S_shadow": 0.2,
                       "Lambda_SOC": 1.0, "L_lipika": 0.5, "Sigma": 2.0, "Sum_MCE": 1.5}
        metrics_bad = {**metrics_ok, "L_lipika": 15.0}
        sky = [0.5] * 9
        self.assertGreater(
            compute_omega_density(metrics_ok, sky),
            compute_omega_density(metrics_bad, sky),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
