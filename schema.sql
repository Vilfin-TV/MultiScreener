-- D1 schema for the IPTV console (vilfintvsql, bound as env.DB in iptv-worker.js).
-- Populated by a periodic sync job (see syncProviderToD1 / syncEpgToD1 in
-- iptv-worker.js) so channel/EPG lookups can eventually read from a real
-- queryable database instead of live-fetching + re-parsing M3U/XMLTV on every
-- request. The live API still reads from the existing cache/live-fetch path;
-- these tables are populated in parallel and not yet the source of truth for
-- reads — see the sync-status notes in iptv-worker.js.

CREATE TABLE IF NOT EXISTS streams_metadata (
    id          TEXT PRIMARY KEY,      -- source_id + '|' + stream url hash
    name        TEXT NOT NULL,
    category    TEXT,
    language    TEXT,
    country     TEXT,
    source_id   TEXT NOT NULL,
    logo_url    TEXT,
    stream_url  TEXT NOT NULL,
    tvg_id      TEXT,                  -- original tvg-id from the M3U, for EPG matching
    quality     TEXT,
    updated_at  INTEGER NOT NULL       -- epoch ms of last sync
);
CREATE INDEX IF NOT EXISTS idx_streams_source   ON streams_metadata(source_id);
CREATE INDEX IF NOT EXISTS idx_streams_category ON streams_metadata(category);
CREATE INDEX IF NOT EXISTS idx_streams_updated  ON streams_metadata(updated_at);

CREATE TABLE IF NOT EXISTS epg_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL,
    tvg_id      TEXT NOT NULL,         -- the guide's own channel id (not always == stream tvg_id)
    title       TEXT NOT NULL,
    description TEXT,
    start_time  INTEGER NOT NULL,      -- epoch ms
    end_time    INTEGER NOT NULL       -- epoch ms
);
CREATE INDEX IF NOT EXISTS idx_epg_lookup ON epg_data(source_id, tvg_id, start_time);
CREATE INDEX IF NOT EXISTS idx_epg_time   ON epg_data(start_time, end_time);

-- Tracks sync progress across cron ticks (Workers cron execution has a time
-- budget, so a full ~157-source sync is spread across many ticks).
CREATE TABLE IF NOT EXISTS sync_state (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  INTEGER
);
