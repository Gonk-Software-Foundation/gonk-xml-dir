import os, requests, xml.sax.saxutils as sax

API_USER = os.environ["VOIPMS_API_USERNAME"]
API_PASS = os.environ["VOIPMS_API_PASSWORD"]
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "dir.xml")
API_URL = "https://voip.ms/api/v1/rest.php"

def api(method, **params):
    p = {
        "api_username": API_USER,
        "api_password": API_PASS,
        "method": method,
    }
    p.update(params)
    r = requests.get(API_URL, params=p, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "success":
        raise SystemExit(f"VoIP.ms API error for {method}: {j}")
    return j

def get_subaccounts():
    # returns list of dicts with at least: username, description (may be None)
    j = api("getSubAccounts")
    subs = j.get("sub_accounts") or j.get("subaccounts") or []
    # normalize keys
    out = []
    for s in subs:
        out.append({
            "username": s.get("username") or s.get("user") or "",
            "description": s.get("description") or "",
        })
    return out

def get_internal_extensions():
    # returns map: username -> internal extension number (string)
    j = api("getInternalExtensions")
    items = j.get("internal_extensions") or j.get("internal") or []
    m = {}
    for it in items:
        # VoIP.ms returns fields like:
        #  - username (subaccount)  OR 'account'/'user'
        #  - internal (the extension number) OR 'extension'
        user = it.get("username") or it.get("account") or it.get("user") or ""
        ext  = it.get("internal") or it.get("extension") or ""
        if user and ext:
            m[user] = str(ext)
    return m

def build_xml(rows):
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<CiscoIPPhoneDirectory>",
        "  <Title>Ham Subaccounts (VoIP.ms)</Title>",
        "  <Prompt>Select contact</Prompt>",
    ]
    for name, tel in rows:
        parts.append(
            f"  <DirectoryEntry><Name>{sax.escape(name)}</Name><Telephone>{sax.escape(tel)}</Telephone></DirectoryEntry>"
        )
    parts.append("</CiscoIPPhoneDirectory>")
    return "\n".join(parts) + "\n"

def main():
    subs = get_subaccounts()
    ext_map = get_internal_extensions()

    entries = []
    for s in subs:
        user = s["username"]
        desc = s["description"] or user
        tel = ext_map.get(user, "")
        if tel:
            entries.append((desc, tel))

    # sort for stable diffs
    entries.sort(key=lambda x: (x[0].lower(), x[1]))

    xml = build_xml(entries)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"Wrote {OUTPUT_PATH} with {len(entries)} entries")
    if not entries:
        print("No matches found. If you expect entries, check:")
        print(" - That API is enabled and not IP-restricted for GitHub Actions")
        print(" - That your subaccounts actually have Internal Extensions assigned")

if __name__ == "__main__":
    main()
