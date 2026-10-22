"""Turn Acronis usage records into the customer rows the dashboard shows.

Prices are Egoz's sell prices, not Acronis's. Counts come from the per-workload
(or per-gigabyte) offering items. Cloud storage is `storage_total` only —
workload breakdowns are parts of that total, not extra gigabytes.
"""
from __future__ import annotations

GB = 1024 ** 3
STORAGE_PER_GB = 0.30
# Billing steps are 500 decimal GB. 3.52 TiB is about 3,870 GB, which rounds up to 4 TB.
BILL_STEP = 500 * 10**9

# offering-item `name` -> product key. Packs and shared seats are not in the price list.
COUNT_NAMES = {
    "pw_base_servers": "servers",
    "pg_base_servers": "servers",
    "pw_base_vms": "vms",
    "pg_base_vms": "vms",
    "pw_base_workstations": "workstations",
    "pg_base_workstations": "workstations",
    "pw_pack_adv_security": "edr",
    "pg_pack_adv_security": "edr",
    "pw_base_m365_seats": "m365",
    "pg_base_m365_seats": "m365",
    "pw_pack_adv_email_security": "email",
    "pg_pack_adv_email_security": "email",
}

# usage_name of the bytes that belong to a product. Not added on top of storage_total.
PART_STORAGE = {
    "server_storage": "servers",
    "vm_storage": "vms",
    "workstation_storage": "workstations",
    "c2c_storage": "m365",
}

PRODUCTS = (
    ("servers", "שרת פיזי", 150),
    ("vms", "מכונה וירטואלית", 50),
    ("workstations", "תחנת עבודה", 30),
    ("edr", "Endpoint עם EDR", 8.75),
    ("m365", "משתמש Microsoft 365", 10.56),
    ("email", "אבטחת דואר", 9.92),
)


def _num(usage: dict) -> float:
    return float(usage.get("absolute_value") or usage.get("value") or 0)


def billed_bytes(used: int) -> int:
    if used <= 0:
        return 0
    return ((used + BILL_STEP - 1) // BILL_STEP) * BILL_STEP


def bill(usages: list[dict]) -> dict:
    counts = {key: 0 for key, _, _ in PRODUCTS}
    parts = {key: 0 for key, _, _ in PRODUCTS}
    total_bytes = 0
    fallback_bytes = 0
    for u in usages:
        name = u.get("name") or ""
        usage_name = u.get("usage_name") or ""
        n = _num(u)
        if not n:
            continue
        key = COUNT_NAMES.get(name)
        if key and u.get("measurement_unit") != "bytes":
            counts[key] += int(n)
        part = PART_STORAGE.get(usage_name)
        if part and u.get("measurement_unit") == "bytes":
            parts[part] += int(n)
        if usage_name == "storage_total" and u.get("measurement_unit") == "bytes":
            total_bytes += int(n)
        elif name in ("pw_base_storage", "pg_base_storage"):
            fallback_bytes += int(n)
    if not total_bytes:
        total_bytes = fallback_bytes

    lines = []
    price = 0.0
    for key, label, unit in PRODUCTS:
        qty = counts[key]
        line = round(qty * unit, 2)
        price += line
        lines.append({
            "key": key,
            "name": label,
            "qty": qty,
            "unit": unit,
            "storage_bytes": parts[key],
            "price": line,
        })
    other = total_bytes - sum(parts.values())
    if other > GB:
        lines.append({
            "key": "other",
            "name": "אחסון לא משויך",
            "qty": None,
            "unit": 0,
            "storage_bytes": other,
            "price": 0,
        })
    charged = billed_bytes(total_bytes)
    storage_price = round((charged / 10**9) * STORAGE_PER_GB, 2)
    price = round(price + storage_price, 2)
    lines.append({
        "key": "storage",
        "name": "אחסון ענן",
        "qty": None,
        "unit": STORAGE_PER_GB,
        "storage_bytes": total_bytes,
        "billed_bytes": charged,
        "price": storage_price,
    })
    return {
        "counts": counts,
        "storage_bytes": total_bytes,
        "billed_bytes": charged,
        "price": price,
        "lines": lines,
    }


def _demo() -> None:
    gb = GB
    row = bill([
        {"name": "pw_base_servers", "usage_name": "servers", "absolute_value": 1, "measurement_unit": "quantity"},
        {"name": "pw_base_vms", "usage_name": "vms", "absolute_value": 2, "measurement_unit": "quantity"},
        {"name": "pw_pack_adv_security", "usage_name": "pack_adv_security", "absolute_value": 4, "measurement_unit": "quantity"},
        {"name": "pw_base_m365_seats", "usage_name": "mailboxes", "absolute_value": 3, "measurement_unit": "quantity"},
        {"name": "pw_pack_adv_email_security", "usage_name": "pack_adv_email_security_mailboxes", "absolute_value": 2, "measurement_unit": "quantity"},
        {"name": "server_storage", "usage_name": "server_storage", "absolute_value": 10 * gb, "measurement_unit": "bytes"},
        {"name": "vm_storage", "usage_name": "vm_storage", "absolute_value": 5 * gb, "measurement_unit": "bytes"},
        {"name": "storage_total", "usage_name": "storage_total", "absolute_value": 20 * gb, "measurement_unit": "bytes"},
        {"name": "pw_base_storage", "usage_name": "storage", "absolute_value": 20 * gb, "measurement_unit": "bytes"},
        {"name": "protected_mailbox_storage", "usage_name": "protected_mailbox_storage", "absolute_value": 99 * gb, "measurement_unit": "bytes"},
        {"name": "pw_base_secondary_m365_seats_shared", "usage_name": "m365_seats_shared", "absolute_value": 11, "measurement_unit": "quantity"},
    ])
    assert row["counts"] == {
        "servers": 1, "vms": 2, "workstations": 0, "edr": 4, "m365": 3, "email": 2,
    }, row["counts"]
    assert row["storage_bytes"] == 20 * gb
    assert row["billed_bytes"] == 500 * 10**9
    assert row["lines"][0]["storage_bytes"] == 10 * gb
    assert row["lines"][1]["storage_bytes"] == 5 * gb
    other = next(l for l in row["lines"] if l["key"] == "other")
    assert other["storage_bytes"] == 5 * gb and other["price"] == 0
    # 150 + 100 + 35 + 31.68 + 19.84 + 500 GB * 0.30
    assert row["price"] == 486.52, row["price"]
    used = int(3.52 * (1024 ** 4))
    assert billed_bytes(used) == 4 * 10**12
    assert billed_bytes(0) == 0
    assert billed_bytes(500 * 10**9) == 500 * 10**9
    print("ok", row["price"])


if __name__ == "__main__":
    _demo()
