from datetime import datetime


def is_weekend_now() -> bool:
    """
    Retorna True si hoy es sabado (5) o domingo (6) en hora local del servidor.
    """
    return datetime.now().weekday() >= 5
