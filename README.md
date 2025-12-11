# Aquaintegral Conversational Assistant

API en FastAPI que recibe webhooks de WhatsApp, registra el interés en Clientify y responde al usuario. Incluye rutas de salud y manejadores de íconos para evitar 404 ruidosos.

## Endpoints principales
- `GET /` responde metadatos de la API.
- `GET /health` indica estado y entorno cargado.
- `POST /webhook/whatsapp` recibe payloads de Meta/WhatsApp, localiza o crea el contacto en Clientify, crea un negocio y agrega una nota con el mensaje recibido. Luego envía una respuesta de cortesía (envío simulado).

## Variables de entorno (`.env`)
- `ENV`: nombre del entorno (ej. `development`).
- `CLIENTIFY_BASE_URL`: base de la API de Clientify (por defecto `https://api.clientify.com/v1`).
- `CLIENTIFY_API_KEY`: token de API para Clientify.
- `WHATSAPP_BASE_URL`: base de WhatsApp Cloud API (por defecto `https://graph.facebook.com/v19.0`).
- `WHATSAPP_PHONE_NUMBER_ID`: ID del número de teléfono en WhatsApp Cloud.
- `WHATSAPP_TOKEN`: token Bearer de WhatsApp Cloud.

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
uvicorn main:app --reload
```

## Flujo del webhook de WhatsApp
- Se extrae el número de teléfono del payload (`wa_id` o `from`) y el texto del mensaje.
- Se consulta/crea el contacto en Clientify, se agrega una nota con el mensaje y se genera un negocio con el nombre “Interés vía WhatsApp (bot)”.
- Se envía una respuesta al usuario con `send_message`; actualmente es un stub que solo imprime en consola. Sustituye esa función por la integración real del proveedor de WhatsApp que utilices.

## Observaciones
- Las rutas de íconos (`/favicon.ico`, `/apple-touch-icon*.png`) devuelven un PNG transparente para evitar 404.
- Configuración centralizada en `app/core/settings.py` usando `get_settings()`.
- `.env` y `.venv` están ignorados en git; mantén credenciales fuera del repositorio.

## Autoría
Creado por **JectCode**.
