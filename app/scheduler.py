import os
from datetime import date

from app.services.supabase_service import (
    get_pending_followups, mark_followup_sent,
    get_appointments_needing_reminder, mark_appointment_reminded,
    get_leases_needing_renewal, mark_lease_renewal_flagged,
    get_rent_due_for_reminder, get_overdue_rent,
    mark_rent_reminder_sent, mark_rent_overdue_alerted,
    get_inspections_needing_notice, mark_inspection_notice_sent,
)
from app.services.twilio_service import send_sms
from app.services.resend_service import send_email, text_to_html
from app.services.claude_service import (
    generate_lease_renewal_offer, generate_rent_reminder, generate_arrears_notice,
    generate_inspection_notice,
)


def _notify_tenant(payment: dict, message: str, email_subject: str):
    """Send a tenant message over SMS if we have a phone, else email. Returns the
    channel used (or None). SMS may be blocked (Twilio) — email is the fallback."""
    if payment.get("tenant_phone"):
        send_sms(payment["tenant_phone"], message)
        return "sms"
    if payment.get("tenant_email"):
        send_email(payment["tenant_email"], email_subject, text_to_html(message))
        return "email"
    return None


async def send_appointment_reminders():
    """Text + email a reminder the day before, to cut no-shows."""
    for appt in get_appointments_needing_reminder(within_hours=24):
        lead = appt.get("leads", {})
        when = appt["scheduled_at"]
        where = appt.get("location") or "the agreed location"
        msg = f"Reminder: your viewing is coming up at {when} at {where}. Reply if you need to reschedule."

        if lead.get("phone"):
            send_sms(lead["phone"], msg)
        if lead.get("email"):
            send_email(lead["email"], "Reminder: your viewing tomorrow", text_to_html(msg))

        mark_appointment_reminded(appt["id"])


async def process_pending_followups():
    followups = get_pending_followups()
    for followup in followups:
        lead = followup.get("leads", {})
        message = followup["message"]
        channel = followup["channel"]

        # Never message a lead who has opted out.
        if lead.get("opted_out"):
            mark_followup_sent(followup["id"])
            continue

        if channel == "sms" and lead.get("phone"):
            send_sms(lead["phone"], message)
        elif channel == "email" and lead.get("email"):
            send_email(lead["email"], "A message from your agent", text_to_html(message))

        mark_followup_sent(followup["id"])


async def process_lease_renewals():
    """Monitor lease end dates: for each active lease 60-90 days from expiry that
    hasn't been flagged yet, draft a retention-focused renewal offer and email the
    agent to review. Flags the lease so it's only actioned once."""
    agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")
    agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")

    for lease in get_leases_needing_renewal(days_min=60, days_max=90):
        period = lease.get("rent_period") or "week"
        result = generate_lease_renewal_offer(
            tenant_name=lease["tenant_name"],
            address=lease["address"],
            current_rent=lease["current_rent"],
            lease_end=lease["lease_end"],
            agent_name=agent_name,
            tenure=lease.get("tenure", ""),
            market_context=lease.get("market_context", ""),
            rent_period=period,
        )

        if agent_email:
            send_email(
                agent_email,
                f"🔄 Lease renewal due — {lease['address']} ({lease['tenant_name']})",
                f"<p><b>Lease ends:</b> {lease['lease_end']}</p>"
                f"<p><b>Current rent:</b> ${float(lease['current_rent']):g}/{period}<br>"
                f"<b>Suggested rent:</b> ${float(result['suggested_rent']):g}/{period} "
                f"({result['change_pct']})<br>"
                f"<b>Retention risk:</b> {result['retention_risk']}</p>"
                f"<p><b>Why:</b> {result['rationale']}</p>"
                f"<hr><p><b>Draft offer to tenant (review before sending):</b></p>"
                f"{text_to_html(result['tenant_message'])}",
            )

        mark_lease_renewal_flagged(lease["id"])


async def process_rent_arrears():
    """Rent monitor: (1) remind tenants of rent due within the next 3 days, and
    (2) detect overdue rent (arrears) — message the tenant and alert the agent.
    Each payment is actioned once (reminder_sent / overdue_alert_sent flags)."""
    agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")
    agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")
    today = date.today()

    # 1. Upcoming-rent reminders.
    for p in get_rent_due_for_reminder(within_days=3):
        msg = generate_rent_reminder(
            tenant_name=p["tenant_name"], address=p["address"],
            amount=float(p["amount"]), due_date=p["due_date"],
            agent_name=agent_name, rent_period=p.get("rent_period", "week"),
        )
        _notify_tenant(p, msg, "Rent reminder")
        mark_rent_reminder_sent(p["id"])

    # 2. Overdue rent (arrears).
    for p in get_overdue_rent():
        try:
            days_overdue = (today - date.fromisoformat(str(p["due_date"]))).days
        except (ValueError, TypeError):
            days_overdue = 0
        msg = generate_arrears_notice(
            tenant_name=p["tenant_name"], address=p["address"],
            amount=float(p["amount"]), days_overdue=days_overdue,
            agent_name=agent_name, rent_period=p.get("rent_period", "week"),
        )
        channel = _notify_tenant(p, msg, "Overdue rent")

        if agent_email:
            send_email(
                agent_email,
                f"⚠️ Rent arrears — {p['address']} ({p['tenant_name']})",
                f"<p><b>{p['tenant_name']}</b> at <b>{p['address']}</b> is "
                f"<b>{days_overdue} day(s) overdue</b>.</p>"
                f"<p><b>Amount owing:</b> ${float(p['amount']):g}/{p.get('rent_period','week')}<br>"
                f"<b>Due date:</b> {p['due_date']}</p>"
                f"<p>Tenant contacted via: {channel or 'no contact on file'}.</p>"
                f"<hr><p><b>Message sent to tenant:</b></p>{text_to_html(msg)}",
            )

        mark_rent_overdue_alerted(p["id"])


async def process_inspections():
    """Routine-inspection monitor: for each scheduled inspection coming up within
    the notice window (14 days) that hasn't been noticed yet, draft and send the
    tenant a compliant advance notice and alert the agent. Actioned once."""
    agent_name = os.getenv("DEFAULT_AGENT_NAME", "Your Property Manager")
    agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")

    for insp in get_inspections_needing_notice(within_days=14):
        msg = generate_inspection_notice(
            tenant_name=insp["tenant_name"], address=insp["address"],
            inspection_date=insp["next_inspection_date"], agent_name=agent_name,
        )
        channel = _notify_tenant(insp, msg, "Routine inspection notice")

        if agent_email:
            send_email(
                agent_email,
                f"🏠 Inspection due — {insp['address']} ({insp['tenant_name']})",
                f"<p>Routine inspection for <b>{insp['tenant_name']}</b> at "
                f"<b>{insp['address']}</b> is scheduled for "
                f"<b>{insp['next_inspection_date']}</b>.</p>"
                f"<p>Tenant notice sent via: {channel or 'no contact on file'}.</p>"
                f"<hr><p><b>Notice sent to tenant:</b></p>{text_to_html(msg)}",
            )

        mark_inspection_notice_sent(insp["id"])
