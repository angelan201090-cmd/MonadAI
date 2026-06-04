import swisseph as swe
import numpy as np
import time
from typing import Dict, Any, Tuple

EPHE_PATH = "/home/angelan/data/Monada-Hardcore/ephe"

# Полный септенар — 7 священных тел
SEPTENAR: Dict[str, int] = {
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus":   swe.VENUS,
    "Mars":    swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
}


class GeocentricOracle:
    """
    Monada-Hardcore Geocentric Oracle.
    Вычисляет геоцентрические эфемеридные позиции через Swiss Ephemeris.
    Центр — Земля (геоцентрическая система координат).
    """

    def __init__(self):
        try:
            swe.set_ephe_path(EPHE_PATH)
            self._ready = True
            print("--> GeocentricOracle: Swiss Ephemeris bound to Earth center.")
        except Exception as e:
            print(f"CRITICAL ORACLE FAILURE: {e}")
            self._ready = False

    def _now_jd(self) -> float:
        t = time.gmtime()
        return swe.julday(t.tm_year, t.tm_mon, t.tm_mday,
                          t.tm_hour + t.tm_min / 60.0 + t.tm_sec / 3600.0)

    def calculate_ephemeris(self, target_jd: float = None) -> Dict[str, Any]:
        """
        Вычисляет геоцентрический вектор позиций для заданного JD (или текущего момента).
        Возвращает словарь {planet: (lon, lat, dist)}.
        """
        if not self._ready:
            return {"status": "error", "message": "Oracle not initialized."}
        jd = target_jd if target_jd is not None else self._now_jd()
        try:
            positions = {}
            for name, body_id in SEPTENAR.items():
                pos, _ = swe.calc_ut(jd, body_id, swe.FLG_SWIEPH)
                positions[name] = {"lon": pos[0], "lat": pos[1], "dist": pos[2]}
            return {"status": "success", "jd": jd, "positions": positions}
        except Exception as e:
            return {"status": "error", "message": f"Calculation failure: {e}"}

    def get_viscosity_metrics(self) -> float:
        """
        Вычисляет дельта-вязкость среды через суммарное угловое движение септенара
        относительно «нулевой точки» (первый вызов устанавливает базис).
        Возвращает нормированное значение ∈ [0, 1].
        """
        result = self.calculate_ephemeris()
        if result["status"] != "success":
            return 0.2
        lons = np.array([v["lon"] for v in result["positions"].values()])
        # Суммарное расстояние между парами планет / максимально возможная дисперсия
        spread = float(np.std(lons))
        return float(np.clip(spread / 180.0, 0.0, 1.0))

    def execute_anticipatory_query(self, delta_hours: float = 2.0) -> float:
        """
        Предсказывает вязкость среды через delta_hours.
        Возвращает predicted_lambda_soc ∈ [0, 1].
        """
        jd_now = self._now_jd()
        jd_future = jd_now + delta_hours / 24.0
        result_now = self.calculate_ephemeris(jd_now)
        result_fut = self.calculate_ephemeris(jd_future)
        if result_now["status"] != "success" or result_fut["status"] != "success":
            return 0.5
        total_delta = 0.0
        for name in SEPTENAR:
            lon_now = result_now["positions"][name]["lon"]
            lon_fut = result_fut["positions"][name]["lon"]
            total_delta += abs(lon_fut - lon_now)
        return float(np.clip(total_delta / (len(SEPTENAR) * 2.0), 0.0, 1.0))


if __name__ == "__main__":
    oracle = GeocentricOracle()
    ephem = oracle.calculate_ephemeris()
    if ephem["status"] == "success":
        print(f"JD: {ephem['jd']:.2f}")
        for planet, coords in ephem["positions"].items():
            print(f"  {planet:10s}: lon={coords['lon']:.4f}°  lat={coords['lat']:.4f}°")
    v = oracle.get_viscosity_metrics()
    print(f"\nViscosity delta: {v:.4f}")
    lam = oracle.execute_anticipatory_query(delta_hours=2.0)
    print(f"Predicted lambda_SOC (+2h): {lam:.4f}")
