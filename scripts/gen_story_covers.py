# -*- coding: utf-8 -*-
"""Generate premium book-cover-style SVG illustrations for every VilfinTV story.
Each cover: themed gradient background + iconic motif + framed title plate.
Output: stories/<genre>/<slug>.svg  (800x520)
"""
import os, re, html

W, H = 800, 520

def esc(s): return html.escape(s, quote=True)

def slugify(t):
    t = re.split(r'—| - ', t)[0]
    t = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')
    return t[:40]

def split_title(t):
    parts = re.split(r'\s*—\s*|\s+-\s+', t, maxsplit=1)
    main = parts[0].strip()
    sub = parts[1].strip() if len(parts) > 1 else ''
    return main, sub

def wrap(main):
    if len(main) <= 20:
        return [main]
    words = main.split()
    # find split near middle
    best, bestd = 1, 1e9
    for i in range(1, len(words)):
        a = len(' '.join(words[:i])); b = len(' '.join(words[i:]))
        d = abs(a - b)
        if d < bestd: bestd, best = d, i
    return [' '.join(words[:best]), ' '.join(words[best:])]

def defs(grad_stops, extra=''):
    s = '<defs>'
    s += '<linearGradient id="bg" x1="0" y1="0" x2="0.4" y2="1">'
    for off, col in grad_stops:
        s += f'<stop offset="{off}" stop-color="{col}"/>'
    s += '</linearGradient>'
    s += '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>'
    s += '<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffffff" stop-opacity="0.9"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>'
    s += extra + '</defs>'
    return s

def frame(accent):
    return (f'<rect x="14" y="14" width="{W-28}" height="{H-28}" rx="18" fill="none" stroke="{accent}" stroke-width="3" opacity="0.85"/>'
            f'<rect x="22" y="22" width="{W-44}" height="{H-44}" rx="13" fill="none" stroke="{accent}" stroke-width="1.4" opacity="0.5"/>')

def title_plate(title, sub_label):
    main, sub = split_title(title)
    lines = wrap(main)
    py = 384
    ph = H - py - 30
    plate = (f'<rect x="60" y="{py}" width="{W-120}" height="{ph}" rx="14" fill="#fbf7ee" opacity="0.97"/>'
             f'<rect x="68" y="{py+8}" width="{W-136}" height="{ph-16}" rx="10" fill="none" stroke="#caa86a" stroke-width="1.6"/>')
    # title text
    if len(lines) == 1:
        fs = 34 if len(lines[0]) <= 16 else 28
        ty = py + 46
        plate += f'<text x="{W/2}" y="{ty}" text-anchor="middle" font-family="Georgia, \'Times New Roman\', serif" font-weight="700" font-size="{fs}" fill="#1c2233">{esc(lines[0])}</text>'
        suby = ty + 26
    else:
        fs = 25
        ty = py + 38
        plate += f'<text x="{W/2}" y="{ty}" text-anchor="middle" font-family="Georgia, \'Times New Roman\', serif" font-weight="700" font-size="{fs}" fill="#1c2233">{esc(lines[0])}</text>'
        plate += f'<text x="{W/2}" y="{ty+30}" text-anchor="middle" font-family="Georgia, \'Times New Roman\', serif" font-weight="700" font-size="{fs}" fill="#1c2233">{esc(lines[1])}</text>'
        suby = ty + 56
    label = (sub if sub else sub_label).upper()
    if len(label) > 46: label = label[:44] + '…'
    plate += f'<text x="{W/2}" y="{suby}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="600" letter-spacing="2.5" font-size="11.5" fill="#8a6d3b">{esc(label)}</text>'
    return plate

# ---------- motif helpers ----------
def stars(n=26, col='#ffffff', y0=40, y1=360):
    import random; random.seed(7)
    out = '<g fill="%s">' % col
    for _ in range(n):
        import random as r
        x = r.randint(50, W-50); y = r.randint(y0, y1); rad = r.choice([1,1,1.4,1.8,2.2])
        out += f'<circle cx="{x}" cy="{y}" r="{rad}" opacity="{r.choice([0.5,0.7,0.9])}"/>'
    out += '</g>'
    return out

def moon(cx, cy, r, col='#fff7df'):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{col}"/><circle cx="{cx-r*0.3}" cy="{cy-r*0.25}" r="{r*0.18}" fill="#000" opacity="0.05"/>'

