from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime
import os

from app.services.supabase_service import get_agent_stats, get_leads_ranked, get_rental_stats
from app.services.resend_service import send_email

router = APIRouter(prefix="/reports", tags=["reports"])


def _build_report_html(stats: dict, top_leads: list, agent_name: str, agency: str, month_label: str, rental: dict = None) -> str:
    rental = rental or {}
    arrears_count   = rental.get("arrears_count", 0)
    arrears_amount  = rental.get("arrears_amount", 0)
    inspections_due = rental.get("inspections_due", 0)
    renewals_due    = rental.get("renewals_due", 0)
    arrears_amount_str = f"${arrears_amount:,.0f}"
    total       = stats.get("total_leads", 0)
    engaged     = stats.get("engaged", 0)
    qualified   = stats.get("qualified", 0)
    hot         = stats.get("hot_leads", 0)
    opted_out   = stats.get("opted_out", 0)
    reply_rate  = stats.get("reply_rate", 0)
    sent        = stats.get("messages_sent", 0)
    received    = stats.get("messages_received", 0)
    booked      = stats.get("appointments_booked", 0)
    completed   = stats.get("appointments_completed", 0)

    # Rough time-saved estimate: 8 min per outbound message vs typing manually
    minutes_saved = sent * 8
    hours_saved   = round(minutes_saved / 60, 1)

    # Commission opportunity: assume avg deal = $500k, 2.5% buyer commission
    # Hot leads are roughly "ready to transact" — conservative 10% close rate
    commission_opportunity = hot * 500_000 * 0.025 * 0.10
    commission_str = f"${commission_opportunity:,.0f}"

    def lead_rows() -> str:
        if not top_leads:
            return "<tr><td colspan='4' style='text-align:center;color:#888;'>No leads yet</td></tr>"
        rows = []
        for l in top_leads[:10]:
            score = l.get("score", 0)
            temp  = l.get("temperature", "cold")
            color_map = {"hot": "#b91c1c", "warm": "#c2410c", "cold": "#4b5563", "dead": "#9ca3af"}
            temp_color = color_map.get(temp, "#4b5563")
            bg_map = {"hot": "#fee2e2", "warm": "#ffedd5", "cold": "#f3f4f6", "dead": "#f9fafb"}
            temp_bg = bg_map.get(temp, "#f3f4f6")
            budget = l.get("budget") or "—"
            timeline = l.get("timeline") or "—"
            rows.append(
                f"<tr>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #f5f5f5;font-weight:600;'>{l.get('name','Unknown')}</td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #f5f5f5;'>"
                f"<span style='background:{temp_bg};color:{temp_color};padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;'>{temp}</span>"
                f"&nbsp;<span style='font-size:13px;color:#666;'>{score}/100</span></td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #f5f5f5;font-size:13px;color:#555;'>{budget}</td>"
                f"<td style='padding:10px 14px;border-bottom:1px solid #f5f5f5;font-size:13px;color:#555;'>{timeline}</td>"
                f"</tr>"
            )
        return "".join(rows)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<title>AI Agent Monthly Report — {month_label}</title>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:680px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

  <!-- Header -->
  <div style="background:#1a1a2e;padding:32px 40px;">
    <div style="color:#fff;font-size:22px;font-weight:700;">Real Estate <span style="color:#4f8ef7;">AI</span> Agent</div>
    <div style="color:#8892a4;font-size:14px;margin-top:6px;">Monthly Performance Report — {month_label}</div>
    <div style="color:#fff;font-size:16px;margin-top:16px;">Hi {agent_name} 👋</div>
    <div style="color:#8892a4;font-size:14px;margin-top:4px;">Here's everything your AI did for you this month at {agency}.</div>
  </div>

  <!-- Key numbers -->
  <div style="padding:32px 40px;">
    <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:20px;">This Month At a Glance</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;">
      <div style="background:#f8faff;border-radius:12px;padding:18px;border:1px solid #eef2ff;">
        <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Messages Sent</div>
        <div style="font-size:36px;font-weight:700;color:#1a1a2e;margin:8px 0 4px;">{sent}</div>
        <div style="font-size:12px;color:#4f8ef7;">By AI, not you</div>
      </div>
      <div style="background:#f8faff;border-radius:12px;padding:18px;border:1px solid #eef2ff;">
        <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Replies Received</div>
        <div style="font-size:36px;font-weight:700;color:#1a1a2e;margin:8px 0 4px;">{received}</div>
        <div style="font-size:12px;color:#22c55e;">{reply_rate}% reply rate</div>
      </div>
      <div style="background:#f8faff;border-radius:12px;padding:18px;border:1px solid #eef2ff;">
        <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Hours Saved</div>
        <div style="font-size:36px;font-weight:700;color:#1a1a2e;margin:8px 0 4px;">{hours_saved}</div>
        <div style="font-size:12px;color:#22c55e;">vs. doing it manually</div>
      </div>
    </div>

    <!-- Divider -->
    <div style="border-top:1px solid #f0f0f0;margin:28px 0;"></div>

    <!-- Lead pipeline -->
    <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:20px;">Lead Pipeline</div>
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;">
          <span style="font-size:14px;color:#555;">Total Leads</span>
        </td>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;text-align:right;">
          <span style="font-weight:700;font-size:18px;">{total}</span>
        </td>
      </tr>
      <tr>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;">
          <span style="font-size:14px;color:#555;">Engaged with AI</span>
        </td>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;text-align:right;">
          <span style="font-weight:700;font-size:18px;color:#166534;">{engaged}</span>
        </td>
      </tr>
      <tr>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;">
          <span style="font-size:14px;color:#555;">Qualified (budget + timeline)</span>
        </td>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;text-align:right;">
          <span style="font-weight:700;font-size:18px;color:#92400e;">{qualified}</span>
        </td>
      </tr>
      <tr>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;">
          <span style="font-size:14px;color:#555;">🔥 Hot Leads (score ≥ 70)</span>
        </td>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;text-align:right;">
          <span style="font-weight:700;font-size:18px;color:#b91c1c;">{hot}</span>
        </td>
      </tr>
      <tr>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;">
          <span style="font-size:14px;color:#555;">Showings Booked</span>
        </td>
        <td style="padding:12px 0;border-bottom:1px solid #f5f5f5;text-align:right;">
          <span style="font-weight:700;font-size:18px;color:#1d4ed8;">{booked}</span>
        </td>
      </tr>
      <tr>
        <td style="padding:12px 0;">
          <span style="font-size:14px;color:#555;">Showings Completed</span>
        </td>
        <td style="padding:12px 0;text-align:right;">
          <span style="font-weight:700;font-size:18px;">{completed}</span>
        </td>
      </tr>
    </table>

    <!-- Divider -->
    <div style="border-top:1px solid #f0f0f0;margin:28px 0;"></div>

    <!-- Rental portfolio -->
    <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:20px;">Rental Portfolio — Managed Automatically</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;">
      <div style="background:#fff7ed;border-radius:12px;padding:18px;border:1px solid #fed7aa;">
        <div style="font-size:11px;color:#9a3412;text-transform:uppercase;letter-spacing:0.5px;">Rent Arrears</div>
        <div style="font-size:36px;font-weight:700;color:#9a3412;margin:8px 0 4px;">{arrears_count}</div>
        <div style="font-size:12px;color:#c2410c;">{arrears_amount_str} outstanding — AI chasing</div>
      </div>
      <div style="background:#f0f9ff;border-radius:12px;padding:18px;border:1px solid #bae6fd;">
        <div style="font-size:11px;color:#075985;text-transform:uppercase;letter-spacing:0.5px;">Inspections Due</div>
        <div style="font-size:36px;font-weight:700;color:#075985;margin:8px 0 4px;">{inspections_due}</div>
        <div style="font-size:12px;color:#0369a1;">Next 30 days — notices auto-sent</div>
      </div>
      <div style="background:#f0fdf4;border-radius:12px;padding:18px;border:1px solid #bbf7d0;">
        <div style="font-size:11px;color:#166534;text-transform:uppercase;letter-spacing:0.5px;">Renewals Due</div>
        <div style="font-size:36px;font-weight:700;color:#166534;margin:8px 0 4px;">{renewals_due}</div>
        <div style="font-size:12px;color:#15803d;">Next 90 days — none missed</div>
      </div>
    </div>

    <!-- Commission opportunity banner -->
    <div style="background:linear-gradient(135deg,#1a1a2e,#252d42);border-radius:12px;padding:20px 24px;margin-top:28px;">
      <div style="color:#8892a4;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Commission Opportunity in Pipeline</div>
      <div style="color:#fff;font-size:38px;font-weight:700;margin:8px 0;">{commission_str}</div>
      <div style="color:#4f8ef7;font-size:13px;">Based on {hot} hot leads × conservative 10% close rate × $500k avg deal</div>
    </div>

    <!-- Divider -->
    <div style="border-top:1px solid #f0f0f0;margin:28px 0;"></div>

    <!-- Top leads table -->
    <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:16px;">Your Top 10 Leads to Call</div>
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#f8faff;">
          <th style="text-align:left;padding:10px 14px;font-size:11px;color:#888;text-transform:uppercase;">Name</th>
          <th style="text-align:left;padding:10px 14px;font-size:11px;color:#888;text-transform:uppercase;">Score</th>
          <th style="text-align:left;padding:10px 14px;font-size:11px;color:#888;text-transform:uppercase;">Budget</th>
          <th style="text-align:left;padding:10px 14px;font-size:11px;color:#888;text-transform:uppercase;">Timeline</th>
        </tr>
      </thead>
      <tbody>
        {lead_rows()}
      </tbody>
    </table>

    <!-- Footer -->
    <div style="margin-top:32px;padding-top:20px;border-top:1px solid #f0f0f0;text-align:center;color:#aaa;font-size:12px;">
      Generated by your Real Estate AI Agent &nbsp;·&nbsp; {datetime.utcnow().strftime('%d %b %Y')}
    </div>
  </div>
