import logging

from app.services.clientify import clientify_client

logger = logging.getLogger(__name__)

DEFAULT_DEAL_NAME = "Interés vía WhatsApp (bot)"
DEFAULT_REPLY = (
    "Gracias por escribirnos. Hemos registrado tu mensaje y "
    "un asesor se pondrá en contacto contigo en breve."
)


async def process_incoming_message(phone: str, text: str) -> str:
    """
    Lógica central cuando llega un mensaje desde WhatsApp.

    1. Garantiza un contacto en Clientify (get_or_create_contact_by_phone).
    2. Añade una nota con el texto del mensaje.
    3. Crea una oportunidad simple asociada al contacto.
    4. Devuelve el texto que se debe responder por WhatsApp.

    Más adelante aquí colgaremos:
    - detección de intención
    - búsqueda de productos en WooCommerce
    - llamadas a OpenAI, etc.
    """
    logger.info(
        "Procesando mensaje entrante de WhatsApp",
        extra={"phone": phone, "text": text},
    )

    # 1) Contacto en Clientify
    contact = await clientify_client.get_or_create_contact_by_phone(phone)
    contact_id = contact["id"]

    # 2) Nota con el mensaje
    await clientify_client.add_note_to_contact(
        contact_id=contact_id,
        text=f"Mensaje WhatsApp: {text}",
    )

    # 3) Oportunidad básica
    await clientify_client.create_deal(
        contact_id=contact_id,
        name=DEFAULT_DEAL_NAME,
    )

    # 4) Respuesta estándar al usuario
    return DEFAULT_REPLY