def sun(cx, cy, r, col='#ffe08a'):
    return f'<circle cx="{cx}" cy="{cy}" r="{r*1.7}" fill="{col}" opacity="0.25" filter="url(#soft)"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="{col}"/>'

def hills(colors, base=360):
    out = ''
    ys = [base, base+24, base+46]
    for i, c in enumerate(colors):
        y = ys[i]
        out += f'<path d="M0 {y} C200 {y-40} 320 {y-10} 460 {y-22} C600 {y-34} 700 {y-6} {W} {y-18} L{W} 400 L0 400 Z" fill="{c}"/>'
    return out

# ---------- per-motif drawers ----------
def m_train(a):
    s = stars(18) + moon(660,90,40)
    s += '<rect x="40" y="300" width="720" height="10" fill="#2a2f45"/>'  # rail
    s += '<g transform="translate(250,180)">'
    s += '<rect x="0" y="60" width="300" height="90" rx="14" fill="%s"/>' % a
    s += '<rect x="20" y="80" width="50" height="40" rx="6" fill="#fff7d6" opacity="0.9"/>'
    s += '<rect x="90" y="80" width="50" height="40" rx="6" fill="#fff7d6" opacity="0.9"/>'
    s += '<rect x="160" y="80" width="50" height="40" rx="6" fill="#fff7d6" opacity="0.9"/>'
    s += '<rect x="-60" y="40" width="80" height="110" rx="16" fill="#3a4straat" />'.replace('3a4straat','3a4366')
    s += '<circle cx="-20" cy="110" r="40" fill="url(#glow)" opacity="0.5"/>'
    s += '<circle cx="40" cy="160" r="14" fill="#1a1d2b"/><circle cx="120" cy="160" r="14" fill="#1a1d2b"/><circle cx="430" cy="160" r="14" fill="#1a1d2b"/>'
    s += '</g>'
    return s

def m_rain(a):
    s = '<g stroke="%s" stroke-width="2" opacity="0.5">' % a
    import random; random.seed(3)
    for _ in range(60):
        x = random.randint(40, W-40); y = random.randint(40, 330)
        s += f'<line x1="{x}" y1="{y}" x2="{x-8}" y2="{y+22}"/>'
    s += '</g>'
    # lone figure with umbrella
    s += '<g transform="translate(400,250)"><path d="M-70 0 a70 40 0 0 1 140 0 z" fill="%s"/>' % a
    s += '<line x1="0" y1="0" x2="0" y2="80" stroke="#cbd2e6" stroke-width="3"/>'
    s += '<circle cx="0" cy="96" r="12" fill="#cbd2e6"/><rect x="-10" y="106" width="20" height="40" rx="8" fill="#cbd2e6"/></g>'
    s += '<circle cx="150" cy="120" r="44" fill="url(#glow)" opacity="0.25"/>'
    return s

def m_city(a):
    s = stars(14)
    cols = ['#1c2740','#243353','#2c3d63','#1f2c49']
    import random; random.seed(5)
    x = 40
    while x < W-40:
        w = random.randint(40,80); h = random.randint(90,210)
        s += f'<rect x="{x}" y="{360-h}" width="{w}" height="{h}" rx="4" fill="{random.choice(cols)}"/>'
        for wy in range(360-h+12, 356, 22):
            for wx in range(x+8, x+w-8, 18):
                if random.random()>0.4:
                    s += f'<rect x="{wx}" y="{wy}" width="7" height="10" fill="{a}" opacity="0.8"/>'
        x += w + 10
    s += f'<circle cx="120" cy="90" r="30" fill="{a}" opacity="0.9"/><circle cx="120" cy="90" r="46" fill="{a}" opacity="0.2" filter="url(#soft)"/>'
    return s

def m_mountain_road(a):
    s = sun(620,110,42)
    s += hills(['#caa15a','#a87f3e','#7d5a29'])
    s += '<path d="M380 400 C420 320 360 250 410 180 L430 180 C400 250 460 320 430 400 Z" fill="#f4e7c8" opacity="0.85"/>'
    s += '<g stroke="#a87f3e" stroke-width="4" stroke-dasharray="10 12" opacity="0.7"><line x1="408" y1="400" x2="418" y2="190"/></g>'
    return s

