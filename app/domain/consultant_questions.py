from __future__ import annotations

from typing import Dict, List, Optional


QUESTION_BANK: Dict[str, List[Dict[str, str]]] = {
    "general": [
        {
            "key": "need",
            "question": "Para ayudarte mejor, ¿qué producto necesitas y para qué uso?",
        }
    ],
    "bombeo": [
        {
            "key": "application",
            "question": "¿La bomba es para piscina, pozo, agua potable o residual?",
        },
        {
            "key": "flow_rate",
            "question": "¿Qué caudal necesitas (m3/h o L/min)?",
        },
        {
            "key": "head",
            "question": "¿Qué altura o presión necesitas (mca)?",
        },
        {
            "key": "power_voltage",
            "question": "¿Qué voltaje y fase tienes disponible (110/220V, mono/trifásica)?",
        },
    ],
    "piscinas": [
        {
            "key": "product_type",
            "question": "¿Buscas bomba, filtro, calentador, accesorio o químico para piscina?",
        },
        {
            "key": "pool_volume",
            "question": "¿Cuál es el volumen de la piscina (m3) o sus medidas?",
        },
        {
            "key": "use_type",
            "question": "¿Es piscina residencial o comercial?",
        },
    ],
    "agua_potable": [
        {
            "key": "use_type",
            "question": "¿Es para hogar o industria?",
        },
        {
            "key": "source",
            "question": "¿El agua viene de acueducto o pozo?",
        },
        {
            "key": "problem",
            "question": "¿Qué problema quieres resolver (olor, sabor, turbidez, dureza)?",
        },
    ],
    "agua_residual": [
        {
            "key": "process",
            "question": "¿Qué tipo de tratamiento necesitas (biológico o físico-químico)?",
        },
        {
            "key": "flow_rate",
            "question": "¿Qué caudal tratas (m3/h)?",
        },
        {
            "key": "contaminants",
            "question": "¿Cuáles son los contaminantes principales?",
        },
    ],
    "analisis": [
        {
            "key": "parameter",
            "question": "¿Qué parámetro necesitas medir (pH, cloro, turbidez, DBO/DQO)?",
        },
        {
            "key": "use_type",
            "question": "¿Es para laboratorio, piscina o planta?",
        },
        {
            "key": "range",
            "question": "¿Tienes un rango de medición requerido?",
        },
    ],
}


LINE_HINT_MAP = {
    "agua potable": "agua_potable",
    "agua potable e industrial": "agua_potable",
    "agua residual": "agua_residual",
    "bombeo": "bombeo",
    "analisis": "analisis",
    "análisis": "analisis",
    "piscinas": "piscinas",
}


def normalize_line_hint(hint: Optional[str]) -> str:
    if not hint:
        return "general"
    key = str(hint).strip().lower()
    return LINE_HINT_MAP.get(key, "general")


def questions_for_line(line_key: str) -> List[Dict[str, str]]:
    return QUESTION_BANK.get(line_key, QUESTION_BANK["general"])
