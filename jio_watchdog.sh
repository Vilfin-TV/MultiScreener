#!/bin/bash
# jio_watchdog.sh — Cron watchdog for jio_bridge.py
# Ensures the Jio bridge process is always running and the M3U is fresh.
# Install in crontab: */10 * * * * /home/vilfintvserver/jio_watchdog.sh >> /home/vilfintvserver/jio_watchdog.log 2>&1

SCRIPT="/home/vilfintvserver/jio_bridge.py"
LOGFILE="/home/vilfintvserver/jio_bridge.log"
PIDFILE="/home/vilfintvserver/jio_bridge.pid"
WORKER_URL="https://screener-proxy.vilfintv.workers.dev"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Watchdog check starting..."

# 1. Check if jio_bridge.py is running
if pgrep -f "python3 .*[j]io_bridge.py" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] jio_bridge.py is running (PID: $(pgrep -f "python3 .*[j]io_bridge.py"))"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] jio_bridge.py is NOT running! Restarting..."
    cd /home/vilfintvserver
    nohup python3 -u "$SCRIPT" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarted jio_bridge.py with PID $!"
    # Give it time to upload M3U
    sleep 45
fi

# 2. Ensure the Cloudflare quick tunnel is running AND reachable (auto-heal).
#    A dead tunnel is exactly what makes the worker's /api/jio/play return 530,
#    so restart it here instead of only warning. tunnel.log is truncated on start
#    so the bridge always picks up the newest URL.
#    NB: the pattern below matches ONLY the quick tunnel, never the named
#    (token) tunnel, whose cmdline is "tunnel --no-autoupdate run --token ...".
QUICK_PAT="tunnel --no-autoupdate --url http://localhost:5000"

start_quick_tunnel() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting quick tunnel -> http://localhost:5000"
    cd /home/vilfintvserver
    : > tunnel.log
    nohup ./cloudflared tunnel --no-autoupdate --url http://localhost:5000 >> tunnel.log 2>&1 &
    sleep 12
}

if ! pgrep -f "$QUICK_PAT" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Quick tunnel NOT running! Starting..."
    start_quick_tunnel
fi

TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' /home/vilfintvserver/tunnel.log 2>/dev/null | tail -n1)
if [ -n "$TUNNEL_URL" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$TUNNEL_URL/playlist.m3u" 2>/dev/null)
    # Healthy = cloudflared reached the origin at all (any non-5xx). 000 (no
    # connection) and 5xx (530 = tunnel not connected) mean the tunnel is down.
    # A 404 just means the bridge is still warming up - do NOT kill the tunnel.
    if [ -n "$HTTP_CODE" ] && [ "$HTTP_CODE" != "000" ] && [ "$HTTP_CODE" -lt 500 ] 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Tunnel healthy ($TUNNEL_URL - HTTP $HTTP_CODE)"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Tunnel UNHEALTHY ($TUNNEL_URL - HTTP $HTTP_CODE) - restarting"
        pkill -f "$QUICK_PAT" 2>/dev/null
        sleep 2
        start_quick_tunnel
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No tunnel URL in tunnel.log - starting quick tunnel"
    start_quick_tunnel
fi

# 3. Verify the M3U is present in KV by checking the IPTV worker API
# (This requires auth, so we just check the local bridge serves channels)
CH_COUNT=$(curl -s --max-time 10 "http://127.0.0.1:5000/playlist.m3u" 2>/dev/null | grep -c "^#EXTINF")
if [ "$CH_COUNT" -gt 10 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Local M3U has $CH_COUNT channels — OK"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Local M3U has only $CH_COUNT channels. Triggering re-upload..."
    # Force a re-upload by sending SIGUSR1 or just restart
    pkill -f "python3 -u $SCRIPT"
    sleep 2
    cd /home/vilfintvserver
    nohup python3 -u "$SCRIPT" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Force-restarted jio_bridge.py with PID $!"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Watchdog check complete."
echo "---"
