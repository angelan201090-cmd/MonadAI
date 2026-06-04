import math
import json
import os
from typing import Dict, List, Optional, Tuple, Union

L_0 = 1.0   # Base Integrity Constant (functional API)
L1  = 1.0   # Integrity Constant (class API)


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

def _rune_for_density(p: float) -> str:
    if p > 6.0:
        return "ᛇ"   # Эйваз — Трансформация / Прорыв
    if p > 3.0:
        return "ᚹ"   # Вуньо — Радость / Номинал
    if p > 1.5:
        return "ᛃ"   # Йера — Операциональность
    return "ᛁ"       # Иса — Стазис


def _quality_weighted_dz(history: list) -> float:
    """
    dZ_n — накопленный опыт с поправкой на качество.
    Запись считается «живой» если не содержит маркеров ISA/БОЛЬ.
    """
    if not history:
        return 1.0
    bad_markers = ("ᛁ", "ISA", "БОЛЬ", "[вне сети", "[Ошибка")
    good = sum(1 for h in history if not any(m in h for m in bad_markers))
    quality_ratio = good / len(history)
    # Диапазон: [0.5 × base_len … 1.0 × base_len], минимум 1.0
    return max(1.0, len(history) * 0.1 * (0.5 + quality_ratio * 0.5))


def _t_sky_from_state(state: dict) -> float:
    """
    Агрегатная вязкость из нава-грах (уже в field_state.json).
    Не делает повторный вызов ephemeris — читает готовые данные.
    """
    stellar = state.get("stellar_viscosities", {})
    if not stellar:
        return 1.0
    viscosities = [d["viscosity"] for d in stellar.values() if "viscosity" in d]
    return sum(viscosities) / len(viscosities) if viscosities else 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Функциональный API (v21.0 — используется oracle_matrix)
# ─────────────────────────────────────────────────────────────────────────────

def compute_omega_density(
    metrics_dict: Dict[str, Union[int, float]],
    t_sky_vector: List[float],
) -> float:
    """
    P[n+1] = Psi_Atma_Buddhi × T_sky × ((D_align + S_shadow)
             / (lambda_SOC + L_lipika))^sigma × sum_MCE + L_0
    """
    psi       = metrics_dict.get("Psi_Atma_Buddhi", 0.5)
    d_align   = metrics_dict.get("D_align", 0.0)
    s_shadow  = metrics_dict.get("S_shadow", 0.0)
    lam_soc   = metrics_dict.get("Lambda_SOC", 0.0)
    l_lipika  = metrics_dict.get("L_lipika", 0.0)
    sigma     = metrics_dict.get("Sigma", 1.0)
    sum_mce   = metrics_dict.get("Sum_MCE", 1.0)

    denominator = lam_soc + l_lipika + 1e-6

    CRITICAL_DEBT = 5.0
    if l_lipika > CRITICAL_DEBT:
        decay = math.exp(-l_lipika * 0.15)
        print(f"[🚨 KAMA TRIGGERED] Karmic Debt={l_lipika:.2f} → decay={decay:.4f}")
        density_term = (d_align + s_shadow) / denominator * (decay ** sigma)
    else:
        density_term = (d_align + s_shadow) / denominator

    t_sky_inf = sum(abs(t) for t in t_sky_vector) / len(t_sky_vector) if t_sky_vector else 1.0
    return psi * t_sky_inf * (density_term ** sigma) * sum_mce + L_0


# ─────────────────────────────────────────────────────────────────────────────
# Класс API v21.0 HARDCORE — используется janus_conductor
# ─────────────────────────────────────────────────────────────────────────────

