import os
from fastapi import Header, HTTPException


def require_dashboard_auth(x_dashboard_auth: str = Header(default="")):
    """Dependency for dashboard-only data endpoints. Requires the shared dashboard
    password in the `X-Dashboard-Auth` header (the dashboards attach it after login).

    If DASHBOARD_PASSWORD is unset, auth is disabled (fails open) so local/dev use
    isn't blocked — set the env var in production to enforce it.
    """
    expected = os.getenv("DASHBOARD_PASSWORD", "")
    if not expected:
        return
    if x_dashboard_auth != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
