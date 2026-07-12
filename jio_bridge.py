#!/usr/bin/env python3
"""
jio_bridge.py

This script runs on your local Linux server.
It polls your Cloudflare Worker for a Jio Phone/OTP request submitted via the Console.
It fetches the channel list, generates an M3U, and runs a local proxy on port 5000.
"""

import time
import requests
import json
import os
import base64
import uuid
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import random

_channel_tokens = {}  # Store acl=/* token for DRM keys

WORKER_URL = "https://screener-proxy.vilfintv.workers.dev"

# Jio's APIs are geo-locked to India. The host's own VPN route flaps between
# exits (it was Singapore when playback broke), and jiotvapi then resets the TLS
# handshake -> SSLEOFError. Always send Jio API calls through the India proxy
# container (nord-india -> 127.0.0.1:8118). Override with the JIO_PROXY env var.
_JIO_PROXY = os.environ.get("JIO_PROXY", "")   # "" = direct (host VPN is India)
JIO_PROXIES = {"http": _JIO_PROXY, "https": _JIO_PROXY} if _JIO_PROXY else None


def _jio_post(url, **kw):
    """POST to a Jio API, surviving brief NordVPN reconnects.

    The host VPN flaps; mid-reconnect the TLS handshake to jiotvapi dies with
    SSLEOFError ("EOF occurred in violation of protocol") and playback 500s.
    Retry a few times with backoff instead of failing the request. Set the
    JIO_PROXY env var to route these calls through an India HTTP proxy instead.
    """
    kw.setdefault("timeout", 15)
    if JIO_PROXIES:
        kw["proxies"] = JIO_PROXIES
    last = None
    for attempt in range(3):
        try:
            return requests.post(url, **kw)
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            last = e
            try:
                host = url.split("/")[2]
            except Exception:
                host = url
            print(f"STATUS: [Jio] {host} attempt {attempt + 1}/3 failed ({type(e).__name__}) - retrying")
            time.sleep(2 * (attempt + 1))
    raise last

_last_m3u = ""  # Cache the last successfully generated M3U in memory

import re as _re
# ── Backend seamless Jio token renewal ──────────────────────────────────────
# Jio's Akamai __hdnea__ token expires in ~120s. Rather than the front-end
# reloading the player (a visible stop), the bridge re-signs server-side: it
# caches each channel's token and, when a /proxy request arrives with an expiring
# token, fetches a fresh geturl for that channel and swaps in the new token. The
# player keeps fetching the same /proxy URLs — no reload, no stop.
_JIO_CH_MAP = {}      # akamai channel folder (e.g. Star_Utsav_Movies_MOB) -> channel_id
_JIO_TOK = {}         # channel_id -> {"keytok": str, "exp": int}
_JIO_TOK_LOCK = threading.Lock()

def _tok_exp(keytok):
    try:
        m = _re.search(r'exp=(\d+)', keytok or '')
        return int(m.group(1)) if m else 0
    except Exception:
        return 0

def _chan_folder(url):
    m = _re.search(r'/bpk-tv/([^/]+)/', url or '')
    return m.group(1) if m else None

