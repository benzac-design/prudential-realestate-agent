from supabase import create_client
import os
from datetime import datetime, timedelta, date

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


def get_followups(agent_id: str) -> list:
    """All scheduled follow-ups for an agent (with the lead they belong to),
    soonest-first — powers the /live Follow-ups tab."""
    db = get_client()
    result = (
        db.table("followup_schedules").select("*, leads(name, phone, email)")
        .eq("agent_id", agent_id).order("send_at", desc=False).execute()
    )
    return result.data or []


def get_seller_leads(agent_id: str) -> list:
    """Leads captured via the home-valuation lead magnet, newest-first — powers
    the /live Seller Valuations tab. Identified by their valuation enquiry
    message (the `leads` table has no lead_type column)."""
    db = get_client()
    result = (
        db.table("leads").select("*").eq("agent_id", agent_id)
        .ilike("message", "%valuation%").order("created_at", desc=True).execute()
    )
    return result.data or []


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


# ---- Leases / renewals ----

def save_lease(data: dict) -> dict:
    db = get_client()
    result = db.table("leases").insert(data).execute()
    return result.data[0] if result.data else {}


def get_leases(agent_id: str) -> list:
    db = get_client()
    result = (
        db.table("leases").select("*")
        .eq("agent_id", agent_id).order("lease_end").execute()
    )
    return result.data or []


def get_leases_needing_renewal(days_min: int = 60, days_max: int = 90) -> list:
    """Active leases whose end date falls inside the renewal window (default 60-90
    days out) and that haven't been flagged for renewal yet."""
    db = get_client()
    today = date.today()
    window_start = (today + timedelta(days=days_min)).isoformat()
    window_end = (today + timedelta(days=days_max)).isoformat()
    result = (
        db.table("leases").select("*")
        .eq("status", "active").eq("renewal_flagged", False)
        .gte("lease_end", window_start).lte("lease_end", window_end)
        .order("lease_end").execute()
    )
    return result.data or []


def mark_lease_renewal_flagged(lease_id: str):
    db = get_client()
    db.table("leases").update({"renewal_flagged": True}).eq("id", lease_id).execute()


# ---- Rent / arrears ----

def save_rent_payment(data: dict) -> dict:
    db = get_client()
    result = db.table("rent_payments").insert(data).execute()
    return result.data[0] if result.data else {}


def get_rent_payments(agent_id: str) -> list:
    db = get_client()
    result = (
        db.table("rent_payments").select("*")
        .eq("agent_id", agent_id).order("due_date").execute()
    )
    return result.data or []


def get_rent_due_for_reminder(within_days: int = 3) -> list:
    """Pending payments due within the next `within_days` days that haven't been
    reminded yet (and aren't already overdue)."""
    db = get_client()
    today = date.today()
    window_end = (today + timedelta(days=within_days)).isoformat()
    result = (
        db.table("rent_payments").select("*")
        .eq("status", "pending").eq("reminder_sent", False)
        .gte("due_date", today.isoformat()).lte("due_date", window_end)
        .order("due_date").execute()
    )
    return result.data or []


def get_overdue_rent() -> list:
    """Pending payments whose due date has passed and that haven't been alerted yet."""
    db = get_client()
    today = date.today()
    result = (
        db.table("rent_payments").select("*")
        .eq("status", "pending").eq("overdue_alert_sent", False)
        .lt("due_date", today.isoformat())
        .order("due_date").execute()
    )
    return result.data or []


def mark_rent_reminder_sent(payment_id: str):
    db = get_client()
    db.table("rent_payments").update({"reminder_sent": True}).eq("id", payment_id).execute()


def mark_rent_overdue_alerted(payment_id: str):
    db = get_client()
    db.table("rent_payments").update(
        {"status": "overdue", "overdue_alert_sent": True}
    ).eq("id", payment_id).execute()


def mark_rent_paid(payment_id: str):
    db = get_client()
    db.table("rent_payments").update(
        {"status": "paid", "paid_date": date.today().isoformat()}
    ).eq("id", payment_id).execute()


# ---- Routine inspections ----