def m_island(a):
    s = '<rect x="0" y="0" width="%d" height="400" fill="#bfe3ee" opacity="0.0"/>' % W
    s += sun(640,100,40,'#fff0c0')
    s += '<path d="M0 300 C200 280 600 280 800 300 L800 400 L0 400 Z" fill="#2f7da8"/>'
    s += '<path d="M0 330 C200 312 600 320 800 330 L800 400 L0 400 Z" fill="#1f5d82"/>'
    s += '<path d="M250 300 C300 230 500 230 560 300 Z" fill="#3a6b4a"/>'
    s += '<path d="M250 300 C320 250 360 250 400 300 Z" fill="#4f8a5e"/>'
    s += '<g stroke="#ffffff" stroke-width="3" opacity="0.5"><path d="M120 320 q20 -8 40 0 M620 318 q20 -8 40 0" fill="none"/></g>'
    return s

def m_train2(a):
    s = stars(16)
    s += hills(['#3a2f5a','#2c2447'])
    s += '<rect x="40" y="320" width="720" height="8" fill="#1c1730"/>'
    s += '<g transform="translate(180,200)"><rect x="0" y="40" width="440" height="80" rx="12" fill="%s"/>' % a
    for i in range(6):
        s += f'<rect x="{20+i*70}" y="60" width="44" height="36" rx="5" fill="#fff7d6" opacity="0.85"/>'
    s += '<circle cx="70" cy="130" r="12" fill="#120f22"/><circle cx="370" cy="130" r="12" fill="#120f22"/></g>'
    return s

def m_longevity(a):
    s = sun(640,110,44,'#ffe08a')
    s += hills(['#7fc6a0','#4ea87f','#2e7d5b'])
    s += '<g transform="translate(360,150)"><path d="M40 18 C40 -8 78 -8 78 18 C78 44 40 64 40 80 C40 64 2 44 2 18 C2 -8 40 -8 40 18 Z" fill="%s"/>' % a
    s += '<path d="M-10 60 l20 0 l8 -18 l10 36 l10 -24 l8 6 l24 0" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></g>'
    return s

def m_runner(a):
    s = '<rect width="%d" height="400" fill="url(#bg)"/>' % W
    s += sun(150,110,40,'#ffd2a6')
    s += hills(['#6a4a8a','#4a3168'])
    s += '<g transform="translate(380,210)" fill="%s"><circle cx="0" cy="-30" r="16"/>' % a
    s += '<path d="M-2 -16 q30 10 28 40 M-2 -10 q-26 14 -34 38" stroke="%s" stroke-width="11" stroke-linecap="round" fill="none"/>' % a
    s += '<path d="M0 0 q22 18 16 56 M0 4 q-20 22 -40 28" stroke="%s" stroke-width="12" stroke-linecap="round" fill="none"/></g>' % a
    return s

def m_gut(a):
    s = '<g transform="translate(400,200)"><path d="M-90 30 C-90 -60 90 -60 90 30 C90 70 40 70 40 40 C40 10 10 10 10 40 C10 70 -40 70 -40 40 C-40 10 -70 20 -70 40 C-70 60 -90 55 -90 30 Z" fill="%s" opacity="0.92"/></g>' % a
    import random; random.seed(9)
    s += '<g>'
    for _ in range(16):
        x=random.randint(120,680); y=random.randint(70,330); r=random.choice([6,8,10])
        s += f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ffffff" opacity="0.18"/><circle cx="{x}" cy="{y}" r="{r/2}" fill="#ffffff" opacity="0.3"/>'
    s += '</g>'
    return s

def m_money(a):
    s = stars(0)
    import random; random.seed(2)
    s += '<g>'
    for _ in range(12):
        x=random.randint(80,680); y=random.randint(70,300); rot=random.randint(-25,25)
        s += f'<g transform="translate({x},{y}) rotate({rot})"><rect x="-34" y="-20" width="68" height="40" rx="6" fill="#3aa76d"/><circle cx="0" cy="0" r="13" fill="#bdf0d2"/><text x="0" y="6" text-anchor="middle" font-family="Georgia,serif" font-size="18" fill="#1c6b44">$</text></g>'
    s += '</g>'
    s += f'<circle cx="400" cy="190" r="56" fill="{a}" opacity="0.25" filter="url(#soft)"/>'
    return s

def m_spy(a):
    s = stars(10)
    s += '<g transform="translate(400,200)">'
    s += '<ellipse cx="0" cy="40" rx="70" ry="60" fill="%s"/>' % a  # coat/body
    s += '<circle cx="0" cy="-30" r="34" fill="#e9d8b8"/>'
    s += '<path d="M-40 -42 a40 18 0 0 1 80 0 z" fill="#222634"/><rect x="-44" y="-44" width="88" height="8" rx="4" fill="#222634"/>'  # hat
    s += '<rect x="-30" y="-30" width="60" height="16" rx="8" fill="#222634"/>'  # sunglasses
    s += '</g>'
    s += '<circle cx="170" cy="120" r="40" fill="url(#glow)" opacity="0.2"/>'
    return s

