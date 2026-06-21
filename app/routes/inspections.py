from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

from app.models.schemas import InspectionRecord
from app.services.supabase_service import (
    save_inspection, get_inspections, get_inspections_needing_notice,
    complete_inspection,
)
from app.services.claude_service import generate_inspection_notice
from app.scheduler import process_inspections

router = APIRouter(prefix="/inspections", tags=["inspections"])


class InspectionNoticeRequest(BaseModel):
    tenant_name: str
    address: str
    inspection_date: str


@router.post("/draft-notice")
async def draft_inspection_notice(req: InspectionNoticeRequest):
    """Draft (without sending) a tenant inspection notice — used by the demo and
    for agent review."""
    try:
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")
        message = generate_inspection_notice(
            tenant_name=req.tenant_name, address=req.address,
            inspection_date=req.inspection_date, agent_name=agent_name,
        )
        return {"success": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def add_inspection(inspection: InspectionRecord):
    """Schedule a routine inspection so the agent can auto-notice the tenant in advance."""
    try:
        saved = save_inspection(inspection.model_dump(exclude_none=True))
        return {"success": True, "inspection": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/due")
async def inspections_due():
    """Preview inspections inside the 14-day notice window not yet noticed."""
    try:
        return {"success": True, "inspections": get_inspections_needing_notice()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def list_inspections(agent_id: str):
    try:
        return {"success": True, "inspections": get_inspections(agent_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{inspection_id}/complete")
async def complete(inspection_id: str):
    """Mark an inspection done; auto-schedules the next one frequency_months out."""
    try:
        result = complete_inspection(inspection_id)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_inspections():
    """Manually trigger the inspection-notice monitor (also runs daily via cron)."""
    try:
        await process_inspections()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