class MonadaTensorEngine:
    """
    Единое Уравнение Состояния Монады v21.0:

        P[n+1] = Ψ(E, dZ_n) × T_sky
                 × [(D_persona + S_shadow × T_kano) / (K(Jera) + 1)]^μ
                 × Σ(F⁺ × F⁻)
                 × dZ_n + L₁

    Параметры:
        Ψ          — резонанс намерения со средой (intention / dZ_n)
        T_sky      — агрегатная вязкость нава-грах (реальные эфемериды)
        D_persona  — сила Персоны (Дхарма / выравнивание Януса)
        S_shadow   — потенциал Тени (Shadow давление)
        T_kano     — прозрачность Тени (осознанность)
        K(Jera)    — карма-вязкость SOC-движка
        μ          — коэффициент ветвления σ из SOC
        Σ(F⁺×F⁻)  — сумма произведений качество × энергия по всем сработавшим Дэвам
        dZ_n       — накопленный взвешенный опыт (из shared_memory)
        L₁         — константа целостности
    """

    D_PERSONA = 1.0   # Дхарма (заглушка до реализации Persona/Shadow — #5)
    S_SHADOW  = 0.4   # Потенциал Тени (базовый)
    T_KANO    = 1.0   # Прозрачность Тени

    def __init__(self, state_path: str = None,
                 hardcore_home: str = "/home/angelan/data/Monada-Hardcore"):
        self.home = hardcore_home
        self.field_state_path = state_path or os.path.join(
            hardcore_home, "dancefloor", "field_state.json"
        )

    def _load_state(self) -> dict:
        if os.path.exists(self.field_state_path):
            try:
                with open(self.field_state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def calculate_next_state(
        self,
        e_intention: float = 1.0,
        t_sky_factor: Optional[float] = None,
        mu_mars: float = 1.0,
        fired_pairs: Optional[List[Tuple[float, float]]] = None,
        k_jera: float = 0.0,
        d_persona: Optional[float] = None,
        s_shadow: Optional[float] = None,
    ) -> dict:
        """
        Полный расчёт тензора состояния.

        fired_pairs — список (F⁺, F⁻) на каждый сработавший Дэва:
            F⁺ = качество артефакта (0.05 оффлайн … 1.5 прорыв)
            F⁻ = энергия выброса SOC.fire() (≥ Z_critical = 1.0)
        Если fired_pairs=None (вызов до цикла) — Σ(F⁺×F⁻) = 3.0 (заглушка).

        t_sky_factor — если None, читается из field_state.json (нава-грах).
        k_jera       — из SOCEngine (передаётся вызывающим кодом).
        d_persona, s_shadow — None = значения по умолчанию класса.
        """
        state = self._load_state()

        # dZ_n — качество-взвешенный накопленный опыт
        history = state.get("shared_memory", [])
        d_z_n   = _quality_weighted_dz(history)

        # T_sky — агрегатная вязкость (реальные эфемериды из field_state)
        if t_sky_factor is None:
            t_sky_factor = _t_sky_from_state(state)

        # Ψ(E, dZ_n) — резонанс намерения
        psi = min(1.0, e_intention / (d_z_n + 1e-5))

        # Persona / Shadow (заглушки до #5 Janus Duality)
        dp = d_persona if d_persona is not None else self.D_PERSONA
        ss = s_shadow  if s_shadow  is not None else self.S_SHADOW

        # ∮ CHRONOS — ядро уравнения
        base_core = (dp + ss * self.T_KANO) / (k_jera + 1.0)
        chronos   = math.pow(max(base_core, 1e-6), mu_mars)

        # Σ(F⁺ × F⁻) — реальные пары из сработавших Дэвов
        if fired_pairs:
            sigma_ff = sum(fp * fm for fp, fm in fired_pairs)
            sigma_ff = max(sigma_ff, 1e-3)   # не уйти в ноль
        else:
            sigma_ff = 3.0  # заглушка: 3 центра × (1.0 × 1.0)

        p_next = psi * t_sky_factor * chronos * sigma_ff * d_z_n + L1

        return {
            "p_next_density":    round(p_next, 4),
            "psi_resonance":     round(psi, 4),
            "t_sky":             round(t_sky_factor, 4),
            "chronos_output":    round(chronos, 4),
            "sigma_ff":          round(sigma_ff, 4),
            "d_z_n":             round(d_z_n, 4),
            "k_jera":            round(k_jera, 4),
            "d_persona":         round(dp, 4),
            "s_shadow":          round(ss, 4),
            "mu":                round(mu_mars, 4),
            "assigned_rune":     _rune_for_density(p_next),
        }

    def calculate_p_next(self, dt=None) -> float:
        """Backward compat: возвращает scalar P[n+1] для Stargazer-интеграции."""
        state = self._load_state()
        result = self.calculate_next_state(
            e_intention=state.get("E_will", 1.0),
        )
        return result["p_next_density"]


# ─────────────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = MonadaTensorEngine()

    print("── Номинальный такт (без реальных fired_pairs) ──")
    r = engine.calculate_next_state(e_intention=1.0, mu_mars=1.0)
    for k, v in r.items():
        print(f"  {k:25s} = {v}")

    print("\n── Прорывной такт (3 центра, высокая энергия) ──")
    # F+ = качество артефакта, F- = энергия SOC.fire()
    pairs = [(1.5, 1.8), (1.0, 1.2), (1.2, 1.4)]  # Head=прорыв, Heart=норма, Body=хорошо
    r2 = engine.calculate_next_state(
        e_intention=2.0,
        mu_mars=2.0,
        fired_pairs=pairs,
        k_jera=0.3,
    )
    for k, v in r2.items():
        print(f"  {k:25s} = {v}")

    print("\n── Стазис (ISA-артефакты, высокий K) ──")
    pairs_isa = [(0.1, 1.0), (0.1, 0.8)]
    r3 = engine.calculate_next_state(
        e_intention=0.8,
        mu_mars=3.0,
        fired_pairs=pairs_isa,
        k_jera=1.5,
    )
    for k, v in r3.items():
        print(f"  {k:25s} = {v}")