def m_lock(a):
    s = stars(0)
    s += '<g transform="translate(400,190)"><rect x="-60" y="0" width="120" height="100" rx="16" fill="%s"/>' % a
    s += '<path d="M-36 0 v-22 a36 36 0 0 1 72 0 v22" fill="none" stroke="%s" stroke-width="16"/>' % a
    s += '<circle cx="0" cy="44" r="14" fill="#1c2233"/><rect x="-6" y="50" width="12" height="26" rx="6" fill="#1c2233"/></g>'
    s += '<text x="400" y="70" text-anchor="middle" font-family="monospace" font-size="26" fill="%s" opacity="0.7">ERROR 50</text>' % a
    return s

def m_star_garden(a):
    s = stars(20)
    s += hills(['#3b2f6e','#2a2150'])
    import random; random.seed(11)
    for _ in range(8):
        x=random.randint(120,680); y=random.randint(150,330)
        s += f'<line x1="{x}" y1="{y}" x2="{x}" y2="360" stroke="#5fae6a" stroke-width="3"/>'
        s += f'<path d="M{x} {y-16} l5 12 l13 0 l-10 9 l4 13 l-12 -8 l-12 8 l4 -13 l-10 -9 l13 0 z" fill="{a}"/>'
    s += moon(650,90,34)
    return s

def m_dragon(a):
    s = stars(12)
    s += '<g transform="translate(400,200)">'
    s += '<path d="M-90 40 C-120 -10 -40 -40 0 -10 C40 -40 120 -10 90 40 C40 20 -40 20 -90 40 Z" fill="%s"/>' % a  # wings
    s += '<ellipse cx="0" cy="50" rx="46" ry="34" fill="%s"/>' % a
    s += '<circle cx="0" cy="0" r="30" fill="%s"/>' % a
    s += '<circle cx="-10" cy="-4" r="5" fill="#fff"/><circle cx="12" cy="-4" r="5" fill="#fff"/><circle cx="-9" cy="-3" r="2.5" fill="#222"/><circle cx="13" cy="-3" r="2.5" fill="#222"/>'
    s += '<path d="M-30 -22 l-10 -16 M30 -22 l10 -16" stroke="%s" stroke-width="8" stroke-linecap="round"/>' % a
    s += '</g>'
    return s

def m_ocean(a):
    s = '<g fill="#bfeaff" opacity="0.5">'
    import random; random.seed(8)
    for _ in range(16):
        x=random.randint(60,740); y=random.randint(60,300); r=random.choice([4,6,8])
        s += f'<circle cx="{x}" cy="{y}" r="{r}"/>'
    s += '</g>'
    s += '<path d="M0 320 C200 300 600 300 800 320 L800 400 L0 400 Z" fill="#0a3f5a"/>'
    s += '<g>'  # corals
    s += '<path d="M120 360 q-12 -50 6 -80 q12 26 4 80 z" fill="#ff7e9d"/><path d="M680 360 q12 -56 -6 -84 q-16 28 -4 84 z" fill="#7fd8b0"/>'
    s += '</g>'
    s += '<g transform="translate(400,180)"><circle r="40" fill="%s"/><circle cx="-14" cy="-6" r="7" fill="#fff"/><circle cx="14" cy="-6" r="7" fill="#fff"/><circle cx="-13" cy="-5" r="3.5" fill="#222"/><circle cx="15" cy="-5" r="3.5" fill="#222"/><path d="M-12 14 q12 10 24 0" stroke="#222" stroke-width="3" fill="none" stroke-linecap="round"/></g>' % a
    return s

def m_monkey(a):
    s = sun(650,100,40,'#ffe08a')
    s += hills(['#9ccb6a','#6fa547'])
    s += '<g transform="translate(400,210)"><circle r="42" fill="%s"/><circle cx="-40" cy="-8" r="16" fill="%s"/><circle cx="40" cy="-8" r="16" fill="%s"/>' % (a,a,a)
    s += '<circle cx="0" cy="6" r="30" fill="#e9cba0"/><circle cx="-13" cy="-6" r="6" fill="#222"/><circle cx="13" cy="-6" r="6" fill="#222"/><path d="M-10 16 q10 8 20 0" stroke="#222" stroke-width="3" fill="none" stroke-linecap="round"/></g>'
    return s

