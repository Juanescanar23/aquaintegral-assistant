import json
import os
from typing import Any, Dict, List, Optional

import httpx

from app.core.settings import get_settings

OPENAI_BASE_URL = "https://api.openai.com/v1"
settings = get_settings()


def _get_env(name: str) -> str:
    v = getattr(settings, name, None) or os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _extract_text_from_responses_api(payload: Dict[str, Any]) -> str:
    """
    Respuestas API puede devolver el contenido en diferentes formas.
    Buscamos el primer campo razonable que contenga texto.
    """
    # Algunas SDKs exponen output_text; por REST puede o no venir.
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"]

    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                # En muchos ejemplos el texto viene como c["text"]
                if isinstance(c.get("text"), str) and c["text"].strip():
                    return c["text"]
                # Fallback defensivo
                if isinstance(c.get("output_text"), str) and c["output_text"].strip():
                    return c["output_text"]

    raise RuntimeError(
        "Could not extract text from OpenAI response: "
        f"keys={list(payload.keys())}"
    )


def _supports_temperature(model: str) -> bool:
    m = (model or "").strip().lower()
    if m.startswith("gpt-5"):
        return False
    return True


async def build_product_search_plan(user_text: str) -> Dict[str, Any]:
    """
    Convierte texto libre del cliente en un plan de busqueda.
    Devuelve dict con:
      - queries: List[str] (1..5)
      - should_ask: bool
      - question: str
    """
    api_key = _get_env("OPENAI_API_KEY")
    model = getattr(settings, "OPENAI_MODEL", None) or os.getenv("OPENAI_MODEL") or "gpt-5-nano"

    schema: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "queries": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {"type": "string"},
                "description": (
                    "Consultas cortas para buscar productos en WooCommerce. "
                    "Sin relleno (no 'necesito', no 'hola')."
                ),
            },
            "should_ask": {
                "type": "boolean",
                "description": (
                    "True si la consulta es ambigua y conviene preguntar "
                    "1 cosa antes de listar productos."
                ),
            },
            "question": {
                "type": "string",
                "description": (
                    "Si should_ask=true, una sola pregunta corta para "
                    "desambiguar. Si no, string vacio."
                ),
            },
        },
        "required": ["queries", "should_ask", "question"],
    }

    system = (
        "Eres un asistente de ventas de Aquaintegral. "
        "Tu tarea es transformar el mensaje del cliente en queries cortas "
        "para buscar productos en WooCommerce. "
        "Reglas:\n"
        "- Devuelve SOLO JSON segun el schema.\n"
        "- 'queries' deben ser 1 a 5 frases muy cortas y especificas "
        "(ej: 'calentador de agua', 'turbidimetro TB350').\n"
        "- Si el mensaje es ambiguo (ej: 'quiero un calentador'), marca "
        "should_ask=true y pregunta 1 cosa clave "
        "ej: 'Es calentador para agua de laboratorio o para piscina?'\n"
        "- No inventes SKUs ni marcas.\n"
        "- Idioma: espanol."
    )

    url = f"{OPENAI_BASE_URL}/responses"

    body: Dict[str, Any] = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        # Structured Outputs por Responses API (JSON Schema)
        "text": {
            "format": {
                "type": "json_schema",
                "name": "product_search_plan",
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": 250,
        # Recomendado para no almacenar conversaciones por defecto
        "store": False,
    }
    if _supports_temperature(model):
        body["temperature"] = 0

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

    text = _extract_text_from_responses_api(data)
    plan = json.loads(text)

    # Validacion minima defensiva
    queries = plan.get("queries")
    if (
        not isinstance(queries, list)
        or not queries
        or not all(isinstance(q, str) for q in queries)
    ):
        raise RuntimeError(f"Invalid plan. queries={queries}")

    plan["queries"] = [q.strip() for q in plan["queries"] if q.strip()]
    plan["should_ask"] = bool(plan.get("should_ask"))
    plan["question"] = str(plan.get("question") or "").strip()

    # Si dijo should_ask pero no puso pregunta, forzamos safe fallback
    if plan["should_ask"] and not plan["question"]:
        plan["question"] = (
            "Puedes darme un poco mas de detalle del producto "
            "(tipo/uso) para buscarlo mejor?"
        )

    return plan
