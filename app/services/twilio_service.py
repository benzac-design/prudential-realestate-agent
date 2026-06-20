from twilio.rest import Client
from twilio.request_validator import RequestValidator
import os


def validate_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Verify an inbound webhook really came from Twilio. If no auth token is
    configured (local dev), skip validation."""
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not auth_token:
        return True
    validator = RequestValidator(auth_token)
    return validator.validate(url, params, signature or "")


def send_sms(to_number: str, message: str) -> dict:
    client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    try:
        msg = client.messages.create(body=message, from_=from_number, to=to_number)
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}
