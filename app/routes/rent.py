from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

from app.models.schemas import RentPaymentRecord
from app.services.supabase_service import (
    save_rent_payment, get_rent_payments, get_rent_due_for_reminder,
    get_overdue_rent, mark_rent_paid,
)
from app.services.claude_service import generate_arrears_notice
from app.scheduler import process_rent_arrears

router = APIRouter(prefix="/rent", tags=["rent"])


class ArrearsNoticeRequest(BaseModel):
    tenant_name: str
    address: str
    amount: float
    days_overdue: int
    rent_period: str = "week"


@router.post("/draft-notice")
async def draft_arrears_notice(req: ArrearsNoticeRequest):
    """Draft (without sending) a tenant arrears notice — used by the demo and for
    agent review."""
    try:
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")
        message = generate_arrears_notice(
            tenant_name=req.tenant_name, address=req.address, amount=req.amount,
            days_overdue=req.days_overdue, agent_name=agent_name,
            rent_period=req.rent_period,
        )
        return {"success": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payments")
async def add_rent_payment(payment: RentPaymentRecord):
    """Register an expected rent payment so the agent can remind the tenant before
    it's due and detect arrears if it's missed."""
    try:
        saved = save_rent_payment(payment.model_dump(exclude_none=True))
        return {"success": True, "payment": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payments/{agent_id}")
async def list_rent_payments(agent_id: str):
    try:
        return {"success": True, "payments": get_rent_payments(agent_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/arrears")
async def rent_arrears():
    """Preview overdue rent (arrears) and upcoming rent due within 3 days."""
    try:
        return {
            "success": True,
            "overdue": get_overdue_rent(),
            "due_soon": get_rent_due_for_reminder(within_days=3),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/payments/{payment_id}/paid")
async def mark_paid(payment_id: str):
    try:
        mark_rent_paid(payment_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_rent_monitor():
    """Manually trigger the rent reminder + arrears monitor (also runs daily via cron)."""
    try:
        await process_rent_arrears()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
