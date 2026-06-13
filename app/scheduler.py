from app.services.supabase_service import get_pending_followups, mark_followup_sent
from app.services.twilio_service import send_sms
from app.services.resend_service import send_email, text_to_html


async def process_pending_followups():
    followups = get_pending_followups()
    for followup in followups:
        lead = followup.get("leads", {})
        message = followup["message"]
        channel = followup["channel"]

        if channel == "sms" and lead.get("phone"):
            send_sms(lead["phone"], message)
        elif channel == "email" and lead.get("email"):
            send_email(lead["email"], "A message from your agent", text_to_html(message))

        mark_followup_sent(followup["id"])
