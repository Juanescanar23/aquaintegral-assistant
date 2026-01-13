from __future__ import annotations

from typing import Optional

from app.domain.catalog_links import CATALOG_URLS, GENERAL_CATALOG_URL
from app.domain.company_profile import (
    COMPANY_NAME,
    WEBSITE_URL,
    BUSINESS_LINES,
    LINE_OFFERS,
    SERVICES,
    normalize_line_key,
)


def _catalog_url_for_line(line_key: Optional[str]) -> str:
    if not line_key:
        return GENERAL_CATALOG_URL
    return CATALOG_URLS.get(line_key, GENERAL_CATALOG_URL)


def _format_lines_list(*, include_title: bool = True) -> str:
    lines = ["Lineas:"] if include_title else []
    for idx, label in enumerate(BUSINESS_LINES.values(), start=1):
        lines.append(f"{idx}) {label}")
    return "\n".join(lines)


def _format_offers(line_key: str) -> str:
    offers = LINE_OFFERS.get(line_key, [])
    if not offers:
        return ""
    lines = ["Ofrecemos:"]
    for item in offers:
        lines.append(f"- {item}")
    return "\n".join(lines)


def build_info_response(
    intent: str,
    *,
    user_text: str,
    line_hint: Optional[str],
) -> Optional[str]:
    line_key = normalize_line_key(line_hint) or normalize_line_key(user_text)

    if intent == "company_info":
        lines = [
            f"Con gusto. Somos {COMPANY_NAME}. Brindamos soluciones en agua potable, residual, bombeo, analisis y piscinas.",
            "",
            _format_lines_list(),
            "",
            "Servicios:",
        ]
        for item in SERVICES:
            lines.append(f"- {item}")
        lines.append("")
        lines.append(f"Catalogo: {WEBSITE_URL}")
        lines.append("Dime que necesitas y te ayudo.")
        return "\n".join(lines)

    if intent == "services":
        lines = ["Servicios que ofrecemos:"]
        for item in SERVICES:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Quieres asesorarte en alguna linea en particular?")
        lines.append(_format_lines_list())
        return "\n".join(lines)

    if intent == "line_info":
        if not line_key:
            return "\n".join(
                [
                    "Trabajamos en estas lineas:",
                    _format_lines_list(include_title=False),
                    "",
                    "Cual te interesa?",
                ]
            )
        label = BUSINESS_LINES.get(line_key, line_key)
        offers_block = _format_offers(line_key)
        lines = [f"Con gusto. Linea: {label}"]
        if offers_block:
            lines.append(offers_block)
        lines.append("")
        lines.append(f"Catalogo: {_catalog_url_for_line(line_key)}")
        lines.append("Dime que producto necesitas o envia el SKU.")
        return "\n".join(lines)

    if intent == "catalog":
        url = _catalog_url_for_line(line_key)
        return f"Aqui tienes el enlace del catalogo: {url}"

    return None
