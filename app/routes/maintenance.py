from fastapi import APIRouter, HTTPException, Depends
import os

from app.models.schemas import MaintenanceRequest, MaintenanceStatusUpdate
from app.services.claude_service import triage_maintenance_request
from app.services.resend_service import send_email, text_to_html
from app.services.supabase_service import (
    save_maintenance_request, get_maintenance_requests, update_maintenance_status,
)
from app.auth import require_dashboard_auth

try:
    from app.services.twilio_service import send_sms
except Exception:  # pragma: no cover - SMS optional
    send_sms = None

router = APIRouter(prefix="/maintenance", tags=["maintenance"], dependencies=[Depends(require_dashboard_auth)])

# How urgency maps to the alert sent to the property manager.
_URGENCY_FLAG = {
    "emergency": "🚨 EMERGENCY",
    "urgent": "⚠️ Urgent",
    "routine": "🛠️ Routine",
}

# Fields the AI triage produces that we persist on the job record.
_TRIAGE_FIELDS = (
    "urgency", "category", "trade", "summary", "likely_cause", "recommended_action",
    "estimated_cost", "eta", "diy_possible", "diy_tip", "safety_warning",
)


@router.post("/triage")
async def triage(req: MaintenanceRequest):
    """A tenant reports a maintenance issue. AI triages it (urgency, trade, likely
    cause, cost estimate, DIY/safety guidance), acknowledges the tenant, alerts the
    property manager, and logs the job on the board."""
    try:
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")

        result = triage_maintenance_request(
            tenant_name=req.tenant_name,
            address=req.address,
            message=req.message,
            agent_name=agent_name,
        )

        flag = _URGENCY_FLAG.get(result["urgency"], "🛠️ Routine")

        # Persist the job so it shows on the maintenance board and can be tracked.
        job = {}
        if req.save:
            data = {k: result.get(k) for k in _TRIAGE_FIELDS}
            data.update({
                "agent_id": req.agent_id or "default",
                "tenant_name": req.tenant_name,
                "address": req.address,
                "message": req.message,
                "tenant_phone": req.tenant_phone or "",
                "tenant_email": req.tenant_email or "",
                "status": "open",
            })
            job = save_maintenance_request(data)

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
            safety = f"<p style='color:#b91c1c'><b>⚠️ Safety:</b> {result['safety_warning']}</p>" if result.get("safety_warning") else ""
            diy = f"<p><b>Possible quick fix to suggest:</b> {result['diy_tip']}</p>" if result.get("diy_possible") and result.get("diy_tip") else ""
            send_email(
                agent_email,
                f"{flag} maintenance — {req.address} ({result['category']})",
                f"<p><b>{flag}</b> &middot; ETA: <b>{result['eta']}</b></p>"
                f"{safety}"
                f"<p><b>Property:</b> {req.address}<br>"
                f"<b>Tenant:</b> {req.tenant_name} ({req.tenant_phone or req.tenant_email or 'no contact'})</p>"
                f"<p><b>Issue:</b> {result['summary']}<br>"
                f"<b>Likely cause:</b> {result.get('likely_cause') or 'n/a'}</p>"
                f"<p><b>Send a:</b> {result.get('trade','tradesperson')} &middot; "
                f"<b>Est. cost:</b> {result.get('estimated_cost','unknown')} &middot; "
                f"<b>Access needed:</b> {'yes' if result.get('access_required') else 'no'}</p>"
                f"<p><b>Recommended action:</b> {result['recommended_action']}</p>"
                f"{diy}"
                f"<hr><p><i>Tenant's original message:</i><br>{req.message}</p>",
            )

        return {"success": True, "job_id": job.get("id"), **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def list_maintenance(agent_id: str):
    """The maintenance job board — open & urgent first, resolved last."""
    try:
        return {"success": True, "jobs": get_maintenance_requests(agent_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{request_id}/status")
async def set_status(request_id: str, update: MaintenanceStatusUpdate):
    """Move a job along: open -> assigned -> scheduled -> resolved (optionally
    record who it was assigned to)."""
    try:
        update_maintenance_status(request_id, update.status, update.assigned_to)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
