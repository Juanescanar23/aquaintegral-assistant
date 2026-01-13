from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from app.core.settings import get_settings
from app.domain.company_profile import BUSINESS_LINES, normalize_line_key


@dataclass(frozen=True)
class IntentResult:
    intent: str
    line_key: Optional[str]
    confidence: float


_INTENTS = {
    "company_info",
    "services",
    "line_info",
    "catalog",
    "faq",
    "product_search",
    "other",
}


def _get_openai_config() -> Optional[tuple[str, str]]:
    settings = get_settings()
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    model = (
        os.getenv("OPENAI_INTENT_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-5-nano"
    )
    return api_key, model


def _extract_text_from_responses_api(payload: Dict[str, Any]) -> str:
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
                if isinstance(c.get("text"), str) and c["text"].strip():
                    return c["text"]
                if isinstance(c.get("output_text"), str) and c["output_text"].strip():
                    return c["output_text"]

    return ""


def _normalize_confidence(value: Any) -> float:
    try:
        conf = float(value)
    except Exception:
        return 0.0
    if conf < 0:
        return 0.0
    if conf > 1:
        return 1.0
    return conf


async def classify_info_intent(
    user_text: str,
    *,
    line_hint: Optional[str],
    min_confidence: float = 0.7,
) -> Optional[IntentResult]:
    raw = (user_text or "").strip()
    if not raw:
        return None

    cfg = _get_openai_config()
    if not cfg:
        return None

    api_key, model = cfg

    line_keys = sorted(list(BUSINESS_LINES.keys()))
    schema: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent": {"type": "string", "enum": sorted(list(_INTENTS))},
            "line": {"type": "string", "enum": line_keys + ["unknown"]},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["intent", "line", "confidence", "reason"],
    }

    system = (
        "Eres un clasificador de intentos para el bot de Aqua Integral SAS. "
        "Elige SOLO 1 intent segun el mensaje del cliente. "
        "Intents disponibles: company_info, services, line_info, catalog, faq, product_search, other. "
        "Reglas:\n"
        "- company_info: preguntas sobre la empresa, que ofrece, informacion general.\n"
        "- services: preguntas sobre servicios (asesoria, instalacion, soporte).\n"
        "- line_info: preguntas sobre una linea (agua potable, residual, bombeo, analisis, piscinas).\n"
        "- catalog: pide link/pagina/tienda/portafolio.\n"
        "- faq: horario, ubicacion, pagos, envios.\n"
        "- product_search: quiere producto, precio, cotizacion o stock.\n"
        "- other: saludo o no aplica.\n"
        "Devuelve JSON segun el schema y no inventes datos."
    )

    user_payload = {
        "message": raw,
        "line_hint": line_hint or "",
        "line_keys": line_keys,
    }

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "intent_classifier",
                "strict": True,
                "schema": schema,
            }
        },
        "store": False,
        "max_output_tokens": 200,
    }

    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None

    text = _extract_text_from_responses_api(data)
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    intent = str(parsed.get("intent") or "").strip()
    if intent not in _INTENTS:
        return None

    confidence = _normalize_confidence(parsed.get("confidence"))
    if confidence < min_confidence:
        return None

    raw_line = str(parsed.get("line") or "").strip()
    line_key = normalize_line_key(raw_line) or normalize_line_key(line_hint) or normalize_line_key(raw)

    if intent in {"product_search", "other"}:
        return None

    return IntentResult(intent=intent, line_key=line_key, confidence=confidence)