def _jio_geturl(ch_id):
    """Call Jio geturl for a channel → (m3u8_url, keytok, exp). Used for the
    initial /play AND for backend token re-signing."""
    if not ch_id or not JIO_AUTH:
        return (None, None, 0)
    url = "https://jiotvapi.media.jio.com/playback/apis/v1/geturl"
    headers = {
        "User-Agent": "okhttp/4.12.0", "Content-Type": "application/x-www-form-urlencoded",
        "appkey": "NzNiMDhlYzQyNjJm", "devicetype": "phone", "os": "android",
        "deviceid": JIO_AUTH.get("deviceId", ""), "versionCode": "402", "osversion": "15",
        "dm": "vivo V2413", "x-platform": "android_mobile", "uniqueid": JIO_AUTH.get("uniqueId", ""),
        "usergroup": "tvYR7NSNn7rymo3F", "languageid": "6", "userid": "ril" + JIO_AUTH.get("crmid", ""),
        "sid": JIO_AUTH.get("analyticsId", ""), "crmid": JIO_AUTH.get("crmid", ""), "isott": "false",
        "channel_id": str(ch_id), "langid": "", "camid": "", "subscriberid": JIO_AUTH.get("crmid", ""),
        "lbcookie": "1", "ssotoken": JIO_AUTH.get("ssoToken", ""), "accesstoken": JIO_AUTH.get("authToken", ""),
    }
    try:
        r = _jio_post(url, headers=headers, data=f"stream_type=Seek&channel_id={ch_id}", timeout=10)
        if r.status_code == 200:
            resp = r.json()
            m3u8_url = resp.get("result", "")
            keytok = ""
            mpd_key = resp.get("mpd", {}).get("key", "")
            if "__hdnea__=" in mpd_key:
                keytok = mpd_key.split("__hdnea__=")[1].split("&")[0]
            if not keytok and "__hdnea__=" in (m3u8_url or ""):
                keytok = m3u8_url.split("__hdnea__=")[1].split("&")[0]
            return (m3u8_url, keytok, _tok_exp(keytok))
    except Exception as e:
        print(f"STATUS: [Jio] re-sign geturl failed for {ch_id}: {e}")
    return (None, None, 0)

def _jio_cache_channel(ch_id, m3u8_url, keytok):
    folder = _chan_folder(m3u8_url)
    if folder:
        _JIO_CH_MAP[folder] = str(ch_id)
    if keytok:
        _JIO_TOK[str(ch_id)] = {"keytok": keytok, "exp": _tok_exp(keytok)}

def _jio_fresh_keytok(target_url, cur_keytok):
    """Return the freshest keytok for the channel behind a /proxy request,
    re-signing (fresh geturl) if within 30s of expiry."""
    folder = _chan_folder(target_url)
    ch_id = _JIO_CH_MAP.get(folder) if folder else None
    if not ch_id:
        return cur_keytok
    now = int(time.time())
    cached = _JIO_TOK.get(ch_id, {})
    best = cached.get("keytok") or cur_keytok
    best_exp = max(_tok_exp(cur_keytok), cached.get("exp", 0))
    if best_exp and best_exp > now + 30:
        return best
    with _JIO_TOK_LOCK:
        cached = _JIO_TOK.get(ch_id, {})
        if cached.get("exp", 0) > now + 30:
            return cached["keytok"]
        _, k, e = _jio_geturl(ch_id)
        if k:
            _JIO_TOK[ch_id] = {"keytok": k, "exp": e}
            print(f"STATUS: [Jio] re-signed token for channel {ch_id} (exp {e})")
            return k
    return best

ADMIN_TOKEN = os.environ.get("WORKER_ADMIN_TOKEN", "")

def set_status(msg):
    print(f"STATUS: {msg}")
    try:
        requests.post(f"{WORKER_URL}/api/jio/auth", headers={"X-Jio-Bridge": "vilfin-secret-jio"}, json={"action": "status", "message": msg}, timeout=5)
    except:
        pass

