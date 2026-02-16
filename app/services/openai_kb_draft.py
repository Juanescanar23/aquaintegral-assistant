from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

from app.core.settings import get_settings


def _supports_temperature(model: str) -> bool:
    m = (model or "").strip().lower()
    if m.startswith("gpt-5"):
        return False
    return True


async def generate_kb_draft(
    question: str,
    *,
    line_hint: Optional[str],
    sources: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = (
        getattr(settings, "OPENAI_KB_MODEL", None)
        or getattr(settings, "OPENAI_MODEL", None)
        or os.getenv("OPENAI_KB_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-5-nano"
    )

    if not question or not sources:
        return None

    schema: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "should_publish": {"type": "boolean"},
            "answer": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "source_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "reason": {"type": "string"},
        },
        "required": ["should_publish", "answer", "tags", "source_ids", "reason"],
    }

    system = (
        "Eres un editor de base de conocimiento de Aqua Integral SAS. "
        "Responde SOLO con informacion contenida en 'sources'. "
        "Si no hay informacion suficiente, devuelve should_publish=false y answer=\"\". "
        "No inventes datos."
    )

    user_payload = {
        "question": question,
        "line_hint": line_hint or "",
        "sources": sources,
        "style": "respuesta corta, clara y enfocada en Aqua Integral SAS",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "kb_draft",
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": 250,
        "store": False,
    }
    if _supports_temperature(model):
        payload["temperature"] = 0

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = "https://api.openai.com/v1/responses"

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    text = data.get("output_text")
    if not text and isinstance(data.get("output"), list):
        for item in data.get("output") or []:
            for c in item.get("content") or []:
                if isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"].strip():
                    text = c["text"]
                    break
            if text:
                break

    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    if not parsed.get("should_publish"):
        return None

    answer = str(parsed.get("answer") or "").strip()
    if not answer:
        return None

    return {
        "answer": answer,
        "tags": parsed.get("tags") or [],
        "source_ids": parsed.get("source_ids") or [],
        "reason": str(parsed.get("reason") or ""),
        "model": model,
    }
