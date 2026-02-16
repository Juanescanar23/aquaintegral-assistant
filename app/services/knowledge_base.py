from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.settings import get_settings
from app.services.openai_kb_draft import generate_kb_draft


_BASE_PATH = Path(__file__).resolve().parents[1] / "domain" / "knowledge_base.json"
_GAPS_PATH = Path(__file__).resolve().parents[1] / "domain" / "knowledge_gaps.jsonl"
_DRAFTS_PATH = Path(__file__).resolve().parents[1] / "domain" / "knowledge_drafts.jsonl"

_CACHE_TTL_SECONDS = 60
_cache_updated_at: float = 0.0
_cache_entries: List[Dict[str, Any]] = []

_write_lock = asyncio.Lock()

_STOPWORDS = {
    "a",
    "al",
    "algo",
    "alguien",
    "as",
    "con",
    "como",
    "cual",
    "cuando",
    "de",
    "del",
    "donde",
    "el",
    "ella",
    "ellos",
    "en",
    "es",
    "esta",
    "estoy",
    "fue",
    "ha",
    "hola",
    "las",
    "lo",
    "los",
    "la",
    "me",
    "mi",
    "mis",
    "necesito",
    "quiero",
    "que",
    "para",
    "por",
    "ser",
    "si",
    "sin",
    "su",
    "sus",
    "una",
    "un",
    "unos",
    "unas",
    "y",
    "o",
}

_INFO_HINTS = {
    "aqua",
    "aquaintegral",
    "empresa",
    "quienes",
    "quien",
    "servicio",
    "servicios",
    "linea",
    "lineas",
    "catalogo",
    "portafolio",
    "pagina",
    "web",
    "sitio",
    "enlace",
    "ubicacion",
    "direccion",
    "horario",
    "horas",
    "atencion",
    "pago",
    "pagos",
    "tarjeta",
    "addi",
    "envio",
    "envios",
}


@dataclass(frozen=True)
class KnowledgeAnswer:
    answer: str
    entry_id: str
    score: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = "".join(
        ch
        for ch in unicodedata.normalize("NFD", t)
        if unicodedata.category(ch) != "Mn"
    )
    t = re.sub(r"[^a-z0-9\\s]", " ", t)
    t = re.sub(r"\\s+", " ", t)
    return t


def _tokenize(text: str) -> List[str]:
    norm = _normalize(text)
    if not norm:
        return []
    parts = re.findall(r"[a-z0-9]+", norm)
    return [p for p in parts if len(p) >= 3 and p not in _STOPWORDS]


def should_attempt_knowledge(text: str) -> bool:
    norm = _normalize(text)
    if not norm:
        return False
    return any(h in norm for h in _INFO_HINTS)


def _load_entries() -> List[Dict[str, Any]]:
    global _cache_entries, _cache_updated_at
    now = datetime.now(timezone.utc).timestamp()
    if _cache_entries and (now - _cache_updated_at) < _CACHE_TTL_SECONDS:
        return _cache_entries
    if not _BASE_PATH.exists():
        _cache_entries = []
        _cache_updated_at = now
        return _cache_entries
    try:
        data = json.loads(_BASE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            _cache_entries = data
        else:
            _cache_entries = []
    except Exception:
        _cache_entries = []
    _cache_updated_at = now
    return _cache_entries


def _score_entry(qtokens: Iterable[str], entry: Dict[str, Any]) -> int:
    tokens = []
    tokens.extend(_tokenize(entry.get("question", "")))
    tokens.extend(_tokenize(" ".join(entry.get("tags") or [])))
    if entry.get("include_answer_in_match"):
        tokens.extend(_tokenize(entry.get("answer", "")))
    etoks = set(tokens)
    score = 0
    for t in qtokens:
        if t in etoks:
            score += 2
    return score


def find_knowledge_answer(
    text: str,
    *,
    min_score: Optional[int] = None,
    require_verified: Optional[bool] = None,
) -> Optional[KnowledgeAnswer]:
    qtokens = _tokenize(text)
    if not qtokens:
        return None
    settings = get_settings()
    if min_score is None:
        min_score = int(getattr(settings, "KB_MIN_SCORE", 2))
    if require_verified is None:
        require_verified = bool(getattr(settings, "KB_REQUIRE_VERIFIED", True))

    best: Optional[KnowledgeAnswer] = None
    for entry in _load_entries():
        if require_verified and not entry.get("verified", False):
            continue
        score = _score_entry(qtokens, entry)
        if score <= 0:
            continue
        if best is None or score > best.score:
            best = KnowledgeAnswer(
                answer=str(entry.get("answer") or "").strip(),
                entry_id=str(entry.get("id") or ""),
                score=score,
            )
    if not best or best.score < min_score or not best.answer:
        return None
    return best


def _select_sources(text: str, entries: List[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    qtokens = _tokenize(text)
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for entry in entries:
        score = _score_entry(qtokens, entry)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _, entry in scored[:limit]:
        out.append(
            {
                "id": str(entry.get("id") or ""),
                "text": f"Q: {entry.get('question','')}\nA: {entry.get('answer','')}",
            }
        )
    return out


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _slugify(text: str) -> str:
    norm = _normalize(text)
    if not norm:
        return "kb"
    norm = re.sub(r"\\s+", "-", norm).strip("-")
    return norm[:64] or "kb"


async def record_gap_and_draft(text: str, *, line_hint: Optional[str]) -> None:
    settings = get_settings()
    payload = {
        "ts": _now_iso(),
        "question": (text or "").strip(),
        "line_hint": (line_hint or "").strip(),
    }
    if not payload["question"]:
        return

    async with _write_lock:
        _append_jsonl(_GAPS_PATH, payload)

    if not bool(getattr(settings, "KB_AUTO_DRAFT", False)):
        return

    entries = _load_entries()
    sources = _select_sources(text, entries, limit=12)
    draft = await generate_kb_draft(text, line_hint=line_hint, sources=sources)
    if not draft:
        return

    entry_id = _slugify(text)
    draft_payload = {
        "id": entry_id,
        "question": (text or "").strip(),
        "answer": draft["answer"].strip(),
        "tags": draft.get("tags") or [],
        "source_ids": draft.get("source_ids") or [],
        "reason": draft.get("reason") or "",
        "model": draft.get("model") or "",
        "created_at": _now_iso(),
        "verified": False,
    }

    async with _write_lock:
        _append_jsonl(_DRAFTS_PATH, draft_payload)

        if bool(getattr(settings, "KB_AUTO_PUBLISH", False)):
            entries = _load_entries()
            entries.append(draft_payload)
            _BASE_PATH.write_text(
                json.dumps(entries, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
