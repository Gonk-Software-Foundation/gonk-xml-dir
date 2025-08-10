#!/usr/bin/env python3
"""
Convert a Cisco-style CiscoIPPhoneDirectory (dir.xml) into Polycom VVX
directory format: 000000000000-directory.xml

Env vars (optional):
  INPUT_PATH  - default: "dir.xml"
  OUTPUT_PATH - default: "000000000000-directory.xml"

Mapping:
  Cisco <DirectoryEntry><Name>AG2V Amelia</Name><Telephone>106962</Telephone>
  -> Polycom <item><ln>AG2V</ln><fn>Amelia</fn><ct>106962</ct></item>
"""

from __future__ import annotations
import os
import sys
import xml.etree.ElementTree as ET
from typing import Tuple

INPUT_PATH = os.environ.get("INPUT_PATH", "dir.xml")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "000000000000-directory.xml")


def split_name(name: str) -> Tuple[str, str]:
    """
    Split "CALLSIGN First Last..." into (ln, fn).
    For your sample data the left column ('ln') is the callsign
    and the right column ('fn') is the person's given name(s).
    If no space is present, put everything in ln.
    """
    if not name:
        return "", ""
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def parse_cisco_dir(path: str):
    tree = ET.parse(path)
    root = tree.getroot()

    # Be tolerant of namespaces or capitalization if they appear later.
    # Expect <CiscoIPPhoneDirectory><DirectoryEntry>...
    entries = []
    for de in root.findall(".//DirectoryEntry"):
        name_el = de.find("Name")
        tel_el = de.find("Telephone")

        name = (name_el.text or "").strip() if name_el is not None else ""
        tel = (tel_el.text or "").strip() if tel_el is not None else ""

        if not tel:
            # Skip entries without a number
            continue

        ln, fn = split_name(name)
        entries.append((ln, fn, tel))

    return entries


def build_polycom_xml(items):
    """
    Construct:
    <directory>
      <item_list>
        <item><ln>..</ln><fn>..</fn><ct>..</ct></item>
      </item_list>
    </directory>
    """
    directory = ET.Element("directory")
    item_list = ET.SubElement(directory, "item_list")

    for ln, fn, ct in items:
        item = ET.SubElement(item_list, "item")
        ln_el = ET.SubElement(item, "ln")
        ln_el.text = ln
        fn_el = ET.SubElement(item, "fn")
        fn_el.text = fn
        ct_el = ET.SubElement(item, "ct")
        ct_el.text = ct

    # Pretty print (ElementTree doesn't do this natively pre-3.9; implement basic indent)
    indent(directory)
    return ET.ElementTree(directory)


def indent(elem, level: int = 0):
    """In-place pretty printer for ElementTree XML."""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: input file not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(2)

    items = parse_cisco_dir(INPUT_PATH)
    tree = build_polycom_xml(items)

    # Ensure target dir exists
    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Write with XML declaration and standalone="yes"
    xml_bytes = ET.tostring(tree.getroot(), encoding="utf-8")
    with open(OUTPUT_PATH, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
        f.write(xml_bytes)

    print(f"Wrote {OUTPUT_PATH} ({len(items)} entries)")


if __name__ == "__main__":
    main()