def generate_and_upload_m3u():
    try:
        set_status("Downloading channel list from Jio CDN...")
        import json
        with open("/home/vilfintvserver/jio_channels.json", "r", encoding="utf-8") as f:
            ch_data = json.load(f)
        
        m3u_lines = ["#EXTM3U"]
        channels = ch_data.get("result", [])
        for ch in channels:
            ch_id = str(ch.get("channel_id", ""))
            ch_name = ch.get("channel_name", f"Channel {ch_id}")
            ch_logo = ch.get("logoUrl", "")
            if ch_logo and not ch_logo.startswith("http"):
                ch_logo = f"https://jiotv.catchup.cdn.jio.com/dare_images/images/{ch_logo}"
            ch_cat = ch.get("channelCategoryId", "General")
            
            # Use jio:// protocol marker so the IPTV Worker resolves the stream
            stream_url = f"jio://{ch_id}"
            
            m3u_lines.append(f'#EXTINF:-1 tvg-id="{ch_id}" tvg-logo="{ch_logo}" group-title="{ch_cat}", {ch_name}')
            m3u_lines.append(stream_url)
            
        m3u_content = "\n".join(m3u_lines)
    except Exception as e:
        set_status(f"Error fetching channels: {e}")
        return None

    # Upload M3U to Worker
    try:
        set_status("Uploading full M3U to Cloudflare KV...")
        upload_payload = {"action": "save_m3u", "m3u": m3u_content}
        r = requests.post(f"{WORKER_URL}/api/jio/auth", headers={"X-Jio-Bridge": "vilfin-secret-jio"}, json=upload_payload, timeout=20)
        if r.status_code != 200:
            set_status(f"Failed to upload M3U, status {r.status_code}: {r.text}")
        else:
            set_status(f"M3U Uploaded ({len(m3u_content)} bytes).")
    except Exception as e:
        set_status(f"Failed to upload M3U: {e}")
        
    # Fetch and Upload EPG
    try:
        set_status("Fetching EPG for India (epg.pw)...")
        epg_req = requests.get("https://epg.pw/xmltv/epg_IN.xml", headers={"User-Agent": "okhttp/4.9.0"}, timeout=20)
        if epg_req.status_code == 200:
            epg_content = epg_req.text
            set_status("Uploading EPG to Cloudflare KV...")
            epg_payload = {"action": "save_epg", "epg": epg_content}
            r_epg = requests.post(f"{WORKER_URL}/api/jio/auth", headers={"X-Jio-Bridge": "vilfin-secret-jio"}, json=epg_payload, timeout=40)
            if r_epg.status_code != 200:
                set_status(f"Failed to upload EPG, status {r_epg.status_code}")
            else:
                set_status(f"EPG Uploaded ({len(epg_content)} bytes). Process complete!")
        else:
            set_status(f"Failed to fetch EPG: HTTP {epg_req.status_code}")
    except Exception as e:
        set_status(f"Failed to fetch/upload EPG: {e}")
    
    # Cache in memory and save local backup
    global _last_m3u
    _last_m3u = m3u_content
    try:
        with open("/home/vilfintvserver/jio_playlist_backup.m3u", "w") as f:
            f.write(m3u_content)
    except:
        pass
        
    return m3u_content

# Store auth globally for the proxy
JIO_AUTH = {}
try:
    with open("jio_auth.json", "r") as f:
        JIO_AUTH = json.load(f)
        try:
            # Get tunnel url if running
            tunnel_url = _get_tunnel_url()

            payload = {"action": "save_auth", "auth": JIO_AUTH}
            if tunnel_url:
                payload["tunnel_url"] = tunnel_url
                print(f"STATUS: Active tunnel detected: {tunnel_url}")

            requests.post(f"{WORKER_URL}/api/jio/auth", headers={"X-Jio-Bridge": "vilfin-secret-jio"}, json=payload, timeout=10)
            print("STATUS: Initial Jio auth creds and tunnel URL uploaded to KV")
            generate_and_upload_m3u()
        except Exception as e:
            print(f"STATUS: Failed to upload auth on startup: {e}")
except:
    pass

def get_auth_request():
    headers = {"X-Jio-Bridge": "vilfin-secret-jio"}
    try:
        r = requests.get(f"{WORKER_URL}/api/jio/auth", headers=headers)
        if r.status_code == 200:
            return r.json().get("data")
    except Exception as e:
        pass
    return None

def set_status(msg):
    print(f"STATUS: {msg}")
    try:
        requests.post(f"{WORKER_URL}/api/jio/auth", headers={"X-Jio-Bridge": "vilfin-secret-jio"}, json={"action": "status", "message": msg}, timeout=5)
    except:
        pass

