# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.0,<2", "httpx>=0.27"]
# ///
"""LMT-GO (Lanka Metro Transit) MCP server — read-only data plus authentication.

Unofficial hobby project intended for personal, non-commercial use, licensed
under PolyForm Noncommercial 1.0.0. Run one client and one account at a time.
See LICENSE for the full permissions and terms of use.

Auth: agent-driven OTP. login_start(phone) sends the SMS, the human reads
the code and gives it to the agent, login_complete(phone, otp_code) stores the token
pair in ~/.config/lmt-mcp/tokens.json (0600). Access token is refreshed
automatically via /auth/refresh.

Env:
  LMT_BASE_URL   API base URL; defaults to the production API
  LMT_TOKEN_FILE override token store path
  LMT_DEVICE_ID  sent on verify-otp/refresh if the backend enforces device binding
"""
import json
import os
import time
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("LMT_BASE_URL", "https://metrobusapiprod.eimsky.com")
USER = "/user-service/api/v1"
FARE = "/fare-service/api/v1"
TICKET = "/ticketing-service/api/v1"
SERVICES = {"user": USER, "fare": FARE, "ticketing": TICKET}
TOKEN_FILE = Path(os.environ.get("LMT_TOKEN_FILE", Path.home() / ".config" / "lmt-mcp" / "tokens.json"))
DEVICE_ID = os.environ.get("LMT_DEVICE_ID")

mcp = FastMCP("lmt-go")
http = httpx.Client(base_url=BASE, timeout=20)


def _save_tokens(d: dict, phone: str | None = None):
    TOKEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    old = _load_tokens() or {}
    TOKEN_FILE.write_text(json.dumps({
        "access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", old.get("refresh_token")),
        "expires_at": time.time() + int(d.get("expires_in", 3600)),
        "phone": phone or old.get("phone"),
        "user": d.get("user", old.get("user")),
    }))
    TOKEN_FILE.chmod(0o600)


def _load_tokens() -> dict | None:
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return None


def _refresh() -> bool:
    t = _load_tokens()
    if not t or not t.get("refresh_token"):
        return False
    body = {"refresh_token": t["refresh_token"]}
    if DEVICE_ID:
        body["device_id"] = DEVICE_ID
    r = http.post(f"{USER}/auth/refresh", json=body)
    if r.status_code != 200:
        return False
    data = r.json()
    _save_tokens(data.get("data", data))
    return True


def _access_token() -> str | None:
    t = _load_tokens()
    if not t:
        return None
    if time.time() > t["expires_at"] - 60 and not _refresh():
        return None
    return _load_tokens()["access_token"]


def _unwrap(r: httpx.Response) -> dict:
    try:
        body = r.json()
    except Exception:
        return {"status": r.status_code, "body": r.text}
    return {"status": r.status_code, "data": body["data"]} if isinstance(body, dict) and "data" in body else {"status": r.status_code, "body": body}


def _req(method: str, service: str, path: str, auth: bool = True, **kw) -> dict:
    if auth:
        tok = _access_token()
        if not tok:
            return {"status": 401, "error": "not_authenticated",
                    "hint": "Call login_start with the user's phone number first."}
        kw.setdefault("headers", {})["Authorization"] = f"Bearer {tok}"
    r = http.request(method, f"{service}{path}", **kw)
    if r.status_code == 401 and auth and _refresh():
        kw["headers"]["Authorization"] = f"Bearer {_load_tokens()['access_token']}"
        r = http.request(method, f"{service}{path}", **kw)
    return _unwrap(r)


# ---------------- auth tools ----------------

@mcp.tool()
def login_start(phone: str) -> dict:
    """Begin login: sends an SMS OTP to the phone. Use the full local number
    with a leading zero (e.g. 0712345678). The app displays +94 beside the
    entered 71… number but sends 071… to the API. This tool forwards phone
    unchanged. After calling, ask the user for the SMS code."""
    return _req("POST", USER, "/auth/customer/check-phone", auth=False, json={"phone": phone})


