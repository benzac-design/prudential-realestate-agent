from fastapi import APIRouter, Request, Response
import os

from app.services.twilio_service import send_sms, validate_twilio_signature
from app.services.resend_service import send_email
from app.services.claude_service import generate_conversation_reply
from app.services.supabase_service import (
    get_lead_by_phone,
    save_lead,
    save_message,
    get_conversation,
    update_lead_fields,
    mark_opted_out,
    cancel_pending_followups,
)
from app.services.scoring import score_lead

router = APIRouter(tags=["conversations"])

# TCPA / carrier-standard keywords.
OPT_OUT_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit", "stop all"}
OPT_IN_WORDS = {"start", "unstop", "yes"}

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _twiml() -> Response:
    return Response(content=_EMPTY_TWIML, media_type="application/xml")


@router.post("/sms/inbound")
async def sms_inbound(request: Request):
    """Twilio inbound-SMS webhook. Handles opt-out, stops the drip sequence on
    reply, and runs the two-way AI conversation."""
    form = dict((await request.form()))
    from_number = form.get("From", "")
    body = (form.get("Body", "") or "").strip()

    # Verify the request actually came from Twilio.
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not validate_twilio_signature(url, form, signature):
        return Response(status_code=403, content="Invalid signature")

    if not from_number or not body:
        return _twiml()

    agent_id = os.getenv("DEFAULT_AGENT_ID", "default")
    agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Agent")
    agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")
    agency = os.getenv("DEFAULT_AGENCY", "")

    # Find the lead, or create a lightweight record for an unknown sender.
    lead = get_lead_by_phone(from_number)
    if not lead:
        lead = save_lead({
            "name": "New Texter",
            "email": "",
            "phone": from_number,
            "message": body,
            "agent_id": agent_id,
            "status": "inbound",
        })
    lead_id = lead["id"]

    # Log what the lead said.
    save_message(lead_id, agent_id, "inbound", body)

    normalized = body.lower().strip()

    # --- Opt-out: legally required, must short-circuit everything else. ---
    if normalized in OPT_OUT_WORDS:
        mark_opted_out(lead_id)
        cancel_pending_followups(lead_id)
        confirm = "You're unsubscribed and won't get more texts. Reply START to opt back in."
        send_sms(from_number, confirm)
        save_message(lead_id, agent_id, "outbound", confirm)
        return _twiml()

    # --- Opt back in. ---
    if normalized in OPT_IN_WORDS:
        update_lead_fields(lead_id, {"opted_out": False, "status": "engaged"})
        msg = f"Welcome back! It's {agent_name}. How can I help with your property search?"
        send_sms(from_number, msg)
        save_message(lead_id, agent_id, "outbound", msg)
        return _twiml()

    # Respect a prior opt-out — never message them again until they opt in.
    if lead.get("opted_out"):
        return _twiml()

    # --- Stop-on-reply: a human responded, so kill the automated drip. ---
    cancel_pending_followups(lead_id)

    # --- Run the AI conversation. ---
    history = get_conversation(lead_id)
    result = generate_conversation_reply(lead, history, agent_name, agency)

    reply = result["reply"]
    send_sms(from_number, reply)
    save_message(lead_id, agent_id, "outbound", reply)

    # Merge what we learned, then re-score the lead.
    updates = {
        "budget": result.get("budget"),
        "timeline": result.get("timeline"),
        "pre_approved": result.get("pre_approved"),
        "conversation_stage": result.get("stage"),
        "status": "engaged" if result.get("intent") != "not_interested" else "cold",
    }
    merged = {**lead, **{k: v for k, v in updates.items() if v is not None}}
    score, temperature = score_lead(merged)
    updates["score"] = score
    updates["temperature"] = temperature
    update_lead_fields(lead_id, updates)

    # Alert the agent when the lead is hot or wants a viewing.
    if agent_email and result.get("intent") in ("wants_showing", "hot"):
        send_email(
            agent_email,
            f"🔥 Hot lead wants to talk: {lead.get('name', from_number)}",
            f"<p><b>{lead.get('name', 'A lead')}</b> ({from_number}) is ready.</p>"
            f"<p><b>They said:</b> {body}</p>"
            f"<p><b>Budget:</b> {result.get('budget') or lead.get('budget') or 'unknown'}<br>"
            f"<b>Timeline:</b> {result.get('timeline') or lead.get('timeline') or 'unknown'}<br>"
            f"<b>Pre-approved:</b> {result.get('pre_approved') if result.get('pre_approved') is not None else lead.get('pre_approved')}</p>"
            f"<p>The AI replied: <i>{reply}</i></p>"
        )

    return _twiml()
