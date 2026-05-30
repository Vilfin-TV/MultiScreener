# VilfinTV — Broken YouTube Channel Audit

**Audited:** 2026-05-14 · **Source of truth:** `index.html` → `YT_CHANNELS` array (141 entries, channel no. 1–141)

---

## Summary

- **141** channels total in the live channel list.
- **57** channels are **broken right now** — they will not play.
- **28** channels **play today but cannot self-repair** (no channel ID, so the daily updater skips them).
- **28** channels work but have **no fallback stream** (minor — redundancy only).
- **28** channels are fully healthy.

> **Important structural finding:** the website builds its channel list from the `YT_CHANNELS` array embedded directly inside `index.html` (around line 8204). It does **not** read `streams.json` at runtime. `streams.json` is a separate 135-entry file used only by the GitHub Actions auto-updater, and it is already out of sync with the 141-channel list. **Any fix must be written into `index.html`.**

---

## Tier 1 — CRITICAL: no primary video ID (55 channels)

These entries have an empty `v1` (and empty `v2`). The player has nothing to load — the channel is dead. Each still has a valid channel ID, so a fresh live video ID can be pulled from the channel's `/live` page.

| # | Channel | Country / Lang | Channel ID | Get fresh ID from |
|---|---|---|---|---|
| 42 | Public TV | India / Kannada | `UCl-OodciBGZ0k8K8rBZGe4w` | https://www.youtube.com/channel/UCl-OodciBGZ0k8K8rBZGe4w/live |
| 43 | Asianet Suvarna News | India / Kannada | `UCjElJyiXmQXnWmceQ1JyKrA` | https://www.youtube.com/channel/UCjElJyiXmQXnWmceQ1JyKrA/live |
| 44 | News18 Kannada | India / Kannada | `UCa-vioGhe2btBcZneaPonKA` | https://www.youtube.com/channel/UCa-vioGhe2btBcZneaPonKA/live |
| 45 | Btv News Kannada | India / Kannada | `UC55LzMuR6ZeSpJMNCAfzb8w` | https://www.youtube.com/channel/UC55LzMuR6ZeSpJMNCAfzb8w/live |
| 46 | Dighvijay News 24x7 | India / Kannada | `UCXiuoyBQfNm0nlDEiy4lXLg` | https://www.youtube.com/channel/UCXiuoyBQfNm0nlDEiy4lXLg/live |
| 47 | OTV (Odisha TV) | India / Odia | `UCCgLMMp4lv7fSD2sBz1Ai6Q` | https://www.youtube.com/channel/UCCgLMMp4lv7fSD2sBz1Ai6Q/live |
| 48 | ABP Majha | India / Marathi | `UCH7nv1A9xIrAifZJNvt7cgA` | https://www.youtube.com/channel/UCH7nv1A9xIrAifZJNvt7cgA/live |
| 49 | News18 Lokmat | India / Marathi | `UCrcpw88HvKJ0skdsHniCJtQ` | https://www.youtube.com/channel/UCrcpw88HvKJ0skdsHniCJtQ/live |
| 50 | ABP Ananda | India / Bengali | `UCv3rFzn-GHGtqzXiaq3sWNg` | https://www.youtube.com/channel/UCv3rFzn-GHGtqzXiaq3sWNg/live |
| 51 | Prudent Media Goa | India / Konkani | `UCJb1MeQClvGeSMeBSVLKnDQ` | https://www.youtube.com/channel/UCJb1MeQClvGeSMeBSVLKnDQ/live |
| 52 | Goa 365 TV | India / Konkani | `UCDFOkbaN9IuV6tjO8Aqo1ww` | https://www.youtube.com/channel/UCDFOkbaN9IuV6tjO8Aqo1ww/live |
| 53 | In Goa 24x7 | India / Konkani | `UCE9AZSYybiCWNYKr9gbY1lA` | https://www.youtube.com/channel/UCE9AZSYybiCWNYKr9gbY1lA/live |
| 73 | United Nations | International / English | `UC5O114-PQNYkurlTg6hekZw` | https://www.youtube.com/channel/UC5O114-PQNYkurlTg6hekZw/live |
| 74 | CNN Indonesia | Indonesia / Indonesian | `UCKII0Ml9S5wneKbHswmUrIQ` | https://www.youtube.com/channel/UCKII0Ml9S5wneKbHswmUrIQ/live |
| 75 | tvOneNews | Indonesia / Indonesian | `UCER4rvDnRBPr_ncYW4UCZjg` | https://www.youtube.com/channel/UCER4rvDnRBPr_ncYW4UCZjg/live |
| 95 | REPORTER LIVE | India / Malayalam | `UCFx1nseXKTc1Culiu3neeSQ` | https://www.youtube.com/channel/UCFx1nseXKTc1Culiu3neeSQ/live |
| 96 | News18 Kerala | India / Malayalam | `UC-mMi78WJST4N5o8_i1FoXw` | https://www.youtube.com/channel/UC-mMi78WJST4N5o8_i1FoXw/live |
| 97 | Jaihind News | India / Malayalam | `UCDM528eqIJElfflkvfT-MuQ` | https://www.youtube.com/channel/UCDM528eqIJElfflkvfT-MuQ/live |
| 98 | Kaumudy TV | India / Malayalam | `UCSVALYUGVruJ4I2RjhiudSQ` | https://www.youtube.com/channel/UCSVALYUGVruJ4I2RjhiudSQ/live |
| 99 | POWERVISION TV | India / Malayalam | `UCzxfpzSF7mz8j7bNIXyZWmA` | https://www.youtube.com/channel/UCzxfpzSF7mz8j7bNIXyZWmA/live |
| 100 | Shalom TV Live | India / Malayalam | `UCw0zgXgBT81prKkU9YwwD8g` | https://www.youtube.com/channel/UCw0zgXgBT81prKkU9YwwD8g/live |
| 101 | Goodness Online | India / Malayalam | `UC1qaqWyxs3QK-4ljZMuSxSA` | https://www.youtube.com/channel/UC1qaqWyxs3QK-4ljZMuSxSA/live |
| 102 | Shalom World Prayer | India / English | `UCIFjeNtkyUCoxoPOxXkarTA` | https://www.youtube.com/channel/UCIFjeNtkyUCoxoPOxXkarTA/live |
| 104 | Star Music X Lyrically | India / Tamil | `UCH-KAVLGvwDg7Ul7XdX2bOA` | https://www.youtube.com/channel/UCH-KAVLGvwDg7Ul7XdX2bOA/live |
| 105 | TBS NEWS DIG | Japan / Japanese | `UC6AG81pAkf6Lbi_1VC5NmPA` | https://www.youtube.com/channel/UC6AG81pAkf6Lbi_1VC5NmPA/live |
| 106 | YTN | South Korea / Korean | `UChlgI3UHCOnwUGzWzbJ3H5w` | https://www.youtube.com/channel/UChlgI3UHCOnwUGzWzbJ3H5w/live |
| 107 | Thairath News | Thailand / Thai | `UCrFDdD-EE05N7gjwZho2wqw` | https://www.youtube.com/channel/UCrFDdD-EE05N7gjwZho2wqw/live |
| 108 | TVBS NEWS | Taiwan / Chinese | `UC5nwNW4KdC0SzrhF9BXEYOQ` | https://www.youtube.com/channel/UC5nwNW4KdC0SzrhF9BXEYOQ/live |
| 109 | VTV24 | Vietnam / Vietnamese | `UCabsTV34JwALXKGMqHpvUiA` | https://www.youtube.com/channel/UCabsTV34JwALXKGMqHpvUiA/live |
| 110 | Eagle News | Philippines / Filipino | `UCPoVy9RE7OvlX8AkksLHsyA` | https://www.youtube.com/channel/UCPoVy9RE7OvlX8AkksLHsyA/live |
| 111 | CNA | Singapore / English | `UC83jt4dlz1Gjl58fzQrrKZg` | https://www.youtube.com/channel/UC83jt4dlz1Gjl58fzQrrKZg/live |
| 112 | Astro AWANI | Malaysia / Malay | `UC5dYmq91e5_g54krpO06NJw` | https://www.youtube.com/channel/UC5dYmq91e5_g54krpO06NJw/live |
| 113 | AlArabiya | Global / Arabic | `UCahpxixMCwoANAftn6IxkTg` | https://www.youtube.com/channel/UCahpxixMCwoANAftn6IxkTg/live |
| 114 | SKAI.gr | Greece / Greek | `UCmHgxU394HiIAsN1fMegqzw` | https://www.youtube.com/channel/UCmHgxU394HiIAsN1fMegqzw/live |
| 115 | Sky TG24 | Italy / Italian | `UCz6E3lF72mb6uoJ-mOlNo2A` | https://www.youtube.com/channel/UCz6E3lF72mb6uoJ-mOlNo2A/live |
| 116 | SRF | Switzerland / German | `UCVuR4hBxX3zWY_xUCZeIc3A` | https://www.youtube.com/channel/UCVuR4hBxX3zWY_xUCZeIc3A/live |
| 117 | Zee 24 Ghanta | India / Bengali | `UCdF5Q5QVbYstYrTfpgUl0ZA` | https://www.youtube.com/channel/UCdF5Q5QVbYstYrTfpgUl0ZA/live |
| 118 | ABP Ananda | India / Bengali | `UCv3rFzn-GHGtqzXiaq3sWNg` | https://www.youtube.com/channel/UCv3rFzn-GHGtqzXiaq3sWNg/live |
| 119 | News Live | India / Assamese | `UCrQHRYuJG8jmpUVALIC9Gkw` | https://www.youtube.com/channel/UCrQHRYuJG8jmpUVALIC9Gkw/live |
| 120 | Pratidin Time | India / Assamese | `UC1JkYCOb4wKvdWreGQ0CR9g` | https://www.youtube.com/channel/UC1JkYCOb4wKvdWreGQ0CR9g/live |
| 121 | News18 Assam/NE | India / Assamese | `UCAjBd-r8JWfnRjfhg23nqLQ` | https://www.youtube.com/channel/UCAjBd-r8JWfnRjfhg23nqLQ/live |
| 122 | Zee 24 Taas | India / Marathi | `UCVbsFo8aCgvIRIO9RYwsQMA` | https://www.youtube.com/channel/UCVbsFo8aCgvIRIO9RYwsQMA/live |
| 123 | ABP Majha | India / Marathi | `UCH7nv1A9xIrAifZJNvt7cgA` | https://www.youtube.com/channel/UCH7nv1A9xIrAifZJNvt7cgA/live |
| 124 | PTC NEWS | India / Punjabi | `UCQLEbraENUGWh6p1Rv664rQ` | https://www.youtube.com/channel/UCQLEbraENUGWh6p1Rv664rQ/live |
| 125 | News18 Punjab | India / Punjabi | `UC-crZTQNRzZgzyighTKF0nQ` | https://www.youtube.com/channel/UC-crZTQNRzZgzyighTKF0nQ/live |
| 126 | Kanak News | India / Odia | `UC90RW5ZmBBqp4r2QIQxfACA` | https://www.youtube.com/channel/UC90RW5ZmBBqp4r2QIQxfACA/live |
| 127 | TV9 Gujarati | India / Gujarati | `UCeJWZgSMlzqYEDytDnvzHnw` | https://www.youtube.com/channel/UCeJWZgSMlzqYEDytDnvzHnw/live |
| 128 | News18 Bihar Jharkhand | India / Hindi | `UC531MlZA5LUbeGwEN_zcppw` | https://www.youtube.com/channel/UC531MlZA5LUbeGwEN_zcppw/live |
| 129 | ABP Ganga | India / Hindi | `UCUGwnDFBHY52YhgVjn-Tvww` | https://www.youtube.com/channel/UCUGwnDFBHY52YhgVjn-Tvww/live |
| 130 | News18 UP Uttarakhand | India / Hindi | `UCafYgzpyw7aIUYOLjjADu7w` | https://www.youtube.com/channel/UCafYgzpyw7aIUYOLjjADu7w/live |
| 131 | Zee Delhi-NCR Haryana | India / Hindi | `UCG6L5cIg2XZvXVksq5B9edw` | https://www.youtube.com/channel/UCG6L5cIg2XZvXVksq5B9edw/live |
| 132 | IBC24 | India / Hindi | `UCBc13XYipnBIBE3Ff8QaaGg` | https://www.youtube.com/channel/UCBc13XYipnBIBE3Ff8QaaGg/live |
| 133 | The Sikkim Chronicle | India / English | `UCcwlzxkvBYAVRfo7gSBC61g` | https://www.youtube.com/channel/UCcwlzxkvBYAVRfo7gSBC61g/live |
| 134 | Gulistan News | India / Urdu | `UCk7rHVFVs1Uf_dDOPKc2l0Q` | https://www.youtube.com/channel/UCk7rHVFVs1Uf_dDOPKc2l0Q/live |
| 135 | News18 J&K | India / Urdu | `UCRcye_z41WXpW5JalQm8wJw` | https://www.youtube.com/channel/UCRcye_z41WXpW5JalQm8wJw/live |

