/**
 * JKK + UR vacancy email digest — Koto & Edogawa wards
 *
 * JKK: scrapes jkkwatcher.com category pages, filters layouts 2LDK / 3DK / 3LDK.
 * UR:  queries the ur-net.go.jp room API, filters vacant rooms 2LDK / 3DK.
 * Sends one combined digest to RECIPIENT (+ BCC list).
 *
 * Required env vars (GitHub Actions secrets):
 *   GMAIL_USER          - Gmail address used as the SMTP sender
 *   GMAIL_APP_PASSWORD  - Gmail App Password (not the account password)
 */

const DRY_RUN = process.argv.includes('--dry-run');

const RECIPIENT = '[redacted]';
const BCC_RECIPIENTS = ['[redacted]', '[redacted]'];
const LAYOUTS = ['2LDK', '3DK', '3LDK'];

const SOURCES = [
  { ward: '江東区 (Koto)', url: 'https://jkkwatcher.com/category/tokyo-ward/east/koto' },
  { ward: '江戸川区 (Edogawa)', url: 'https://jkkwatcher.com/category/tokyo-ward/east/edogawa' },
];

const NO_VACANCY = '空室なし';

const UR_LAYOUTS = ['2LDK', '3DK'];
const UR_API = 'https://chintai.r6.ur-net.go.jp/chintai/api/bukken/result/bukken_result/';
const UR_SOURCES = [
  { ward: '江東区 (Koto)', skcs: '108', url: 'https://www.ur-net.go.jp/chintai/kanto/tokyo/area/108.html' },
  { ward: '江戸川区 (Edogawa)', skcs: '123', url: 'https://www.ur-net.go.jp/chintai/kanto/tokyo/area/123.html' },
];

function decodeEntities(s) {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .trim();
}

function parseCards(html) {
  const cards = [];
  // Each listing is a "category-result-card" block; split and parse each chunk.
  const chunks = html.split('category-result-card').slice(1);
  for (const chunk of chunks) {
    const link = chunk.match(/<a class="stretched-link" href="([^"]+)"[^>]*>([^<]+)<\/a>/);
    if (!link) continue;
    const layout = chunk.match(/>([^<>]*㎡[^<>]*)</);
    const station = chunk.match(/<p style="font-size:0\.85rem;color:var\(--text-muted\)">([^<]+)<\/p>/);
    const address = chunk.match(/<p style="font-size:0\.8rem;color:var\(--text-light\)">([^<]+)<\/p>/);
    const badge = chunk.match(/<span class="badge badge-[a-z]+"[^>]*>([^<]+)<\/span>/);
    cards.push({
      name: decodeEntities(link[2]),
      url: new URL(link[1], 'https://jkkwatcher.com').href,
      layout: layout ? decodeEntities(layout[1]) : '',
      station: station ? decodeEntities(station[1]) : '',
      address: address ? decodeEntities(address[1]) : '',
      vacancy: badge ? decodeEntities(badge[1]) : '不明',
    });
  }
  return cards;
}

function matchesTargetLayout(layoutText) {
  return LAYOUTS.some((l) => layoutText.includes(l));
}

async function fetchWard(source) {
  const res = await fetch(source.url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; JKKDigestBot/1.0)' },
  });
  if (!res.ok) throw new Error(`Fetch failed ${res.status} for ${source.url}`);
  const html = await res.text();
  const all = parseCards(html);
  const matched = all.filter((c) => matchesTargetLayout(c.layout));
  return { ...source, all, matched };
}

async function fetchUrWard(source) {
  const body = new URLSearchParams({
    mode: 'area',
    skcs: source.skcs,
    block: 'kanto',
    tdfk: '13',
    rireki_tdfk: '13',
    orderByField: '0',
    pageSize: '100',
    pageIndex: '0',
    shisya: '',
    danchi: '',
    shikibetu: '',
    pageIndexRoom: '0',
    sp: '',
  });
  const res = await fetch(UR_API, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': 'Mozilla/5.0 (compatible; URDigestBot/1.0)',
    },
    body,
  });
  if (!res.ok) throw new Error(`UR API failed ${res.status} for skcs=${source.skcs}`);
  const items = (await res.json()) || [];
  const rooms = [];
  for (const b of items) {
    for (const r of b.room || []) {
      if (!UR_LAYOUTS.some((l) => (r.type || '').includes(l))) continue;
      rooms.push({
        danchi: b.danchiNm,
        place: b.place,
        room: `${r.roomNmMain || ''} ${r.roomNmSub || ''}`.trim(),
        type: r.type,
        floorspace: (r.floorspace || '').replace(/&#13217;/g, '㎡'),
        floor: r.floor || '',
        rent: r.rent || '',
        commonfee: r.commonfee || '',
        url: r.roomLinkPc ? `https://www.ur-net.go.jp${r.roomLinkPc}` : source.url,
      });
    }
  }
  const vacantRoomsTotal = items.reduce((n, b) => n + (Number(b.roomCount) || 0), 0);
  return { ...source, danchiCount: items.length, vacantRoomsTotal, rooms };
}