def jio_send_otp(phone):
    set_status(f"Sending OTP to {phone}...")
    if not phone.startswith("+91"):
        phone = "+91" + phone.lstrip("0")
    b64_num = base64.b64encode(phone.strip().encode('ascii')).decode('ascii')
    url = "https://jiotvapi.media.jio.com/userservice/apis/v1/loginotp/send"
    headers = {
        "appName": "RJIL_JioTV",
        "os": "android",
        "deviceId": uuid.uuid4().hex[:16],
        "devicetype": "phone",
        "User-Agent": "okhttp/4.9.0",
        "Content-Type": "application/json"
    }
    try:
        # Note: Using India proxy might be needed here if running outside India
        # proxies={"http": "http://127.0.0.1:8118", "https": "http://127.0.0.1:8118"}
        r = _jio_post(url, headers=headers, json={"number": b64_num}, timeout=15)
        if r.status_code == 204:
            set_status("OTP Sent successfully. Please enter it below.")
        else:
            set_status(f"Error from Jio: {r.text}")
    except Exception as e:
        set_status(f"Network error sending OTP: {e}")

def jio_verify_otp_and_generate(phone, otp):
    global JIO_AUTH
    set_status(f"Verifying OTP {otp}...")
    if not phone.startswith("+91"):
        phone = "+91" + phone.lstrip("0")
    b64_num = base64.b64encode(phone.strip().encode('ascii')).decode('ascii')
    url = "https://jiotvapi.media.jio.com/userservice/apis/v1/loginotp/verify"
    device_id = uuid.uuid4().hex[:16]
    headers = {
        "appName": "RJIL_JioTV",
        "os": "android",
        "deviceId": device_id,
        "devicetype": "phone",
        "User-Agent": "okhttp/4.9.0",
        "Content-Type": "application/json"
    }
    payload = {
        "number": b64_num,
        "otp": str(otp).strip(),
        "deviceInfo": {
            "consumptionDeviceName": "Jio",
            "info": {
                "type": "android",
                "platform": {"name": "android", "version": "8.0.0"},
                "androidId": device_id
            }
        }
    }
    try:
        r = _jio_post(url, headers=headers, json=payload, timeout=15)
        resp = r.json()
        if "ssoToken" in r.text or r.status_code == 200:
            JIO_AUTH = {
                "ssoToken": resp.get("ssoToken"),
                "crmid": resp.get("sessionAttributes", {}).get("user", {}).get("subscriberId"),
                "uniqueId": resp.get("sessionAttributes", {}).get("user", {}).get("unique"),
                "deviceId": device_id
            }
            if "tempToken" in resp.get("data", resp) and not resp.get("data", resp).get("authToken"):
                # Need to expire other sessions to get authToken
                expire_url = "https://auth.media.jio.com/tokenservice/apis/v2/expireallusers?langId=6"
                expire_headers = {
                    "User-Agent": "okhttp/4.12.0",
                    "x-platform": "android_mobile",
                    "temptoken": resp.get("data", resp).get("tempToken", ""),
                    "Content-Type": "application/json; charset=utf-8"
                }
                expire_payload = {"appName": "RJIL_JioTV", "deviceId": device_id}
                expire_r = _jio_post(expire_url, headers=expire_headers, json=expire_payload, timeout=15)
                expire_resp = expire_r.json()
                if "authToken" in expire_resp.get("data", expire_resp):
                    JIO_AUTH["authToken"] = expire_resp.get("data", expire_resp).get("authToken", "")
                    if "ssoToken" in expire_resp.get("data", expire_resp):
                        JIO_AUTH["ssoToken"] = expire_resp.get("data", expire_resp).get("ssoToken", "")
            else:
                JIO_AUTH["authToken"] = resp.get("data", resp).get("authToken", "")
            
            with open("jio_auth.json", "w") as f:
                json.dump(JIO_AUTH, f)
            
            # Upload auth creds to KV so the IPTV Worker can call Jio API directly
            try:
                payload = {"action": "save_auth", "auth": JIO_AUTH}
                _tu = _get_tunnel_url()
                if _tu: payload["tunnel_url"] = _tu
                requests.post(f"{WORKER_URL}/api/jio/auth", headers={"X-Jio-Bridge": "vilfin-secret-jio"}, json=payload, timeout=10)
            except:
                pass
            
            set_status("OTP Verified successfully! Fetching channels...")
        else:
            set_status(f"Verification Failed: {r.text}")
            return None
    except Exception as e:
        set_status(f"Network error verifying OTP: {e}")
        return None
    
    # Fetch Channels
    generate_and_upload_m3u()
    return "M3U generated and uploaded"



