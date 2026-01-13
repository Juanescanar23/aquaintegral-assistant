from __future__ import annotations

from typing import Dict, List, Optional


QUESTION_BANK: Dict[str, List[Dict[str, str]]] = {
    "general": [
        {
            "key": "need",
            "question": "Para ayudarte, dime que producto necesitas y para que uso.",
        }
    ],
    "bombeo": [
        {
            "key": "application",
            "question": "La bomba es para piscina, pozo, agua potable o residual?",
        },
        {
            "key": "flow_rate",
            "question": "Que caudal necesitas (m3/h o L/min)?",
        },
        {
            "key": "head",
            "question": "Que altura o presion necesitas (mca)?",
        },
        {
            "key": "power_voltage",
            "question": "Que voltaje y fase tienes disponible (110/220V, mono/trifasica)?",
        },
    ],
    "piscinas": [
        {
            "key": "product_type",
            "question": "Buscas bomba, filtro, calentador o quimico para piscina?",
        },
        {
            "key": "pool_volume",
            "question": "Cual es el volumen de la piscina (m3) o sus medidas?",
        },
        {
            "key": "use_type",
            "question": "Es piscina residencial o comercial?",
        },
    ],
    "agua_potable": [
        {
            "key": "use_type",
            "question": "Es para hogar o industria?",
        },
        {
            "key": "source",
            "question": "El agua viene de acueducto o pozo?",
        },
        {
            "key": "problem",
            "question": "Que problema quieres resolver (olor, sabor, turbidez, dureza)?",
        },
    ],
    "agua_residual": [
        {
            "key": "process",
            "question": "Que tipo de tratamiento necesitas (biologico o fisico-quimico)?",
        },
        {
            "key": "flow_rate",
            "question": "Que caudal tratas (m3/h)?",
        },
        {
            "key": "contaminants",
            "question": "Cuales son los contaminantes principales?",
        },
    ],
    "analisis": [
        {
            "key": "parameter",
            "question": "Que parametro necesitas medir (pH, cloro, turbidez, DBO/DQO)?",
        },
        {
            "key": "use_type",
            "question": "Es para laboratorio, piscina o planta?",
        },
        {
            "key": "range",
            "question": "Tienes un rango de medicion requerido?",
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
