import swisseph as swe
import datetime

EPHE_PATH = "/home/angelan/data/Monada-Hardcore/ephe"

# Sun=0, Mars=4, Saturn=6 — индексы в swisseph
_BODIES = {0: "Sun", 4: "Mars", 6: "Saturn"}


class Stargazer:
    """
    Считывает эфемериды через swisseph и генерирует модулятор
    для динамической флуктуации весов Монады (T_sky в Core Tensor).
    """

    def __init__(self):
        try:
            swe.set_ephe_path(EPHE_PATH)
            self._ready = True
        except Exception as e:
            print(f"CRITICAL SWISSEPH INIT FAILURE: {e}. Falling back to static state.")
            self._ready = False

    def _jd(self, dt: datetime.datetime) -> float:
        return swe.julday(
            dt.year, dt.month, dt.day,
            dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        )

    def get_positions(self, dt: datetime.datetime) -> dict:
        """Возвращает словарь {name: lon_degrees} для ключевых тел."""
        jd = self._jd(dt)
        result = {}
        for body_id, name in _BODIES.items():
            try:
                flags = swe.FLG_SWIEPH
                pos, _ = swe.calc_ut(jd, body_id, flags)
                result[name] = pos[0]
            except Exception:
                result[name] = 0.0
        return result

    def calculate_modulation_factor(self, dt: datetime.datetime) -> float:
        """
        Возвращает фактор модуляции DELTA_PSI ∈ [1.0, 3.0].
        Чем шире угловое расстояние между Солнцем/Марсом/Сатурном — тем выше флуктуация.
        """
        if not self._ready:
            return 1.0
        try:
            pos = self.get_positions(dt)
            sun, mars, sat = pos["Sun"], pos["Mars"], pos["Saturn"]
            spread = abs(sun - mars) + abs(mars - sat) + abs(sun - sat)
            return 1.0 + (spread / 180.0) * 2.0
        except Exception as e:
            print(f"Stargazer calculation failed: {e}. Defaulting to 1.0.")
            return 1.0


if __name__ == "__main__":
    sg = Stargazer()
    now = datetime.datetime.utcnow()
    pos = sg.get_positions(now)
    factor = sg.calculate_modulation_factor(now)
    for name, lon in pos.items():
        print(f"{name:10s}: {lon:.4f}°")
    print(f"DELTA_PSI: {factor:.4f}")
