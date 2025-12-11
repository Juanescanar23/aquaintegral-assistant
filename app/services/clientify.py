from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.core.settings import get_settings

settings = get_settings()


class ClientifyClient:
    def __init__(self) -> None:
        base_url = settings.CLIENTIFY_BASE_URL.rstrip("/")
        if not base_url:
            raise ValueError("CLIENTIFY_BASE_URL is required")
        if not settings.CLIENTIFY_API_KEY:
            raise ValueError("CLIENTIFY_API_KEY is required")
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Token {settings.CLIENTIFY_API_KEY}",
            "Content-Type": "application/json",
        }

    async def get_or_create_contact_by_phone(self, phone: str) -> Dict[str, Any]:
        phone_normalized = phone.strip()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(10.0),
        ) as client:
            response = await client.get("/contacts/", params={"phone": phone_normalized})
            response.raise_for_status()
            data = response.json()
            results: Optional[list] = data.get("results", [])
            if results:
                return results[0]

            payload = {
                "phone": phone_normalized,
                "contact_source": "whatsapp-bot",
                "tags": ["aquaintegral", "whatsapp"],
            }
            created = await client.post("/contacts/", json=payload)
            created.raise_for_status()
            return created.json()

    async def create_deal(
        self, contact_id: int, name: str, value: float | None = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": name,
            "contact": contact_id,
            "source": "whatsapp-bot",
        }
        if value is not None:
            payload["value"] = value

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(10.0),
        ) as client:
            created = await client.post("/deals/", json=payload)
            created.raise_for_status()
            return created.json()

    async def add_note_to_contact(self, contact_id: int, text: str) -> Dict[str, Any]:
        payload = {"text": text}
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(10.0),
        ) as client:
            created = await client.post(f"/contacts/{contact_id}/notes/", json=payload)
            created.raise_for_status()
            return created.json()


clientify_client = ClientifyClient()
