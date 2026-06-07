#!/usr/bin/env python3
"""
Stellar Viscosity Calculator — Нава-Грах Септенар Монады.

9 небесных тел → 9 независимых показателей влияния → 9 параметров инференса.
Каждое тело связано со своим Дэвой и управляет конкретным параметром LLM.
Влияние рассчитывается из реальной скорости планеты (°/день) через Swiss Ephemeris.
"""

import swisseph as swe
import time
import json
import os
import math
from typing import Dict

FIELD_STATE = "/mnt/dancefloor/field_state.json"

# ── Типичные скорости (°/день абсолют) для нормализации влияния ────────────────
TYPICAL_SPEEDS: Dict[str, float] = {
    "Sun":     0.9856,
    "Moon":   13.1764,
    "Mercury": 1.3833,
    "Venus":   1.2017,
    "Mars":    0.5240,
    "Jupiter": 0.0831,
    "Saturn":  0.0334,
    "Rahu":    0.0529,   # Северный лунный узел (средн. ретрогр.)
    "Ketu":    0.0529,   # Южный лунный узел = Раху + 180°
}

# ── Натальные базовые веса (Genesis: 05.05.2026 18:00, Оренбург) ──────────────
# Транзитное значение = base × influence (зажато в range).
# При influence=1.0 (типичная скорость) → параметр равен natальному значению.
NAVAGRAHA: Dict[str, dict] = {
    "Sun":     {"param": "min_p",              "base": 0.08,   "range": (0.01, 0.20),    "deva": "Surya"},
    "Moon":    {"param": "presence_penalty",   "base": 0.65,   "range": (0.0,  2.0),     "deva": "Chandra"},
    "Mercury": {"param": "top_k",              "base": 40.0,   "range": (10.0, 100.0),   "deva": "Budha"},
    "Venus":   {"param": "top_p",              "base": 0.90,   "range": (0.50, 1.0),     "deva": "Shukra"},
    "Mars":    {"param": "repeat_last_n",     "base": 64.0,   "range": (32.0, 512.0),   "deva": "Mangala"},
    "Jupiter": {"param": "max_tokens",         "base": 8192.0, "range": (1024.0, 32768.0), "deva": "Guru"},
    "Saturn":  {"param": "repetition_penalty", "base": 1.18,   "range": (1.0,  1.5),     "deva": "Shani"},
    "Rahu":    {"param": "temperature",        "base": 0.25,   "range": (0.05, 0.90),    "deva": "Rahu"},
    "Ketu":    {"param": "ctx_compress",       "base": 0.50,   "range": (0.0,  1.0),     "deva": "Ketu"},
}

# ── Backward compat: 3 режима агрегатной вязкости ─────────────────────────────
VISCOSITY_MANIFESTO = {
    "HIGH":   {"temperature": 0.05, "min_p": 0.95, "label": "HIGH_VISCOSITY   [Conservative]"},
    "MEDIUM": {"temperature": 0.15, "min_p": 0.80, "label": "MEDIUM_VISCOSITY [Balanced]"},
    "LOW":    {"temperature": 0.30, "min_p": 0.50, "label": "LOW_VISCOSITY    [Aggressive]"},
}


