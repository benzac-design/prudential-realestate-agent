import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate_listing_description(address, bedrooms, bathrooms, sqft, price, features, neighborhood="", agent_name=""):
    prompt = f"""You are a professional real estate copywriter. Write a compelling MLS listing description.

Property Details:
- Address: {address}
- Bedrooms: {bedrooms} | Bathrooms: {bathrooms}
- Square Feet: {sqft:,}
- Price: ${price:,}
- Key Features: {features}
- Neighborhood: {neighborhood}
- Listing Agent: {agent_name}

Write a 150-200 word listing description that:
1. Opens with a strong hook
2. Highlights the best features naturally
3. Mentions the neighborhood appeal
4. Ends with a call to action
5. Uses professional real estate language

Return only the listing description, nothing else."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def generate_lead_followup_sms(lead_name, agent_name, property_type="home"):
    prompt = f"""Write a friendly, professional SMS text message from a real estate agent to a new lead.

Lead name: {lead_name}
Agent name: {agent_name}
They inquired about: {property_type}

Rules:
- Max 160 characters
- Warm and personal, not salesy
- Ask one simple question to start conversation
- Sign with agent name

Return only the SMS text, nothing else."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def generate_lead_followup_email(lead_name, agent_name, lead_message="", agency=""):
    prompt = f"""Write a warm follow-up email from a real estate agent to a new lead.

Lead name: {lead_name}
Agent name: {agent_name}
Agency: {agency}
Lead's inquiry: {lead_message or "general real estate inquiry"}

Rules:
- Subject line included at top as "Subject: ..."
- 3-4 short paragraphs
- Professional but warm tone
- Ask about their timeline and budget if not mentioned
- End with clear next step (schedule a call)

Return the subject line and email body, nothing else."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def generate_followup_sequence_message(lead_name, agent_name, day_number, context=""):
    prompts = {
        3: f"Write a 3-day follow-up SMS to {lead_name} from agent {agent_name}. Mention you have new listings. Max 160 chars.",
        7: f"Write a 1-week follow-up SMS to {lead_name} from agent {agent_name}. Share a market insight. Max 160 chars.",
        14: f"Write a 2-week follow-up SMS to {lead_name} from agent {agent_name}. Ask if their search criteria changed. Max 160 chars.",
        30: f"Write a 1-month follow-up SMS to {lead_name} from agent {agent_name}. Mention a new listing in their area. Max 160 chars.",
        60: f"Write a 2-month follow-up SMS to {lead_name} from agent {agent_name}. Market update, keep it light. Max 160 chars.",
    }

    prompt = prompts.get(day_number, f"Write a follow-up SMS to {lead_name} from agent {agent_name}. Keep it friendly. Max 160 chars.")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def audit_fair_housing_compliance(listing_description):
    prompt = f"""You are a Fair Housing Act compliance expert. Audit this real estate listing description for violations.

Listing:
\"\"\"{listing_description}\"\"\"

Check for forbidden or risky language related to:
- Race, color, national origin
- Religion (e.g. "walking distance to church", "great Jewish neighborhood")
- Sex or gender
- Familial status (e.g. "perfect for young families", "ideal for couples", "no kids")
- Disability (e.g. "able-bodied", "perfect for active people")
- Age
- Any language that targets or excludes a demographic group

Respond in this exact format:

RESULT: PASS or FAIL

VIOLATIONS:
- [list each violation found, or "None" if clean]

RISKY PHRASES:
- [list phrases that could be borderline, or "None"]

SUGGESTED FIXES:
- [for each violation, give the exact replacement text]

SUMMARY:
[One sentence summary of the compliance status]"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def generate_client_update_email(client_name, agent_name, new_listings, criteria):
    listings_text = "\n".join([f"- {l}" for l in new_listings]) if new_listings else "- No new listings this week, but we are watching closely"

    prompt = f"""Write a weekly property update email from a real estate agent to a buyer client.

Client name: {client_name}
Agent name: {agent_name}
Search criteria: {criteria}
New listings this week:
{listings_text}

Rules:
- Subject line at top as "Subject: ..."
- Friendly, helpful tone
- 2-3 short paragraphs
- Highlight the best listing if there are multiple
- End with offer to schedule viewings

Return only the subject line and email body."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