class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class ProxyHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def send_error(self, code, message=None, explain=None):
        self.send_response(code, message)
        self._send_cors_headers()
        self.send_header("Connection", "close")
        self.end_headers()
        if message:
            self.wfile.write(message.encode('utf-8'))

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        
        if parsed.path == "/playlist.m3u":
            global _last_m3u
            if _last_m3u:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header('Content-Type', 'audio/x-mpegurl')
                self.end_headers()
                self.wfile.write(_last_m3u.encode('utf-8'))
            else:
                self.send_error(404, "M3U not generated yet")
            return
        
        if parsed.path == "/play":
            ch_id = qs.get("id", [""])[0]
            if not ch_id or not JIO_AUTH:
                self.send_error(400, "Missing ID or not authenticated")
                return
                
            url = "https://jiotvapi.media.jio.com/playback/apis/v1/geturl"
            headers = {
                "User-Agent": "okhttp/4.12.0",
                "Content-Type": "application/x-www-form-urlencoded",
                "appkey": "NzNiMDhlYzQyNjJm",
                "devicetype": "phone",
                "os": "android",
                "deviceid": JIO_AUTH.get("deviceId", ""),
                "versionCode": "402",
                "osversion": "15",
                "dm": "vivo V2413",
                "x-platform": "android_mobile",
                "uniqueid": JIO_AUTH.get("uniqueId", ""),
                "usergroup": "tvYR7NSNn7rymo3F",
                "languageid": "6",
                "userid": "ril" + JIO_AUTH.get("crmid", ""),
                "sid": JIO_AUTH.get("analyticsId", ""),
                "crmid": JIO_AUTH.get("crmid", ""),
                "isott": "false",
                "channel_id": str(ch_id),
                "langid": "",
                "camid": "",
                "subscriberid": JIO_AUTH.get("crmid", ""),
                "lbcookie": "1",
                "ssotoken": JIO_AUTH.get("ssoToken", ""),
                "accesstoken": JIO_AUTH.get("authToken", "")
            }
            payload = f"stream_type=Seek&channel_id={ch_id}"
            try:
                print("DEBUG Headers:", headers)
                print("DEBUG Payload:", payload)
                r = _jio_post(url, headers=headers, data=payload, timeout=10)
                print("DEBUG Response:", r.text)
                if r.status_code == 200:
                    resp = r.json()
                    m3u8_url = resp.get("result", "")
                    if m3u8_url:
                        proxy_url = f"/proxy?url={base64.urlsafe_b64encode(m3u8_url.encode()).decode()}"

                        mpd_key = resp.get("mpd", {}).get("key", "")
                        token = ""
                        if "__hdnea__=" in mpd_key:
                            token = mpd_key.split("__hdnea__=")[1].split("&")[0]
                            proxy_url += f"&keytok={base64.urlsafe_b64encode(token.encode()).decode()}"
                        _jio_cache_channel(ch_id, m3u8_url, token)   # remember for backend re-signing

                        self.send_response(302)
                        self.send_header('Location', proxy_url)
                        self._send_cors_headers()
                        self.end_headers()
                        return
                
                self.send_error(500, f"Jio error: {r.text}")
            except Exception as e:
                self.send_error(500, str(e))
                
        elif parsed.path == "/proxy":
            target_b64 = qs.get("url", [""])[0]
            keytok_b64 = qs.get("keytok", [""])[0]
            if not target_b64:
                self.send_error(400, "Missing target")
                return
            target_url = base64.urlsafe_b64decode(target_b64 + "=" * ((4 - len(target_b64) % 4) % 4)).decode()
            
            # JIO CDN CANONICALIZATION (REMOVED - IT BROKE OTHER CHANNELS)
            # if '.cdn.jio.com' in target_url and '/bpk-tv/' not in target_url:
            #     import re
            #     target_url = re.sub(r'\.cdn\.jio\.com/([^/]+)/\1\.m3u8', r'.cdn.jio.com/\1/index.m3u8', target_url)
            #     target_url = re.sub(r'\.cdn\.jio\.com/([^/]+)/', r'.cdn.jio.com/bpk-tv/\1/Fallback/', target_url)
            
            keytok = ""
            if keytok_b64:
                keytok_b64 += "=" * ((4 - len(keytok_b64) % 4) % 4)
                keytok = base64.urlsafe_b64decode(keytok_b64).decode()

            # Backend seamless renewal: if this channel's token is expiring, swap in
            # a freshly re-signed one so playback never stops (no front-end reload).
            keytok = _jio_fresh_keytok(target_url, keytok)

            if keytok:
                if '__hdnea__=' in target_url:
                    target_url = target_url.split('__hdnea__=')[0]
                    if target_url.endswith('&') or target_url.endswith('?'):
                        target_url = target_url[:-1]
                separator = '&' if '?' in target_url else '?'
                target_url = f"{target_url}{separator}__hdnea__={keytok}"

            # FASTLY BYPASS: Force streams to use Akamai instead of Fastly
            # to prevent NordVPN 450 blocks, BUT ONLY IF the path is a BPK path.
            # Akamai does not mirror non-BPK paths, so rewriting them would cause 404s.
            if '/bpk-tv/' in target_url:
                if 'tv.media.jio.com' in target_url:
                    target_url = target_url.replace('tv.media.jio.com', 'jiotvbpkmob.cdn.jio.com')
                if 'jiotvmblive.cdn.jio.com' in target_url:
                    target_url = target_url.replace('jiotvmblive.cdn.jio.com', 'jiotvbpkmob.cdn.jio.com')
                
            try:
                headers = {
                    "User-Agent": "okhttp/4.12.0"
                }
                
                
                r = requests.get(target_url, headers=headers, stream=True)
                
                self.send_response(r.status_code)
                self._send_cors_headers()
                
                for k, v in r.headers.items():
                    if k.lower() not in ['content-encoding', 'transfer-encoding', 'connection', 'access-control-allow-origin', 'content-length']:
                        self.send_header(k, v)
                self.end_headers()
                
                if 'mpegurl' in r.headers.get('content-type', '').lower() or target_url.endswith('.m3u8'):
                    content = r.text
                    lines = content.split('\n')
                    import re
                    for i, line in enumerate(lines):
                        line = line.strip()
                        if line:
                            if line.startswith('#EXT-X-KEY:'):
                                match = re.search(r'URI="([^"]+)"', line)
                                if match:
                                    key_url = match.group(1)
                                    qs_idx = target_url.find('?')
                                    query_string = target_url[qs_idx:] if qs_idx != -1 else ""
                                    
                                    from urllib.parse import urljoin
                                    if not key_url.startswith('http'):
                                        key_url = urljoin(target_url, key_url)
                                    
                                    if query_string and "?" not in key_url:
                                        key_url = f"{key_url}{query_string}"
                                        
                                    if 'tv.media.jio.com/fallback/bpk-tv/' in key_url:
                                        key_url = key_url.replace('tv.media.jio.com/fallback/bpk-tv/', 'jiotvbpkmob.cdn.jio.com/bpk-tv/')
                                    
                                    proxy_key_url = f"/proxy?url={base64.urlsafe_b64encode(key_url.encode()).decode()}"
                                    if keytok:
                                        proxy_key_url += f"&keytok={base64.urlsafe_b64encode(keytok.encode()).decode()}"
                                    lines[i] = line.replace(f'URI="{match.group(1)}"', f'URI="{proxy_key_url}"')
                            elif not line.startswith('#'):
                                if not line.startswith('http'):
                                    from urllib.parse import urljoin
                                    qs_idx = target_url.find('?')
                                    query_string = target_url[qs_idx:] if qs_idx != -1 else ""
                                    
                                    line = urljoin(target_url, line)

                                    if query_string and "?" not in line:
                                        line = f"{line}{query_string}"
                                proxy_url = f"/proxy?url={base64.urlsafe_b64encode(line.encode()).decode()}"
                                if keytok:
                                    proxy_url += f"&keytok={base64.urlsafe_b64encode(keytok.encode()).decode()}"
                                lines[i] = proxy_url
                    self.wfile.write('\n'.join(lines).encode())
                else:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            self.wfile.write(chunk)
            except Exception as e:
                pass
        else:
            self.send_error(404, "Not Found")

