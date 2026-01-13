from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from app.services.session_state import set_line_hint, clear_last_candidates

# Import seguro (no revienta si faltan constantes)
from app.domain import playbook as pb


WELCOME_MESSAGE = getattr(pb, "WELCOME_MESSAGE", "Responde 1-5 para elegir una línea.")


# Si tienes estos textos en app.domain.playbook, se usan.
BROCHURE_1 = getattr(pb, "BROCHURE_AGUA_POTABLE", None)
BROCHURE_2 = getattr(pb, "BROCHURE_AGUA_RESIDUAL", None)
BROCHURE_3 = getattr(pb, "BROCHURE_BOMBEO", None)
BROCHURE_4 = getattr(pb, "BROCHURE_ANALISIS", None)
BROCHURE_5 = getattr(pb, "BROCHURE_PISCINAS", None)

# CTA corto (no cambia el brochure “literal”, solo lo complementa)
POST_BROCHURE_CTA = "\n\nDime qué producto necesitas (o envíame el SKU) y te muestro opciones con precio y stock."


@dataclass(frozen=True)
class PlaybookResult:
    reply: str


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


def _is_greeting(norm: str) -> bool:
    greetings = {
        "hola",
        "buenas",
        "buen dia",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "saludos",
        "que tal",
        "hey",
        "hi",
        "hello",
    }
    return norm in greetings


def _extract_menu_choice(norm: str) -> Optional[str]:
    # SOLO si el mensaje es exactamente una selección
    if re.fullmatch(r"[1-5]", norm):
        return norm
    if re.fullmatch(r"([1-5])\s*[\.\)\-]", norm):
        return norm[0]
    if re.fullmatch(r"(opcion|opción|op)\s*([1-5])", norm):
        return norm.split()[-1]
    # "3 bombeo" SOLO si arranca con número y el resto es una palabra de línea
    m = re.fullmatch(r"([1-5])\s+(agua potable|agua residual|bombeo|analisis|análisis|piscinas?)", norm)
    if m:
        return m.group(1)
    return None


def _exact_line_word(norm: str) -> Optional[str]:
    # SOLO exactos (evita “producto químico para piscina”)
    if norm in {"agua potable", "agua potable e industrial", "potable", "industrial"}:
        return "1"
    if norm in {"agua residual", "residual", "aguas residuales"}:
        return "2"
    if norm in {"bombeo"}:
        return "3"
    if norm in {"analisis", "análisis", "medicion", "medición", "control"}:
        return "4"
    if norm in {"piscinas", "piscina"}:
        return "5"
    return None


def infer_line_hint_from_text(text: str) -> Optional[str]:
    """
    Inferencia suave de línea a partir de palabras clave (sin responder).
    """
    norm = _normalize(text)
    if not norm:
        return None

    if "piscin" in norm:
        return "piscinas"
    if "bomba" in norm or "bombeo" in norm:
        return "bombeo"
    if "residual" in norm or "aguas residuales" in norm:
        return "agua residual"
    if "potable" in norm or "industrial" in norm:
        return "agua potable"
    if "analisis" in norm or "medicion" in norm or "laboratorio" in norm:
        return "analisis"
    return None


def clarify_question_for_text(text: str, *, line_hint: Optional[str]) -> Optional[str]:
    """
    Preguntas cortas para desambiguar solicitudes muy genericas.
    """
    norm = _normalize(text)
    if not norm:
        return None

    if line_hint is None and ("bomba" in norm or "bombeo" in norm):
        return (
            "Para ayudarte con la bomba, ¿es para piscina, agua potable o residual? "
            "Si tienes caudal/altura o HP, indícalo."
        )

    if line_hint is None and ("filtro" in norm or "filtracion" in norm or "filtración" in norm):
        if not any(k in norm for k in ("arena", "cartucho", "carb", "piscin")):
            return "¿Buscas filtro de arena o cartucho? ¿Para piscina o agua potable?"

    if "dosificacion" in norm or "dosificación" in norm or "dosificador" in norm:
        return "¿Qué químico deseas dosificar y a qué caudal?"

    if "accesor" in norm or "repuesto" in norm:
        if "piscin" in norm:
            return (
                "Para piscina, que tipo de accesorio buscas "
                "(iluminacion, limpieza, seguridad o repuestos)?"
            )
        return "Que tipo de accesorio buscas?"

    return None


def route_playbook(phone: str, text: str, is_weekend: bool) -> Optional[PlaybookResult]:
    """
    Router estricto:
      - saludo/menu => menú
      - selección explícita 1-5 o palabra exacta de línea => brochure
      - TODO lo demás => None (para que caiga a búsqueda en Woo)
    """
    norm = _normalize(text)
    if not norm:
        return PlaybookResult(reply=WELCOME_MESSAGE)

    if _is_greeting(norm) or norm in {"menu", "inicio", "empezar", "start"}:
        clear_last_candidates(phone)
        return PlaybookResult(reply=WELCOME_MESSAGE)

    choice = _extract_menu_choice(norm) or _exact_line_word(norm)
    if not choice:
        return None  # IMPORTANTÍSIMO: no interceptar “filtración”, “producto químico…”, etc.

    # Si el usuario elige línea, limpiamos candidatos previos
    clear_last_candidates(phone)

    if choice == "1":
        set_line_hint(phone, "agua potable")
        reply = (BROCHURE_1 or WELCOME_MESSAGE) + POST_BROCHURE_CTA
        return PlaybookResult(reply=reply)

    if choice == "2":
        set_line_hint(phone, "agua residual")
        reply = (BROCHURE_2 or WELCOME_MESSAGE) + POST_BROCHURE_CTA
        return PlaybookResult(reply=reply)

    if choice == "3":
        set_line_hint(phone, "bombeo")
        reply = (BROCHURE_3 or WELCOME_MESSAGE) + POST_BROCHURE_CTA
        return PlaybookResult(reply=reply)

    if choice == "4":
        set_line_hint(phone, "analisis")
        reply = (BROCHURE_4 or WELCOME_MESSAGE) + POST_BROCHURE_CTA
        return PlaybookResult(reply=reply)

    if choice == "5":
        set_line_hint(phone, "piscinas")
        reply = (BROCHURE_5 or WELCOME_MESSAGE) + POST_BROCHURE_CTA
        return PlaybookResult(reply=reply)

    return PlaybookResult(reply=WELCOME_MESSAGE)
