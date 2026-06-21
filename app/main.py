from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

from fastapi import Depends
from app.routes import listings, leads, followups, clients, conversations, appointments, stats, valuation, reports, maintenance, renewals, rent, inspections, applications
from app.scheduler import process_pending_followups, send_appointment_reminders, process_lease_renewals, process_rent_arrears, process_inspections
from app.auth import require_dashboard_auth

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Real Estate AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend"))

# Dashboard-only data routers — require the shared dashboard password.
_auth = [Depends(require_dashboard_auth)]
app.include_router(listings.router, prefix="/api", dependencies=_auth)
app.include_router(followups.router, prefix="/api", dependencies=_auth)
app.include_router(clients.router, prefix="/api", dependencies=_auth)
app.include_router(appointments.router, prefix="/api", dependencies=_auth)
app.include_router(stats.router, prefix="/api", dependencies=_auth)
app.include_router(reports.router, prefix="/api", dependencies=_auth)
app.include_router(maintenance.router, prefix="/api", dependencies=_auth)
app.include_router(renewals.router, prefix="/api", dependencies=_auth)
app.include_router(rent.router, prefix="/api", dependencies=_auth)
app.include_router(inspections.router, prefix="/api", dependencies=_auth)
app.include_router(applications.router, prefix="/api")  # auth baked into the router

# Mixed/public routers — these contain endpoints the public website + Twilio call,
# so auth is applied per-endpoint inside the router (not router-wide).
app.include_router(leads.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")   # /sms/inbound webhook stays open
app.include_router(valuation.router, prefix="/api")       # /request seller magnet stays open


@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/prudential-demo")
async def prudential_demo(request: Request):
    # Retired — canonical demo now lives at the dusky link. Redirect any old traffic there.
    return RedirectResponse("https://prudential-demo-dusky.vercel.app/", status_code=308)


@app.get("/sales")
async def sales(request: Request):
    return templates.TemplateResponse("sales.html", {"request": request})


@app.get("/overview")
async def overview(request: Request):
    return templates.TemplateResponse("overview.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/auth/login")
async def auth_login(payload: dict):
    """Simple shared-password gate for the dashboards. Checks against the
    DASHBOARD_PASSWORD env var (server-side, so the password is never in page source)."""
    expected = os.getenv("DASHBOARD_PASSWORD", "")
    supplied = (payload or {}).get("password", "")
    if expected and supplied == expected:
        return {"ok": True}
    return {"ok": False}


@app.get("/api/process-followups")
async def run_followups():
    await process_pending_followups()
    await send_appointment_reminders()
    await process_lease_renewals()
    await process_rent_arrears()
    await process_inspections()
    return {"status": "ok"}
