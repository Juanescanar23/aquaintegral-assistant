# Aquaintegral Conversational Assistant

API en FastAPI que recibe webhooks de WhatsApp (Meta o Twilio), registra el interés en Clientify y responde al usuario. Además, integra WooCommerce para consultar inventario por SKU (MVP con SKUs numéricos). Incluye rutas de salud y manejadores de íconos para evitar 404 ruidosos.

## Endpoints principales
- `GET /` responde metadatos de la API.
- `GET /health` indica estado y entorno cargado.
- `POST /webhook/whatsapp` recibe payloads de Meta/WhatsApp, localiza o crea el contacto en Clientify, crea un negocio y agrega una nota con el mensaje recibido. Si detecta un SKU, consulta WooCommerce y responde con stock/precio cuando aplique. Luego envía la respuesta al usuario usando WhatsApp Cloud API.
- `POST /webhook/twilio` recibe mensajes entrantes de Twilio (x-www-form-urlencoded), ejecuta la misma lógica de conversación y responde por WhatsApp usando Twilio en background para evitar timeouts.
- `GET /woocommerce/inventory/sku/{sku}` endpoint de prueba para consultar inventario por SKU directamente (útil para validar conectividad con WooCommerce).

## Variables de entorno (`.env`)
- `ENV`: nombre del entorno (ej. `development`).
- `CLIENTIFY_BASE_URL`: base de la API de Clientify (recomendado `https://api.clientify.net/v1`, sin `/` final).
- `CLIENTIFY_API_KEY`: token de API para Clientify.
- `WHATSAPP_BASE_URL`: base de WhatsApp Cloud API (por defecto `https://graph.facebook.com/v19.0`).
- `WHATSAPP_TOKEN`: token Bearer de WhatsApp Cloud.
- `WHATSAPP_PHONE_NUMBER_ID`: ID del número de teléfono en WhatsApp Cloud.
- `WHATSAPP_VERIFY_TOKEN`: token de verificación del webhook configurado en Meta.
- `TWILIO_ACCOUNT_SID`: Account SID de Twilio.
- `TWILIO_AUTH_TOKEN`: Auth Token de Twilio.
- `TWILIO_WHATSAPP_FROM`: número de WhatsApp de Twilio (ej: `whatsapp:+14155238886`).
- `WOOCOMMERCE_BASE_URL`: URL base de WordPress/WooCommerce (sin `/wp-json`). Ej: `https://aquaintegral.co`
- `WOOCOMMERCE_CONSUMER_KEY`: Consumer Key de WooCommerce REST API (ej: `ck_...`).
- `WOOCOMMERCE_CONSUMER_SECRET`: Consumer Secret de WooCommerce REST API (ej: `cs_...`).
- `OPENAI_API_KEY`: API key opcional de OpenAI.
- `DATABASE_URL`: URL de base de datos opcional.
- `HOST`: host para levantar la app (por defecto `0.0.0.0`).
- `PORT`: puerto para levantar la app (por defecto `8000`).
- `BOT_TEST_MODE`: activa modo pruebas (true/false).
- `BOT_TEST_NUMBERS`: lista de números permitidos separados por coma (solo dígitos, ej: `573001112233,573001112234`).
- `BOT_TEST_TAG`: prefijo para notas y deals cuando el bot está en modo pruebas (por defecto `[TEST]`).

## Instalación y ejecución local
1) Crear y activar entorno virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
```
2) Instalar dependencias
```bash
pip install -r requirements.txt
```
3) Configurar `.env` (puedes partir de `.env.example`) y levantar la API
```bash
python -m uvicorn app.main:app --reload --port 8000
# o (equivalente, por el wrapper main.py en la raíz)
uvicorn main:app --reload --port 8000
```

## Flujo del webhook de WhatsApp
- Se extrae el número de teléfono del payload (`wa_id` o `from`) y el texto del mensaje.
- `process_incoming_message` consulta/crea el contacto en Clientify, agrega una nota con el mensaje y genera un negocio con el nombre “Interés vía WhatsApp (bot)”.
- Si el texto contiene un SKU numérico (4 a 10 dígitos), consulta WooCommerce por SKU y construye una respuesta con nombre, stock (cantidad o estado) y precio cuando esté disponible.
- Se envía la respuesta al usuario con `send_message`, que llama a WhatsApp Cloud API con el `WHATSAPP_TOKEN` configurado.

## Flujo del webhook de Twilio
- Twilio envía `From` y `Body` en formato `x-www-form-urlencoded`.
- Se normaliza el número y se reutiliza la misma lógica de conversación.
- La respuesta se envía usando Twilio en background para responder rápido al webhook.

## Pruebas rápidas
1) Probar inventario directo (antes de meterlo al bot)
```bash
curl "http://127.0.0.1:8000/woocommerce/inventory/sku/TU_SKU"
```

2) Simular webhook de WhatsApp (ojo: intentará enviar WhatsApp real si `WHATSAPP_*` está configurado)
```bash
curl -X POST "http://127.0.0.1:8000/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "contacts": [{"wa_id": "573001112233"}],
          "messages": [{
            "from": "573001112233",
            "text": {"body": "Hola, ¿tienen disponible el 194300?"}
          }]
        }
      }]
    }]
  }'
```

## Observaciones
- Las rutas de íconos (`/favicon.ico`, `/apple-touch-icon*.png`) devuelven un PNG transparente para evitar 404.
- Configuración centralizada en `app/core/settings.py` usando `get_settings()`.
- `.env` y `.venv` están ignorados en git; mantén credenciales fuera del repositorio.

## Autoría
Creado por **JectCode**.
