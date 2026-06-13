import traceback
import sys

try:
    from app.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()

    error_detail = traceback.format_exc()

    @app.get("/{path:path}")
    async def catch_all(path: str):
        return JSONResponse({"error": str(e), "traceback": error_detail}, status_code=500)
