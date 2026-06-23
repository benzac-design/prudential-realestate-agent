from fastapi import APIRouter, HTTPException, Depends
import os

from app.models.schemas import ValuationRequest
from app.services.claude_service import generate_home_valuation
from app.services.supabase_service import save_lead, save_message, get_seller_leads
from app.services.resend_service import send_email, text_to_html
from app.auth import require_dashboard_auth

router = APIRouter(prefix="/valuation", tags=["valuation"])


@router.get("/{agent_id}", dependencies=[Depends(require_dashboard_auth)])
async def list_valuations(agent_id: str):
    """Seller leads captured via the home-valuation lead magnet."""
    try:
        return {"success": True, "valuations": get_seller_leads(agent_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request")
async def request_valuation(req: ValuationRequest):
    """'What's my home worth' lead magnet: capture a seller lead, generate an
    instant AI valuation, deliver it, and alert the agent."""
    try:
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Agent")

        valuation = generate_home_valuation(
            address=req.address,
            bedrooms=req.bedrooms,
            bathrooms=req.bathrooms,
            sqm=req.sqm,
            condition=req.condition,
            year_built=req.year_built,
            recent_upgrades=req.recent_upgrades,
            neighborhood=req.neighborhood,
            agent_name=agent_name,
        )

        # Capture as a seller lead.
        lead = save_lead({
            "name": req.name,
            "email": req.email or "",
            "phone": req.phone or "",
            "message": f"Home valuation request for {req.address}",
            "agent_id": req.agent_id,
            "lead_type": "seller",
            "status": "new",
        })
        if lead.get("id"):
            save_message(lead["id"], req.agent_id, "outbound", valuation)

        # Email the seller their valuation.
        if req.email:
            send_email(req.email, f"Your home value estimate for {req.address}", text_to_html(valuation))

        # Alert the agent to the new seller lead.
        agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")
        if agent_email:
            send_email(agent_email, f"🏠 New seller lead: {req.name} — {req.address}",
                       f"<p><b>{req.name}</b> ({req.phone or req.email}) requested a valuation for <b>{req.address}</b>.</p>"
                       f"<p>This is a SELLER lead — high value. Follow up to win the listing.</p>")

        return {"success": True, "valuation": valuation, "lead_id": lead.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
