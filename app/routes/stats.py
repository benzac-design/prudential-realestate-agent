from fastapi import APIRouter, HTTPException

from app.services.supabase_service import get_agent_stats, get_leads_ranked

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/{agent_id}")
async def agent_stats(agent_id: str):
    """ROI dashboard numbers: leads, reply rate, qualified, hot, bookings."""
    try:
        return get_agent_stats(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/call-list")
async def call_list(agent_id: str, limit: int = 10):
    """Hottest leads first — the agent's prioritized call list."""
    try:
        ranked = get_leads_ranked(agent_id)[:limit]
        return [{
            "id": l["id"],
            "name": l.get("name"),
            "phone": l.get("phone"),
            "score": l.get("score", 0),
            "temperature": l.get("temperature", "cold"),
            "budget": l.get("budget"),
            "timeline": l.get("timeline"),
            "pre_approved": l.get("pre_approved"),
        } for l in ranked]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