function renderUrSection(results) {
  const sections = results
    .map((r) => {
      const rows = r.rooms.length
        ? r.rooms
            .map(
              (c) => `<tr style="border-top:1px solid #e2e8f0;background:#f0fdf4">
        <td style="padding:10px;vertical-align:top">
          <a href="${c.url}" style="color:#0a3d91;font-weight:700;text-decoration:none">${c.danchi} ${c.room}</a><br>
          <span style="font-size:12px;color:#8892a6">${c.place}</span>
        </td>
        <td style="padding:10px;vertical-align:top;white-space:nowrap">${c.type}（${c.floorspace}・${c.floor}）</td>
        <td style="padding:10px;vertical-align:top;font-size:12px;color:#5a6478">家賃 ${c.rent}<br>共益費 ${c.commonfee}</td>
        <td style="padding:10px;vertical-align:top;text-align:center">
          <span style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;background:#16a34a;color:#ffffff">空室あり</span>
        </td>
      </tr>`
            )
            .join('\n')
        : `<tr><td colspan="4" style="padding:10px;color:#8892a6">対象間取り（${UR_LAYOUTS.join('/')}）の空室なし — 巡回中の団地 ${r.danchiCount}件</td></tr>`;
      return `
      <h2 style="font-size:16px;color:#0a192f;margin:24px 0 8px">UR ${r.ward}
        <span style="font-size:12px;font-weight:400;color:#8892a6">— 空室 ${r.rooms.length}件（全間取り ${r.vacantRoomsTotal}件）/ 団地 ${r.danchiCount}件</span>
      </h2>
      <table style="width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;font-size:14px">
        <tr style="background:#0a192f;color:#ffffff;text-align:left">
          <th style="padding:10px">団地 / 部屋</th>
          <th style="padding:10px">間取り</th>
          <th style="padding:10px">家賃</th>
          <th style="padding:10px;text-align:center">状況</th>
        </tr>
        ${rows}
      </table>
      <p style="font-size:12px;margin:6px 0 0"><a href="${r.url}" style="color:#0a3d91">${r.url}</a></p>`;
    })
    .join('\n');
  return sections;
}

function renderRows(cards) {
  if (!cards.length) {
    return '<tr><td colspan="4" style="padding:10px;color:#8892a6">該当物件なし</td></tr>';
  }
  return cards
    .map((c) => {
      const vacant = c.vacancy !== NO_VACANCY;
      const badgeStyle = vacant
        ? 'background:#16a34a;color:#ffffff'
        : 'background:#eef1f6;color:#8892a6';
      return `<tr style="border-top:1px solid #e2e8f0${vacant ? ';background:#f0fdf4' : ''}">
        <td style="padding:10px;vertical-align:top">
          <a href="${c.url}" style="color:#0a3d91;font-weight:700;text-decoration:none">${c.name}</a><br>
          <span style="font-size:12px;color:#8892a6">${c.address}</span>
        </td>
        <td style="padding:10px;vertical-align:top;white-space:nowrap">${c.layout}</td>
        <td style="padding:10px;vertical-align:top;font-size:12px;color:#5a6478">${c.station}</td>
        <td style="padding:10px;vertical-align:top;text-align:center">
          <span style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;${badgeStyle}">${c.vacancy}</span>
        </td>
      </tr>`;
    })
    .join('\n');
}

