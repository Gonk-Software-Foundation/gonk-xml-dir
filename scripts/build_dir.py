import os, requests, xml.sax.saxutils as sax

API_URL = "https://voip.ms/api/v1/rest.php"
API_USER = os.environ["VOIPMS_API_USERNAME"]
API_PASS = os.environ["VOIPMS_API_PASSWORD"]
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "dir.xml")

def api(method, **params):
    r = requests.get(API_URL, params={"api_username": API_USER,
                                      "api_password": API_PASS,
                                      "method": method, **params}, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "success":
        raise SystemExit(f"VoIP.ms API error for {method}: {j}")
    return j

def norm(s):
    return (s or "").strip()

def build_xml(entries):
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<CiscoIPPhoneDirectory>",
        "  <Title>Ham Subaccounts (VoIP.ms)</Title>",
        "  <Prompt>Select contact</Prompt>",
    ]
    for name, tel in entries:
        parts.append(f"  <DirectoryEntry><Name>{sax.escape(name)}</Name>"
                     f"<Telephone>{sax.escape(tel)}</Telephone></DirectoryEntry>")
    parts.append("</CiscoIPPhoneDirectory>")
    return "\n".join(parts) + "\n"

def main():
    subs = api("getSubAccounts").get("sub_accounts") or []
    entries = []
    for s in subs:
        # Common keys seen in the wild
        user = norm(s.get("username") or s.get("user"))
        desc = norm(s.get("description")) or user
        ext  = norm(s.get("internal_extension") or s.get("internal") or s.get("extension"))

        # If your account doesn’t expose an internal extension via API,
        # you can fall back to SIP URI dialing (uncomment next two lines):
        # if not ext and user:
        #     ext = f"{user}@{norm(s.get('server') or 'newyork1.voip.ms')}"

        if ext:
            entries.append((desc, ext))

    entries.sort(key=lambda x: (x[0].lower(), x[1]))
    xml = build_xml(entries)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Wrote {OUTPUT_PATH} with {len(entries)} entries")

if __name__ == "__main__":
    main()
