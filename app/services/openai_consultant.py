from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from app.core.settings import get_settings
from app.domain.consultant_questions import normalize_line_hint, questions_for_line


@dataclass(frozen=True)
class QuestionChoice:
    key: str
    question: str
    line: str


def _get_openai_config() -> Optional[tuple[str, str]]:
    settings = get_settings()
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    model = (
        getattr(settings, "OPENAI_CONSULTANT_MODEL", None)
        or getattr(settings, "OPENAI_MODEL", None)
        or os.getenv("OPENAI_CONSULTANT_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-5-nano"
    )
    return api_key, model


def _supports_temperature(model: str) -> bool:
    m = (model or "").strip().lower()
    if m.startswith("gpt-5"):
        return False
    return True


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


async def select_consultant_question(
    user_text: str,
    *,
    line_hint: Optional[str],
    asked_keys: List[str],
) -> Optional[QuestionChoice]:
    line_key = normalize_line_hint(line_hint)
    questions = questions_for_line(line_key)
    available = [q for q in questions if q.get("key") not in set(asked_keys)]
    if not available:
        return None

    cfg = _get_openai_config()
    if not cfg:
        # Sin OpenAI, no forzamos pregunta automatica.
        return None

    api_key, model = cfg

    schema: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "should_ask": {"type": "boolean"},
            "question_key": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["should_ask", "question_key", "reason"],
    }

    system = (
        "Eres un asesor de Aquaintegral. Tu tarea es decidir si hace falta "
        "hacer UNA pregunta corta para precisar la solicitud antes de buscar productos. "
        "Reglas:\n"
        "- Si el cliente ya dio suficiente informacion tecnica, no preguntes.\n"
        "- Si el mensaje es muy general, elige una pregunta de la lista disponible.\n"
        "- No inventes preguntas fuera de la lista.\n"
        "- Devuelve JSON segun el schema."
    )

    user_payload = {
        "message": user_text,
        "line_hint": line_key,
        "asked_keys": asked_keys,
        "available_questions": available,
    }

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "consultant_question",
                "strict": True,
                "schema": schema,
            }
        },
        "store": False,
        "max_output_tokens": 200,
    }
    if _supports_temperature(model):
        payload["temperature"] = 0

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

    should_ask = bool(parsed.get("should_ask"))
    question_key = str(parsed.get("question_key") or "").strip()
    if not should_ask or not question_key:
        return None

    question_map = {q["key"]: q["question"] for q in available if "key" in q and "question" in q}
    question_text = question_map.get(question_key)
    if not question_text:
        return None

    return QuestionChoice(key=question_key, question=question_text, line=line_key)
