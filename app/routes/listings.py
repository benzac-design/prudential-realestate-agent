from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.models.schemas import ListingRequest
from app.services.claude_service import generate_listing_description, audit_fair_housing_compliance, generate_property_match_sms
from app.services.supabase_service import save_listing, get_listings, find_matching_leads, save_message
from app.services.twilio_service import send_sms
import os

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("/generate")
async def generate_listing(request: ListingRequest):
    try:
        description = generate_listing_description(
            address=request.address,
            bedrooms=request.bedrooms,
            bathrooms=request.bathrooms,
            sqm=request.sqm,
            price=request.price,
            features=request.features,
            neighborhood=request.neighborhood,
            agent_name=request.agent_name,
            listing_type=request.listing_type,
        )
        compliance = audit_fair_housing_compliance(description)
        passed = compliance.startswith("RESULT: PASS")
        return {"success": True, "description": description, "compliance": compliance, "compliance_passed": passed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AuditRequest(BaseModel):
    description: str


@router.post("/audit")
async def audit_listing(request: AuditRequest):
    """Run a Fair Housing Act compliance check on any listing description."""
    try:
        compliance = audit_fair_housing_compliance(request.description)
        passed = compliance.startswith("RESULT: PASS")
        return {"success": True, "compliance": compliance, "compliance_passed": passed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_listing_route(request: ListingRequest, description: str, agent_id: str):
    try:
        req = request.model_dump()
        # The request schema carries fields the Supabase `listings` table doesn't
        # have (agent_name, listing_type, and `sqm` which maps to the `sqft`
        # column). Build an insert with only real columns so it doesn't 500.
        data = {
            "agent_id": agent_id,
            "address": req.get("address"),
            "bedrooms": req.get("bedrooms"),
            "bathrooms": req.get("bathrooms"),
            "sqft": req.get("sqm"),
            "price": req.get("price"),
            "features": req.get("features"),
            "neighborhood": req.get("neighborhood"),
            "description": description,
        }
        result = save_listing(data)
        return {"success": True, "listing": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def list_listings(agent_id: str):
    try:
        listings = get_listings(agent_id)
        return {"success": True, "listings": listings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MatchRequest(BaseModel):
    agent_id: str
    address: str
    price: int
    bedrooms: int
    bathrooms: float
    features: str = ""
    neighborhood: str = ""
    send_sms: bool = False  # if True, fire the SMS blast


def _blast_matches(leads: list, listing: dict, agent_name: str):
    for lead in leads:
        if not lead.get("phone"):
            continue
        msg = generate_property_match_sms(lead, listing, agent_name)
        send_sms(lead["phone"], msg)
        save_message(lead["id"], listing.get("agent_id", "default"), "outbound", msg)


@router.post("/match-leads")
async def match_leads(req: MatchRequest, background_tasks: BackgroundTasks):
    """Find leads whose budget matches a listing price and optionally SMS them all."""
    try:
        listing = req.model_dump()
        matches = find_matching_leads(req.agent_id, req.price, req.bedrooms)
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Agent")

        if req.send_sms:
            background_tasks.add_task(_blast_matches, matches, listing, agent_name)

        return {
            "success": True,
            "matched": len(matches),
            "sms_queued": req.send_sms,
            "leads": [{
                "id": l["id"],
                "name": l.get("name"),
                "phone": l.get("phone"),
                "budget": l.get("budget"),
                "temperature": l.get("temperature", "cold"),
                "score": l.get("score", 0),
            } for l in matches],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