def _add_months(d: date, months: int) -> date:
    """Add whole months to a date, clamping the day to the target month's length."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    # Clamp day (e.g. Jan 31 + 1 month -> Feb 28/29).
    next_month_start = date(year + (month // 12), (month % 12) + 1, 1) if month < 12 else date(year + 1, 1, 1)
    last_day = (next_month_start - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day))


def save_inspection(data: dict) -> dict:
    db = get_client()
    result = db.table("inspections").insert(data).execute()
    return result.data[0] if result.data else {}


def get_inspections(agent_id: str) -> list:
    db = get_client()
    result = (
        db.table("inspections").select("*")
        .eq("agent_id", agent_id).order("next_inspection_date").execute()
    )
    return result.data or []


def get_inspections_needing_notice(within_days: int = 14) -> list:
    """Scheduled inspections coming up within the notice window that haven't had
    a tenant notice sent yet."""
    db = get_client()
    today = date.today()
    window_end = (today + timedelta(days=within_days)).isoformat()
    result = (
        db.table("inspections").select("*")
        .eq("status", "scheduled").eq("notice_sent", False)
        .gte("next_inspection_date", today.isoformat())
        .lte("next_inspection_date", window_end)
        .order("next_inspection_date").execute()
    )
    return result.data or []


def mark_inspection_notice_sent(inspection_id: str):
    db = get_client()
    db.table("inspections").update(
        {"notice_sent": True, "status": "notice_sent"}
    ).eq("id", inspection_id).execute()


def complete_inspection(inspection_id: str) -> dict:
    """Mark an inspection done and auto-schedule the next one frequency_months out."""
    db = get_client()
    rows = db.table("inspections").select("*").eq("id", inspection_id).execute().data or []
    if not rows:
        return {}
    insp = rows[0]
    freq = insp.get("frequency_months") or 6
    try:
        base = date.fromisoformat(str(insp["next_inspection_date"]))
    except (ValueError, TypeError):
        base = date.today()
    next_date = _add_months(date.today() if base < date.today() else base, freq)
    db.table("inspections").update({
        "last_completed": date.today().isoformat(),
        "next_inspection_date": next_date.isoformat(),
        "status": "scheduled",
        "notice_sent": False,
    }).eq("id", inspection_id).execute()
    return {"next_inspection_date": next_date.isoformat()}


# ---- Maintenance jobs ----

_URGENCY_RANK = {"emergency": 0, "urgent": 1, "routine": 2}


def save_maintenance_request(data: dict) -> dict:
    db = get_client()
    result = db.table("maintenance_requests").insert(data).execute()
    return result.data[0] if result.data else {}


def get_maintenance_requests(agent_id: str) -> list:
    """Open jobs first, most urgent first; resolved jobs sink to the bottom."""
    db = get_client()
    rows = db.table("maintenance_requests").select("*").eq("agent_id", agent_id).execute().data or []
    return sorted(rows, key=lambda r: (
        r.get("status") == "resolved",
        _URGENCY_RANK.get(r.get("urgency"), 3),
        r.get("created_at") or "",
    ))


def update_maintenance_status(request_id: str, status: str, assigned_to: str = None):
    db = get_client()
    fields = {"status": status}
    if assigned_to is not None:
        fields["assigned_to"] = assigned_to
    if status == "resolved":
        fields["resolved_at"] = datetime.utcnow().isoformat()
    db.table("maintenance_requests").update(fields).eq("id", request_id).execute()


# ---- Rental applications ----

def save_application(data: dict) -> dict:
    db = get_client()
    result = db.table("applications").insert(data).execute()
    return result.data[0] if result.data else {}


def get_applications(agent_id: str) -> list:
    """Applications for an agent, highest score first (unscored last)."""
    db = get_client()
    rows = db.table("applications").select("*").eq("agent_id", agent_id).execute().data or []
    return sorted(rows, key=lambda a: (a.get("score") is not None, a.get("score") or 0), reverse=True)


def update_application_screening(application_id: str, fields: dict):
    db = get_client()
    db.table("applications").update(fields).eq("id", application_id).execute()


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


def get_rental_stats(agent_id: str) -> dict:
    """Rental-portfolio numbers for the monthly report: arrears, inspections and
    lease renewals coming due."""
    db = get_client()
    today = date.today()

    payments = db.table("rent_payments").select("amount, status, due_date").eq("agent_id", agent_id).execute().data or []
    arrears = [p for p in payments if p.get("status") == "overdue"
               or (p.get("status") == "pending" and str(p.get("due_date", "")) < today.isoformat())]
    arrears_amount = sum(float(p.get("amount") or 0) for p in arrears)

    insp_window = (today + timedelta(days=30)).isoformat()
    inspections = db.table("inspections").select("id").eq("agent_id", agent_id) \
        .neq("status", "completed").lte("next_inspection_date", insp_window).execute().data or []

    lease_window = (today + timedelta(days=90)).isoformat()
    renewals = db.table("leases").select("id").eq("agent_id", agent_id) \
        .eq("status", "active").lte("lease_end", lease_window).execute().data or []

    return {
        "arrears_count": len(arrears),
        "arrears_amount": arrears_amount,
        "inspections_due": len(inspections),
        "renewals_due": len(renewals),
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
