import os, sys, requests, json, xml.sax.saxutils as sax

API_USER = os.environ["VOIPMS_API_USERNAME"]
API_PASS = os.environ["VOIPMS_API_PASSWORD"]
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "dir.xml")
DEBUG = os.environ.get("DEBUG", "0") not in ("", "0", "false", "False", "no", "No")

API_URL = "https://voip.ms/api/v1/rest.php"  # no 'www' per provider notes

def dprint(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs, flush=True)

def get_subaccounts():
    # voip.ms REST style: GET with method name + credentials
    params = {
        "api_username": API_USER,
        "api_password": API_PASS,
        "method": "getSubAccounts",
        # If you ever want to filter: "account": "100000_VoIP"
        # Some deployments require explicit JSON; usually not needed:
        # "format": "json",
    }
    redacted = {**params, "api_username": "***", "api_password": "***"}
    dprint(f"[voip.ms] GET {API_URL} params={redacted}")

    resp = requests.get(API_URL, params=params, timeout=30)
    dprint(f"[voip.ms] HTTP {resp.status_code}")
    resp.raise_for_status()

    # Try to parse JSON; show a short preview on failure
    try:
        data = resp.json()
    except Exception:
        dprint("[voip.ms] Non-JSON response body (first 500 chars):")
        dprint(resp.text[:500])
        raise

    dprint("[voip.ms] top-level keys:", list(data.keys()))

    status = data.get("status")
    if status != "success":
        # voip.ms often includes 'status' and 'message' on errors
        raise SystemExit(f"VoIP.ms API error: status={status!r} message={data.get('message')!r}")

    # voip.ms docs/examples use 'accounts' for this method
    rows = data.get("accounts")
    if rows is None:
        # be tolerant of alternate naming
        rows = data.get("sub_accounts")

    if rows is None:
        raise SystemExit(
            f"Unexpected API shape: couldn't find 'accounts' or 'sub_accounts'. "
            f"Top-level keys were: {list(data.keys())}"
        )

    if DEBUG and isinstance(rows, list) and rows:
        preview = {k: rows[0].get(k) for k in ("id","account","username","description","internal_extension")}
        dprint("[voip.ms] first account preview:", json.dumps(preview, indent=2))

    return rows

def build_xml(rows):
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<CiscoIPPhoneDirectory>",
        "  <Title>Ham Subaccounts (VoIP.ms)</Title>",
        "  <Prompt>Select contact</Prompt>",
    ]
    used = 0
    skipped_no_ext = 0
    for r in rows:
        name = r.get("description") or r.get("username") or "Unknown"
        tel  = r.get("internal_extension") or ""  # skip if none/0/empty
        if not tel:
            skipped_no_ext += 1
            continue
        parts.append(
            f"  <DirectoryEntry><Name>{sax.escape(name)}</Name><Telephone>{sax.escape(str(tel))}</Telephone></DirectoryEntry>"
        )
        used += 1

    parts.append("</CiscoIPPhoneDirectory>")
    xml = "\n".join(parts) + "\n"
    return xml, used, skipped_no_ext

def main():
    subs = get_subaccounts()
    dprint(f"[voip.ms] received {len(subs)} total rows")

    subs.sort(key=lambda r: ((r.get("description") or "").lower(), (r.get("username") or "").lower()))
    xml, used, skipped_no_ext = build_xml(subs)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"Wrote {OUTPUT_PATH} with {used} entries (skipped {skipped_no_ext} without internal_extension)")

if __name__ == "__main__":
    main()
