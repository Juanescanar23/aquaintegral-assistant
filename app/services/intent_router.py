from __future__ import annotations

import re
import unicodedata
from typing import Optional

from app.domain import playbook as pb
from app.domain.catalog_links import CATALOG_URLS, GENERAL_CATALOG_URL


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = "".join(
        ch
        for ch in unicodedata.normalize("NFD", t)
        if unicodedata.category(ch) != "Mn"
    )
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _has_any(norm: str, tokens: list[str]) -> bool:
    return any(tok in norm for tok in tokens)


def _is_placeholder(text: str) -> bool:
    return "MISSING_TEMPLATE" in (text or "")


def _catalog_url_for_line(line_hint: Optional[str], text_norm: str) -> str:
    if line_hint:
        norm = _normalize(line_hint)
        for key, url in CATALOG_URLS.items():
            if key in norm:
                return url
    for key, url in CATALOG_URLS.items():
        if key in text_norm:
            return url
    return GENERAL_CATALOG_URL


def route_info_request(text: str, *, line_hint: Optional[str]) -> Optional[str]:
    """
    Respuestas directas a preguntas comunes (link, horario, ubicacion, pagos).
    Si no aplica, retorna None.
    """
    norm = _normalize(text)
    if not norm:
        return None

    if _has_any(norm, ["link", "enlace", "pagina", "web", "sitio", "tienda", "catalogo", "portafolio"]):
        url = _catalog_url_for_line(line_hint, norm)
        return f"Aquí tienes el enlace del catálogo: {url}"

    if _has_any(norm, ["horario", "hora", "horas", "atencion", "atienden", "abren", "cierran"]):
        msg = pb.FAQ_HORARIO_ATENCION
        if _is_placeholder(msg):
            msg = getattr(pb, "HUMAN_HOURS_MESSAGE", "") or getattr(pb, "HUMAN_HOURS", "")
        return msg or "Nuestro horario es de lunes a viernes en horario laboral."

    if _has_any(norm, ["ubicacion", "direccion", "donde", "ubicados", "envios", "envio"]):
        msg = pb.FAQ_UBICACION_ENVIOS
        if _is_placeholder(msg):
            msg = "Estamos en Bogota y hacemos envios a nivel nacional."
        return msg

    if _has_any(norm, ["pago", "pagos", "tarjeta", "credito", "debito", "addi"]):
        msg = pb.FAQ_PAGOS_TARJETA_ADDI
        if _is_placeholder(msg):
            msg = "Aceptamos tarjeta y Addi. Si necesitas una opcion especifica, dime cual."
        return msg

    return None
