from fastapi import APIRouter, HTTPException, Depends
import os

from app.models.schemas import ApplicationRecord, ApplicationScreenRequest
from app.services.claude_service import screen_rental_application
from app.services.supabase_service import (
    save_application, get_applications, update_application_screening,
)
from app.auth import require_dashboard_auth

router = APIRouter(prefix="/applications", tags=["applications"], dependencies=[Depends(require_dashboard_auth)])


def _screen(req) -> dict:
    agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")
    return screen_rental_application(
        applicant_name=req.applicant_name, address=req.address, weekly_rent=req.weekly_rent,
        annual_income=req.annual_income, employment=req.employment,
        rental_history=req.rental_history, references_note=req.references_note,
        notes=req.notes, agent_name=agent_name,
    )


@router.post("/screen")
async def screen_application(req: ApplicationScreenRequest):
    """Screen an applicant and return the score + recommendation WITHOUT saving.
    Used by the demo 'Try It Live' button and quick checks."""
    try:
        return {"success": True, **_screen(req)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def add_application(app: ApplicationRecord):
    """Register an applicant, run AI screening, and store the result."""
    try:
        result = _screen(app)
        data = app.model_dump(exclude={"save"}, exclude_none=True)
        data.update({
            "score": result["score"],
            "recommendation": result["recommendation"],
            "rationale": result["rationale"],
            "rent_to_income": result["rent_to_income"],
            "status": "screened",
        })
        if app.save:
            saved = save_application(data)
            return {"success": True, "application": saved, "flags": result.get("flags", [])}
        return {"success": True, "application": data, "flags": result.get("flags", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def list_applications(agent_id: str):
    """All applicants for an agent, ranked by score (best first)."""
    try:
        return {"success": True, "applications": get_applications(agent_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{application_id}/rescreen")
async def rescreen_application(application_id: str, req: ApplicationScreenRequest):
    """Re-run screening for an existing application (e.g. after new info)."""
    try:
        result = _screen(req)
        update_application_screening(application_id, {
            "score": result["score"], "recommendation": result["recommendation"],
            "rationale": result["rationale"], "rent_to_income": result["rent_to_income"],
            "status": "screened",
        })
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