def m_crow(a):
    s = sun(160,110,38,'#ffd9a0')
    s += hills(['#caa15a','#9b7838'])
    s += '<g transform="translate(430,180)"><ellipse cx="0" cy="20" rx="46" ry="34" fill="%s"/><circle cx="34" cy="-6" r="22" fill="%s"/>' % (a,a)
    s += '<path d="M54 -6 l28 6 l-28 8 z" fill="#f4a83b"/><circle cx="40" cy="-10" r="4" fill="#fff"/><circle cx="41" cy="-10" r="2" fill="#222"/>'
    s += '<path d="M-30 18 l-30 -10 l24 22 z" fill="%s"/></g>' % a
    s += '<rect x="350" y="300" width="60" height="70" rx="8" fill="#5a7fa0" opacity="0.8"/>'  # pot
    return s

def m_caps(a):
    s = sun(640,110,40,'#ffe08a')
    s += hills(['#9ccb6a','#6fa547'])
    cols=['#e0584f','#3a86c0','#ffb15a','#7b5fd6']
    for i,c in enumerate(cols):
        s += f'<g transform="translate(400,{300-i*34})"><ellipse cx="0" cy="0" rx="44" ry="14" fill="{c}"/><path d="M-30 0 a30 24 0 0 1 60 0 z" fill="{c}"/></g>'
    return s

def m_donkey(a):
    s = sun(160,110,38,'#ffd9a0')
    s += hills(['#caa15a','#9b7838'])
    s += '<g transform="translate(400,210)"><ellipse cx="0" cy="20" rx="60" ry="36" fill="%s"/><circle cx="60" cy="-6" r="26" fill="%s"/>' % (a,a)
    s += '<path d="M48 -28 l-6 -28 l16 18 z" fill="%s"/><path d="M74 -28 l6 -28 l-16 18 z" fill="%s"/>' % (a,a)
    s += '<circle cx="66" cy="-8" r="4" fill="#222"/>'
    s += '<line x1="-40" y1="44" x2="-46" y2="80" stroke="%s" stroke-width="10" stroke-linecap="round"/><line x1="40" y1="44" x2="46" y2="80" stroke="%s" stroke-width="10" stroke-linecap="round"/></g>' % (a,a)
    s += '<path d="M120 330 q40 -10 80 0" stroke="#6fa6c8" stroke-width="6" fill="none" opacity="0.6"/>'
    return s

def m_tortoise_hare(a):
    s = sun(640,110,40,'#ffe08a')
    s += hills(['#9ccb6a','#6fa547'])
    # tortoise
    s += '<g transform="translate(300,250)"><path d="M-40 10 a40 26 0 0 1 80 0 z" fill="#3e7d4f"/><ellipse cx="-46" cy="14" rx="14" ry="11" fill="#6fae5e"/><circle cx="-54" cy="12" r="2.5" fill="#222"/><rect x="-30" y="30" width="12" height="14" rx="4" fill="#6fae5e"/><rect x="18" y="30" width="12" height="14" rx="4" fill="#6fae5e"/></g>'
    # hare
    s += '<g transform="translate(520,230)"><ellipse cx="0" cy="20" rx="34" ry="24" fill="%s"/><circle cx="24" cy="-2" r="16" fill="%s"/><path d="M18 -16 l-4 -30 l12 22 z" fill="%s"/><path d="M30 -16 l8 -28 l-10 20 z" fill="%s"/><circle cx="28" cy="-4" r="3" fill="#222"/></g>' % (a,a,a,a)
    return s

def m_school(a):
    s = stars(0)
    s += '<g transform="translate(400,180)"><path d="M-90 30 L0 -20 L90 30 L0 80 Z" fill="%s"/>' % a  # cap
    s += '<rect x="-30" y="40" width="60" height="40" fill="%s"/>' % a
    s += '<rect x="-6" y="30" width="12" height="60" fill="#caa86a"/><circle cx="0" cy="90" r="8" fill="#caa86a"/></g>'
    s += '<g stroke="%s" stroke-width="2" opacity="0.4" fill="none"><circle cx="160" cy="120" r="20"/><circle cx="640" cy="120" r="20"/></g>' % a
    return s

