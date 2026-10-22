"""Build the folder GitHub Pages serves. Credentials come from the environment."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import acronis_client

ROOT = Path(__file__).parent
SITE = ROOT / "site"


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(ROOT / "static", SITE)
    data = acronis_client.dashboard(refresh=True)
    (SITE / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"site ready, {len(data['customers'])} customers")


if __name__ == "__main__":
    main()
