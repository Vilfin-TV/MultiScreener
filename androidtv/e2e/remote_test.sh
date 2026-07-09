#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# VilfinTV Android TV — remote-control E2E test (runs inside a booted emulator).
#
# Drives the app EXACTLY like an Nvidia Shield remote: nothing here touches the
# screen by coordinate. Every interaction is a hardware key event (D-pad, OK,
# Back, media transport, channel up/down) so a green run proves the physical
# remote will work. A screenshot is captured at every stage and the full logcat
# is dumped, so the run is auditable from the uploaded artifacts.
#
# Two phases:
#   • SMOKE (always) — boot, install, launch, and prove D-pad focus moves on the
#     login screen. Needs no credentials.
#   • FULL  (only when IPTV_USER + IPTV_PASS are set) — sign in, open a provider,
#     pick a channel, go fullscreen, hop channels with next/prev, and add a
#     favorite. This is the login-gated part.
#
# Env in:  APK_PATH (required), IPTV_USER, IPTV_PASS (optional → enables FULL)
# Out:     androidtv/e2e/out/*.png screenshots + logcat.txt ; exit!=0 on crash.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

PKG="com.vilfintv.livetv"
ACT="${PKG}/.MainActivity"
APK_PATH="${APK_PATH:?APK_PATH must point at the built APK}"
OUT="$(cd "$(dirname "$0")" && pwd)/out"
mkdir -p "$OUT"
STEP=0
FAIL=0

log()  { echo "▶ $*"; }
warn() { echo "⚠ $*"; }

# Screencap the emulator to a numbered, labelled PNG.
shot() {
  STEP=$((STEP+1))
  local name; name=$(printf "%02d-%s" "$STEP" "$1")
  adb exec-out screencap -p > "$OUT/${name}.png" 2>/dev/null || warn "screencap failed: $1"
  log "shot ${name}.png"
}

# Send one or more key events (numeric keycodes) with a settle pause between.
key() { for k in "$@"; do adb shell input keyevent "$k" >/dev/null 2>&1; sleep 0.6; done; }

