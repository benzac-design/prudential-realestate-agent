from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.schemas import LeadForm
from app.services.claude_service import generate_lead_followup_sms, generate_lead_followup_email
from app.services.twilio_service import send_sms
from app.services.resend_service import send_email, text_to_html
from app.services.supabase_service import save_lead, get_leads, update_lead_status
import os

router = APIRouter(prefix="/leads", tags=["leads"])


def handle_new_lead(lead_data: dict, agent_name: str, agent_email: str):
    lead_name = lead_data["name"]
    lead_phone = lead_data["phone"]
    lead_email = lead_data["email"]
    lead_message = lead_data.get("message", "")

    # Send SMS to lead
    sms_text = generate_lead_followup_sms(lead_name, agent_name)
    send_sms(lead_phone, sms_text)

    # Send email to lead
    email_content = generate_lead_followup_email(lead_name, agent_name, lead_message)
    lines = email_content.split("\n")
    subject = lines[0].replace("Subject:", "").strip() if lines[0].startswith("Subject:") else "Thanks for reaching out!"
    body = "\n".join(lines[1:]).strip()
    send_email(lead_email, subject, text_to_html(body))

    # Notify agent
    send_email(
        agent_email,
        f"New Lead: {lead_name}",
        f"<p>New lead received!</p><p><b>Name:</b> {lead_name}</p><p><b>Phone:</b> {lead_phone}</p><p><b>Email:</b> {lead_email}</p><p><b>Message:</b> {lead_message}</p><p>AI has already contacted them.</p>"
    )


@router.post("/new")
async def new_lead(lead: LeadForm, background_tasks: BackgroundTasks):
    try:
        lead_data = lead.model_dump()
        saved = save_lead(lead_data)

        # Get agent info (in production this comes from DB)
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Agent")
        agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "agent@example.com")

        background_tasks.add_task(handle_new_lead, lead_data, agent_name, agent_email)

        return {"success": True, "message": "Lead received and AI follow-up triggered", "lead_id": saved.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def list_leads(agent_id: str):
    try:
        leads = get_leads(agent_id)
        return {"success": True, "leads": leads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{lead_id}/status")
async def update_status(lead_id: str, status: str):
    try:
        update_lead_status(lead_id, status)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
