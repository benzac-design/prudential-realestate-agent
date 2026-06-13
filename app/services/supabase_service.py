from supabase import create_client
import os
from datetime import datetime

_client = None


def get_client():
    global _client
    if _client is None:
        _client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return _client


def save_lead(lead_data: dict) -> dict:
    db = get_client()
    lead_data["created_at"] = datetime.utcnow().isoformat()
    result = db.table("leads").insert(lead_data).execute()
    return result.data[0] if result.data else {}


def get_leads(agent_id: str) -> list:
    db = get_client()
    result = db.table("leads").select("*").eq("agent_id", agent_id).order("created_at", desc=True).execute()
    return result.data or []


def update_lead_status(lead_id: str, status: str):
    db = get_client()
    db.table("leads").update({"status": status}).eq("id", lead_id).execute()


def save_followup_schedule(lead_id: str, agent_id: str, send_at: str, message: str, channel: str):
    db = get_client()
    db.table("followup_schedules").insert({
        "lead_id": lead_id,
        "agent_id": agent_id,
        "send_at": send_at,
        "message": message,
        "channel": channel,
        "sent": False,
    }).execute()


def get_pending_followups() -> list:
    db = get_client()
    now = datetime.utcnow().isoformat()
    result = db.table("followup_schedules").select("*, leads(*)").eq("sent", False).lte("send_at", now).execute()
    return result.data or []


def mark_followup_sent(followup_id: str):
    db = get_client()
    db.table("followup_schedules").update({"sent": True}).eq("id", followup_id).execute()


def get_clients_for_update(agent_id: str) -> list:
    db = get_client()
    result = db.table("buyer_clients").select("*").eq("agent_id", agent_id).execute()
    return result.data or []


def save_listing(listing_data: dict) -> dict:
    db = get_client()
    listing_data["created_at"] = datetime.utcnow().isoformat()
    result = db.table("listings").insert(listing_data).execute()
    return result.data[0] if result.data else {}


def get_listings(agent_id: str) -> list:
    db = get_client()
    result = db.table("listings").select("*").eq("agent_id", agent_id).order("created_at", desc=True).execute()
    return result.data or []
