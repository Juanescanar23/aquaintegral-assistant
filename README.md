# Aquaintegral Conversational Assistant

API en FastAPI que recibe webhooks de WhatsApp, registra el interés en Clientify y responde al usuario. Incluye rutas de salud y manejadores de íconos para evitar 404 ruidosos.

## Endpoints principales
- `GET /` responde metadatos de la API.
- `GET /health` indica estado y entorno cargado.
- `POST /webhook/whatsapp` recibe payloads de Meta/WhatsApp, localiza o crea el contacto en Clientify, crea un negocio y agrega una nota con el mensaje recibido. Luego envía una respuesta de cortesía (envío simulado).

## Variables de entorno (`.env`)
- `ENV`: nombre del entorno (ej. `local`, `dev`, `prod`).
- `OPENAI_API_KEY`: opcional, reservado para futuras integraciones.
- `DATABASE_URL`: opcional.
- `WHATSAPP_VERIFY_TOKEN`: opcional, para validación de webhooks si se requiere.
- `WHATSAPP_ACCESS_TOKEN`: opcional, para futuras llamadas al API oficial de WhatsApp.
- `CLIENTIFY_API_KEY`: token de API obligatorio para crear/consultar contactos y negocios.
- `CLIENTIFY_BASE_URL`: base del API de Clientify (`https://api.clientify.com/v1` por defecto).
- `HOST`: host de escucha (por defecto `0.0.0.0`).
- `PORT`: puerto (por defecto `8000`).

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
- `.env` y `.venv` están ignorados en git; mantén credenciales fuera del repositorio.
