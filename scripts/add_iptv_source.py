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

new = {
    "id":      os.environ["SRC_ID"].strip(),
    "name":    os.environ.get("SRC_NAME", "").strip() or os.environ["SRC_ID"],
    "icon":    os.environ.get("SRC_ICON", "").strip(),
    "group":   os.environ.get("SRC_GROUP", "").strip(),
    "region":  os.environ.get("SRC_REGION", "").strip(),
    "enabled": True,
    "url":     os.environ.get("SRC_URL", "").strip(),
    "epg":     os.environ.get("SRC_EPG", "").strip(),
}
if not new["id"] or not new["url"]:
    print("ABORT: SRC_ID and SRC_URL are required", file=sys.stderr)
    sys.exit(1)

before = len(provs)
idx = next((i for i, p in enumerate(provs) if isinstance(p, dict) and p.get("id") == new["id"]), None)
if idx is None:
    provs.append(new)
    action = "added"
else:
    provs[idx] = new  # update in place (idempotent re-run)
    action = "updated"

settings["providers"] = provs

# Preserve the wrapper shape if the source used one.
out = {"settings": settings} if ("settings" in s and s is not settings) else settings

# Final guard: never shrink the list.
final = out.get("settings", out).get("providers", [])
if len(final) < before:
    print(f"ABORT: provider count shrank {before} -> {len(final)}", file=sys.stderr)
    sys.exit(1)

print(f"{action} '{new['id']}' ({new['name']}); providers {before} -> {len(final)}", file=sys.stderr)
json.dump(out, sys.stdout, ensure_ascii=False)
