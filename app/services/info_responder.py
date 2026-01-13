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
    lines = ["Líneas:"] if include_title else []
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
            f"Con gusto. En {COMPANY_NAME} ayudamos con soluciones en agua potable, residual, bombeo, análisis y piscinas.",
            "",
            _format_lines_list(),
            "",
            "Servicios:",
        ]
        for item in SERVICES:
            lines.append(f"- {item}")
        lines.append("")
        lines.append(f"Catálogo: {WEBSITE_URL}")
        lines.append("Cuéntame qué necesitas y te guío.")
        return "\n".join(lines)

    if intent == "services":
        lines = ["Servicios que ofrecemos:"]
        for item in SERVICES:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("¿Quieres asesorarte en alguna línea en particular?")
        lines.append(_format_lines_list())
        return "\n".join(lines)

    if intent == "line_info":
        if not line_key:
            return "\n".join(
                [
                    "Trabajamos en estas líneas:",
                    _format_lines_list(include_title=False),
                    "",
                    "¿Cuál te interesa?",
                ]
            )
        label = BUSINESS_LINES.get(line_key, line_key)
        offers_block = _format_offers(line_key)
        lines = [f"Con gusto. Línea: {label}"]
        if offers_block:
            lines.append(offers_block)
        lines.append("")
        lines.append(f"Catálogo: {_catalog_url_for_line(line_key)}")
        lines.append("Dime qué producto necesitas o envíame el SKU.")
        return "\n".join(lines)

    if intent == "catalog":
        url = _catalog_url_for_line(line_key)
        return f"Aquí tienes el enlace del catálogo: {url}"

    return None
