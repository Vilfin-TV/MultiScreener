# VilfinTV Live TV — Android TV app (Nvidia Shield)

A lightweight Android TV (Leanback) wrapper around the live VilfinTV web app,
restricted to **IPTV + Jio TV**. Everything streams from the existing backend —
no channel data is bundled, so the app never needs rebuilding for content changes.

- Loads `https://vilfintv.com/iptv.html?app=tv`
- D-pad / Shield-remote focus navigation, full-screen HLS playback, BACK handling
- Leanback launcher entry so it appears on the Shield home row
- Only `INTERNET` + `ACCESS_NETWORK_STATE` permissions → clean install

## How the APK is built

There is no local Android toolchain requirement. The APK is built in the cloud by
GitHub Actions (`.github/workflows/build_tv_apk.yml`) and published as a downloadable
artifact named **VilfinTV-LiveTV-apk**.

Trigger it: GitHub → Actions → "Build VilfinTV Android TV APK" → Run workflow
(it also runs automatically on any push under `androidtv/`).

The signed (debug-key) `VilfinTV-LiveTV.apk` is committed to `androidtv/dist/`
for direct USB sideloading.

## Install on the Shield

1. Copy `dist/VilfinTV-LiveTV.apk` to a USB stick.
2. On the Shield: Settings → Device Preferences → Security & restrictions →
   Unknown sources → enable your file manager.
3. Open the APK with a file manager (e.g. "X-plore" or "Send files to TV") and install.
4. Launch "VilfinTV Live TV" from the home row, sign in once with your console
   credentials — the login persists.

## First-run

The app opens the lineup hub with just **IPTV** and **Jio TV**. Everything else
(channel grid, EPG guide, favourites, full-screen) works exactly as on the website.