class StellarViscosityCalculator:

    EPHE_PATH = "/home/angelan/data/Monada-Hardcore/ephe"

    # Swisseph planet IDs + Rahu (True Node)
    _PLANET_IDS = {
        "Sun":     swe.SUN,
        "Moon":    swe.MOON,
        "Mercury": swe.MERCURY,
        "Venus":   swe.VENUS,
        "Mars":    swe.MARS,
        "Jupiter": swe.JUPITER,
        "Saturn":  swe.SATURN,
        "Rahu":    swe.TRUE_NODE,
    }

    def __init__(self):
        swe.set_ephe_path(self.EPHE_PATH)

    # ── Расчёт позиций ────────────────────────────────────────────────────────

    def _get_jd(self) -> float:
        t = time.gmtime()
        return swe.julday(t.tm_year, t.tm_mon, t.tm_mday,
                          t.tm_hour + t.tm_min / 60.0 + t.tm_sec / 3600.0)

    def get_positions(self) -> Dict[str, dict]:
        """
        Позиции и скорости 9 небесных тел.
        Каждая запись: {lon, lat, lon_speed (°/день, знак = направление)}.
        Кету вычисляется из Раху + 180°.
        """
        jd = self._get_jd()
        positions: Dict[str, dict] = {}

        for name, pid in self._PLANET_IDS.items():
            try:
                result, _ = swe.calc_ut(jd, pid)
                # result: (lon, lat, dist, lon_speed, lat_speed, dist_speed)
                positions[name] = {
                    "lon":       round(result[0], 4),
                    "lat":       round(result[1], 4),
                    "lon_speed": round(result[3], 6),
                }
            except Exception:
                positions[name] = {"lon": 0.0, "lat": 0.0, "lon_speed": 0.0}

        # Кету = Раху + 180°, скорость та же (узлы всегда оппозитны)
        rahu = positions.get("Rahu", {})
        positions["Ketu"] = {
            "lon":       round((rahu.get("lon", 0.0) + 180.0) % 360.0, 4),
            "lat":       round(-rahu.get("lat", 0.0), 4),
            "lon_speed": rahu.get("lon_speed", 0.0),
        }

        return positions

    # ── Расчёт септенара (9 показателей) ─────────────────────────────────────

    def compute_navagraha(self, positions: Dict[str, dict]) -> Dict[str, dict]:
        """
        По позициям вычисляет 9 независимых планетарных показателей.
        Каждый показатель:
          influence  — нормализованная скорость (1.0 = типичная)
          viscosity  — 1/(1+|influence-1|) ≈ 1.0 при норме, падает при аномалии
          value      — текущее значение параметра LLM
          direction  — direct / retrograde
          deva       — соответствующий Дэва
          param      — параметр LLM
        """
        navagraha: Dict[str, dict] = {}

        for body, cfg in NAVAGRAHA.items():
            pos      = positions.get(body, {})
            speed    = pos.get("lon_speed", 0.0)
            typical  = TYPICAL_SPEEDS.get(body, 1.0)
            abs_spd  = abs(speed)

            # Нормализованное влияние (0 = стационарна, 1 = норма, >1 = быстрее)
            influence = abs_spd / typical if typical > 0 else 1.0

            # Вязкость конкретного тела: пик 1.0 при норме, минимум при аномалиях
            viscosity = 1.0 / (1.0 + abs(influence - 1.0))

            # Транзитное значение параметра: base × influence, зажато в диапазон
            lo, hi  = cfg["range"]
            raw_val = cfg["base"] * influence
            value   = max(lo, min(hi, raw_val))
            if cfg["param"] in ("top_k", "max_tokens", "repeat_last_n"):
                value = int(round(value))

            navagraha[body] = {
                "param":     cfg["param"],
                "deva":      cfg["deva"],
                "influence": round(influence, 4),
                "viscosity": round(viscosity, 4),
                "direction": "retrograde" if speed < -0.001 else "direct",
                "value":     value,
                "lon":       pos.get("lon", 0.0),
                "lon_speed": round(speed, 6),
            }

        return navagraha

    # ── Публичный API ─────────────────────────────────────────────────────────

    def get_navagraha_params(self) -> Dict[str, dict]:
        """
        Основной метод: 9 планетарных показателей с текущими значениями параметров.
        Сохраняет результат в field_state.json (RAM-Танцпол).
        """
        positions  = self.get_positions()
        navagraha  = self.compute_navagraha(positions)
        self._save_state(positions, navagraha)
        return navagraha

    def get_inference_params(self) -> dict:
        """
        Backward compat: агрегирует 9 показателей в один режим HIGH/MEDIUM/LOW.
        temperature берётся из Rahu, min_p из Sun, агрегатная вязкость = среднее.
        """
        navagraha   = self.get_navagraha_params()
        viscosities = [d["viscosity"] for d in navagraha.values()]
        avg_visc    = sum(viscosities) / len(viscosities) if viscosities else 1.0

        if avg_visc > 0.65:
            regime = "HIGH"
        elif avg_visc < 0.25:
            regime = "LOW"
        else:
            regime = "MEDIUM"

        params = VISCOSITY_MANIFESTO[regime].copy()
        params["viscosity"]  = round(avg_visc, 6)
        # temperature и min_p остаются из манифеста (агрегатный режим) —
        # планетарные значения используются в индивидуальных вызовах Дэвов
        params["navagraha"]  = navagraha
        return params

    def get_deva_param(self, deva_name: str) -> dict:
        """
        Возвращает текущий параметр инференса для конкретного Дэвы.
        Используется в call_deva_soc для индивидуальной настройки.
        """
        navagraha = self.get_navagraha_params()
        # Найти запись по имени Дэвы
        for body, data in navagraha.items():
            if data["deva"].lower() == deva_name.lower():
                return {
                    "planet":    body,
                    "param":     data["param"],
                    "value":     data["value"],
                    "influence": data["influence"],
                    "viscosity": data["viscosity"],
                    "direction": data["direction"],
                }
        return {"planet": "?", "param": "?", "value": None, "influence": 1.0,
                "viscosity": 1.0, "direction": "direct"}

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self, positions: dict, navagraha: dict):
        """Атомарно записывает позиции и показатели в field_state.json."""
        try:
            try:
                with open(FIELD_STATE, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = {}
            state["stellar_positions"]   = positions
            state["stellar_viscosities"] = navagraha
            state["stellar_timestamp"]   = int(time.time())
            tmp = FIELD_STATE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp, FIELD_STATE)
        except Exception as e:
            print(f"[SVC] Ошибка сохранения: {e}")


