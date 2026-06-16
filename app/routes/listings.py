from fastapi import APIRouter, HTTPException
from app.models.schemas import ListingRequest
from app.services.claude_service import generate_listing_description, audit_fair_housing_compliance
from app.services.supabase_service import save_listing, get_listings

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


@router.post("/save")
async def save_listing_route(request: ListingRequest, description: str, agent_id: str):
    try:
        data = request.model_dump()
        data["description"] = description
        data["agent_id"] = agent_id
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
