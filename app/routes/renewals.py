from fastapi import APIRouter, HTTPException
import os

from app.models.schemas import LeaseRenewalRequest
from app.services.claude_service import generate_lease_renewal_offer
from app.services.resend_service import send_email, text_to_html

router = APIRouter(prefix="/renewals", tags=["renewals"])


@router.post("/draft")
async def draft_renewal(req: LeaseRenewalRequest):
    """A lease is approaching its end date. AI recommends a retention-focused new rent
    and drafts a renewal offer message for the tenant. Returns the draft for the agent
    to review; emails the agent a copy if configured."""
    try:
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")

        result = generate_lease_renewal_offer(
            tenant_name=req.tenant_name,
            address=req.address,
            current_rent=req.current_rent,
            lease_end=req.lease_end,
            agent_name=agent_name,
            tenure=req.tenure,
            market_context=req.market_context,
            rent_period=req.rent_period or "week",
        )

        period = req.rent_period or "week"

        # Send the agent a review copy of the recommendation + draft.
        agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")
        if agent_email:
            send_email(
                agent_email,
                f"🔄 Lease renewal due — {req.address} ({req.tenant_name})",
                f"<p><b>Lease ends:</b> {req.lease_end}</p>"
                f"<p><b>Current rent:</b> ${req.current_rent:g}/{period}<br>"
                f"<b>Suggested rent:</b> ${float(result['suggested_rent']):g}/{period} "
                f"({result['change_pct']})<br>"
                f"<b>Retention risk:</b> {result['retention_risk']}</p>"
                f"<p><b>Why:</b> {result['rationale']}</p>"
                f"<hr><p><b>Draft offer to tenant (review before sending):</b></p>"
                f"{text_to_html(result['tenant_message'])}",
            )

        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