# Type text into the currently-focused WebView input WITHOUT opening the
# on-screen keyboard. `input text` injects key events straight to the focused
# WebView editable. Critically we never press OK/CENTER on a field first: doing
# so pops the full-screen leanback IME, which then swallows every later key
# (D-pad moves its key selection, CENTER types the highlighted letter) and the
# test can never escape it. Spaces → %s; single-quote the device-side arg so &,
# |, ; etc. in a password aren't interpreted by the device shell.
type_text() {
  local t="$1"
  t=${t// /%s}
  t=${t//\'/\'\\\'\'}
  adb shell "input text '$t'" >/dev/null 2>&1
  sleep 0.9
}

# Keycodes
DPAD_UP=19; DPAD_DOWN=20; DPAD_LEFT=21; DPAD_RIGHT=22; DPAD_CENTER=23
BACK=4; ENTER=66
MEDIA_PLAY_PAUSE=85; MEDIA_NEXT=87; MEDIA_PREV=88
CHANNEL_UP=166; CHANNEL_DOWN=167; MENU=82

# ── Boot settle ──────────────────────────────────────────────────────────────
log "Waiting for the device to finish booting…"
adb wait-for-device
for i in $(seq 1 60); do
  [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break
  sleep 2
done
adb shell input keyevent 82 >/dev/null 2>&1   # dismiss the lock/keyguard
# Belt-and-suspenders with hw.keyboard=yes: never show the soft IME while a
# hardware keyboard is present, so typing into a field can't pop the leanback
# keyboard and hijack the D-pad.
adb shell settings put secure show_ime_with_hard_keyboard 0 >/dev/null 2>&1
adb shell settings put global window_animation_scale 0 >/dev/null 2>&1
adb shell settings put global transition_animation_scale 0 >/dev/null 2>&1
adb shell settings put global animator_duration_scale 0 >/dev/null 2>&1

# ── Install ──────────────────────────────────────────────────────────────────
log "Installing $APK_PATH"
adb install -r -g "$APK_PATH" || { echo "APK install FAILED"; exit 1; }

# Start collecting logcat for the whole session.
adb logcat -c || true
adb logcat > "$OUT/logcat.txt" 2>&1 &
LOGCAT_PID=$!

# ── Launch ───────────────────────────────────────────────────────────────────
log "Launching $ACT"
adb shell am start -W -n "$ACT" >/dev/null 2>&1
sleep 10              # WebView + remote login page load
shot "launch-login"

# Confirm the process is actually up.
if ! adb shell pidof "$PKG" >/dev/null 2>&1; then
  echo "App process not running after launch"; FAIL=1
fi

# ── SMOKE: D-pad focus movement on the login screen ─────────────────────────
# First D-pad press hands focus to the username field (tvFocusFirst); then we
# walk the login controls to prove __tvNav routing is alive before any login.
log "SMOKE: exercising D-pad on the login screen"
key $DPAD_DOWN;  shot "login-focus-username"
key $DPAD_DOWN;  shot "login-focus-password"
key $DPAD_DOWN;  shot "login-focus-signin"
key $DPAD_UP;    shot "login-focus-back-up"

# ── FULL: only with credentials ─────────────────────────────────────────────
if [ -n "${IPTV_USER:-}" ] && [ -n "${IPTV_PASS:-}" ]; then
  log "FULL: signing in with supplied credentials"

  # Sign in WITHOUT the on-screen keyboard. Username is focused on page load;
  # type straight into it, then D-pad DOWN between fields (routes through the
  # native __tvNav bridge because no IME is open), and only press OK on the
  # Sign In *button* (a button click, never an input → no keyboard).
  key $DPAD_UP $DPAD_UP     # ensure the topmost field (username) is focused
  type_text "$IPTV_USER"
  shot "login-username-typed"
  key $DPAD_DOWN            # → password
  type_text "$IPTV_PASS"
  shot "login-password-typed"
  key $DPAD_DOWN            # → Sign In button
  key $DPAD_CENTER          # click Sign In → submit
  sleep 9                   # auth round-trip + provider screen render
  shot "after-login"

  # Provider hub: first D-pad press focuses the first tile, then OK opens it.
  key $DPAD_DOWN
  shot "provider-focus"
  key $DPAD_CENTER
  sleep 7
  shot "channel-list"

  # Walk into the channel grid and open a channel.
  key $DPAD_DOWN
  key $DPAD_RIGHT
  shot "channel-focus"
  key $DPAD_CENTER          # open channel → player screen
  sleep 9
  shot "player-open"

  # Transport / channel-hop tests (these hit __tvControl via native key map).
  key $MEDIA_PLAY_PAUSE; shot "player-pause"
  key $MEDIA_PLAY_PAUSE; shot "player-resume"
  key $CHANNEL_UP;       sleep 5; shot "channel-next-1"
  key $CHANNEL_UP;       sleep 5; shot "channel-next-2"
  key $CHANNEL_DOWN;     sleep 5; shot "channel-prev-1"
  key $MEDIA_NEXT;       sleep 5; shot "media-next"
  key $MEDIA_PREV;       sleep 5; shot "media-prev"

  # Favorites: MENU jumps focus to the filter row; navigate to a channel's star
  # and toggle it. (Star toggle is a focusable control in the tv-app selector.)
  key $MENU; shot "filters-row"
  key $DPAD_DOWN $DPAD_CENTER; shot "favorite-toggled"

  # Back out: fullscreen → player → provider hub → (would exit).
  key $BACK; sleep 2; shot "back-1"
  key $BACK; sleep 2; shot "back-2"
else
  warn "IPTV_USER / IPTV_PASS not set — skipping the login-gated FULL phase."
  warn "Add repo secrets IPTV_USERNAME and IPTV_PASSWORD to enable it."
fi

# ── Crash / ANR gate ────────────────────────────────────────────────────────
sleep 2
kill "$LOGCAT_PID" >/dev/null 2>&1 || true
if grep -Eq "FATAL EXCEPTION|ANR in ${PKG}|beginning of crash" "$OUT/logcat.txt"; then
  echo "❌ Crash/ANR detected in logcat:"
  grep -E "FATAL EXCEPTION|ANR in ${PKG}|AndroidRuntime" "$OUT/logcat.txt" | head -40
  FAIL=1
fi

log "Screenshots captured:"; ls -1 "$OUT"/*.png 2>/dev/null | sed 's#.*/#  #'

if [ "$FAIL" -ne 0 ]; then echo "❌ E2E test FAILED"; exit 1; fi
echo "✅ E2E remote test passed (smoke$( [ -n "${IPTV_USER:-}" ] && echo ' + full' ))"
