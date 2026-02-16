from __future__ import annotations

import asyncio
import logging
import time

from app.core.settings import get_settings
from app.services.session_state import (
    close_session,
    get_idle_actions,
    mark_followup_sent,
)
from app.services.whatsapp import send_message
from app.services.twilio import send_twilio_whatsapp_message

logger = logging.getLogger(__name__)


async def _send(channel: str, phone: str, text: str) -> None:
    if channel == "twilio":
        await send_twilio_whatsapp_message(to_whatsapp=f"whatsapp:+{phone}", body=text)
    else:
        await send_message(phone, text)


async def idle_followup_loop() -> None:
    settings = get_settings()
    if not bool(getattr(settings, "IDLE_FOLLOWUP_ENABLED", False)):
        logger.info("Idle follow-up disabled")
        return

    followup_after = int(getattr(settings, "IDLE_FOLLOWUP_AFTER_MINUTES", 15)) * 60
    final_after = int(getattr(settings, "IDLE_FINAL_AFTER_MINUTES", 60)) * 60
    interval = int(getattr(settings, "IDLE_CHECK_INTERVAL_SECONDS", 60))
    max_followups = int(getattr(settings, "IDLE_MAX_FOLLOWUPS", 1))
    followup_message = str(getattr(settings, "IDLE_FOLLOWUP_MESSAGE", "")).strip()
    final_message = str(getattr(settings, "IDLE_FINAL_MESSAGE", "")).strip()

    interval = max(10, interval)
    followup_after = max(60, followup_after)
    final_after = max(followup_after + 60, final_after)

    logger.info(
        "Idle follow-up loop started",
        extra={
            "followup_after_sec": followup_after,
            "final_after_sec": final_after,
            "interval_sec": interval,
            "max_followups": max_followups,
        },
    )

    while True:
        try:
            actions = get_idle_actions(
                now=time.time(),
                followup_after=followup_after,
                final_after=final_after,
                max_followups=max_followups,
            )
            for action in actions:
                phone = action["phone"]
                channel = action.get("channel") or "meta"
                kind = action.get("kind")
                try:
                    if kind == "followup" and followup_message:
                        await _send(channel, phone, followup_message)
                        mark_followup_sent(phone)
                    elif kind == "final" and final_message:
                        await _send(channel, phone, final_message)
                        close_session(phone)
                except Exception:
                    logger.exception(
                        "Idle follow-up send failed",
                        extra={"phone": phone, "channel": channel, "kind": kind},
                    )
        except Exception:
            logger.exception("Idle follow-up loop error")

        await asyncio.sleep(interval)


def start_idle_followup_task() -> None:
    asyncio.create_task(idle_followup_loop())
