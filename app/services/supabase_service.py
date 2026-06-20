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


# ---- Two-way conversation ----

def get_lead_by_phone(phone: str) -> dict | None:
    """Find a lead by phone number, matching on the last 10 digits to dodge
    +1 / formatting differences."""
    db = get_client()
    digits = "".join(c for c in (phone or "") if c.isdigit())
    tail = digits[-10:] if len(digits) >= 10 else digits
    result = db.table("leads").select("*").ilike("phone", f"%{tail}%").order("created_at", desc=True).execute()
    rows = result.data or []
    return rows[0] if rows else None


def save_message(lead_id: str, agent_id: str, direction: str, body: str, channel: str = "sms"):
    db = get_client()
    db.table("messages").insert({
        "lead_id": lead_id,
        "agent_id": agent_id,
        "direction": direction,
        "body": body,
        "channel": channel,
    }).execute()


def get_conversation(lead_id: str, limit: int = 20) -> list:
    """Return recent messages oldest-first as chat turns for the model."""
    db = get_client()
    result = (
        db.table("messages").select("*")
        .eq("lead_id", lead_id).order("created_at", desc=True).limit(limit).execute()
    )
    rows = list(reversed(result.data or []))
    return [
        {"role": "user" if m["direction"] == "inbound" else "assistant", "content": m["body"]}
        for m in rows
    ]


def update_lead_fields(lead_id: str, fields: dict):
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return
    db = get_client()
    db.table("leads").update(fields).eq("id", lead_id).execute()


def mark_opted_out(lead_id: str):
    db = get_client()
    db.table("leads").update({"opted_out": True, "status": "opted_out"}).eq("id", lead_id).execute()


def cancel_pending_followups(lead_id: str) -> int:
    """Stop-on-reply: cancel any unsent scheduled follow-ups for this lead."""
    db = get_client()
    result = (
        db.table("followup_schedules").update({"sent": True})
        .eq("lead_id", lead_id).eq("sent", False).execute()
    )
    return len(result.data or [])


# ---- Appointments ----

def save_appointment(data: dict) -> dict:
    db = get_client()
    data["created_at"] = datetime.utcnow().isoformat()
    result = db.table("appointments").insert(data).execute()
    return result.data[0] if result.data else {}


def get_appointments(agent_id: str) -> list:
    db = get_client()
    result = (
        db.table("appointments").select("*, leads(name, phone, email)")
        .eq("agent_id", agent_id).order("scheduled_at").execute()
    )
    return result.data or []


def get_appointments_needing_reminder(within_hours: int = 24) -> list:
    """Upcoming appointments inside the reminder window that haven't been
    reminded yet."""
    db = get_client()
    now = datetime.utcnow()
    window_end = (now + timedelta(hours=within_hours)).isoformat()
    result = (
        db.table("appointments").select("*, leads(name, phone, email)")
        .eq("reminder_sent", False).eq("status", "scheduled")
        .gte("scheduled_at", now.isoformat()).lte("scheduled_at", window_end).execute()
    )
    return result.data or []


def mark_appointment_reminded(appointment_id: str):
    db = get_client()
    db.table("appointments").update({"reminder_sent": True}).eq("id", appointment_id).execute()


# ---- Analytics ----

def get_agent_stats(agent_id: str) -> dict:
    """Aggregate the numbers an agent needs to see the AI is earning its fee."""
    db = get_client()
    leads = db.table("leads").select("*").eq("agent_id", agent_id).execute().data or []
    appts = db.table("appointments").select("id, status").eq("agent_id", agent_id).execute().data or []
    msgs = db.table("messages").select("direction").eq("agent_id", agent_id).execute().data or []

    total = len(leads)
    engaged = sum(1 for l in leads if (l.get("conversation_stage") or "new") != "new")
    qualified = sum(1 for l in leads if l.get("budget") or l.get("timeline") or l.get("pre_approved"))
    opted_out = sum(1 for l in leads if l.get("opted_out"))
    hot = sum(1 for l in leads if l.get("temperature") == "hot")
    inbound = sum(1 for m in msgs if m["direction"] == "inbound")
    outbound = sum(1 for m in msgs if m["direction"] == "outbound")

    return {
        "total_leads": total,
        "engaged": engaged,
        "qualified": qualified,
        "hot_leads": hot,
        "opted_out": opted_out,
        "reply_rate": round(engaged / total * 100, 1) if total else 0.0,
        "messages_sent": outbound,
        "messages_received": inbound,
        "appointments_booked": len(appts),
        "appointments_completed": sum(1 for a in appts if a["status"] == "completed"),
    }


def get_leads_ranked(agent_id: str) -> list:
    """Leads sorted hottest-first, for the agent's call list."""
    leads = get_leads(agent_id)
    return sorted(leads, key=lambda l: l.get("score") or 0, reverse=True)


def _parse_budget(text: str) -> float | None:
    """Extract a dollar amount from a budget string like '$400k', '400,000', '1.2m'."""
    import re
    if not text:
        return None
    s = text.lower().replace(",", "").replace("$", "").strip()
    m = re.search(r"([\d.]+)\s*([mk]?)", s)
    if not m:
        return None
    num = float(m.group(1))
    suffix = m.group(2)
    if suffix == "k":
        num *= 1_000
    elif suffix == "m":
        num *= 1_000_000
    return num


def find_matching_leads(agent_id: str, listing_price: int, bedrooms: int, tolerance: float = 0.15) -> list:
    """Return leads whose budget is within tolerance of the listing price and who
    haven't opted out. Leads with no budget are included (can't rule them out)."""
    leads = get_leads(agent_id)
    matches = []
    for lead in leads:
        if lead.get("opted_out"):
            continue
        budget = _parse_budget(lead.get("budget") or "")
        if budget is None:
            # No budget on file — include anyway, they might be interested
            matches.append(lead)
            continue
        # Budget is within tolerance above or below listing price
        low = listing_price * (1 - tolerance)
        high = listing_price * (1 + tolerance)
        if low <= budget <= high:
            matches.append(lead)
    return matches


def get_leads_for_reengagement(agent_id: str, segment: str) -> list:
    """Return leads matching a re-engagement segment, excluding opted-out leads."""
    leads = get_leads(agent_id)
    active = [l for l in leads if not l.get("opted_out")]
    if segment == "cold":
        return [l for l in active if (l.get("score") or 0) < 40 and (l.get("conversation_stage") or "new") == "new"]
    if segment == "dormant":
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        return [l for l in active if (l.get("created_at") or "") < cutoff and (l.get("conversation_stage") or "new") == "new"]
    if segment == "unqualified":
        engaged_stages = {"engaged", "qualifying"}
        return [l for l in active if (l.get("conversation_stage") or "new") in engaged_stages
                and not l.get("budget") and not l.get("timeline")]
    return []
