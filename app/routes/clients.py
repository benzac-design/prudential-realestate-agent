from fastapi import APIRouter, HTTPException
from app.models.schemas import ClientCriteria
from app.services.claude_service import generate_client_update_email
from app.services.resend_service import send_email, text_to_html
from app.services.supabase_service import get_clients_for_update

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/send-updates/{agent_id}")
async def send_weekly_updates(agent_id: str, new_listings: list[str] = []):
    try:
        clients = get_clients_for_update(agent_id)

        if not clients:
            return {"success": True, "message": "No clients to update"}

        sent_count = 0
        for client in clients:
            criteria = f"{client.get('min_beds', 2)}+ beds, under ${client.get('max_price', 500000):,}, in {client.get('areas', 'your area')}"
            email_content = generate_client_update_email(
                client_name=client["name"],
                agent_name=client.get("agent_name", "Your Agent"),
                new_listings=new_listings,
                criteria=criteria,
            )

            lines = email_content.split("\n")
            subject = lines[0].replace("Subject:", "").strip() if lines[0].startswith("Subject:") else "Your Weekly Property Update"
            body = "\n".join(lines[1:]).strip()

            send_email(client["email"], subject, text_to_html(body))
            sent_count += 1

        return {"success": True, "message": f"Updates sent to {sent_count} clients"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_client(criteria: ClientCriteria):
    from app.services.supabase_service import get_client
    try:
        db = get_client()
        db.table("buyer_clients").insert(criteria.model_dump()).execute()
        return {"success": True, "message": "Client added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
