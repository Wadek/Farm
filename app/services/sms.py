"""Outbound SMS. Logs every message. Sends for real only if a provider is configured."""

import re
import uuid
from app.config import settings
from app.models.ask import SmsLog


def e164(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("0"):
        digits = "358" + digits[1:]
    if not digits.startswith("358") and len(digits) == 9:
        digits = "358" + digits
    return "+" + digits


def same_phone(a: str, b: str) -> bool:
    da, db = re.sub(r"\D", "", a or ""), re.sub(r"\D", "", b or "")
    if len(da) < 8 or len(db) < 8:
        return False
    return da[-9:] == db[-9:]


def send_sms(db, phone: str, body: str, ask_id: str | None = None) -> dict:
    dest = e164(phone)
    provider = (settings.sms_provider or "log").lower()
    sent = False
    error = ""
    if dest and provider in ("elks", "46elks") and settings.elks_username and settings.elks_password:
        try:
            import requests
            r = requests.post(
                "https://api.46elks.com/a1/sms",
                auth=(settings.elks_username, settings.elks_password),
                data={"from": settings.sms_from or "Satokori", "to": dest, "message": body},
                timeout=15,
            )
            sent = r.status_code < 300
            if not sent:
                error = r.text[:200]
            provider = "elks"
        except Exception as exc:
            error = str(exc)[:200]
    elif dest and provider == "twilio" and settings.twilio_sid and settings.twilio_token:
        try:
            import requests
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_sid}/Messages.json",
                auth=(settings.twilio_sid, settings.twilio_token),
                data={"From": settings.twilio_from or settings.sms_from, "To": dest, "Body": body},
                timeout=15,
            )
            sent = r.status_code < 300
            if not sent:
                error = r.text[:200]
            provider = "twilio"
        except Exception as exc:
            error = str(exc)[:200]
    else:
        provider = "log"

    row = SmsLog(
        id=str(uuid.uuid4()),
        direction="out",
        phone=dest or phone,
        body=body if not error else f"{body}\n[{error}]",
        ask_id=ask_id,
        provider=provider if sent or provider == "log" else f"{provider}-failed",
    )
    db.add(row)
    db.commit()
    return {"sent": sent or provider == "log", "provider": provider, "phone": dest}
