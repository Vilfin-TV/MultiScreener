# Playlists

Drop M3U playlists you are entitled to serve here, named `{provider}.m3u`
(e.g. `jio.m3u`, `airtel.m3u`). The sync workflow (`.github/workflows/main.yml`
→ `scripts/sync_playlists.py`) uploads them into Cloudflare KV under the key
`{provider}_playlist`, which `worker.js` reads at `/api/playlist`.

Source resolution order per provider:

1. Environment URL — `{PROVIDER}_PLAYLIST_URL` repo secret (e.g. `JIO_PLAYLIST_URL`)
2. Committed file — `playlists/{provider}.m3u`

## M3U format

```
#EXTM3U
#EXTINF:-1 tvg-logo="https://example.com/logo.png" group-title="News" tvg-language="English",Channel Name HD
https://example.com/stream/channel.m3u8
```

Recognized attributes: `tvg-logo`, `group-title` (category), `tvg-language`,
and the trailing title. `HD`/`SD` quality is inferred from the title when not
otherwise specified.

> Use only playlists pointing at content you have the right to distribute
> (your own media/RTSP/HLS origins, or openly-licensed catalogs). This pipeline
> does not extract authorized links from commercial provider apps.
