import os, sys, requests, xml.sax.saxutils as sax

API_USER = os.environ["VOIPMS_API_USERNAME"]
API_PASS = os.environ["VOIPMS_API_PASSWORD"]
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "dir.xml")

API_URL = "https://voip.ms/api/v1/rest.php"  # no 'www' per provider notes

def get_subaccounts():
    # voip.ms REST style: POST/GET with method name + credentials
    # Example style documented widely for SMS/etc., same endpoint here.  method=getSubAccounts
    resp = requests.get(API_URL, params={
        "api_username": API_USER,
        "api_password": API_PASS,
        "method": "getSubAccounts"
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise SystemExit(f"VoIP.ms API error: {data}")
    return data.get("sub_accounts", [])

def build_xml(rows):
    # Build Cisco/Fanvil-acceptable phonebook
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<CiscoIPPhoneDirectory>",
        "  <Title>Ham Subaccounts (VoIP.ms)</Title>",
        "  <Prompt>Select contact</Prompt>",
    ]
    # Prefer Description -> else Username; phone number = Internal Extension
    for r in rows:
        name = r.get("description") or r.get("username") or "Unknown"
        tel  = r.get("internal_extension") or ""  # skip if none
        if not tel:
            continue
        parts.append(
            f"  <DirectoryEntry><Name>{sax.escape(name)}</Name><Telephone>{sax.escape(str(tel))}</Telephone></DirectoryEntry>"
        )
    parts.append("</CiscoIPPhoneDirectory>")
    return "\n".join(parts) + "\n"

def main():
    subs = get_subaccounts()
    # Sort by description then username for stable diffs
    subs.sort(key=lambda r: ((r.get("description") or "").lower(), (r.get("username") or "").lower()))
    xml = build_xml(subs)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Wrote {OUTPUT_PATH} with {sum(1 for r in subs if r.get('internal_extension'))} entries")

if __name__ == "__main__":
    main()