def m_math(a):
    s = stars(0)
    syms=['π','√','∞','Σ','Δ','φ','÷','×']
    import random; random.seed(4)
    s += '<g font-family="Georgia,serif" fill="%s">' % a
    for sy in syms:
        x=random.randint(90,680); y=random.randint(90,300); fs=random.choice([30,40,52]); op=random.choice([0.5,0.7,0.9])
        s += f'<text x="{x}" y="{y}" font-size="{fs}" opacity="{op}">{sy}</text>'
    s += '</g>'
    s += '<g stroke="%s" stroke-width="2" fill="none" opacity="0.5"><path d="M120 320 Q400 120 700 320"/></g>' % a
    return s

def m_kite(a):
    s = '<rect width="%d" height="400" fill="url(#bg)"/>' % W
    s += sun(650,100,40,'#fff0b0')
    s += '<g transform="translate(360,170) rotate(15)"><path d="M0 -50 L40 0 L0 50 L-40 0 Z" fill="%s"/><line x1="0" y1="-50" x2="0" y2="50" stroke="#fff" stroke-width="2" opacity="0.6"/><line x1="-40" y1="0" x2="40" y2="0" stroke="#fff" stroke-width="2" opacity="0.6"/></g>' % a
    s += '<path d="M348 230 q40 30 0 60 q-40 30 0 60" stroke="#fff" stroke-width="2" fill="none" opacity="0.7"/>'
    return s

def m_film(a):
    s = stars(0)
    s += '<g transform="translate(400,200)"><rect x="-150" y="-70" width="300" height="140" rx="10" fill="#1c2233"/>'
    for i in range(-2,3):
        s += f'<rect x="{i*56-20}" y="-66" width="14" height="132" fill="#0c111c"/>'
        for yy in (-58,52):
            s += f'<rect x="{i*56-12}" y="{yy}" width="22" height="14" rx="3" fill="{a}" opacity="0.8"/>'
    s += '<rect x="-110" y="-44" width="220" height="88" rx="6" fill="%s" opacity="0.85"/></g>' % a
    return s

