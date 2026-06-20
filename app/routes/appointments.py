from fastapi import APIRouter, HTTPException
import os

from app.models.schemas import AppointmentRequest
from app.services.supabase_service import save_appointment, get_appointments, get_leads, update_lead_fields
from app.services.twilio_service import send_sms
from app.services.resend_service import send_email

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("/book")
async def book_appointment(req: AppointmentRequest):
    """Book a showing/call and confirm it to both the lead and the agent."""
    try:
        appt = save_appointment(req.model_dump())

        # Mark the lead as having a booking in progress.
        update_lead_fields(req.lead_id, {"conversation_stage": "showing_requested", "status": "appointment_booked"})

        # Look up the lead's contact details.
        leads = get_leads(req.agent_id)
        lead = next((l for l in leads if l["id"] == req.lead_id), None)

        when = req.scheduled_at
        where = req.location or "to be confirmed"
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Agent")

        if lead:
            if lead.get("phone"):
                send_sms(lead["phone"], f"You're booked! {agent_name} will see you {when} at {where}. Reply if you need to reschedule.")
            if lead.get("email"):
                send_email(lead["email"], "Your viewing is confirmed",
                           f"<p>Hi {lead.get('name','there')},</p><p>Your appointment with {agent_name} is confirmed for <b>{when}</b> at <b>{where}</b>.</p><p>See you then!</p>")

        agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")
        if agent_email and lead:
            send_email(agent_email, f"📅 New booking: {lead.get('name','Lead')}",
                       f"<p>{lead.get('name','A lead')} ({lead.get('phone','')}) is booked for <b>{when}</b> at <b>{where}</b>.</p><p>Notes: {req.notes or '—'}</p>")

        return {"success": True, "appointment": appt}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def list_appointments(agent_id: str):
    try:
        return {"success": True, "appointments": get_appointments(agent_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
