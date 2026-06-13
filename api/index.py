import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Define app at top level unconditionally so Vercel can find it
app = FastAPI()

_import_error = None
_import_traceback = None

try:
    from app.main import app  # replaces the fallback if import succeeds
except Exception as e:
    _import_error = str(e)
    _import_traceback = traceback.format_exc()

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def catch_all(path: str = ""):
        return JSONResponse({"error": _import_error, "traceback": _import_traceback}, status_code=500)
