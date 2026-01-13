from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional


def format_cop(value: Optional[Any]) -> str:
    """
    Formatea un valor a COP con miles y sin decimales (estilo ES).
    Ej: 1234567.8 -> $1.234.568 COP
    """
    if value is None:
        return "N/D"
    if isinstance(value, str) and not value.strip():
        return "N/D"
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return "N/D"

    dec = dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    raw = f"{dec:,.0f}"  # 1,234,568
    # Convertir a formato español: 1.234.568
    formatted = raw.replace(",", ".")
    return f"${formatted} COP"