@mcp.tool()
def login_complete(phone: str, otp_code: str, otp_reference: str = "") -> dict:
    """Complete login with the SMS code the user received. Stores tokens locally
    (never returned). Use exactly the same local-format phone number as
    login_start. Pass otp_reference from login_start if one was returned."""
    body = {"phone": phone, "otp_code": otp_code}
    if otp_reference:
        body["otp_reference"] = otp_reference
    if DEVICE_ID:
        body["device_id"] = DEVICE_ID
    r = http.post(f"{USER}/auth/customer/verify-otp", json=body)
    if r.status_code != 200:
        return _unwrap(r)
    data = r.json()
    data = data.get("data", data)
    if "access_token" not in data:
        return {"status": r.status_code, "body": data}
    _save_tokens(data, phone)
    return {"status": "authenticated", "user": data.get("user"), "expires_in": data.get("expires_in")}


@mcp.tool()
def auth_status() -> dict:
    """Show login state: whether tokens exist, who for, and access-token expiry."""
    t = _load_tokens()
    if not t:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "phone": t.get("phone"),
        "user": t.get("user"),
        "access_token_expires_in_seconds": int(t["expires_at"] - time.time()),
    }


# ---------------- read-only data tools (verified against live API 2026-09-29) ----------------

@mcp.tool()
def search_stops(query: str) -> dict:
    """Search bus stops by name (e.g. 'colombo', 'pettah'). Returns stop ids,
    trilingual names and coordinates. Resolve names to stop ids here first."""
    return _req("GET", FARE, "/stops/search", params={"q": query})


@mcp.tool()
def nearest_stops(lat: float, lng: float) -> dict:
    """Find bus stops nearest to a latitude/longitude."""
    return _req("GET", FARE, "/stops/nearest", params={"lat": lat, "lng": lng})


@mcp.tool()
def plan_journey(from_stop_id: str, to_stop_id: str, date: str = "") -> dict:
    """Plan a trip between two stop ids (from search_stops/nearest_stops).
    Returns itinerary options with departure/arrival times, legs, route codes,
    transfers and fare. Pass date as YYYY-MM-DD, or omit for next available."""
    params = {"from_stop_id": from_stop_id, "to_stop_id": to_stop_id}
    if date:
        params["date"] = date
    else:
        params["now"] = "true"
    return _req("GET", FARE, "/journeys/plan", params=params)


@mcp.tool()
def list_routes() -> dict:
    """List all bus routes with geometry/directions (route code, name, stops)."""
    return _req("GET", FARE, "/routes/geo")


@mcp.tool()
def active_journey() -> dict:
    """The user's currently active journey, if any."""
    return _req("GET", FARE, "/journeys/active")


@mcp.tool()
def favorite_routes() -> dict:
    """List the user's favorite/saved routes."""
    return _req("GET", FARE, "/favorites/routes")


@mcp.tool()
def list_passes() -> dict:
    """List available pass products (pass id, name, options, fares)."""
    return _req("GET", TICKET, "/passes")


@mcp.tool()
def my_passes() -> dict:
    """List the user's purchased passes (includes route info and qr_token)."""
    return _req("GET", TICKET, "/user-passes")


@mcp.tool()
def trip_history(page: int = 1, limit: int = 20) -> dict:
    """Boarding/trip history: boarding stop, drop stop, GPS, fare, times."""
    return _req("GET", TICKET, "/customers/me/boardings", params={"page": page, "limit": limit})


@mcp.tool()
def overview() -> dict:
    """Account overview: wallet balance, QR token, passes, cards, web app URL."""
    return _req("GET", TICKET, "/customers/me/overview")


@mcp.tool()
def wallet_transactions() -> dict:
    """Wallet transaction history."""
    return _req("GET", TICKET, "/customers/me/wallet/transactions")


@mcp.tool()
def notifications(page: int = 1, limit: int = 20) -> dict:
    """List notifications and unread count."""
    items = _req("GET", USER, "/notifications", params={"page": page, "limit": limit})
    unread = _req("GET", USER, "/notifications/unread-count")
    return {"notifications": items, "unread": unread}


@mcp.tool()
def api_get(service: str, path: str) -> dict:
    """Escape hatch: GET any path on a service ('user', 'fare', 'ticketing').
    path must start with '/', may include query string. Sends auth if logged in;
    also works on unauthenticated endpoints (e.g. /auth/app-versions/current?platform=android)."""
    if service not in SERVICES or not path.startswith("/"):
        return {"error": f"service must be one of {sorted(SERVICES)}, path must start with '/'"}
    return _req("GET", SERVICES[service], path, auth=bool(_load_tokens()))


if __name__ == "__main__":
    mcp.run()
