from twilio.rest import Client
import os


def send_sms(to_number: str, message: str) -> dict:
    client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    try:
        msg = client.messages.create(body=message, from_=from_number, to=to_number)
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}
