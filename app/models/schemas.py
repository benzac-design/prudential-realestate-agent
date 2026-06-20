from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class ListingRequest(BaseModel):
    address: str
    bedrooms: int
    bathrooms: float
    sqm: int
    price: int
    features: str
    neighborhood: Optional[str] = ""
    agent_name: Optional[str] = ""
    listing_type: Optional[str] = "sale"  # "sale" or "rental"


class LeadForm(BaseModel):
    name: str
    email: str
    phone: str
    message: Optional[str] = ""
    budget: Optional[str] = ""
    timeline: Optional[str] = ""
    agent_id: str


class Lead(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    phone: str
    message: Optional[str] = ""
    budget: Optional[str] = ""
    timeline: Optional[str] = ""
    pre_approved: Optional[bool] = None
    status: str = "new"
    agent_id: str
    created_at: Optional[datetime] = None


class FollowUpSequence(BaseModel):
    lead_id: str
    agent_id: str
    sequence_type: str = "cold_lead"


class ClientCriteria(BaseModel):
    client_id: str
    agent_id: str
    min_beds: int
    max_price: int
    areas: str
    property_type: str = "any"


class AppointmentRequest(BaseModel):
    lead_id: str
    agent_id: str
    scheduled_at: str          # ISO datetime
    location: Optional[str] = ""
    notes: Optional[str] = ""


class ValuationRequest(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    address: str
    bedrooms: int
    bathrooms: float
    sqm: int
    condition: Optional[str] = ""
    year_built: Optional[str] = ""
    recent_upgrades: Optional[str] = ""
    neighborhood: Optional[str] = ""
    agent_id: str


class AgentProfile(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    phone: str
    agency: Optional[str] = ""
    calendly_link: Optional[str] = ""
