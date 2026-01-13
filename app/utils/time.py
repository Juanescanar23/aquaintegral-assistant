from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for older Python
    ZoneInfo = None


_TZ = ZoneInfo("America/Bogota") if ZoneInfo else timezone(timedelta(hours=-5))


def _local_now() -> datetime:
    return datetime.now(_TZ)


def time_greeting() -> str:
    """
    Saludo segun horario GMT-5 (America/Bogota).
    """
    hour = _local_now().hour
    if 5 <= hour < 12:
        return "Buenos días"
    if 12 <= hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


def is_weekend_now() -> bool:
    """
    Retorna True si hoy es sabado (5) o domingo (6) en hora local del servidor.
    """
    return _local_now().weekday() >= 5
