from app.services.supabase_service import (
    get_pending_followups, mark_followup_sent,
    get_appointments_needing_reminder, mark_appointment_reminded,
)
from app.services.twilio_service import send_sms
from app.services.resend_service import send_email, text_to_html


async def send_appointment_reminders():
    """Text + email a reminder the day before, to cut no-shows."""
    for appt in get_appointments_needing_reminder(within_hours=24):
        lead = appt.get("leads", {})
        when = appt["scheduled_at"]
        where = appt.get("location") or "the agreed location"
        msg = f"Reminder: your viewing is coming up at {when} at {where}. Reply if you need to reschedule."

        if lead.get("phone"):
            send_sms(lead["phone"], msg)
        if lead.get("email"):
            send_email(lead["email"], "Reminder: your viewing tomorrow", text_to_html(msg))

        mark_appointment_reminded(appt["id"])


async def process_pending_followups():
    followups = get_pending_followups()
    for followup in followups:
        lead = followup.get("leads", {})
        message = followup["message"]
        channel = followup["channel"]

        # Never message a lead who has opted out.
        if lead.get("opted_out"):
            mark_followup_sent(followup["id"])
            continue

        if channel == "sms" and lead.get("phone"):
            send_sms(lead["phone"], message)
        elif channel == "email" and lead.get("email"):
            send_email(lead["email"], "A message from your agent", text_to_html(message))

        mark_followup_sent(followup["id"])
