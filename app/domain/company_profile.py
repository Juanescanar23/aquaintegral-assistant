from __future__ import annotations

import re
import unicodedata
from typing import Optional


COMPANY_NAME = "Aqua Integral SAS"
WEBSITE_URL = "https://aquaintegral.co/"

BUSINESS_LINES = {
    "agua potable": "Agua Potable e Industrial",
    "agua residual": "Agua Residual",
    "bombeo": "Bombeo",
    "analisis": "Analisis de agua / Medicion y Control",
    "piscinas": "Piscinas",
}

LINE_OFFERS = {
    "agua potable": [
        "Filtracion y microfiltracion",
        "Osmosis inversa",
        "UV y ozono",
        "Dosificacion",
        "Plantas de tratamiento",
    ],
    "agua residual": [
        "Equipos para tratamiento",
        "Plantas de tratamiento",
        "Quimicos para procesos",
        "Equipos de aireacion",
    ],
    "bombeo": [
        "Bombas centrifugas y multietapas",
        "Bombas sumergibles",
        "Bombas perifericas",
        "Presurizacion",
        "Accesorios de instalacion",
    ],
    "analisis": [
        "Equipos de medicion",
        "Fotometros y comparadores",
        "Reactivos y laboratorio",
    ],
    "piscinas": [
        "Filtros y bombas",
        "Calefaccion",
        "Desinfeccion",
        "Quimicos y accesorios",
    ],
}

SERVICES = [
    "Asesoria tecnica",
    "Suministro de equipos",
    "Instalacion (segun producto)",
]

LINE_ALIASES = {
    "agua potable e industrial": "agua potable",
    "agua potable": "agua potable",
    "potable": "agua potable",
    "industrial": "agua potable",
    "agua residual": "agua residual",
    "aguas residuales": "agua residual",
    "residual": "agua residual",
    "bombeo": "bombeo",
    "bombas": "bombeo",
    "analisis": "analisis",
    "analisis de agua": "analisis",
    "medicion": "analisis",
    "medicion y control": "analisis",
    "control": "analisis",
    "piscinas": "piscinas",
    "piscina": "piscinas",
}


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = "".join(
        ch for ch in unicodedata.normalize("NFD", t)
        if unicodedata.category(ch) != "Mn"
    )
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def normalize_line_key(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    norm = _normalize(text)
    if not norm:
        return None
    for alias, canonical in LINE_ALIASES.items():
        if alias in norm:
            return canonical
    return None
