"""Build the folder GitHub Pages serves. The customer file is encrypted."""
from __future__ import annotations

import base64
import json
import os
import shutil
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import acronis_client

ROOT = Path(__file__).parent
SITE = ROOT / "site"
ITERS = 100_000


def seal(payload: dict, password: str) -> dict:
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERS).derive(password.encode())
    blob = AESGCM(key).encrypt(iv, json.dumps(payload, ensure_ascii=False).encode(), None)
    return {
        "v": 1,
        "iters": ITERS,
        "salt": base64.b64encode(salt).decode(),
        "iv": base64.b64encode(iv).decode(),
        "data": base64.b64encode(blob).decode(),
    }


def open_seal(box: dict, password: str) -> dict:
    salt = base64.b64decode(box["salt"])
    iv = base64.b64decode(box["iv"])
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=box["iters"]).derive(password.encode())
    plain = AESGCM(key).decrypt(iv, base64.b64decode(box["data"]), None)
    return json.loads(plain)


def main() -> None:
    password = os.environ.get("SITE_PASSWORD", "")
    if not password:
        raise SystemExit("SITE_PASSWORD is missing")
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(ROOT / "static", SITE)
    data = acronis_client.dashboard(refresh=True)
    (SITE / "data.json").write_text(json.dumps(seal(data, password)), encoding="utf-8")
    print(f"site ready, {len(data['customers'])} customers")


def _demo() -> None:
    box = seal({"customers": [{"name": "א"}]}, "secret")
    assert open_seal(box, "secret")["customers"][0]["name"] == "א"
    try:
        open_seal(box, "nope")
    except Exception:
        print("ok")
        return
    raise SystemExit("wrong password was accepted")


if __name__ == "__main__":
    main()
