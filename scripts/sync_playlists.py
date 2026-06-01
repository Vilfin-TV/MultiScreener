#!/usr/bin/env python3
"""
sync_playlists.py — compile M3U playlists and push them into Cloudflare KV.

Scope
-----
This script syncs playlists YOU supply and are entitled to serve. For each
provider it resolves an M3U source in this priority order:

  1. Environment URL   ->  {PROVIDER}_PLAYLIST_URL   (e.g. JIO_PLAYLIST_URL)
  2. Committed file     ->  playlists/{provider}.m3u

It then uploads the raw M3U to the KV namespace under the key
"{provider}_playlist", which worker.js reads at /api/playlist.

It deliberately does NOT log in to any commercial provider's mobile API to
harvest authorized stream tokens — supply your own source URL or file instead.

Environment variables
----------------------
  CLOUDFLARE_API_TOKEN    (required)  Workers KV Storage: Edit
  CLOUDFLARE_ACCOUNT_ID   (required)
  IPTV_KV_NAMESPACE_ID    (required)
  PROVIDERS               (optional)  default "jio,airtel"
  {PROVIDER}_PLAYLIST_URL (optional)  per-provider source URL
"""

import os
import sys
import pathlib
import requests

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAYLIST_DIR = REPO_ROOT / "playlists"

CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
KV_NAMESPACE_ID = os.environ.get("IPTV_KV_NAMESPACE_ID", "").strip()
PROVIDERS = [p.strip().lower() for p in os.environ.get("PROVIDERS", "jio,airtel").split(",") if p.strip()]

HTTP_TIMEOUT = 30


def fail(msg: str) -> None:
    print(f"::error::{msg}")
    sys.exit(1)


def fetch_url(url: str) -> str:
    """Fetch an M3U from a source you control."""
    resp = requests.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": "IPTVConsole-Sync/1.0"})
    resp.raise_for_status()
    return resp.text


def resolve_playlist(provider: str) -> str | None:
    """Resolve an M3U for a provider from env URL or committed file."""
    env_key = f"{provider.upper()}_PLAYLIST_URL"
    url = os.environ.get(env_key, "").strip()
    if url:
        print(f"[{provider}] sourcing from {env_key}")
        try:
            return fetch_url(url)
        except requests.RequestException as exc:
            print(f"::warning::[{provider}] URL fetch failed: {exc}")

    local = PLAYLIST_DIR / f"{provider}.m3u"
    if local.exists():
        print(f"[{provider}] sourcing from committed file {local.relative_to(REPO_ROOT)}")
        return local.read_text(encoding="utf-8")

    print(f"::warning::[{provider}] no source found (set {env_key} or add playlists/{provider}.m3u)")
    return None


def validate_m3u(text: str) -> bool:
    return "#EXTM3U" in text or "#EXTINF" in text


def upload_to_kv(provider: str, body: str) -> None:
    """PUT raw M3U into Cloudflare KV under {provider}_playlist."""
    key = f"{provider}_playlist"
    api = (
        f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}"
        f"/storage/kv/namespaces/{KV_NAMESPACE_ID}/values/{key}"
    )
    resp = requests.put(
        api,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "text/plain",
        },
        data=body.encode("utf-8"),
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code not in (200, 201):
        fail(f"[{provider}] KV upload failed ({resp.status_code}): {resp.text[:300]}")
    print(f"[{provider}] uploaded {len(body)} bytes to KV key '{key}'")


def main() -> None:
    missing = [n for n, v in {
        "CLOUDFLARE_API_TOKEN": CF_API_TOKEN,
        "CLOUDFLARE_ACCOUNT_ID": CF_ACCOUNT_ID,
        "IPTV_KV_NAMESPACE_ID": KV_NAMESPACE_ID,
    }.items() if not v]
    if missing:
        fail(f"Missing required secrets: {', '.join(missing)}")

    synced = 0
    for provider in PROVIDERS:
        body = resolve_playlist(provider)
        if not body:
            continue
        if not validate_m3u(body):
            print(f"::warning::[{provider}] content does not look like M3U; skipping")
            continue
        upload_to_kv(provider, body)
        synced += 1

    if synced == 0:
        # Not an error: jio/airtel have no source configured, and free/pro are
        # fetched directly by the worker (no KV sync needed). Exit cleanly so the
        # scheduled run stays green instead of emailing a failure every 6 hours.
        print("::notice::No playlist sources configured for "
              f"{', '.join(PROVIDERS)} — nothing to sync. "
              "Set {PROVIDER}_PLAYLIST_URL secrets or add playlists/{provider}.m3u to enable.")
        return
    print(f"Done. Synced {synced}/{len(PROVIDERS)} provider(s).")


if __name__ == "__main__":
    main()