</div>
</body>
</html>"""


@router.get("/{agent_id}/monthly", response_class=HTMLResponse)
async def preview_monthly_report(agent_id: str):
    """Preview the monthly report as HTML in the browser."""
    try:
        stats = get_agent_stats(agent_id)
        top_leads = get_leads_ranked(agent_id)
        rental = get_rental_stats(agent_id)
        agent_name = os.getenv("DEFAULT_AGENT_NAME", "Agent")
        agency     = os.getenv("DEFAULT_AGENCY", "")
        month_label = datetime.utcnow().strftime("%B %Y")
        html = _build_report_html(stats, top_leads, agent_name, agency, month_label, rental)
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/monthly/send")
async def send_monthly_report(agent_id: str):
    """Generate and email the monthly report to the agent."""
    try:
        stats = get_agent_stats(agent_id)
        top_leads = get_leads_ranked(agent_id)
        rental = get_rental_stats(agent_id)
        agent_name  = os.getenv("DEFAULT_AGENT_NAME", "Agent")
        agency      = os.getenv("DEFAULT_AGENCY", "")
        agent_email = os.getenv("DEFAULT_AGENT_EMAIL", "")
        month_label = datetime.utcnow().strftime("%B %Y")

        if not agent_email:
            raise HTTPException(status_code=400, detail="DEFAULT_AGENT_EMAIL not set")

        html = _build_report_html(stats, top_leads, agent_name, agency, month_label, rental)
        send_email(agent_email, f"Your AI Agent Report — {month_label}", html)
        return {"success": True, "message": f"Report emailed to {agent_email}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
