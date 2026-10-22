"""Read-only Acronis Account Management client. Credentials stay in .env."""
from __future__ import annotations

import base64
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

import acronis_billing

# ponytail: one in-process cache. Fine for a single local server; a second
# process would each keep its own. Refresh button bypasses it.
_CACHE: dict = {"at": 0.0, "data": None}
_TOKEN: dict = {"value": "", "exp": 0.0}
TTL = 10 * 60


def _creds() -> tuple[str, str, str]:
    dc = os.environ.get("ACRONIS_DC_URL", "").rstrip("/")
    cid = os.environ.get("ACRONIS_CLIENT_ID", "")
    secret = os.environ.get("ACRONIS_CLIENT_SECRET", "")
    if not (dc and cid and secret):
        raise RuntimeError("חסרים פרטי API של אקרוניס ב-.env")
    return dc, cid, secret


def _auth_header() -> tuple[str, dict]:
    dc, cid, secret = _creds()
    if _TOKEN["value"] and time.time() < _TOKEN["exp"] - 60:
        return dc, {"Authorization": "Bearer " + _TOKEN["value"]}
    raw = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    res = requests.post(
        f"{dc}/api/2/idp/token",
        headers={
            "Authorization": "Basic " + raw,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=60,
    )
    res.raise_for_status()
    body = res.json()
    _TOKEN["value"] = body["access_token"]
    _TOKEN["exp"] = float(body.get("expires_on") or time.time() + 3600)
    return dc, {"Authorization": "Bearer " + _TOKEN["value"]}


def _get(dc: str, auth: dict, path: str, **params):
    res = requests.get(f"{dc}/api/2{path}", headers=auth, params=params, timeout=120)
    res.raise_for_status()
    return res.json()


def _load() -> dict:
    dc, auth = _auth_header()
    cid = os.environ["ACRONIS_CLIENT_ID"]
    partner = _get(dc, auth, f"/clients/{cid}")["tenant_id"]
    tenants = _get(dc, auth, "/tenants", parent_id=partner, limit=300)["items"]
    customers = [t for t in tenants if t.get("kind") == "customer"]
    usages: dict[str, list] = {t["id"]: [] for t in customers}
    ids = list(usages)
    for i in range(0, len(ids), 15):
        chunk = ids[i : i + 15]
        data = _get(dc, auth, "/tenants/usages", tenants=",".join(chunk))
        for block in data.get("items") or []:
            usages[block["tenant"]] = block.get("usages") or []
    rows = []
    for t in customers:
        row = acronis_billing.bill(usages.get(t["id"]) or [])
        row["id"] = t["id"]
        row["name"] = t.get("name") or ""
        rows.append(row)
    rows.sort(key=lambda r: (-r["price"], r["name"]))
    return {
        "fetched_at": datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%d.%m.%Y %H:%M"),
        "customers": rows,
    }


def dashboard(refresh: bool = False) -> dict:
    if not refresh and _CACHE["data"] and time.time() - _CACHE["at"] < TTL:
        return _CACHE["data"]
    data = _load()
    _CACHE["at"] = time.time()
    _CACHE["data"] = data
    return data
