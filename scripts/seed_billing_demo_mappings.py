"""Seed demo category mappings and packages for billing QA."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from billing_demo_mappings import DEMO_PACKAGES, DEMO_SERVICE_MAPPINGS, apply_demo_mappings

BASE = f"http://127.0.0.1:{os.getenv('BACKEND_PORT', '8010')}/api/v1"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=60.0)
    r = client.post("/auth/login", json={"email": "admin@admin.com", "password": "admin123"})
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} {r.text[:200]}")
        return 1
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    result = apply_demo_mappings(client, headers)
    print(f"Mapped {result['mapped_services']} services to category/sub-category")
    print(f"Demo packages: {', '.join(result['package_ids'].keys()) or 'none'}")
    print(f"Service mappings defined: {len(DEMO_SERVICE_MAPPINGS)}")
    print(f"Package definitions: {len(DEMO_PACKAGES)}")
    for code, pkg_id in result["package_ids"].items():
        detail = client.get(f"/billing-packages/{pkg_id}", headers=headers).json()
        print(f"  {code}: {len(detail.get('items', []))} services, total={detail.get('package_total')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
