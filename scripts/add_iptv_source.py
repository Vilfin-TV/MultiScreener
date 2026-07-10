#!/usr/bin/env python3
"""Add (idempotently) one IPTV source to the live iptv_settings JSON.

Reads the CURRENT settings JSON from stdin, appends the new provider if it's not
already there, and writes the merged settings to stdout. Hard safety guard: if
the input doesn't already contain a healthy provider list, it ABORTS (exit 1)
rather than risk clobbering the live 266-source lineup with an empty write.

Env inputs (the source to add):
  SRC_ID, SRC_NAME, SRC_ICON, SRC_REGION, SRC_GROUP, SRC_URL, SRC_EPG
"""
import json
import os
import sys

MIN_PROVIDERS = 20  # sanity floor: the live list has ~130+, never write if fewer

raw = sys.stdin.read().strip()
if not raw:
    print("ABORT: empty iptv_settings input — refusing to write", file=sys.stderr)
    sys.exit(1)
try:
    s = json.loads(raw)
except Exception as e:
    print(f"ABORT: iptv_settings is not valid JSON ({e})", file=sys.stderr)
    sys.exit(1)

# settings may be the object itself, or wrapped as {"settings": {...}}
settings = s.get("settings", s) if isinstance(s, dict) else None
if not isinstance(settings, dict):
    print("ABORT: unexpected settings shape", file=sys.stderr)
    sys.exit(1)

provs = settings.get("providers")
# providers may be an array or a dict (object) — normalise to a list
if isinstance(provs, dict):
    provs = list(provs.values())
if not isinstance(provs, list):
    print("ABORT: providers is not a list/dict", file=sys.stderr)
    sys.exit(1)

if len(provs) < MIN_PROVIDERS:
    print(f"ABORT: only {len(provs)} providers in current settings (<{MIN_PROVIDERS}); "
          "refusing to write — this looks like a bad/empty read", file=sys.stderr)
    sys.exit(1)

# Sources to add: either a batch JSON file ($SRC_FILE, an array of provider
# objects) or a single one from SRC_* env vars.
if os.environ.get("SRC_FILE"):
    try:
        incoming = json.load(open(os.environ["SRC_FILE"], encoding="utf-8"))
    except Exception as e:
        print(f"ABORT: cannot read SRC_FILE ({e})", file=sys.stderr)
        sys.exit(1)
    if not isinstance(incoming, list) or not incoming:
        print("ABORT: SRC_FILE must be a non-empty JSON array", file=sys.stderr)
        sys.exit(1)
else:
    incoming = [{
        "id":     os.environ.get("SRC_ID", ""),
        "name":   os.environ.get("SRC_NAME", ""),
        "icon":   os.environ.get("SRC_ICON", ""),
        "group":  os.environ.get("SRC_GROUP", ""),
        "region": os.environ.get("SRC_REGION", ""),
        "url":    os.environ.get("SRC_URL", ""),
        "epg":    os.environ.get("SRC_EPG", ""),
    }]

before = len(provs)
for src in incoming:
    new = {
        "id":      str(src.get("id", "")).strip(),
        "name":    str(src.get("name", "")).strip() or str(src.get("id", "")),
        "icon":    str(src.get("icon", "")).strip(),
        "group":   str(src.get("group", "")).strip(),
        "region":  str(src.get("region", "")).strip(),
        "enabled": bool(src.get("enabled", True)),
        "url":     str(src.get("url", "")).strip(),
        "epg":     str(src.get("epg", "")).strip(),
    }
    if not new["id"] or not new["url"]:
        print(f"ABORT: each source needs id+url (bad entry: {src})", file=sys.stderr)
        sys.exit(1)
    idx = next((i for i, p in enumerate(provs) if isinstance(p, dict) and p.get("id") == new["id"]), None)
    if idx is None:
        provs.append(new)
        print(f"added '{new['id']}' ({new['name']})", file=sys.stderr)
    else:
        provs[idx] = new  # idempotent re-run
        print(f"updated '{new['id']}' ({new['name']})", file=sys.stderr)

settings["providers"] = provs

# Preserve the wrapper shape if the source used one.
out = {"settings": settings} if ("settings" in s and s is not settings) else settings

# Final guard: never shrink the list.
final = out.get("settings", out).get("providers", [])
if len(final) < before:
    print(f"ABORT: provider count shrank {before} -> {len(final)}", file=sys.stderr)
    sys.exit(1)

print(f"providers {before} -> {len(final)}", file=sys.stderr)
json.dump(out, sys.stdout, ensure_ascii=False)