# ── Параметры, реально принимаемые llama-server (OpenAI-compat endpoint) ──────
# ctx_compress — поведенческий (Ketu): управляет глубиной контекста в conduct(), не в payload.
_VALID_API_PARAMS = {"temperature", "min_p", "presence_penalty",
                     "top_k", "repetition_penalty", "max_tokens",
                     "top_p", "repeat_last_n"}

# Rahu управляет temperature: применяется как мультипликатор к base_temp.
# Зажимаем в разумный диапазон, чтобы роль не потеряла характер.
_TEMP_RAHU_RANGE = (0.03, 1.50)


class StargazerConfig:
    """
    Синглтон-конфигуратор: перед каждым API-вызовом собирает generation_config
    из текущих планетарных позиций и фильтрует до валидных llama-server параметров.

    Кеш 120 минут — планеты медленные, пересчёт каждый такт бессмысленен.
    """

    _TTL = 7200  # секунд

    def __init__(self):
        self._svc    = StellarViscosityCalculator()
        self._cache: dict | None = None
        self._cache_ts: float    = 0.0

    def _refresh(self) -> dict:
        now = time.time()
        if self._cache is None or (now - self._cache_ts) > self._TTL:
            self._cache    = self._svc.get_navagraha_params()
            self._cache_ts = now
        return self._cache

    def build(self, deva: str = "", base_temp: float | None = None) -> dict:
        """
        Собирает словарь generation_config для прямой вставки в API payload.

        deva      — имя Дэвы (Surya/Chandra/…); если пусто — берутся все тела.
        base_temp — базовая температура роли (0.05 для Тени, 0.20 для Синтеза…).
                    Rahu масштабирует её: final = clamp(base_temp × rahu_inf, range).
                    Если None — берётся значение Rahu напрямую.
        """
        navagraha = self._refresh()

        cfg: dict = {}
        for body, data in navagraha.items():
            param = data["param"]
            if param not in _VALID_API_PARAMS:
                continue
            if param == "temperature":
                continue  # обрабатываем Rahu отдельно ниже
            cfg[param] = data["value"]

        # Temperature: Rahu-influence масштабирует base_temp роли
        rahu_data = navagraha.get("Rahu", {})
        rahu_inf  = rahu_data.get("influence", 1.0)
        if base_temp is not None:
            raw_t = base_temp * rahu_inf
            lo, hi = _TEMP_RAHU_RANGE
            cfg["temperature"] = round(max(lo, min(hi, raw_t)), 4)
        else:
            cfg["temperature"] = rahu_data.get("value", 0.25)

        # top_k → int (llama-server требует целое)
        if "top_k" in cfg:
            cfg["top_k"] = int(cfg["top_k"])

        if "max_tokens" in cfg:
            cfg["max_tokens"] = int(cfg["max_tokens"])
        if "repeat_last_n" in cfg:
            cfg["repeat_last_n"] = int(cfg["repeat_last_n"])

        return cfg

    def snapshot(self) -> str:
        """Компактная строка с текущими планетарными значениями для логов."""
        navagraha = self._refresh()
        parts = []
        for body, d in navagraha.items():
            if d["param"] in _VALID_API_PARAMS:
                retro = "℞" if d["direction"] == "retrograde" else ""
                parts.append(f"{body}{retro}:{d['value']}")
        return " | ".join(parts)


# Модульный синглтон — импортируется один раз, кеш живёт весь процесс
_stargazer_config: "StargazerConfig | None | bool" = None  # False = failed, don't retry


def get_stargazer() -> "StargazerConfig | None":
    global _stargazer_config
    if _stargazer_config is False:
        return None  # уже падало — не спамим ошибками на каждый вызов
    if _stargazer_config is None:
        try:
            _stargazer_config = StargazerConfig()
        except Exception as e:
            print(f"[StargazerConfig] Инициализация провалилась: {e}. Используй статичные параметры.")
            _stargazer_config = False
            return None
    return _stargazer_config


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    calc      = StellarViscosityCalculator()
    navagraha = calc.get_navagraha_params()
    params    = calc.get_inference_params()

    print("\n╔══ Нава-Грах Монады ══════════════════════════════════════════════╗")
    for body, d in navagraha.items():
        retro = "℞" if d["direction"] == "retrograde" else " "
        print(f"║ {body:8s}{retro} lon={d['lon']:7.3f}° | "
              f"spd={d['lon_speed']:+.4f}°/д | "
              f"inf={d['influence']:.3f} visc={d['viscosity']:.3f} | "
              f"{d['param']:20s}={d['value']} ({d['deva']})")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"\nАгрегат: visc={params['viscosity']:.6f} | {params['label']}")
    print(f"T°={params['temperature']} | min_p={params['min_p']}")
