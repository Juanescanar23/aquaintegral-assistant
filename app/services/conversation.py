import asyncio
import logging
import re
import unicodedata
from typing import Optional

from app.services.clientify import clientify_client
from app.services.playbook_router import (
    route_playbook,
    infer_line_hint_from_text,
    clarify_question_for_text,
)
from app.services.product_search import smart_product_search, format_products_reply
from app.services.woocommerce import woocommerce_client
from app.services.session_state import (
    get_line_hint,
    set_line_hint,
    set_last_candidates,
    clear_last_candidates,
    get_candidate_by_choice,
    should_greet,
    mark_greeted,
    set_customer_name,
    get_consult_questions,
    add_consult_question,
    get_next_search_results,
    set_search_pool,
    clear_search_pool,
)
from app.services.openai_consultant import select_consultant_question
from app.services.intent_router import route_info_request
from app.services.openai_intent import classify_info_intent
from app.services.info_responder import build_info_response
from app.utils.time import is_weekend_now, time_greeting
from app.utils.formatting import format_cop
from app.utils.test_mode import prefix_with_test_tag

logger = logging.getLogger(__name__)

DEFAULT_DEAL_NAME = "Interés vía WhatsApp (bot)"

INVENTORY_ERROR_REPLY = (
    "En este momento no puedo consultar el inventario. "
    "Si me compartes el SKU y la cantidad, lo reviso y te confirmo."
)

SKU_PATTERN = re.compile(r"\b(\d{4,10})\b")
NAME_CONNECTORS = {"de", "del", "la", "las", "los", "y"}
NAME_PATTERNS = [
    re.compile(r"(?:mi nombre es|me llamo)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]{2,40})", re.IGNORECASE),
    re.compile(r"\bsoy\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-\s]{2,40})", re.IGNORECASE),
]


def _extract_sku_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    match = SKU_PATTERN.search(text)
    return match.group(1) if match else None


async def _sync_clientify(phone: str, text: str) -> None:
    """
    Sincroniza el mensaje con Clientify sin bloquear la respuesta al usuario.
    """
    contact_id = None

    try:
        contact = await clientify_client.get_or_create_contact_by_phone(phone)
        contact_id = contact.get("id")
    except Exception:
        logger.exception("Clientify: fallo get_or_create_contact_by_phone", extra={"phone": phone})

    if contact_id:
        try:
            await clientify_client.add_note_to_contact(
                contact_id=contact_id,
                text=prefix_with_test_tag(f"Mensaje WhatsApp: {text}"),
            )
        except Exception:
            logger.exception(
                "Clientify: fallo add_note_to_contact",
                extra={"phone": phone, "contact_id": contact_id},
            )

        try:
            await clientify_client.create_deal(
                contact_id=contact_id,
                name=prefix_with_test_tag(DEFAULT_DEAL_NAME),
            )
        except Exception:
            logger.exception(
                "Clientify: fallo create_deal",
                extra={"phone": phone, "contact_id": contact_id},
            )


def _with_greeting(phone: str, text: str) -> str:
    if not text:
        return text
    if not should_greet(phone):
        return text
    greeting = time_greeting()
    mark_greeted(phone)
    return f"{greeting}. {text}"


def _normalize_intent(text: str) -> str:
    t = (text or "").strip().lower()
    t = "".join(
        ch
        for ch in unicodedata.normalize("NFD", t)
        if unicodedata.category(ch) != "Mn"
    )
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _is_only_greeting(text: str) -> bool:
    norm = _normalize_intent(text)
    if not norm:
        return True
    greetings = {
        "hola",
        "buenas",
        "buen dia",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "saludos",
        "que tal",
    }
    return norm in greetings


def _title_case_name(raw: str) -> str:
    parts = [p for p in re.split(r"\s+", raw.strip()) if p]
    if not parts:
        return raw.strip()
    out = []
    for p in parts:
        lower = p.lower()
        if lower in NAME_CONNECTORS:
            out.append(lower)
        else:
            out.append(p[:1].upper() + p[1:].lower())
    return " ".join(out)


def _extract_name_and_remainder(text: str) -> tuple[Optional[str], str]:
    if not text:
        return None, ""
    for pattern in NAME_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw_name = match.group(1) or ""
        raw_name = re.sub(r"[\s,;:\-\.]+$", "", raw_name).strip()
        if not raw_name:
            continue
        if re.search(r"\d", raw_name):
            continue
        parts = [p for p in re.split(r"\s+", raw_name) if p]
        if len(parts) > 4:
            continue
        if parts[0].lower() in {"de", "del", "desde"}:
            continue
        if all(p.lower() in NAME_CONNECTORS for p in parts):
            continue
        name = _title_case_name(raw_name)
        remainder = (text[: match.start()] + text[match.end() :]).strip()
        remainder = re.sub(r"^[\s,;:\-\.]+", "", remainder)
        remainder = re.sub(r"[\s,;:\-\.]+$", "", remainder)
        return name, remainder
    return None, ""


def _is_more_options_request(text: str) -> bool:
    norm = _normalize_intent(text)
    if not norm:
        return False
    triggers = [
        "mas opciones",
        "mas productos",
        "tienes mas opciones",
        "tienes mas productos",
        "hay mas opciones",
        "hay mas productos",
        "ver mas",
        "mas resultados",
    ]
    return any(t in norm for t in triggers)