def m_color_swirl(a):
    s = ''
    cols=['#ff5d8f','#ffb14e','#4ee0c1','#5b8cff','#b15bff']
    import random; random.seed(6)
    for i,c in enumerate(cols):
        cx=random.randint(160,640); cy=random.randint(110,300); r=random.randint(40,90)
        s += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}" opacity="0.55" filter="url(#soft)"/>'
    s += '<path d="M120 300 C300 160 500 360 700 200" stroke="#fff" stroke-width="5" fill="none" opacity="0.5"/>'
    return s

def m_yarn(a):
    s = stars(0)
    s += '<g transform="translate(400,200)"><circle r="64" fill="%s"/>' % a
    s += '<g stroke="#ffffff" stroke-width="2" opacity="0.5" fill="none"><ellipse rx="64" ry="26"/><ellipse rx="64" ry="26" transform="rotate(60)"/><ellipse rx="64" ry="26" transform="rotate(120)"/></g></g>'
    s += '<path d="M464 210 q60 20 80 80" stroke="%s" stroke-width="4" fill="none"/>' % a
    return s

def m_neural(a):
    s = stars(0)
    import random; random.seed(1)
    layers=[(160,[120,200,280]),(330,[100,170,240,310]),(500,[140,220,300]),(660,[180,260])]
    nodes=[]
    for lx,ys in layers:
        col=[]
        for y in ys:
            col.append((lx,y));
        nodes.append(col)
    s += '<g stroke="%s" stroke-width="1.2" opacity="0.4">' % a
    for i in range(len(nodes)-1):
        for (x1,y1) in nodes[i]:
            for (x2,y2) in nodes[i+1]:
                s += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>'
    s += '</g><g fill="%s">' % a
    for col in nodes:
        for (x,y) in col:
            s += f'<circle cx="{x}" cy="{y}" r="9"/><circle cx="{x}" cy="{y}" r="16" fill="{a}" opacity="0.2" filter="url(#soft)"/>'
    s += '</g>'
    return s

def m_molecule(a):
    s = stars(0)
    import random; random.seed(12)
    pts=[(300,160),(420,130),(500,220),(380,260),(260,250),(560,150)]
    s += '<g stroke="%s" stroke-width="3" opacity="0.6">' % a
    for i in range(len(pts)-1):
        s += f'<line x1="{pts[i][0]}" y1="{pts[i][1]}" x2="{pts[i+1][0]}" y2="{pts[i+1][1]}"/>'
    s += '</g><g>'
    for (x,y) in pts:
        s += f'<circle cx="{x}" cy="{y}" r="16" fill="{a}"/><circle cx="{x}" cy="{y}" r="26" fill="{a}" opacity="0.2" filter="url(#soft)"/>'
    s += '</g>'
    return s

def m_forest_sensor(a):
    s = stars(14)
    s += hills(['#1f5d4a','#13402f'])
    for x in (160,300,640,720):
        s += f'<path d="M{x} 340 l-26 -120 l52 0 z" fill="#1c6b4f"/><path d="M{x} 280 l-20 -90 l40 0 z" fill="#247a5b"/><rect x="{x-5}" y="330" width="10" height="20" fill="#5a3b2e"/>'
    s += f'<g transform="translate(400,180)"><circle r="30" fill="{a}"/><circle r="46" fill="none" stroke="{a}" stroke-width="2" opacity="0.6"/><circle r="64" fill="none" stroke="{a}" stroke-width="2" opacity="0.35"/><circle r="82" fill="none" stroke="{a}" stroke-width="2" opacity="0.18"/></g>'
    return s

MOTIFS = {
 'm_train':m_train,'m_rain':m_rain,'m_city':m_city,'m_mountain_road':m_mountain_road,'m_island':m_island,
 'm_train2':m_train2,'m_longevity':m_longevity,'m_runner':m_runner,'m_gut':m_gut,'m_money':m_money,
 'm_spy':m_spy,'m_lock':m_lock,'m_star_garden':m_star_garden,'m_dragon':m_dragon,'m_ocean':m_ocean,
 'm_monkey':m_monkey,'m_crow':m_crow,'m_caps':m_caps,'m_donkey':m_donkey,'m_tortoise_hare':m_tortoise_hare,
 'm_school':m_school,'m_math':m_math,'m_kite':m_kite,'m_film':m_film,'m_color_swirl':m_color_swirl,
 'm_yarn':m_yarn,'m_neural':m_neural,'m_molecule':m_molecule,'m_forest_sensor':m_forest_sensor,
}

# genre -> default subtitle label
GENRE_LABEL = {'triller':'VilfinTV Thriller','travel':'VilfinTV Travel','health':'VilfinTV Health',
 'comedy':'VilfinTV Comedy','kids':'VilfinTV Kids','education':'VilfinTV Education',
 'animation':'VilfinTV Animation','ai':'VilfinTV Future & AI'}

# story specs: (genre, title, motif, [grad stops], accent)
SPECS = [
 ('triller','The Last Train Home — A Midnight Crossing','m_train',[('0','#0d1020'),('1','#262b45')],'#7c8ce0'),
 ('triller','Echoes in the Rain — A Ghost in the Alley','m_rain',[('0','#0f1622'),('1','#23303f')],'#8fb6c9'),
 ('triller','Neon Noir — The Detective Who Knew Too Little','m_city',[('0','#10081f'),('1','#241043')],'#ff5d8f'),
 ('travel','The Silk Road Solo — Retracing Ancient Trailways','m_mountain_road',[('0','#ffd79a'),('1','#e08a4e')],'#7d5a29'),
 ('travel','Islands of Solitude — Finding Peace in the Faroes','m_island',[('0','#bfe6f0'),('1','#6fb3cc')],'#1f5d82'),
 ('travel','The Trans-Siberian Chronicle — 9,289 Kilometres','m_train2',[('0','#21183b'),('1','#3a2f5a')],'# caa8e0'.replace(' ','')),
 ('health','The Blue Zone Secret — The Longest-Lived People','m_longevity',[('0','#bdeccf'),('1','#5fae8a')],'#2e7d5b'),
 ('health','Running from Darkness — Recovery Through Movement','m_runner',[('0','#2a1f44'),('1','#5a3a78')],'#ffb14e'),
 ('health','The Microbiome Revolution — Your Second Brain','m_gut',[('0','#0e3b3a'),('1','#1d6a63')],'#7fe0c8'),
 ('comedy','The Accidental Billionaire — A Satirical Pitch','m_money',[('0','#103d2a'),('1','#1f6b46')],'#ffe08a'),
 ('comedy','My Neighbour is a Spy (Or Just Very Eccentric)','m_spy',[('0','#1b2030'),('1','#33405e')],'#e0a44e'),
 ('comedy','Access Denied — The $50 Typo','m_lock',[('0','#241026'),('1','#4a1f4e')],'#ff8a5c'),
 ('kids','Luna and the Star Garden — A Bedtime Adventure','m_star_garden',[('0','#1a1340'),('1','#3a2f6e')],'#ffd75e'),
 ('kids','The Dragon Who Forgot How to Fly','m_dragon',[('0','#16203f'),('1','#2d3f6b')],'#7fd8b0'),
 ('kids','Captain Coral and the Clean Sea','m_ocean',[('0','#0e5e84'),('1','#063a56')],'#ffd75e'),
 ('kids','The Clever Monkey and the Two Cats','m_monkey',[('0','#bfe3a0'),('1','#7fb85e')],'#a9743b'),
 ("kids","The Thirsty Crow's Smart Idea",'m_crow',[('0','#ffe7b0'),('1','#e0a85a')],'#3a3a44'),
 ('kids','The Cap Seller and the Copycat Monkeys','m_caps',[('0','#bfe3a0'),('1','#7fb85e')],'#e0584f'),
 ("kids","The Lazy Donkey's Wet Trick",'m_donkey',[('0','#ffe7b0'),('1','#e0a85a')],'#9c8a6a'),
 ('kids','The Hare and the Steady Tortoise','m_tortoise_hare',[('0','#cdeaa6'),('1','#86bd5e')],'#c98a5a'),
 ('education','The School of Trust — Finland’s Education Success','m_school',[('0','#16294a'),('1','#274a7a')],'#ffd06b'),
 ('education','Language of the Universe — Math in Nature','m_math',[('0','#11132a'),('1','#23284f')],'#8fd0ff'),
 ('animation','Pixel Dreams — The Flying Kite Animation','m_kite',[('0','#1b2a55'),('1','#3a6bbf')],'#ffcf5c'),
 ('animation','Beyond the Frame — Squash and Stretch','m_film',[('0','#241043'),('1','#4a2487')],'#2ad0ff'),
 ('animation','The Dancing Colours — Abstract Rhythm','m_color_swirl',[('0','#140d24'),('1','#2a1a44')],'#ff5d8f'),
 ('animation','The Yarn Adventure — Crafting Masterpieces','m_yarn',[('0','#3a1530'),('1','#6e2a52')],'#ffb15a'),
 ('ai','The Ghost in the Neural Network — AI Memories','m_neural',[('0','#091a33'),('1','#103a63')],'#12d6df'),
 ('ai','The Silicon Valley Chef — Generative Chemistry','m_molecule',[('0','#0c1230'),('1','#1c2a63')],'#5be0a8'),
 ('ai','The Sentinel of the Forest — Eco-Acoustic AI','m_forest_sensor',[('0','#0a1f2a'),('1','#103f3a')],'#5be0c8'),
]

def build(genre, title, motif, grad, accent, sub_label):
    bg = '<rect width="%d" height="%d" fill="url(#bg)"/>' % (W, H)
    art = MOTIFS[motif](accent)
    # vignette
    vig = '<rect width="%d" height="400" fill="#000000" opacity="0.12"/>' % W
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">'
            % (W, H, W, H, esc(title)) + defs(grad) + bg + art + '</svg>').replace('</svg>', '') + title_plate(title, sub_label) + frame(accent) + '</svg>'

