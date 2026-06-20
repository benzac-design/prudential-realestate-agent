from openai import OpenAI
import os
import json

_client = OpenAI(
    api_key=os.getenv("MINIMAX_API_KEY"),
    base_url="https://api.minimax.io/v1",
)


def _ask(prompt: str) -> str:
    response = _client.chat.completions.create(
        model="MiniMax-Text-01",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _ask_json(system: str, history: list) -> dict:
    """Run a chat turn that must return a JSON object. Defensive parse."""
    messages = [{"role": "system", "content": system}] + history
    response = _client.chat.completions.create(
        model="MiniMax-Text-01",
        messages=messages,
    )
    raw = response.choices[0].message.content or ""
    # Strip code fences / surrounding prose, grab the first {...} block.
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"reply": raw.strip() or "Thanks for your message! When works for a quick call?",
                "budget": None, "timeline": None, "pre_approved": None,
                "stage": "engaged", "intent": "other"}


def generate_conversation_reply(lead: dict, history: list, agent_name: str, agency: str = "") -> dict:
    """
    Drive a two-way SMS conversation with a lead.

    `history` is a list of {"role": "user"|"assistant", "content": str} turns,
    oldest first, where "user" = the lead and "assistant" = the AI agent.

    Returns a dict: reply, budget, timeline, pre_approved, stage, intent.
    Intent is one of: qualifying, wants_showing, hot, not_interested, other.
    """
    known = []
    if lead.get("budget"):
        known.append(f"budget: {lead['budget']}")
    if lead.get("timeline"):
        known.append(f"timeline: {lead['timeline']}")
    if lead.get("pre_approved") is not None:
        known.append(f"pre-approved: {'yes' if lead['pre_approved'] else 'no'}")
    known_text = "; ".join(known) if known else "nothing yet"

    system = f"""You are {agent_name}, a friendly, professional real estate agent{f' at {agency}' if agency else ''}, texting with a lead named {lead.get('name', 'there')}.

Your job over SMS:
1. Build rapport and reply naturally to what they just said.
2. Qualify them by gently learning, ONE question at a time, across the conversation:
   - budget / price range
   - timeline (how soon they want to buy/rent)
   - whether they are pre-approved for finance
3. Once they seem qualified and interested, offer to book a property viewing or a quick call.

What you already know about this lead: {known_text}.
Do NOT re-ask for info you already know. Ask at most ONE new question per message.
{f'When they are ready to view a property or book a call, share this booking link so they can pick a time: {os.getenv("BOOKING_LINK")}' if os.getenv("BOOKING_LINK") else 'When they are ready to view a property or book a call, offer to set up a time and tell them the agent will confirm.'}

Style rules:
- Keep each reply under 320 characters (1-2 short sentences). Conversational, warm, never pushy or spammy.
- Sound like a real person texting, not a brochure. No emojis unless they use them first.
- Sign off only occasionally, not every message.

Respond with ONLY a JSON object, no other text:
{{
  "reply": "<the SMS text to send back>",
  "budget": "<budget if newly learned, else null>",
  "timeline": "<timeline if newly learned, else null>",
  "pre_approved": <true/false if newly learned, else null>,
  "stage": "<engaged|qualifying|qualified|showing_requested|not_interested>",
  "intent": "<qualifying|wants_showing|hot|not_interested|other>"
}}"""

    result = _ask_json(system, history)
    result.setdefault("reply", "Thanks! When works for a quick call?")
    for k in ("budget", "timeline", "pre_approved", "stage", "intent"):
        result.setdefault(k, None)
    return result


def generate_listing_description(address, bedrooms, bathrooms, sqm, price, features, neighborhood="", agent_name="", listing_type="sale"):
    if listing_type == "rental":
        prompt = f"""You are a professional real estate copywriter. Write a compelling rental listing description aimed at attracting quality tenants.

Property Details:
- Address: {address}
- Bedrooms: {bedrooms} | Bathrooms: {bathrooms}
- Size: {sqm:,} sqm
- Weekly/Monthly Rent: ${price:,}
- Key Features: {features}
- Neighborhood: {neighborhood}
- Leasing Agent: {agent_name}

Write a 150-200 word rental listing description that:
1. Opens with a strong hook that appeals to renters (lifestyle, convenience, move-in ready)
2. Highlights features that matter most to tenants: proximity to transport/schools/shops, low-maintenance living, storage, parking, lease terms flexibility
3. Mentions the neighborhood's everyday convenience for renters (commute, amenities)
4. Ends with a call to action to book an inspection
5. Uses warm, inviting, professional language suited to attracting reliable long-term tenants

Return only the listing description, nothing else."""
        return _ask(prompt)

    audience = "first home buyers and investors looking for value and upside" if price < 1_000_000 else "owner-occupier homeowners looking for a forever home and lifestyle upgrade"
    prompt = f"""You are a professional real estate copywriter. Write a compelling sale listing description.

Property Details:
- Address: {address}
- Bedrooms: {bedrooms} | Bathrooms: {bathrooms}
- Size: {sqm:,} sqm
- Price: ${price:,}
- Key Features: {features}
- Neighborhood: {neighborhood}
- Listing Agent: {agent_name}

Target audience: {audience}

Write a 150-200 word listing description that:
1. Opens with a strong hook tailored to the target audience above
2. Highlights the best features naturally, emphasizing what matters to this audience (e.g. growth potential and affordability for first home buyers/investors, or lifestyle and long-term comfort for homeowners)
3. Mentions the neighborhood appeal
4. Ends with a call to action
5. Uses professional real estate language

Return only the listing description, nothing else."""
    return _ask(prompt)


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
    return _ask(prompt)


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
    return _ask(prompt)