async def process_incoming_message(phone: str, text: str) -> str:
    logger.info("Procesando mensaje entrante de WhatsApp", extra={"phone": phone, "text": text})

    # 1) Clientify en segundo plano para no bloquear la respuesta
    asyncio.create_task(_sync_clientify(phone, text))

    name_prefix: Optional[str] = None
    detected_name, name_remainder = _extract_name_and_remainder(text)
    if detected_name:
        set_customer_name(phone, detected_name)
        mark_greeted(phone)
        name_prefix = (
            f"Hola {detected_name}, bienvenido a Aqua Integral SAS. "
            "Soy tu asesor online."
        )
        if not name_remainder or _is_only_greeting(name_remainder):
            return f"{name_prefix} ¿En qué puedo ayudarte hoy?"
        text = name_remainder

    def _respond(body: str) -> str:
        if name_prefix:
            return f"{name_prefix}\n\n{body}"
        return _with_greeting(phone, body)

    # 2) Si el usuario responde 1/2/3 y hay candidatos pendientes, interpretar como selección
    choice_match = re.fullmatch(r"\s*([1-3])\s*[\.\)\-]?\s*", text or "")
    if choice_match:
        cand = get_candidate_by_choice(phone, int(choice_match.group(1)))
        if cand:
            clear_last_candidates(phone)
            clear_search_pool(phone)
            name = cand.get("name") or "producto"
            sku_value = cand.get("sku") or "N/D"
            price = format_cop(cand.get("price"))
            link = cand.get("permalink") or ""
            link_part = f"\nEnlace: {link}" if link else ""
            return _respond(
                (
                    f"Perfecto, gracias. Seleccionaste: {name} (SKU {sku_value}).\n"
                    f"Precio: {price}.{link_part}\n"
                    "Para cotizar, dime ciudad y cantidad."
                ),
            )

    if _is_more_options_request(text):
        next_items = get_next_search_results(phone, batch_size=3)
        if next_items:
            clear_last_candidates(phone)
            set_last_candidates(phone, next_items)
            return _respond(
                format_products_reply(
                    next_items,
                    intro="Con gusto. Aquí tienes más opciones del catálogo de Aqua:",
                    show_more_hint=False,
                ),
            )
        return _respond(
            "Por ahora no veo más opciones con esa descripción en el catálogo. "
            "Si me das más detalles o el SKU, afino la búsqueda.",
        )

    # 3) Router playbook (menú/folletos) ANTES de búsqueda
    pb = route_playbook(phone=phone, text=text, is_weekend=is_weekend_now())
    if pb:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        return _respond(pb.reply)

    hint = get_line_hint(phone)
    if not hint:
        inferred = infer_line_hint_from_text(text)
        if inferred:
            set_line_hint(phone, inferred)
            hint = inferred

    info_reply = route_info_request(text, line_hint=hint)
    if info_reply:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        return _respond(info_reply)

    # 4) OpenAI intent (info/servicios/lineas/catalogo) si aplica
    intent_result = await classify_info_intent(text, line_hint=hint)
    if intent_result:
        if intent_result.line_key and not hint:
            set_line_hint(phone, intent_result.line_key)
            hint = intent_result.line_key
        info_response = build_info_response(
            intent_result.intent,
            user_text=text,
            line_hint=hint,
        )
        if info_response:
            clear_last_candidates(phone)
            clear_search_pool(phone)
            return _respond(info_response)

    # 5) SKU directo
    sku = _extract_sku_from_text(text)
    if sku:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        try:
            product = await woocommerce_client.get_product_by_sku(sku)
        except Exception:
            logger.exception("Error consultando WooCommerce para SKU", extra={"phone": phone, "sku": sku})
            return _respond(INVENTORY_ERROR_REPLY)

        if product is None:
            return _respond(
                (
                    f"No veo ese SKU en el catálogo ({sku}). "
                    "¿Puedes verificar el código o describirme el producto que necesitas?"
                ),
            )

        name = product.get("name") or "producto"
        sku_value = product.get("sku") or sku
        manage_stock = product.get("manage_stock")
        stock_qty = product.get("stock_quantity")
        stock_status = product.get("stock_status")
        price = product.get("price") or product.get("regular_price")

        if manage_stock and stock_qty is not None:
            stock_part = f"Actualmente tenemos {stock_qty} unidades en stock."
        else:
            status_map = {
                "instock": "Actualmente aparece como disponible.",
                "outofstock": "Actualmente aparece como agotado.",
                "onbackorder": "Actualmente aparece como en pedido pendiente.",
            }
            stock_part = status_map.get(stock_status or "", "Actualmente no puedo confirmar el stock exacto.")

        price_part = f" El precio actual es {format_cop(price)}." if price else ""
        reply_text = (
            f"Esto es lo que tengo en el catálogo para {name} (SKU {sku_value}). "
            f"{stock_part}{price_part} "
            "¿Quieres que te cotice? Si es así, dime cantidad y ciudad."
        )
        return _respond(reply_text)

    # 6) Pregunta consultiva (OpenAI) si falta contexto
    asked = get_consult_questions(phone)
    choice = await select_consultant_question(text, line_hint=hint, asked_keys=asked)
    if choice:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        add_consult_question(phone, choice.key)
        return _respond(choice.question)

    # 7) Pregunta corta si la solicitud es muy ambigua (fallback)
    question = clarify_question_for_text(text, line_hint=hint)
    if question:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        return _respond(question)

    # 8) Búsqueda inteligente por texto (siempre Woo + rerank)
    try:
        reply_text, selected, pool = await smart_product_search(text, line_hint=hint)
    except Exception:
        logger.exception("Fallo smart_product_search", extra={"phone": phone, "text": text})
        return _respond(
            "En este momento no puedo consultar el catálogo. ¿Me compartes el SKU o una foto del producto?",
        )

    if pool:
        set_search_pool(phone, text, pool, batch_size=3)
    else:
        clear_search_pool(phone)

    if selected:
        set_last_candidates(phone, selected)
    else:
        clear_last_candidates(phone)

    return _respond(reply_text)
