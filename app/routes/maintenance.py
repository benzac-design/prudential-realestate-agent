from fastapi import APIRouter, HTTPException
import os

from app.models.schemas import MaintenanceRequest
from app.services.claude_service import triage_maintenance_request
from app.services.resend_service import send_email, text_to_html

try:
    from app.services.twilio_service import send_sms
except Exception:  # pragma: no cover - SMS optional
    send_sms = None

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

# How urgency maps to the alert sent to the property manager.
_URGENCY_FLAG = {
    "emergency": "🚨 EMERGENCY",
    "urgent": "⚠️ Urgent",
    "routine": "🛠️ Routine",
}


@router.post("/triage")
async def triage(req: MaintenanceRequest):
    """A tenant reports a maintenance issue. AI classifies urgency, acknowledges the
    tenant, and alerts the property manager with a prioritised summary."""
    try:
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")

        result = triage_maintenance_request(
            tenant_name=req.tenant_name,
            address=req.address,
            message=req.message,
            agent_name=agent_name,
        )

        flag = _URGENCY_FLAG.get(result["urgency"], "🛠️ Routine")

        # Acknowledge the tenant straight away.
        if req.tenant_phone and send_sms:
            try:
                send_sms(req.tenant_phone, result["tenant_reply"])
            except Exception:
                pass
        if req.tenant_email:
            send_email(req.tenant_email, f"We've received your maintenance request — {req.address}",
                       text_to_html(result["tenant_reply"]))

        # Alert the property manager, prioritised by urgency.
        agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")
        if agent_email:
            send_email(
                agent_email,
                f"{flag} maintenance — {req.address} ({result['category']})",
                f"<p><b>{flag}</b> &middot; ETA: <b>{result['eta']}</b></p>"
                f"<p><b>Property:</b> {req.address}<br>"
                f"<b>Tenant:</b> {req.tenant_name} ({req.tenant_phone or req.tenant_email or 'no contact'})</p>"
                f"<p><b>Issue:</b> {result['summary']}</p>"
                f"<p><b>Recommended action:</b> {result['recommended_action']}</p>"
                f"<hr><p><i>Tenant's original message:</i><br>{req.message}</p>",
            )

        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
