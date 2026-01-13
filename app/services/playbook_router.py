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
    t = re.sub(r"\s+", " ", t)
    return t


def _is_greeting(norm: str) -> bool:
    return bool(re.fullmatch(r"(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|hi|hello)", norm))


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
