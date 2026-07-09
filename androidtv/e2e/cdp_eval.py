#!/usr/bin/env python3
"""Evaluate JavaScript in the app's WebView over Chrome DevTools Protocol.

Used by remote_test.sh to (a) sign in without touching the flaky on-screen
keyboard and (b) read page state for real assertions (which screen is active,
current channel, fullscreen, favourites count) instead of eyeballing pixels.

Usage:
    echo "<js expr>" | cdp_eval.py       # prints JSON of the expression value
    cdp_eval.py --login                  # fills #username/#password from
                                         # $IPTV_USER/$IPTV_PASS and submits

Assumes `adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>` is
already set up. Requires the `websocket-client` package.
"""
import json
import os
import sys
import time
import urllib.request

import websocket  # websocket-client


def _page_ws(retries=30):
    """Return the debugger websocket URL of the app's page target."""
    last = None
    for _ in range(retries):
        try:
            data = json.load(urllib.request.urlopen("http://localhost:9222/json", timeout=5))
            pages = [p for p in data if p.get("type") == "page" and p.get("webSocketDebuggerUrl")]
            # Prefer the iptv page; fall back to the first page target.
            for p in pages:
                if "iptv" in (p.get("url") or ""):
                    return p["webSocketDebuggerUrl"]
            if pages:
                return pages[0]["webSocketDebuggerUrl"]
        except Exception as e:  # devtools not ready yet
            last = e
        time.sleep(1)
    raise SystemExit("CDP: no page target found (%s)" % last)


def evaluate(expr, timeout=20):
    ws = websocket.create_connection(_page_ws(), timeout=timeout)
    try:
        ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        ws.recv()
        ws.send(json.dumps({
            "id": 2,
            "method": "Runtime.evaluate",
            # userGesture lets gesture-gated calls (requestFullscreen, media
            # play) run when we script them.
            "params": {"expression": expr, "returnByValue": True,
                       "awaitPromise": True, "userGesture": True},
        }))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(ws.recv())
            if msg.get("id") == 2:
                res = msg.get("result", {})
                if "exceptionDetails" in res:
                    raise SystemExit("CDP eval error: " + json.dumps(res["exceptionDetails"]))
                return res.get("result", {}).get("value")
        raise SystemExit("CDP: evaluate timed out")
    finally:
        ws.close()


def do_login():
    user = os.environ.get("IPTV_USER", "")
    pw = os.environ.get("IPTV_PASS", "")
    # Build the JS with json.dumps so any quotes/specials in the password are
    # safely escaped — no shell/JS injection, no typing, no keyboard.
    js = (
        "(function(){"
        "var u=document.getElementById('username');"
        "var p=document.getElementById('password');"
        "var b=document.getElementById('login-btn');"
        "if(!u||!p||!b) return 'no-form';"
        "u.value=%s; p.value=%s;"
        "b.click();"
        "return 'submitted';"
        "})()" % (json.dumps(user), json.dumps(pw))
    )
    print(evaluate(js))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--login":
        do_login()
    else:
        expr = sys.stdin.read()
        print(json.dumps(evaluate(expr)))