count = 0
for genre, title, motif, grad, accent, in_accent in [(s[0],s[1],s[2],s[3],s[4],s[4]) for s in SPECS]:
    slug = slugify(title)
    d = os.path.join('stories', genre)
    os.makedirs(d, exist_ok=True)
    svg = build(genre, title, motif, grad, accent, GENRE_LABEL.get(genre,'VilfinTV Stories'))
    with open(os.path.join(d, slug + '.svg'), 'w', encoding='utf-8') as f:
        f.write(svg)
    count += 1
    print(f"{genre}/{slug}.svg  ({motif})")

# default cover
os.makedirs('stories', exist_ok=True)
defsvg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 520" width="800" height="520" role="img" aria-label="VilfinTV Stories">'
 + defs([('0','#0e1430'),('1','#243a6b')]) + '<rect width="800" height="520" fill="url(#bg)"/>'
 + stars(30) + '<g transform="translate(400,200)"><path d="M0 -70 L20 -20 L74 -20 L30 12 L46 64 L0 32 L-46 64 L-30 12 L-74 -20 L-20 -20 Z" fill="#ffd75e"/></g>'
 + title_plate('VilfinTV Stories', 'STORIES & TALES') + frame('#ffd75e') + '</svg>')
open(os.path.join('stories','_default.svg'),'w',encoding='utf-8').write(defsvg)
print('stories/_default.svg')
print('TOTAL covers:', count + 1)
