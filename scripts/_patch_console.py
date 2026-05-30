#!/usr/bin/env python3
"""Idempotent, self-validating patch: add an IPTV management tab to
link-console.html. Whitespace-robust (line-based) anchoring. Aborts without
changes if anchors are not found. Creates a .bak backup before writing."""
import sys, hashlib, pathlib

F = pathlib.Path("link-console.html")
src = F.read_text(encoding="utf-8")

if 'data-tab="iptv"' in src:
    print("ALREADY PATCHED - no changes made.")
    sys.exit(0)

lines = src.splitlines(keepends=True)

def indent_of(s):
    return s[:len(s) - len(s.lstrip(" "))]

home_i = next((i for i, l in enumerate(lines) if 'data-tab="homepage"' in l), None)
if home_i is None:
    print("ABORT: homepage nav tab not found. No changes."); sys.exit(1)
close_i = next((j for j in range(home_i, min(home_i + 6, len(lines))) if lines[j].strip() == "</div>"), None)
if close_i is None:
    print("ABORT: homepage tab closing </div> not found. No changes."); sys.exit(1)
sw_i = next((i for i, l in enumerate(lines) if "loadAcademyContent()" in l and "name ===" in l), None)
if sw_i is None:
    print("ABORT: switchTab academy dispatch not found. No changes."); sys.exit(1)
if "</script>" not in src:
    print("ABORT: no </script> found. No changes."); sys.exit(1)

ind_nav = indent_of(lines[home_i])
nav_block = (
    ind_nav + "<div class=\"c-tab\" data-tab=\"iptv\" onclick=\"switchTab('iptv')\">\n"
    + ind_nav + "  <span class=\"c-tab-ico\">\U0001F4FA</span> IPTV\n"
    + ind_nav + "</div>\n"
)
ind_sw = indent_of(lines[sw_i])
sw_line = ind_sw + "if (name === 'iptv')     loadIptv();\n"

if sw_i > close_i:
    lines.insert(sw_i + 1, sw_line)
    lines.insert(close_i + 1, nav_block)
else:
    lines.insert(close_i + 1, nav_block)
    lines.insert(sw_i + 1, sw_line)

out = "".join(lines)