---

## Tier 2 — HIGH: duplicate / placeholder video ID (2 channels)

These channels share one identical `v1`, so at least one is showing the wrong stream.

| # | Channel | Country / Lang | Channel ID | Shared v1 | Get fresh ID from |
|---|---|---|---|---|---|
| 5 | CNN-News18 | India / English | `UCef1-8eOpJgud7szVPlZQAQ` | `4yivvIX7Umo` | https://www.youtube.com/channel/UCef1-8eOpJgud7szVPlZQAQ/live |
| 30 | News18 Telugu | India / Telugu | `UC-PPlFHLfi4wcFOe6DrReCQ` | `4yivvIX7Umo` | https://www.youtube.com/channel/UC-PPlFHLfi4wcFOe6DrReCQ/live |

Both `#5 CNN-News18` and `#30 News18 Telugu` point at `4yivvIX7Umo`. News18 Telugu should have its own Telugu live ID.

---

## Tier 3 — HIGH: no channel ID, cannot self-heal (28 channels)

These have a video ID and may play today, but `cid` is empty. The daily auto-updater (`update-streams.js`) needs a channel ID to find a replacement when a stream ends — so when these go dark they will stay dark permanently. They need a channel ID added.

| # | Channel | Country / Lang | Current v1 | Needs channel ID |
|---|---|---|---|---|
| 54 | SOMOY TV | Bangladesh / Bengali | `pxM8iN3kVd0` | YES |
| 55 | Jamuna TV | Bangladesh / Bengali | `xOjTaJFd-RA` | YES |
| 56 | Hiru TV 24x7 | Sri Lanka / Sinhala | `A5ygZltd-1M` | YES |
| 76 | Good Life Radio (Chill) | International / English | `jNgP6d9HraI` | YES |
| 77 | Radio Hits (Pop) | International / English | `b-bK2Vn3D38` | YES |
| 78 | Radio Mix (70s/80s) | International / English | `WnCfvAMM9eY` | YES |
| 79 | Rock FM (Classic Rock) | International / English | `Nt27aBceerI` | YES |
| 80 | Deep House Hits | International / English | `cnVPm1dGQJc` | YES |
| 81 | Radio Mix (Pop 2025) | International / English | `Uqk9YlmH3b4` | YES |
| 82 | Monstercat Silk | Canada / English | `WsDyRAPFBC8` | YES |
| 83 | Cafe Music BGM (Jazz) | Japan / English | `_dnYojGecWc` | YES |
| 84 | Cafe Music (Smooth Jazz) | Japan / English | `rUVpkJ0v8Eo` | YES |
| 85 | Aditya Music (Telugu) | India / Telugu | `B8ilYn_EO6g` | YES |
| 86 | 24 Hours Songs (Mal) | India / Malayalam | `R_JBMQ9nM8k` | YES |
| 87 | 123Musix Jukebox (Mal) | India / Malayalam | `dFN5l5k3fME` | YES |
| 88 | Malayali Mix (Chillstep) | India / Malayalam | `gK8GVzqPnzQ` | YES |
| 89 | ONE8 NICK (Mal Lofi) | India / Malayalam | `R_Y9jn99lwQ` | YES |
| 90 | 123Musix Relax (Mal) | India / Malayalam | `bA7HvJsCAiI` | YES |
| 91 | Saregama Malayalam | India / Malayalam | `u9tYgAK-V_c` | YES |
| 92 | Star Music India (Tamil) | India / Tamil | `Yb8kSxx9z9M` | YES |
| 93 | Tamil Music Lofi | India / Tamil | `hKc6_rT2ROQ` | YES |
| 94 | Thamizh Lofi Nights | India / Tamil | `PHdBLGDNa1s` | YES |
| 136 | Star Sports (Hindi) | India / Hindi | `b-K5jxQq1cg` | YES |
| 137 | JioCinema Sports | India / Hindi | `BfKX7S1q0d4` | YES |
| 138 | DD Sports | India / Hindi | `X8xT-3kQoQs` | YES |
| 139 | PTV Sports | Pakistan / English | `_Lx7iWmvGuY` | YES |
| 140 | Willow Cricket | USA / English | `3tSfq9RqoAQ` | YES |
| 141 | Supersport Cricket | South Africa / English | `DZpjqKgFXMc` | YES |

