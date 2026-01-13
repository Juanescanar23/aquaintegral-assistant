from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

try:
    from app.core.settings import get_settings  # opcional (si existe)
except Exception:  # pragma: no cover
    get_settings = None  # type: ignore


def _get_openai_config() -> Tuple[str, str]:
    """
    Lee OPENAI_API_KEY y modelo desde settings o env.
    Forzamos un modelo compatible con json_schema por defecto.
    """
    api_key = None
    model = None

    if get_settings:
        try:
            s = get_settings()
            api_key = getattr(s, "OPENAI_API_KEY", None)
            model = getattr(s, "OPENAI_RERANK_MODEL", None) or getattr(s, "OPENAI_MODEL", None)
        except Exception:
            pass

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta OPENAI_API_KEY (settings o env).")

    # Por compatibilidad con Structured Outputs json_schema, default gpt-4o-mini.
    # (puedes setear OPENAI_RERANK_MODEL en env)
    model = model or os.getenv("OPENAI_RERANK_MODEL") or "gpt-4o-mini"
    return api_key, model


def _strip_html(text: str) -> str:
    if not text:
        return ""
    # Remueve tags básicos para no contaminar tokens.
    return re.sub(r"<[^>]+>", " ", text).strip()


def _extract_output_text(resp_json: Dict[str, Any]) -> str:
    """
    Responses API devuelve output[] con content[].
    Buscamos todos los content items con "type": "output_text".
    """
    out = []
    for item in resp_json.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") == "output_text" and isinstance(c.get("text"), str):
                out.append(c["text"])
    return "\n".join(out).strip()


async def rerank_products(
    user_query: str,
    candidates: Sequence[Dict[str, Any]],
    *,
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    Devuelve:
      {
        "selected_ids": [int...],
        "clarifying_question": str
      }
    Reglas:
      - solo puede elegir IDs existentes en candidates
      - puede devolver [] + pregunta si no hay match claro
    """
    api_key, model = _get_openai_config()

    # Limita contexto: 30 items máximo
    cand_list = list(candidates)[:30]
    allowed_ids = {int(p["id"]) for p in cand_list if isinstance(p.get("id"), int)}

    compact = []
    for p in cand_list:
        compact.append(
            {
                "id": p.get("id"),
                "sku": p.get("sku") or "",
                "name": p.get("name") or "",
                "price": p.get("price") or p.get("regular_price") or "",
                "stock_status": p.get("stock_status") or "",
                "stock_quantity": p.get("stock_quantity"),
                "short_description": _strip_html((p.get("short_description") or "")[:220]),
            }
        )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["selected_ids", "clarifying_question"],
        "properties": {
            "selected_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 0,
                "maxItems": top_k,
            },
            "clarifying_question": {"type": "string"},
        },
    }

    system = (
        "Eres un asistente de e-commerce. Tu tarea es seleccionar productos reales "
        "de una lista. NO inventes productos. Solo puedes elegir IDs presentes en la lista."
    )

    user = {
        "query": user_query,
        "top_k": top_k,
        "allowed_ids": sorted(list(allowed_ids))[:200],
        "products": compact,
        "instructions": (
            "Selecciona hasta top_k productos más relevantes para la consulta.\n"
            "Si no hay match claro, devuelve selected_ids=[] y una pregunta corta (máx 1 frase) "
            "pidiendo el dato mínimo que falta (ej: capacidad HP, voltaje, tipo de equipo, uso)."
        ),
    }

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "temperature": 0,
        # Structured Outputs (json_schema) en Responses API.
        "text": {
            "format": {
                "type": "json_schema",
                "strict": True,
                "schema": schema,
            }
        },
    }

    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    txt = _extract_output_text(data)
    if not txt:
        return {"selected_ids": [], "clarifying_question": "¿Qué características clave necesitas (tipo/capacidad/uso)?"}

    try:
        parsed = json.loads(txt)
    except Exception:
        return {"selected_ids": [], "clarifying_question": "¿Puedes darme 2 datos (tipo/capacidad/uso) para buscar mejor?"}

    selected = parsed.get("selected_ids") or []
    if not isinstance(selected, list):
        selected = []

    # Validación dura: solo IDs permitidos, únicos, top_k
    clean_ids: List[int] = []
    for x in selected:
        try:
            xid = int(x)
        except Exception:
            continue
        if xid in allowed_ids and xid not in clean_ids:
            clean_ids.append(xid)
        if len(clean_ids) >= top_k:
            break

    q = parsed.get("clarifying_question") or ""
    if not isinstance(q, str):
        q = ""

    return {"selected_ids": clean_ids, "clarifying_question": q.strip()}
