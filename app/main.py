from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

from app.routes import listings, leads, followups, clients, conversations, appointments, stats, valuation, reports, maintenance, renewals
from app.scheduler import process_pending_followups, send_appointment_reminders

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

app.include_router(listings.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(followups.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(appointments.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(valuation.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")
app.include_router(renewals.router, prefix="/api")


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


@app.get("/api/process-followups")
async def run_followups():
    await process_pending_followups()
    await send_appointment_reminders()
    return {"status": "ok"}
