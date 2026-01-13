from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def format_cop(value: Optional[Any]) -> str:
    """
    Formatea un valor a COP con miles y 2 decimales (estilo ES).
    Ej: 1234567.8 -> $1.234.567,80 COP
    """
    if value is None:
        return "N/D"
    if isinstance(value, str) and not value.strip():
        return "N/D"
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return "N/D"

    dec = dec.quantize(Decimal("0.01"))
    raw = f"{dec:,.2f}"  # 1,234,567.89
    # Convertir a formato español: 1.234.567,89
    formatted = raw.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"${formatted} COP"
