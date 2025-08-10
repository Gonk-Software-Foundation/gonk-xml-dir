import os, requests, xml.sax.saxutils as sax

API_URL   = "https://voip.ms/api/v1/rest.php"
API_USER  = os.environ["VOIPMS_API_USERNAME"]
API_PASS  = os.environ["VOIPMS_API_PASSWORD"]
OUTPUT    = os.environ.get("OUTPUT_PATH", "dir.xml")
DEFAULT_POP = os.environ.get("VOIPMS_DEFAULT_POP", "newyork1.voip.ms")  # change if you like

def api(method, **params):
    r = requests.get(API_URL, params={"api_username": API_USER,
                                      "api_password": API_PASS,
                                      "method": method, **params}, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "success":
        raise SystemExit(f"VoIP.ms API error for {method}: {j}")
    return j

def norm(x): return (x or "").strip()

def build_xml(entries):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<CiscoIPPhoneDirectory>",
        "  <Title>Ham Subaccounts (VoIP.ms)</Title>",
        "  <Prompt>Select contact</Prompt>",
    ]
    for name, tel in entries:
        lines.append(f"  <DirectoryEntry><Name>{sax.escape(name)}</Name>"
                     f"<Telephone>{sax.escape(tel)}</Telephone></DirectoryEntry>")
    lines.append("</CiscoIPPhoneDirectory>")
    return "\n".join(lines) + "\n"

def main():
    subs = api("getSubAccounts").get("sub_accounts") or []

    entries = []
    for s in subs:
        user = norm(s.get("username") or s.get("user"))
        desc = norm(s.get("description")) or user

        # try all likely internal-extension keys first
        ext  = norm(s.get("internal_extension") or s.get("internal") or s.get("extension") or "")
        if ext:
            dial = ext
        else:
            # fall back to free SIP-URI (works if internal extensions are enabled)
            # try to discover their POP/server from payload, else use DEFAULT_POP
            pop = norm(s.get("server") or s.get("pop") or s.get("server_name") or s.get("server_hostname") or DEFAULT_POP)
            # ensure it looks like a hostname
            if "." not in pop:
                pop = DEFAULT_POP
            dial = f"{user}@{pop}"

        if user and dial:
            entries.append((desc, dial))

    entries.sort(key=lambda x: (x[0].lower(), x[1].lower()))
    xml = build_xml(entries)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Wrote {OUTPUT} with {len(entries)} entries")

if __name__ == "__main__":
    main()