function buildEmail(results, urResults, nowJst) {
  const jkkVacant = results.reduce(
    (n, r) => n + r.matched.filter((c) => c.vacancy !== NO_VACANCY).length,
    0
  );
  const urVacant = urResults.reduce((n, r) => n + r.rooms.length, 0);
  const vacantCount = jkkVacant + urVacant;
  const subject = vacantCount > 0
    ? `【空室あり ${vacantCount}件】JKK・UR 江東区・江戸川区 — ${nowJst}`
    : `JKK・UR 江東区・江戸川区 空室状況 — ${nowJst}`;

  const sections = results
    .map(
      (r) => `
      <h2 style="font-size:16px;color:#0a192f;margin:24px 0 8px">${r.ward}
        <span style="font-size:12px;font-weight:400;color:#8892a6">— 対象 ${r.matched.length}件 / 全 ${r.all.length}件</span>
      </h2>
      <table style="width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;font-size:14px">
        <tr style="background:#0a192f;color:#ffffff;text-align:left">
          <th style="padding:10px">物件名 / 所在地</th>
          <th style="padding:10px">間取り</th>
          <th style="padding:10px">アクセス</th>
          <th style="padding:10px;text-align:center">空室状況</th>
        </tr>
        ${renderRows(r.matched)}
      </table>
      <p style="font-size:12px;margin:6px 0 0"><a href="${r.url}" style="color:#0a3d91">${r.url}</a></p>`
    )
    .join('\n');

  const html = `
  <div style="font-family:'Segoe UI',Meiryo,sans-serif;max-width:720px;margin:0 auto;color:#1a2333">
    <div style="background:#0a192f;color:#ffffff;padding:18px 24px;border-radius:10px 10px 0 0">
      <h1 style="margin:0;font-size:18px">JKK・UR 空室ウォッチ — 江東区・江戸川区</h1>
      <p style="margin:4px 0 0;font-size:12px;color:#9fb3d1">JKK: 2LDK / 3DK / 3LDK ・ UR: 2LDK / 3DK ・ ${nowJst} (JST)</p>
    </div>
    <div style="padding:8px 24px 24px;background:#f7f9fc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 10px 10px">
      ${vacantCount > 0
        ? `<p style="background:#16a34a;color:#ffffff;padding:12px 16px;border-radius:8px;font-weight:800;font-size:15px;margin-top:16px"><strong>現在 ${vacantCount} 件の空室があります — 早めの申込をおすすめします。</strong></p>`
        : `<p style="background:#dc2626;color:#ffffff;padding:12px 16px;border-radius:8px;font-weight:700;font-size:14px;margin-top:16px">現在、対象間取りの空室はありません。次回の巡回で変化があればお知らせします。</p>`}
      <h2 style="font-size:14px;color:#8892a6;margin:20px 0 0;border-bottom:2px solid #0a192f;padding-bottom:4px">JKK東京（東京都住宅供給公社）</h2>
      ${sections}
      <h2 style="font-size:14px;color:#8892a6;margin:28px 0 0;border-bottom:2px solid #0a192f;padding-bottom:4px">UR賃貸住宅</h2>
      ${renderUrSection(urResults)}
      <p style="font-size:11px;color:#8892a6;margin-top:24px">Source: jkkwatcher.com / ur-net.go.jp ・ Automated digest (daily 09:35 / 11:00 / 14:30 / 18:20 JST)</p>
    </div>
  </div>`;

  return { subject, html };
}

async function main() {
  const user = process.env.GMAIL_USER;
  const pass = process.env.GMAIL_APP_PASSWORD;
  if (!DRY_RUN && (!user || !pass)) {
    console.error('Missing GMAIL_USER / GMAIL_APP_PASSWORD environment variables.');
    process.exit(1);
  }

  const results = [];
  for (const source of SOURCES) {
    const r = await fetchWard(source);
    console.log(`JKK ${r.ward}: ${r.all.length} properties, ${r.matched.length} match ${LAYOUTS.join('/')}`);
    results.push(r);
  }

  const urResults = [];
  for (const source of UR_SOURCES) {
    const r = await fetchUrWard(source);
    console.log(`UR ${r.ward}: ${r.danchiCount} complexes, ${r.vacantRoomsTotal} vacant rooms, ${r.rooms.length} match ${UR_LAYOUTS.join('/')}`);
    urResults.push(r);
  }

  const nowJst = new Date().toLocaleString('ja-JP', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });

  const { subject, html } = buildEmail(results, urResults, nowJst);

  if (DRY_RUN) {
    console.log(`\n[dry-run] Subject: ${subject}`);
    for (const r of results) {
      for (const c of r.matched) {
        console.log(`[dry-run] JKK ${r.ward} | ${c.name} | ${c.layout} | ${c.vacancy} | ${c.url}`);
      }
    }
    for (const r of urResults) {
      for (const c of r.rooms) {
        console.log(`[dry-run] UR ${r.ward} | ${c.danchi} ${c.room} | ${c.type} | ${c.rent} | ${c.url}`);
      }
    }
    console.log(`[dry-run] HTML length: ${html.length} chars. No email sent.`);
    return;
  }

  const nodemailer = require('nodemailer');
  const transporter = nodemailer.createTransport({
    host: 'smtp.gmail.com',
    port: 465,
    secure: true,
    auth: { user, pass },
  });

  const info = await transporter.sendMail({
    from: `"JKK Watch" <${user}>`,
    to: RECIPIENT,
    bcc: BCC_RECIPIENTS,
    subject,
    html,
  });
  console.log(`Email sent to ${RECIPIENT} (+${BCC_RECIPIENTS.length} bcc): ${info.messageId}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
