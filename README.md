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
- `OPENAI_MODEL`: modelo por defecto de OpenAI (recomendado `gpt-5.2`).
- `OPENAI_INTENT_MODEL`: modelo para clasificación de intentos (opcional).
- `OPENAI_CONSULTANT_MODEL`: modelo para preguntas consultivas (opcional).
- `OPENAI_RERANK_MODEL`: modelo para rerank de productos (opcional).
- `OPENAI_KB_MODEL`: modelo para borradores de base de conocimiento (opcional).
- `DATABASE_URL`: URL de base de datos opcional.
- `HOST`: host para levantar la app (por defecto `0.0.0.0`).
- `PORT`: puerto para levantar la app (por defecto `8000`).
- `BOT_TEST_MODE`: activa modo pruebas (true/false).
- `BOT_TEST_NUMBERS`: lista de números permitidos separados por coma (solo dígitos, ej: `573001112233,573001112234`).
- `BOT_TEST_TAG`: prefijo para notas y deals cuando el bot está en modo pruebas (por defecto `[TEST]`).
- `KB_AUTO_DRAFT`: genera borradores con OpenAI cuando falta respuesta (true/false).
- `KB_AUTO_PUBLISH`: publica borradores automáticamente en la base (true/false).
- `KB_MIN_SCORE`: score mínimo para usar una respuesta de la base (default `2`).
- `KB_REQUIRE_VERIFIED`: exige `verified=true` para responder desde la base (true/false).
- `IDLE_FOLLOWUP_ENABLED`: activa mensajes automáticos por inactividad (true/false).
- `IDLE_FOLLOWUP_AFTER_MINUTES`: minutos de inactividad antes del primer seguimiento.
- `IDLE_FINAL_AFTER_MINUTES`: minutos de inactividad antes del mensaje de cierre.
- `IDLE_CHECK_INTERVAL_SECONDS`: intervalo de chequeo en segundos.
- `IDLE_MAX_FOLLOWUPS`: máximo de seguimientos por conversación.
- `IDLE_FOLLOWUP_MESSAGE`: mensaje de seguimiento por inactividad.
- `IDLE_FINAL_MESSAGE`: mensaje de cierre por inactividad.

## Base de conocimiento y aprendizaje controlado
El bot usa una base de conocimiento local para respuestas institucionales y puede generar borradores con OpenAI cuando no encuentra respuesta.

Archivos clave:
- `app/domain/knowledge_base.json`: base de conocimiento curada (versionada en git).
- `app/domain/knowledge_gaps.jsonl`: preguntas que faltaron respuesta (log, ignorado en git).
- `app/domain/knowledge_drafts.jsonl`: borradores generados por OpenAI (log, ignorado en git).

Flujo recomendado:
1) El bot intenta responder desde `knowledge_base.json`.
2) Si no encuentra respuesta suficiente, registra la pregunta en `knowledge_gaps.jsonl`.
3) Si `KB_AUTO_DRAFT=true`, genera un borrador en `knowledge_drafts.jsonl`.
4) Un humano revisa el borrador y lo promueve a `knowledge_base.json` con `verified=true`.

Ejemplo de entrada en `knowledge_base.json`:
```json
{
  "id": "company_overview",
  "question": "A que se dedica Aqua Integral?",
  "answer": "Aqua Integral SAS ofrece soluciones en agua potable e industrial, agua residual, bombeo, analisis de agua y piscinas.",
  "tags": ["empresa", "aqua integral", "servicios"],
  "source": "company_profile",
  "verified": true
}
```

Notas:
- El auto-aprendizaje es **controlado**: por defecto NO publica sin revisión.
- Si deseas auto-publicación total, define `KB_AUTO_PUBLISH=true` (no recomendado sin control).

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
