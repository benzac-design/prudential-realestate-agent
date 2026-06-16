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


class AgentProfile(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    phone: str
    agency: Optional[str] = ""
    calendly_link: Optional[str] = ""
