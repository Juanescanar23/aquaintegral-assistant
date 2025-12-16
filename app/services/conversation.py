import logging
import re
from typing import Optional

from app.services.clientify import clientify_client
from app.services.woocommerce import woocommerce_client

logger = logging.getLogger(__name__)

DEFAULT_DEAL_NAME = "Interés vía WhatsApp (bot)"
DEFAULT_REPLY = (
    "Gracias por escribirnos. Hemos registrado tu mensaje y "
    "un asesor se pondrá en contacto contigo en breve."
)

INVENTORY_ERROR_REPLY = (
    "He recibido tu consulta, pero en este momento no puedo consultar el inventario. "
    "Un asesor te ayudará en breve."
)

# Detecta posibles SKUs numéricos de 4 a 10 dígitos dentro del texto.
SKU_PATTERN = re.compile(r"\b(\d{4,10})\b")


def _extract_sku_from_text(text: str) -> Optional[str]:
    """
    Extrae un SKU simple del texto del mensaje.

    Para este primer MVP asumimos que los SKUs de Aquaintegral son
    números (ej: '194300'). Si luego hay SKUs alfanuméricos,
    ajustamos este patrón.
    """
    if not text:
        return None

    match = SKU_PATTERN.search(text)
    if not match:
        return None

    return match.group(1)


async def process_incoming_message(phone: str, text: str) -> str:
    """
    Lógica central cuando llega un mensaje desde WhatsApp.

    1. Garantiza un contacto en Clientify (get_or_create_contact_by_phone).
    2. Añade una nota con el texto del mensaje.
    3. Crea una oportunidad simple asociada al contacto.
    4. Intenta detectar un SKU en el mensaje y consultar inventario en WooCommerce.
       - Si encuentra producto, responde con info de stock (y precio si está disponible).
       - Si no encuentra SKU o producto, responde mensaje estándar.
    5. Devuelve el texto que se debe responder por WhatsApp.

    Más adelante aquí colgaremos:
    - detección de intención más avanzada
    - búsqueda de productos por texto
    - llamadas a OpenAI, etc.
    """
    logger.info(
        "Procesando mensaje entrante de WhatsApp",
        extra={"phone": phone, "text": text},
    )

    # 1) Contacto en Clientify
    contact = await clientify_client.get_or_create_contact_by_phone(phone)
    contact_id = contact["id"]

    # 2) Nota con el mensaje original
    await clientify_client.add_note_to_contact(
        contact_id=contact_id,
        text=f"Mensaje WhatsApp: {text}",
    )

    # 3) Oportunidad básica
    await clientify_client.create_deal(
        contact_id=contact_id,
        name=DEFAULT_DEAL_NAME,
    )

    # 4) Intentar detectar SKU y consultar inventario
    sku = _extract_sku_from_text(text)

    if not sku:
        # Mensaje genérico sin SKU detectado, respondemos estándar.
        logger.info(
            "No se detectó SKU en el mensaje, usando respuesta por defecto",
            extra={"phone": phone},
        )
        return DEFAULT_REPLY

    logger.info(
        "SKU detectado en mensaje",
        extra={"phone": phone, "sku": sku},
    )

    try:
        # Usamos el cliente de WooCommerce para obtener el producto completo.
        product = await woocommerce_client.get_product_by_sku(sku)
    except Exception:
        # Cualquier fallo con WooCommerce no debe tumbar el webhook.
        logger.exception(
            "Error consultando WooCommerce para SKU",
            extra={"phone": phone, "sku": sku},
        )
        return INVENTORY_ERROR_REPLY

    if product is None:
        # SKU detectado pero Woo no devuelve producto.
        logger.info(
            "No se encontró producto para SKU en WooCommerce",
            extra={"phone": phone, "sku": sku},
        )
        return (
            f"No encontré ningún producto con el SKU {sku}. "
            "¿Puedes verificar el código o describirme el producto que necesitas?"
        )

    # Construir respuesta con info del producto.
    name = product.get("name") or "producto"
    sku_value = product.get("sku") or sku
    manage_stock = product.get("manage_stock")
    stock_qty = product.get("stock_quantity")
    stock_status = product.get("stock_status")
    price = product.get("price") or product.get("regular_price")

    # Texto de stock.
    if manage_stock and stock_qty is not None:
        stock_part = f"Actualmente tenemos {stock_qty} unidades en stock."
    else:
        status_map = {
            "instock": "Actualmente aparece como disponible.",
            "outofstock": "Actualmente aparece como agotado.",
            "onbackorder": "Actualmente aparece como en pedido pendiente.",
        }
        stock_part = status_map.get(
            stock_status or "",
            "Actualmente no puedo confirmar el stock exacto.",
        )

    # Texto de precio.
    if price:
        price_part = f" El precio actual es ${price} COP."
    else:
        price_part = ""

    reply_text = (
        f"Encontré el producto {name} (SKU {sku_value}). "
        f"{stock_part}{price_part} "
        "Si quieres, puedo pasarte con un asesor para avanzar con la cotización o el pedido."
    )

    return reply_text