---

## Tier 4 — LOW: no fallback stream (28 channels)

These play fine; they just have no `v2` fallback, so there is no redundancy if the primary stream drops. Not urgent.

#13 Zee News · #21 Sun News · #24 TV9 Telugu · #25 NTV Telugu · #32 Asianet News · #33 24 News · #34 Mathrubhumi News · #35 Manorama News · #36 MediaOne TV · #37 Kairali News · #38 Janam TV · #39 Kerala Vision News 24x7 · #40 BIGTV 24x7 · #57 Al Jazeera English · #58 Sky News · #59 DW News · #60 France 24 English · #61 Bloomberg Television · #62 CNA (Channel NewsAsia) · #63 NHK WORLD-JAPAN · #64 TRT World · #65 ABC News · #66 NBC News · #67 CBS News · #68 Fox News · #70 Euronews · #71 Arirang TV · #103 NEWS (NTV News)

---

## How to pull a fresh live video ID

For any channel with a channel ID, open:

```
https://www.youtube.com/channel/<CHANNEL_ID>/live
```

The page redirects to `watch?v=XXXXXXXXXXX` — that 11-character `v=` value is the new `v1`. For the Tier 3 channels with no channel ID, search the channel on YouTube, open *About*, and copy the `UC…` ID from the share/page URL.

You already have the right tooling for this: `update-streams.js` does exactly this lookup via the YouTube Data API v3. Pointing it at the 141-channel list (instead of the stale `streams.json`) and running it with your `YOUTUBE_API_KEY` would repair every Tier 1 and Tier 2 entry automatically.

