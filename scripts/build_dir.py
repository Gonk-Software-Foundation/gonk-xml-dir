import os, sys, json, datetime, pathlib
import requests
import xml.sax.saxutils as sax

API_URL   = "https://voip.ms/api/v1/rest.php"
API_USER  = os.environ["VOIPMS_API_USERNAME"]
API_PASS  = os.environ["VOIPMS_API_PASSWORD"]
OUTPUT    = os.environ.get("OUTPUT_PATH", "dir.xml")
DEFAULT_POP = os.environ.get("VOIPMS_DEFAULT_POP", "newyork1.voip.ms")
LOG_PATH  = os.environ.get("LOG_PATH", "logs/voipms_build.log")

def now_utc_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def ensure_dir(p: pathlib.Path):
    p.parent.mkdir(parents=True, exist_ok=True)

def append_log(text: str):
    """Append to rolling log and write a timestamped snapshot."""
    ts = now_utc_iso().replace(":", "-")
    rolling = pathlib.Path(LOG_PATH)
    snapshot = rolling.with_name(f"{rolling.stem}_{ts}{rolling.suffix}")
    ensure_dir(rolling)
    for dest in (rolling, snapshot):
        with open(dest, "a", encoding="utf-8") as f:
            f.write(text)

def api(method, **params):
    q = {"api_username": API_USER, "api_password": API_PASS, "method": method}
    q.update(params)
    r = requests.get(API_URL, params=q, timeout=30)
    info = {
        "time": now_utc_iso(),
        "url": r.url.split("api_password=")[0] + "api_password=***"  # mask pass
    }
    try:
        j = r.json()
    except Exception as e:
        append_log(f"[API] {info['time']} {method} -> HTTP {r.status_code}, non-JSON body\n")
        r.raise_for_status()
        raise

    append_log(
        f"[API] {info['time']} {method} -> HTTP {r.status_code}, status={j.get('status')}\n"
    )
    if j.get("status") != "success":
        # include a short pretty block for visibility
        append_log("[API] payload:\n" + json.dumps(j, indent=2) + "\n")
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
        lines.append(
            f"  <DirectoryEntry><Name>{sax.escape(name)}</Name>"
            f"<Telephone>{sax.escape(tel)}</Telephone></DirectoryEntry>"
        )
    lines.append("</CiscoIPPhoneDirectory>")
    return "\n".join(lines) + "\n"

def main():
    append_log(f"=== Build start {now_utc_iso()} ===\n")
    subs_payload = api("getSubAccounts")
    subs = subs_payload.get("sub_accounts") or subs_payload.get("subaccounts") or []
    append_log(f"[INFO] sub_accounts count: {len(subs)}\n")

    # Show field names and first 3 objects for debugging
    for i, s in enumerate(subs[:3]):
        append_log(f"[DEBUG] sub[{i}] keys: {sorted(s.keys())}\n")
        append_log(json.dumps(s, indent=2) + "\n")

    entries = []
    for idx, s in enumerate(subs):
        user = norm(s.get("username") or s.get("user"))
        desc = norm(s.get("description")) or user

        # try internal extension first (many tenants include it here)
        ext  = norm(s.get("internal_extension") or s.get("internal") or s.get("extension") or "")
        if ext:
            dial = ext
            src  = "internal_extension"
        else:
            # fall back to SIP-URI dialing
            pop = norm(
                s.get("server") or s.get("pop") or s.get("server_name")
                or s.get("server_hostname") or DEFAULT_POP
            )
            if "." not in pop:
                pop = DEFAULT_POP
            dial = f"{user}@{pop}"
            src  = "sip_uri"

        if user and dial:
            entries.append((desc, dial))
            append_log(f"[MAP] {desc}  user={user}  pop={pop if not ext else '-'}  "
                       f"dial={dial}  via={src}\n")
        else:
            append_log(f"[SKIP] idx={idx} missing user or dial. raw={s}\n")

    entries.sort(key=lambda x: (x[0].lower(), x[1].lower()))
    xml = build_xml(entries)
    ensure_dir(pathlib.Path(OUTPUT))
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(xml)