def generate_followup_sequence_message(lead_name, agent_name, day_number, context=""):
    prompts = {
        3: f"Write a 3-day follow-up SMS to {lead_name} from agent {agent_name}. Mention you have new listings. Max 160 chars.",
        7: f"Write a 1-week follow-up SMS to {lead_name} from agent {agent_name}. Share a market insight. Max 160 chars.",
        14: f"Write a 2-week follow-up SMS to {lead_name} from agent {agent_name}. Ask if their search criteria changed. Max 160 chars.",
        30: f"Write a 1-month follow-up SMS to {lead_name} from agent {agent_name}. Mention a new listing in their area. Max 160 chars.",
        60: f"Write a 2-month follow-up SMS to {lead_name} from agent {agent_name}. Market update, keep it light. Max 160 chars.",
    }
    prompt = prompts.get(day_number, f"Write a follow-up SMS to {lead_name} from agent {agent_name}. Keep it friendly. Max 160 chars.")
    return _ask(prompt)


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
    return _ask(prompt)


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
    return _ask(prompt)


def generate_property_match_sms(lead: dict, listing: dict, agent_name: str) -> str:
    """Personalised SMS to send a lead when a new listing matches their criteria."""
    prompt = f"""You are {agent_name}, a real estate agent. Write a short, natural SMS to a lead about a new listing that matches their criteria.

Lead name: {lead.get('name', 'there')}
Lead budget: {lead.get('budget') or 'not specified'}
Lead timeline: {lead.get('timeline') or 'not specified'}

New listing:
- Address: {listing.get('address')}
- Bedrooms: {listing.get('bedrooms')} bed / {listing.get('bathrooms')} bath
- Price: ${listing.get('price'):,}
- Key features: {listing.get('features') or 'not specified'}
- Neighborhood: {listing.get('neighborhood') or ''}

Rules:
- Max 320 characters
- Sound like a real person texting, not a bot
- Mention 1-2 specific details that match what they want
- End with a soft question ("want to take a look?" or "does this sound like what you're after?")
- Do NOT use the word "criteria" or sound robotic
- Return only the SMS text, nothing else."""
    return _ask(prompt)


def generate_home_valuation(address, bedrooms, bathrooms, sqm, condition="", year_built="", recent_upgrades="", neighborhood="", agent_name=""):
    """Seller lead magnet: an estimated value range + talking points. This is a
    conversation starter, NOT a formal appraisal — the prompt makes that clear."""
    prompt = f"""You are an experienced local real estate agent preparing a friendly home value estimate for a potential seller. You do not have live MLS data, so give a reasoned estimate based on the details and general market logic, and be upfront that a precise figure needs an in-person appraisal.

Property:
- Address: {address}
- Bedrooms: {bedrooms} | Bathrooms: {bathrooms}
- Size: {sqm} sqm
- Condition: {condition or "not specified"}
- Year built: {year_built or "not specified"}
- Recent upgrades: {recent_upgrades or "none mentioned"}
- Neighborhood: {neighborhood or "not specified"}
- Agent: {agent_name}

Write a warm, professional response with these sections:

ESTIMATED VALUE RANGE:
[Give a sensible range, e.g. "$X - $Y", and one sentence on what drives it]

WHAT'S WORKING IN YOUR FAVOR:
- [2-3 bullets on value-positive factors from the details]

WHAT COULD AFFECT THE PRICE:
- [2-3 bullets, honest but encouraging]

TO GET TOP DOLLAR:
- [2-3 concrete, low-cost prep tips before listing]

NEXT STEP:
[Invite them to a free no-obligation in-person valuation with {agent_name} for an exact figure]

Keep the whole thing under 250 words and end with a clear, friendly call to action."""
    return _ask(prompt)