def start_proxy():
    server = ThreadedHTTPServer(('0.0.0.0', 5000), ProxyHandler)
    print("Local Stream Proxy running on port 5000...")
    server.serve_forever()


M3U_REFRESH_INTERVAL = 20 * 60  # Re-upload M3U every 20 minutes

def _get_tunnel_url():
    """Return the NEWEST *reachable* Cloudflare quick-tunnel URL from tunnel.log.

    Two bugs used to live here:
      1) re.search() returned the FIRST url ever written to tunnel.log, so after
         cloudflared restarted (appending a new url) the bridge kept publishing
         the old, dead one -> the worker proxied to a corpse and returned 530.
      2) It published the url without checking it was alive.
    Take the LAST match, and never publish a tunnel we cannot reach.
    """
    try:
        import re
        home_dir = os.path.expanduser("~")
        with open(os.path.join(home_dir, "tunnel.log"), "r") as tf:
            urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', tf.read())
        if not urls:
            return None
        url = urls[-1]
        try:
            r = requests.get(url + "/playlist.m3u", timeout=8)
            if r.status_code >= 500:
                print(f"STATUS: [Tunnel] {url} unhealthy (HTTP {r.status_code}) - not publishing")
                return None
        except Exception as e:
            print(f"STATUS: [Tunnel] {url} unreachable ({e}) - not publishing")
            return None
        return url
    except Exception:
        pass
    return None

