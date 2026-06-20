"""Rule-based lead scoring. Deterministic and explainable — an agent can see
exactly why a lead is hot, which an LLM score can't reliably give."""

URGENT_TIMELINE_WORDS = ("asap", "immediately", "now", "this month", "weeks", "30 days", "soon", "ready")


def score_lead(lead: dict) -> tuple[int, str]:
    """Return (score 0-100, temperature). Temperature: hot/warm/cold/dead."""
    if lead.get("opted_out"):
        return 0, "dead"

    score = 0

    # Reachable.
    if lead.get("phone"):
        score += 10

    # Actually engaged in conversation.
    stage = (lead.get("conversation_stage") or "").lower()
    if stage in ("engaged", "qualifying", "qualified", "showing_requested"):
        score += 20

    # Qualification signals.
    if lead.get("budget"):
        score += 20
    if lead.get("timeline"):
        score += 15
        if any(w in str(lead["timeline"]).lower() for w in URGENT_TIMELINE_WORDS):
            score += 10
    if lead.get("pre_approved") is True:
        score += 25

    # Buying intent.
    if stage == "showing_requested" or lead.get("status") == "showing_requested":
        score += 25

    score = min(score, 100)

    if score >= 70:
        temp = "hot"
    elif score >= 40:
        temp = "warm"
    else:
        temp = "cold"
    return score, temp
