from fastapi import APIRouter, HTTPException
from app.models.schemas import FollowUpSequence
from app.services.claude_service import generate_followup_sequence_message
from app.services.supabase_service import save_followup_schedule, get_leads
from datetime import datetime, timedelta

router = APIRouter(prefix="/followups", tags=["followups"])

SEQUENCE_DAYS = [3, 7, 14, 30, 60]


@router.post("/start")
async def start_followup_sequence(request: FollowUpSequence):
    try:
        leads = get_leads(request.agent_id)
        lead = next((l for l in leads if l["id"] == request.lead_id), None)

        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        lead_name = lead["name"]
        agent_name = "Your Agent"

        for day in SEQUENCE_DAYS:
            message = generate_followup_sequence_message(lead_name, agent_name, day)
            send_at = (datetime.utcnow() + timedelta(days=day)).isoformat()
            save_followup_schedule(
                lead_id=request.lead_id,
                agent_id=request.agent_id,
                send_at=send_at,
                message=message,
                channel="sms"
            )

        return {"success": True, "message": f"Follow-up sequence started — {len(SEQUENCE_DAYS)} messages scheduled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