def periodic_m3u_refresh():
    """Background thread: re-upload the Jio M3U to KV every 20 minutes
    so the channel list never disappears due to KV TTL expiration."""
    while True:
        try:
            print(f"STATUS: [Refresh] Periodic M3U re-upload starting...")
            result = generate_and_upload_m3u()
            if result:
                print(f"STATUS: [Refresh] M3U refreshed successfully ({len(result)} bytes)")
            else:
                print(f"STATUS: [Refresh] M3U refresh returned None — will retry next cycle")
            # Also refresh the tunnel URL in case it changed
            tunnel_url = _get_tunnel_url()
            if tunnel_url and JIO_AUTH:
                payload = {"action": "save_auth", "auth": JIO_AUTH}
                payload["tunnel_url"] = tunnel_url
                requests.post(f"{WORKER_URL}/api/jio/auth",
                              headers={"X-Jio-Bridge": "vilfin-secret-jio"},
                              json=payload, timeout=10)
                print(f"STATUS: [Refresh] Tunnel URL updated: {tunnel_url}")
        except Exception as e:
            print(f"STATUS: [Refresh] Error in periodic refresh: {e}")
        time.sleep(M3U_REFRESH_INTERVAL)


def main():
    print("=== JioTV Local Bridge & Proxy Started ===")
    
    t = threading.Thread(target=start_proxy, daemon=True)
    t.start()
    
    # Start periodic M3U refresh thread
    refresh_t = threading.Thread(target=periodic_m3u_refresh, daemon=True)
    refresh_t.start()
    print("STATUS: Periodic M3U refresh thread started (every 20 min)")
    
    print("Listening for Console OTP requests...")
    last_state = None
    
    while True:
        try:
            req = get_auth_request()
            if req:
                action = req.get("action")
                phone = req.get("phone")
                if action == "set_phone" and last_state != "phone_sent" and phone:
                    jio_send_otp(phone)
                    last_state = "phone_sent"
                elif action == "set_otp" and last_state != "otp_sent":
                    otp = req.get("otp")
                    if phone and otp:
                        m3u = jio_verify_otp_and_generate(phone, otp)
                        last_state = "otp_sent"
                        print("[*] Proxy is running. Open vilfintv.com, ensure Mixed Content is allowed, and play!")
        except Exception as e:
            pass
                
        time.sleep(5)

if __name__ == "__main__":
    main()