MODULE = r"""
<!-- IPTV management (added by scripts/_patch_console.py) -->
<script>
var IPTV_PANEL_HTML =
  '<div style="max-width:760px">' +
    '<h2 style="margin:0 0 6px">\U0001F4FA IPTV Console</h2>' +
    '<p style="opacity:.7;margin:0 0 18px;font-size:14px">Create the login ID &amp; password your viewers use at the private IPTV dashboard, and tune playback settings. The password is salted + hashed before storage in Cloudflare KV.</p>' +
    '<div id="iptv-status" style="padding:12px 14px;border:1px solid rgba(255,255,255,.12);border-radius:10px;margin-bottom:20px;font-size:14px">Loading...</div>' +
    '<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:18px;margin-bottom:18px">' +
      '<h3 style="margin:0 0 14px;font-size:15px">Login credentials</h3>' +
      '<label style="display:block;font-size:12px;opacity:.7;margin-bottom:6px">IPTV Login ID</label>' +
      '<input id="iptv-username" type="text" autocomplete="off" placeholder="e.g. family" style="width:100%;padding:11px 12px;margin-bottom:14px;background:#0f0f12;border:1px solid rgba(255,255,255,.16);border-radius:9px;color:#fff;font-size:14px;box-sizing:border-box">' +
      '<div style="display:flex;gap:12px;flex-wrap:wrap">' +
        '<div style="flex:1;min-width:200px">' +
          '<label style="display:block;font-size:12px;opacity:.7;margin-bottom:6px">Password</label>' +
          '<input id="iptv-password" type="password" autocomplete="new-password" placeholder="at least 6 characters" style="width:100%;padding:11px 12px;background:#0f0f12;border:1px solid rgba(255,255,255,.16);border-radius:9px;color:#fff;font-size:14px;box-sizing:border-box">' +
        '</div>' +
        '<div style="flex:1;min-width:200px">' +
          '<label style="display:block;font-size:12px;opacity:.7;margin-bottom:6px">Confirm Password</label>' +
          '<input id="iptv-password2" type="password" autocomplete="new-password" placeholder="re-enter password" style="width:100%;padding:11px 12px;background:#0f0f12;border:1px solid rgba(255,255,255,.16);border-radius:9px;color:#fff;font-size:14px;box-sizing:border-box">' +
        '</div>' +
      '</div>' +
      '<button id="iptv-cred-save" style="margin-top:16px;padding:11px 20px;background:linear-gradient(135deg,#7c4dff,#6b3dff);color:#fff;border:none;border-radius:9px;font-weight:600;font-size:14px;cursor:pointer">Save login</button>' +
      '<div id="iptv-cred-msg" style="margin-top:10px;font-size:13px;min-height:18px"></div>' +
    '</div>' +
    '<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:18px">' +
      '<h3 style="margin:0 0 14px;font-size:15px">Playback settings</h3>' +
      '<div style="display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end">' +
        '<div style="min-width:150px">' +
          '<label style="display:block;font-size:12px;opacity:.7;margin-bottom:6px">Session length (hours)</label>' +
          '<input id="iptv-session-hours" type="number" min="1" max="168" value="8" style="width:100%;padding:11px 12px;background:#0f0f12;border:1px solid rgba(255,255,255,.16);border-radius:9px;color:#fff;font-size:14px;box-sizing:border-box">' +
        '</div>' +
        '<div style="min-width:170px">' +
          '<label style="display:block;font-size:12px;opacity:.7;margin-bottom:6px">Default provider</label>' +
          '<select id="iptv-default-provider" style="width:100%;padding:11px 12px;background:#0f0f12;border:1px solid rgba(255,255,255,.16);border-radius:9px;color:#fff;font-size:14px;box-sizing:border-box">' +
            '<option value="jio">Jio IPTV</option><option value="airtel">Airtel IPTV</option>' +
          '</select>' +
        '</div>' +
      '</div>' +
      '<div style="margin-top:16px;display:flex;gap:24px;flex-wrap:wrap">' +
        '<label style="display:flex;align-items:center;gap:8px;font-size:14px;cursor:pointer"><input id="iptv-jio-enabled" type="checkbox" checked> Enable Jio</label>' +
        '<label style="display:flex;align-items:center;gap:8px;font-size:14px;cursor:pointer"><input id="iptv-airtel-enabled" type="checkbox" checked> Enable Airtel</label>' +
      '</div>' +
      '<button id="iptv-settings-save" style="margin-top:16px;padding:11px 20px;background:linear-gradient(135deg,#7c4dff,#6b3dff);color:#fff;border:none;border-radius:9px;font-weight:600;font-size:14px;cursor:pointer">Save settings</button>' +
      '<div id="iptv-settings-msg" style="margin-top:10px;font-size:13px;min-height:18px"></div>' +
    '</div>' +
  '</div>';

function _iptvBuildPanel() {
  if (document.getElementById('tab-iptv')) return;
  var host = document.getElementById('tab-content');
  if (!host || !host.parentNode) return;
  var div = document.createElement('div');
  div.className = 'c-panel';
  div.id = 'tab-iptv';
  div.innerHTML = IPTV_PANEL_HTML;
  host.parentNode.appendChild(div);
  document.getElementById('iptv-cred-save').addEventListener('click', saveIptvCredentials);
  document.getElementById('iptv-settings-save').addEventListener('click', saveIptvSettings);
}

function loadIptv() {
  _iptvBuildPanel();
  document.querySelectorAll('.c-panel').forEach(function (p) {
    p.classList.toggle('active', p.id === 'tab-iptv');
  });
  _iptvLoadConfig();
}

async function _iptvLoadConfig() {
  var st = document.getElementById('iptv-status');
  if (!st) return;
  st.textContent = 'Loading...';
  try {
    var res = await authFetch(WORKER + '/api/iptv/config', { method: 'GET' });
    var data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || ('HTTP ' + res.status));
    if (data.credentialsSet) {
      st.innerHTML = 'Login configured - <b>' + esc(data.username || '') + '</b>' +
        (data.updatedAt ? ' <span style="opacity:.6">(updated ' + esc(new Date(data.updatedAt).toLocaleString()) + ')</span>' : '');
    } else {
      st.innerHTML = 'No IPTV login set yet. Create one below.';
    }
    document.getElementById('iptv-username').value = data.username || '';
    var s = data.settings || {};
    document.getElementById('iptv-session-hours').value = s.sessionHours || 8;
    document.getElementById('iptv-default-provider').value = (s.defaultProvider === 'airtel') ? 'airtel' : 'jio';
    document.getElementById('iptv-jio-enabled').checked    = !(s.providers && s.providers.jio    && s.providers.jio.enabled    === false);
    document.getElementById('iptv-airtel-enabled').checked = !(s.providers && s.providers.airtel && s.providers.airtel.enabled === false);
  } catch (e) {
    st.innerHTML = '<span style="color:#ff6b6b">Could not load: ' + esc(e.message) + '</span>';
  }
}

async function saveIptvCredentials() {
  var u = document.getElementById('iptv-username').value.trim();
  var p = document.getElementById('iptv-password').value;
  var c = document.getElementById('iptv-password2').value;
  var msg = document.getElementById('iptv-cred-msg');
  msg.textContent = '';
  if (!u) { msg.innerHTML = '<span style="color:#ff6b6b">Enter a login ID.</span>'; return; }
  if (p.length < 6) { msg.innerHTML = '<span style="color:#ff6b6b">Password must be at least 6 characters.</span>'; return; }
  if (p !== c) { msg.innerHTML = '<span style="color:#ff6b6b">Passwords do not match.</span>'; return; }
  var btn = document.getElementById('iptv-cred-save'); btn.disabled = true; var t = btn.textContent; btn.textContent = 'Saving...';
  try {
    var res = await authFetch(WORKER + '/api/iptv/credentials', { method: 'POST', body: JSON.stringify({ username: u, password: p }) });
    var data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || ('HTTP ' + res.status));
    msg.innerHTML = '<span style="color:#4ddb8a">Saved. Viewers can now sign in with this login.</span>';
    document.getElementById('iptv-password').value = '';
    document.getElementById('iptv-password2').value = '';
    _iptvLoadConfig();
  } catch (e) {
    msg.innerHTML = '<span style="color:#ff6b6b">' + esc(e.message) + '</span>';
  } finally {
    btn.disabled = false; btn.textContent = t;
  }
}

async function saveIptvSettings() {
  var msg = document.getElementById('iptv-settings-msg'); msg.textContent = '';
  var payload = { settings: {
    sessionHours: parseInt(document.getElementById('iptv-session-hours').value, 10) || 8,
    defaultProvider: document.getElementById('iptv-default-provider').value,
    providers: {
      jio:    { enabled: document.getElementById('iptv-jio-enabled').checked },
      airtel: { enabled: document.getElementById('iptv-airtel-enabled').checked }
    }
  }};
  var btn = document.getElementById('iptv-settings-save'); btn.disabled = true; var t = btn.textContent; btn.textContent = 'Saving...';
  try {
    var res = await authFetch(WORKER + '/api/iptv/settings', { method: 'POST', body: JSON.stringify(payload) });
    var data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || ('HTTP ' + res.status));
    msg.innerHTML = '<span style="color:#4ddb8a">Settings saved.</span>';
  } catch (e) {
    msg.innerHTML = '<span style="color:#ff6b6b">' + esc(e.message) + '</span>';
  } finally {
    btn.disabled = false; btn.textContent = t;
  }
}
</script>
"""

idx = out.rfind("</script>")
out = out[:idx + len("</script>")] + MODULE + out[idx + len("</script>"):]

F.with_suffix(".html.bak").write_text(src, encoding="utf-8")
F.write_text(out, encoding="utf-8")

print("PATCHED link-console.html")
print("  nav tab after homepage close line", close_i + 1, "; dispatch after line", sw_i + 1)
print("  +bytes:", len(out) - len(src), "sha256:", hashlib.sha256(out.encode('utf-8')).hexdigest()[:16])
