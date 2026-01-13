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
    "He recibido tu consulta, pero en este momento no puedo consultar el inventario. "
    "Un asesor te ayudará en breve."
)

SKU_PATTERN = re.compile(r"\b(\d{4,10})\b")


def _extract_sku_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    match = SKU_PATTERN.search(text)
    return match.group(1) if match else None


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

    # 1) Contacto + nota + deal (dejo tu comportamiento actual)
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
            link_part = f"\nLink: {link}" if link else ""
            return _with_greeting(
                phone,
                (
                    f"Perfecto. Elegiste: {name} (SKU {sku_value}).\n"
                    f"Precio: {price}.{link_part}\n"
                    "Confírmame ciudad y cantidad para cotizar."
                ),
            )

    if _is_more_options_request(text):
        next_items = get_next_search_results(phone, batch_size=3)
        if next_items:
            clear_last_candidates(phone)
            set_last_candidates(phone, next_items)
            return _with_greeting(phone, format_products_reply(next_items))
        return _with_greeting(
            phone,
            "No tengo mas opciones con esa descripcion. "
            "Puedes darme mas detalles o un SKU?",
        )

    # 3) Router playbook (menú/folletos) ANTES de búsqueda
    pb = route_playbook(phone=phone, text=text, is_weekend=is_weekend_now())
    if pb:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        return _with_greeting(phone, pb.reply)

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
        return _with_greeting(phone, info_reply)

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
            return _with_greeting(phone, info_response)

    # 5) SKU directo
    sku = _extract_sku_from_text(text)
    if sku:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        try:
            product = await woocommerce_client.get_product_by_sku(sku)
        except Exception:
            logger.exception("Error consultando WooCommerce para SKU", extra={"phone": phone, "sku": sku})
            return _with_greeting(phone, INVENTORY_ERROR_REPLY)

        if product is None:
            return _with_greeting(
                phone,
                (
                    f"No encontré ningún producto con el SKU {sku}. "
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
            f"Encontré el producto {name} (SKU {sku_value}). "
            f"{stock_part}{price_part} "
            "Si quieres, puedo pasarte con un asesor para avanzar con la cotización o el pedido."
        )
        return _with_greeting(phone, reply_text)

    # 6) Pregunta consultiva (OpenAI) si falta contexto
    asked = get_consult_questions(phone)
    choice = await select_consultant_question(text, line_hint=hint, asked_keys=asked)
    if choice:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        add_consult_question(phone, choice.key)
        return _with_greeting(phone, choice.question)

    # 7) Pregunta corta si la solicitud es muy ambigua (fallback)
    question = clarify_question_for_text(text, line_hint=hint)
    if question:
        clear_last_candidates(phone)
        clear_search_pool(phone)
        return _with_greeting(phone, question)

    # 8) Búsqueda inteligente por texto (siempre Woo + rerank)
    try:
        reply_text, selected, pool = await smart_product_search(text, line_hint=hint)
    except Exception:
        logger.exception("Fallo smart_product_search", extra={"phone": phone, "text": text})
        return _with_greeting(
            phone,
            "En este momento no puedo consultar el catálogo. ¿Me indicas el SKU o una foto del producto?",
        )

    if pool:
        set_search_pool(phone, text, pool, batch_size=3)
    else:
        clear_search_pool(phone)

    if selected:
        set_last_candidates(phone, selected)
    else:
        clear_last_candidates(phone)

    return _with_greeting(phone, reply_text)
