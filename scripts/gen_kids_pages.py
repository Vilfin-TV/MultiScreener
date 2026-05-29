# -*- coding: utf-8 -*-
"""Generate per-page picture-book illustrations for the 8 Kids stories.
Output: stories/kids/<slug>/page1.svg .. page3.svg  (800x520)
Consistent flat/rounded storybook style (matches the Pip set).
"""
import os

W, H = 800, 520
OUT = 'stories/kids'

# ---------- shared primitives ----------
def svg(inner, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="{label}">'
            '<defs>'
            '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>'
            '<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fff3c4" stop-opacity="0.95"/><stop offset="1" stop-color="#ffd75e" stop-opacity="0"/></radialGradient>'
            '</defs>' + inner + '</svg>')

def bg(top, bot):
    return (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/></linearGradient></defs>'
            f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')

def sun(cx, cy, r, c='#ffe08a'):
    return f'<circle cx="{cx}" cy="{cy}" r="{r*1.8}" fill="{c}" opacity="0.25" filter="url(#soft)"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>'

def moon(cx, cy, r):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff7df"/>'

def stars_dots(seed=1, n=18, y1=320):
    import random; random.seed(seed)
    s = '<g fill="#fdf6d8">'
    for _ in range(n):
        x = random.randint(40, W-40); y = random.randint(30, y1); r = random.choice([1,1.4,1.8,2.2])
        s += f'<circle cx="{x}" cy="{y}" r="{r}" opacity="{random.choice([0.5,0.7,0.9])}"/>'
    return s + '</g>'

def hills(colors, base=360):
    out = ''
    for i, c in enumerate(colors):
        y = base + i*24
        out += f'<path d="M0 {y} C200 {y-38} 340 {y-8} 470 {y-22} C600 {y-34} 700 {y-6} {W} {y-18} L{W} {H} L0 {H} Z" fill="{c}"/>'
    return out

def water(y, c1='#2f7da8', c2='#1f5d82'):
    return (f'<path d="M0 {y} C200 {y-16} 600 {y-16} {W} {y} L{W} {H} L0 {H} Z" fill="{c1}"/>'
            f'<path d="M0 {y+26} C220 {y+12} 560 {y+18} {W} {y+24} L{W} {H} L0 {H} Z" fill="{c2}"/>')

def tree(x, base, s=1.0, leaf='#4f9e57'):
    return (f'<g transform="translate({x},{base}) scale({s})"><rect x="-10" y="-70" width="20" height="80" rx="8" fill="#7a5230"/>'
            f'<circle cx="0" cy="-90" r="56" fill="{leaf}"/><circle cx="-38" cy="-70" r="34" fill="{leaf}"/><circle cx="38" cy="-70" r="34" fill="{leaf}"/></g>')

def house(x, base, w=90, col='#e0a04e', roof='#b5532f'):
    h = w
    return (f'<g transform="translate({x},{base})"><rect x="{-w/2}" y="{-h}" width="{w}" height="{h}" rx="6" fill="{col}"/>'
            f'<path d="M{-w/2-10} {-h} L0 {-h-46} L{w/2+10} {-h} Z" fill="{roof}"/>'
            f'<rect x="-14" y="{-h+24}" width="28" height="28" rx="4" fill="#fff3c4"/></g>')

def star_shape(x, y, s=1.0, col='#FFD75E', face=True, glow=True):
    g = f'<g transform="translate({x},{y}) scale({s})">'
    if glow: g += '<circle cx="0" cy="0" r="42" fill="url(#glow)"/>'
    g += '<path d="M0 -34 L10 -10 L36 -10 L15 6 L23 32 L0 16 L-23 32 L-15 6 L-36 -10 L-10 -10 Z" fill="%s"/>' % col
    if face:
        g += ('<ellipse cx="-9" cy="-2" rx="4.5" ry="5.5" fill="#3A2E2E"/><ellipse cx="9" cy="-2" rx="4.5" ry="5.5" fill="#3A2E2E"/>'
              '<circle cx="-14" cy="7" r="3.6" fill="#FF9DB0"/><circle cx="14" cy="7" r="3.6" fill="#FF9DB0"/>'
              '<path d="M-6 8 q6 6 12 0" stroke="#3A2E2E" stroke-width="2" fill="none" stroke-linecap="round"/>')
    return g + '</g>'

def girl(x, base, s=1.0, dress='#c95ca0', hair='#6b4a2e'):
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<path d="M-34 0 L34 0 L24 -70 L-24 -70 Z" fill="{dress}"/>'  # dress
            f'<ellipse cx="-22" cy="6" rx="9" ry="7" fill="#3a2e2e"/><ellipse cx="22" cy="6" rx="9" ry="7" fill="#3a2e2e"/>'  # shoes
            f'<circle cx="0" cy="-92" r="24" fill="#f3d3b3"/>'  # head
            f'<path d="M-26 -96 a26 26 0 0 1 52 0 q-6 -16 -26 -16 q-20 0 -26 16 z" fill="{hair}"/>'  # hair
            f'<path d="M-24 -92 q-8 26 -2 44 M24 -92 q8 26 2 44" stroke="{hair}" stroke-width="8" fill="none"/>'  # pigtails
            f'<circle cx="-8" cy="-92" r="3" fill="#3a2e2e"/><circle cx="8" cy="-92" r="3" fill="#3a2e2e"/>'
            f'<path d="M-6 -82 q6 5 12 0" stroke="#c0607a" stroke-width="2.4" fill="none" stroke-linecap="round"/></g>')

def cat(x, base, s=1.0, col='#f2f2f2', line='#c9c2bb'):
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<ellipse cx="0" cy="0" rx="34" ry="26" fill="{col}" stroke="{line}" stroke-width="1.5"/>'  # body
            f'<path d="M28 -6 q34 -10 26 18" stroke="{col}" stroke-width="10" fill="none" stroke-linecap="round"/>'  # tail
            f'<circle cx="-18" cy="-26" r="20" fill="{col}" stroke="{line}" stroke-width="1.5"/>'  # head
            f'<path d="M-34 -38 l-4 -16 l14 8 z" fill="{col}"/><path d="M-2 -38 l4 -16 l-14 8 z" fill="{col}"/>'  # ears
            f'<circle cx="-24" cy="-28" r="3" fill="#3a2e2e"/><circle cx="-12" cy="-28" r="3" fill="#3a2e2e"/>'
            f'<path d="M-20 -22 l3 3 l3 -3" stroke="#c0607a" stroke-width="1.6" fill="none"/></g>')

def mouse(x, base, s=1.0):
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<ellipse cx="0" cy="0" rx="18" ry="14" fill="#b9aeb8"/>'
            f'<circle cx="-12" cy="-8" r="11" fill="#b9aeb8"/>'
            f'<circle cx="-18" cy="-16" r="7" fill="#d8c7d6"/><circle cx="-6" cy="-16" r="7" fill="#d8c7d6"/>'
            f'<circle cx="-15" cy="-8" r="2" fill="#3a2e2e"/><circle cx="-9" cy="-8" r="2" fill="#3a2e2e"/>'
            f'<path d="M18 4 q18 4 24 -6" stroke="#b9aeb8" stroke-width="3" fill="none"/></g>')

def dragon(x, base, s=1.0, col='#F4733A'):
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<path d="M-70 -10 C-100 -56 -30 -80 0 -52 C30 -80 100 -56 70 -10 C30 -32 -30 -32 -70 -10 Z" fill="{col}" opacity="0.92"/>'
            f'<ellipse cx="0" cy="6" rx="40" ry="30" fill="{col}"/>'
            f'<circle cx="0" cy="-30" r="26" fill="{col}"/>'
            f'<circle cx="-10" cy="-32" r="5" fill="#fff"/><circle cx="10" cy="-32" r="5" fill="#fff"/>'
            f'<circle cx="-9" cy="-31" r="2.5" fill="#222"/><circle cx="11" cy="-31" r="2.5" fill="#222"/>'
            f'<path d="M-26 -48 l-8 -14 M26 -48 l8 -14" stroke="{col}" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M-8 -20 q8 6 16 0" stroke="#7a3b1f" stroke-width="2.5" fill="none" stroke-linecap="round"/></g>')

def octopus(x, base, s=1.0, col='#b07ce0', sad=False):
    mouth = 'M-8 14 q8 -6 16 0' if sad else 'M-8 12 q8 7 16 0'
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<ellipse cx="0" cy="0" rx="42" ry="38" fill="{col}"/>'
            f'<g stroke="{col}" stroke-width="11" stroke-linecap="round" fill="none">'
            f'<path d="M-28 22 q-18 18 -32 8"/><path d="M-14 34 q-8 24 -20 28"/><path d="M0 38 q0 26 -6 38"/>'
            f'<path d="M14 34 q8 24 18 26"/><path d="M28 22 q20 14 32 4"/></g>'
            f'<circle cx="-13" cy="-6" r="8" fill="#fff"/><circle cx="13" cy="-6" r="8" fill="#fff"/>'
            f'<circle cx="-12" cy="-5" r="4" fill="#3a2e2e"/><circle cx="14" cy="-5" r="4" fill="#3a2e2e"/>'
            f'<path d="{mouth}" stroke="#3a2e2e" stroke-width="2.4" fill="none" stroke-linecap="round"/></g>')

def crow(x, base, s=1.0):
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<ellipse cx="0" cy="10" rx="40" ry="28" fill="#2b2f3a"/>'
            f'<circle cx="28" cy="-12" r="20" fill="#2b2f3a"/>'
            f'<path d="M46 -12 l28 5 l-28 8 z" fill="#f2a13b"/>'
            f'<circle cx="32" cy="-16" r="4" fill="#fff"/><circle cx="33" cy="-16" r="2" fill="#222"/>'
            f'<path d="M-30 6 l-34 -8 l28 22 z" fill="#23262f"/></g>')

def pitcher(x, base, s=1.0, level=0.4):
    fillh = 90 * level
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<path d="M-34 -110 q-6 0 -6 8 l4 92 q0 18 36 18 q36 0 36 -18 l4 -92 q0 -8 -6 -8 z" fill="#cfe8f2" opacity="0.55" stroke="#9fc6d6" stroke-width="2"/>'
            f'<path d="M-30 {10 - fillh} q30 8 60 0 l-2 8 q0 14 -28 14 q-28 0 -28 -14 z" fill="#3aa0d0" opacity="0.85"/></g>')

def whale(x, base, s=1.0):
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<path d="M-70 0 C-50 -40 50 -40 70 0 C50 26 -50 26 -70 0 Z" fill="#5b8fb0"/>'
            f'<path d="M-70 0 C-46 18 46 18 70 0 C46 14 -46 14 -70 0 Z" fill="#cfe6f0"/>'
            f'<path d="M64 -4 q22 -14 28 -24 q-6 18 -12 24 q12 2 16 -6 q-4 16 -22 12 z" fill="#5b8fb0"/>'
            f'<circle cx="-44" cy="-2" r="3" fill="#23414f"/>'
            f'<path d="M-58 -16 q-2 -16 8 -22" stroke="#bfe9ff" stroke-width="3" fill="none" stroke-linecap="round"/></g>')

def crab(x, base, s=1.0):
    return (f'<g transform="translate({x},{base}) scale({s})"><ellipse cx="0" cy="0" rx="24" ry="16" fill="#e0584f"/>'
            f'<path d="M-22 -4 q-16 -14 -26 -4 M22 -4 q16 -14 26 -4" stroke="#e0584f" stroke-width="6" fill="none" stroke-linecap="round"/>'
            f'<circle cx="-8" cy="-12" r="4" fill="#fff"/><circle cx="8" cy="-12" r="4" fill="#fff"/>'
            f'<circle cx="-8" cy="-12" r="2" fill="#222"/><circle cx="8" cy="-12" r="2" fill="#222"/></g>')

def turtle(x, base, s=1.0):
    return (f'<g transform="translate({x},{base}) scale({s})"><path d="M-30 8 a30 22 0 0 1 60 0 z" fill="#3e7d4f"/>'
            f'<ellipse cx="-34" cy="12" rx="11" ry="9" fill="#6fae5e"/><circle cx="-40" cy="10" r="2.5" fill="#222"/>'
            f'<rect x="-22" y="26" width="10" height="10" rx="3" fill="#6fae5e"/><rect x="12" y="26" width="10" height="10" rx="3" fill="#6fae5e"/></g>')

def hare(x, base, s=1.0, col='#c9a06a'):
    return (f'<g transform="translate({x},{base}) scale({s})"><ellipse cx="0" cy="10" rx="30" ry="22" fill="{col}"/>'
            f'<circle cx="22" cy="-8" r="15" fill="{col}"/>'
            f'<path d="M16 -20 l-4 -30 l12 22 z" fill="{col}"/><path d="M28 -20 l8 -28 l-10 20 z" fill="{col}"/>'
            f'<circle cx="26" cy="-10" r="3" fill="#222"/></g>')

def monkey(x, base, s=1.0):
    return (f'<g transform="translate({x},{base}) scale({s})"><ellipse cx="0" cy="6" rx="26" ry="22" fill="#9b6b43"/>'
            f'<circle cx="-26" cy="-6" r="11" fill="#9b6b43"/><circle cx="26" cy="-6" r="11" fill="#9b6b43"/>'
            f'<circle cx="0" cy="-4" r="20" fill="#9b6b43"/><ellipse cx="0" cy="2" rx="14" ry="12" fill="#e9cba0"/>'
            f'<circle cx="-7" cy="-6" r="3" fill="#222"/><circle cx="7" cy="-6" r="3" fill="#222"/>'
            f'<path d="M-6 4 q6 5 12 0" stroke="#7a5230" stroke-width="2" fill="none" stroke-linecap="round"/></g>')

def donkey(x, base, s=1.0, col='#9aa0ad'):
    return (f'<g transform="translate({x},{base}) scale({s})"><ellipse cx="0" cy="0" rx="44" ry="26" fill="{col}"/>'
            f'<circle cx="44" cy="-18" r="18" fill="{col}"/>'
            f'<path d="M36 -34 l-4 -22 l12 16 z" fill="{col}"/><path d="M52 -34 l6 -22 l-12 16 z" fill="{col}"/>'
            f'<circle cx="50" cy="-18" r="3" fill="#222"/>'
            f'<line x1="-26" y1="24" x2="-30" y2="48" stroke="{col}" stroke-width="9" stroke-linecap="round"/>'
            f'<line x1="24" y1="24" x2="28" y2="48" stroke="{col}" stroke-width="9" stroke-linecap="round"/></g>')

def man(x, base, s=1.0, shirt='#3a6ea5'):
    return (f'<g transform="translate({x},{base}) scale({s})">'
            f'<rect x="-22" y="-60" width="44" height="62" rx="14" fill="{shirt}"/>'
            f'<circle cx="0" cy="-78" r="20" fill="#e3b58c"/>'
            f'<path d="M-20 -84 a20 14 0 0 1 40 0 z" fill="#2b2f3a"/>'
            f'<circle cx="-7" cy="-78" r="2.6" fill="#222"/><circle cx="7" cy="-78" r="2.6" fill="#222"/>'
            f'<path d="M-6 -70 q6 5 12 0" stroke="#7a5230" stroke-width="2" fill="none" stroke-linecap="round"/></g>')

CAPCOLS = ['#e0584f', '#3a86c0', '#ffb15a', '#7b5fd6']

# ---------- scene builders: return inner svg ----------
def P(top, bot, body): return bg(top, bot) + body

def luna1():
    s = stars_dots(2) + moon(660, 90, 40)
    s += '<rect x="0" y="360" width="800" height="160" fill="#2a2150"/>'
    # window
    s += '<rect x="120" y="150" width="200" height="220" rx="10" fill="#16234a" stroke="#3a4f86" stroke-width="6"/>'
    s += '<line x1="220" y1="150" x2="220" y2="370" stroke="#3a4f86" stroke-width="5"/><line x1="120" y1="260" x2="320" y2="260" stroke="#3a4f86" stroke-width="5"/>'
    s += star_shape(170,200,0.5)+star_shape(280,300,0.4,glow=False)
    s += girl(470, 470, 1.05)
    # grandmother hand giving seed (simple sparkle)
    s += star_shape(560, 360, 0.3, col='#cfe0ff')
    return P('#1a1340', '#3a2f6e', s)

def luna2():
    s = stars_dots(3) + moon(120, 100, 34)
    s += hills(['#3b2f6e', '#2a2150'])
    # vine with star
    s += '<path d="M400 470 C380 400 430 360 400 280" stroke="#5fae6a" stroke-width="10" fill="none"/>'
    s += '<path d="M400 360 q30 -10 44 6 M400 320 q-30 -10 -44 6" stroke="#5fae6a" stroke-width="6" fill="none"/>'
    s += star_shape(400, 250, 0.9, col='#7fc4ff')
    s += house(660, 470, 110, '#2c3d63', '#1f2c49')
    s += star_shape(640, 320, 0.45, col='#7fc4ff')
    return P('#1a1340', '#3a2f6e', s)

def luna3():
    s = stars_dots(4, n=10)
    s += hills(['#3b2f6e', '#2a2150'])
    cols = ['#ffd75e', '#ff9ec7', '#7fd8a0', '#7fc4ff']
    for i in range(7):
        x = 90 + i*100; y = 120 + (i % 3)*40
        s += star_shape(x, y, 0.5, col=cols[i % 4])
    for i, c in enumerate(['#2c3d63', '#3a4f86', '#2c3d63']):
        s += house(170+i*230, 470, 120, c, '#1f2c49')
    return P('#241a52', '#43368a', s)

def dragon1():
    s = stars_dots(5, n=8) + sun(120, 110, 40, '#ffd2a6')
    s += hills(['#9ccb6a', '#6fa547'])
    s += dragon(400, 320, 1.4)
    # heavy wings droop indicated by sweat drops
    s += '<g fill="#9fd0ff"><circle cx="500" cy="250" r="5"/><circle cx="520" cy="270" r="4"/></g>'
    return P('#bfe3f0', '#7fb0cf', s)

def dragon2():
    s = sun(660, 110, 40, '#ffe08a')
    s += hills(['#9ccb6a', '#6fa547'])
    s += dragon(330, 340, 1.1)
    s += mouse(470, 360, 1.6)
    # laughter marks
    s += '<g fill="#ffd75e"><path d="M250 200 l5 12 l13 0 l-10 9 l4 13 l-12 -8 l-12 8 l4 -13 l-10 -9 l13 0 z"/></g>'
    return P('#cdeefb', '#88c3df', s)

def dragon3():
    s = stars_dots(6, n=6) + sun(140, 100, 42, '#ffe08a')
    s += '<g fill="#ffffff" opacity="0.7"><ellipse cx="600" cy="160" rx="60" ry="26"/><ellipse cx="180" cy="240" rx="50" ry="22"/></g>'
    s += dragon(420, 250, 1.3)
    s += mouse(420, 205, 1.2)
    s += hills(['#9ccb6a'], base=430)
    return P('#9fd6f5', '#5fa8d8', s)

def coral1():
    s = water(60, '#0e6ea0', '#063a56')
    s += '<g fill="#bfeaff" opacity="0.5"><circle cx="120" cy="120" r="7"/><circle cx="640" cy="150" r="8"/><circle cx="520" cy="100" r="5"/></g>'
    s += octopus(400, 230, 1.4, sad=True)
    # plastic trash
    s += '<g opacity="0.85"><rect x="150" y="360" width="40" height="28" rx="5" fill="#cfd8e0"/><rect x="620" y="380" width="46" height="20" rx="8" fill="#dfe8ee"/><ellipse cx="300" cy="400" rx="26" ry="12" fill="#e6eef3"/></g>'
    s += '<path d="M0 440 C200 420 600 420 800 440 L800 520 L0 520 Z" fill="#0a2f45"/>'
    return P('#0e5e84', '#063a56', s)

def coral2():
    s = water(60, '#0e6ea0', '#063a56')
    s += whale(620, 200, 1.1)
    s += octopus(150, 250, 0.9)
    s += crab(330, 360, 1.4)
    s += turtle(470, 360, 1.6)
    s += '<g fill="#bfeaff" opacity="0.5"><circle cx="250" cy="120" r="6"/><circle cx="560" cy="120" r="7"/></g>'
    s += '<path d="M0 440 C200 420 600 420 800 440 L800 520 L0 520 Z" fill="#0a2f45"/>'
    return P('#0e5e84', '#063a56', s)

def coral3():
    s = sun(660, 90, 40, '#ffe7a6')
    s += '<path d="M0 250 C200 230 600 230 800 250 L800 360 L0 360 Z" fill="#2f7da8"/>'  # sea
    s += '<path d="M0 330 C200 360 600 360 800 330 L800 520 L0 520 Z" fill="#e7d4a6"/>'  # sand
    s += girl(250, 470, 0.95, dress='#3a86c0')
    # shell with picture
    s += '<g transform="translate(470,430)"><path d="M-30 0 a30 26 0 0 1 60 0 z" fill="#ffd0c0"/><g stroke="#e08a6a" stroke-width="2"><path d="M0 0 L-18 -16 M0 0 L0 -22 M0 0 L18 -16"/></g></g>'
    s += '<g fill="#bfeaff" opacity="0.6"><circle cx="640" cy="300" r="5"/><circle cx="120" cy="280" r="5"/></g>'
    return P('#bfe6f0', '#7fc2dc', s)

def cats1():
    s = sun(660, 100, 40) + hills(['#9ccb6a', '#6fa547'])
    s += tree(120, 380, 1.0)
    s += cat(300, 360, 1.5, '#f2f2f2', '#cabfb6')
    s += cat(520, 360, 1.5, '#9aa0ad', '#7e828c')
    # bread
    s += '<ellipse cx="410" cy="400" rx="34" ry="20" fill="#e0a85a"/><ellipse cx="410" cy="394" rx="32" ry="16" fill="#f0c27a"/>'
    return P('#bfe3a0', '#7fb85e', s)

def cats2():
    s = sun(140, 100, 38) + hills(['#9ccb6a', '#6fa547'])
    s += tree(600, 400, 1.2)
    s += monkey(560, 250, 1.2)
    # balance scale
    s += '<g transform="translate(380,250)"><line x1="0" y1="-30" x2="0" y2="40" stroke="#8a6d3b" stroke-width="5"/><line x1="-60" y1="-30" x2="60" y2="-30" stroke="#8a6d3b" stroke-width="5"/>'
    s += '<path d="M-60 -30 a26 14 0 0 0 52 0 z" fill="#cdb98a"/><path d="M8 -30 a26 14 0 0 0 52 0 z" fill="#cdb98a"/>'
    s += '<ellipse cx="-34" cy="-16" rx="14" ry="7" fill="#e0a85a"/><ellipse cx="34" cy="-16" rx="14" ry="7" fill="#e0a85a"/></g>'
    s += cat(170, 380, 1.1, '#f2f2f2', '#cabfb6')
    return P('#cdeaa6', '#86bd5e', s)

def cats3():
    s = sun(140, 100, 38) + hills(['#9ccb6a', '#6fa547'])
    s += tree(640, 400, 1.3)
    s += monkey(560, 300, 1.5)
    # full belly + crumbs
    s += '<g fill="#e0a85a"><circle cx="500" cy="380" r="3"/><circle cx="520" cy="392" r="2.5"/></g>'
    s += cat(220, 380, 1.2, '#f2f2f2', '#cabfb6')
    s += cat(330, 380, 1.2, '#9aa0ad', '#7e828c')
    # sad marks
    s += '<g fill="#9fd0ff"><circle cx="250" cy="330" r="4"/><circle cx="360" cy="330" r="4"/></g>'
    return P('#cdeaa6', '#86bd5e', s)

def crow1():
    s = sun(660, 110, 44, '#ffd98a') + hills(['#caa15a', '#9b7838'])
    s += tree(120, 400, 1.0, leaf='#6fa547')
    s += crow(420, 230, 1.5)
    # heat lines
    s += '<g stroke="#ffd98a" stroke-width="3" opacity="0.5" fill="none"><path d="M620 180 q10 -10 0 -20 M650 190 q10 -10 0 -20"/></g>'
    return P('#ffe7b0', '#e0a85a', s)

def crow2():
    s = sun(140, 110, 38, '#ffd98a') + hills(['#caa15a', '#9b7838'])
    s += '<rect x="300" y="360" width="220" height="20" rx="6" fill="#9b7838"/>'  # table
    s += pitcher(410, 470, 1.2, level=0.25)
    s += crow(560, 300, 1.1)
    return P('#ffe7b0', '#e0a85a', s)

def crow3():
    s = sun(660, 110, 38, '#ffd98a') + hills(['#caa15a', '#9b7838'])
    s += '<rect x="300" y="360" width="220" height="20" rx="6" fill="#9b7838"/>'
    s += pitcher(410, 470, 1.2, level=0.7)
    s += crow(300, 300, 1.1)
    # pebbles
    s += '<g fill="#7a6a52"><circle cx="250" cy="430" r="6"/><circle cx="270" cy="440" r="5"/><circle cx="560" cy="440" r="6"/></g>'
    return P('#ffe7b0', '#e0a85a', s)

def caps1():
    s = sun(660, 100, 40) + hills(['#9ccb6a', '#6fa547'])
    s += tree(420, 400, 1.6)
    s += man(250, 470, 1.0)
    # basket of caps
    s += '<g transform="translate(360,440)"><path d="M-34 0 h68 l-8 30 h-52 z" fill="#a9743b"/>'
    for i, c in enumerate(CAPCOLS):
        s += f'<ellipse cx="{-24+i*16}" cy="-6" rx="12" ry="6" fill="{c}"/>'
    s += '</g>'
    # zzz
    s += '<text x="300" y="370" font-size="22" fill="#5a7a3a">z</text>'
    return P('#bfe3a0', '#7fb85e', s)

def caps2():
    s = sun(140, 100, 38) + hills(['#9ccb6a', '#6fa547'])
    s += tree(560, 420, 1.8)
    for i, c in enumerate(CAPCOLS):
        s += monkey(470+i*60, 220+(i % 2)*40, 0.7)
        s += f'<ellipse cx="{470+i*60}" cy="{195+(i%2)*40}" rx="12" ry="6" fill="{c}"/>'
    s += man(180, 470, 1.0)
    s += '<text x="150" y="360" font-size="26" fill="#b5532f">!</text>'
    return P('#cdeaa6', '#86bd5e', s)

def caps3():
    s = sun(660, 100, 40) + hills(['#9ccb6a', '#6fa547'])
    s += tree(560, 420, 1.8)
    for i in range(4):
        s += monkey(470+i*60, 230+(i % 2)*30, 0.6)
    s += man(220, 470, 1.0)
    # caps on ground
    for i, c in enumerate(CAPCOLS):
        s += f'<ellipse cx="{420+i*40}" cy="430" rx="14" ry="7" fill="{c}"/>'
    return P('#cdeaa6', '#86bd5e', s)

def donkey1():
    s = sun(660, 100, 40) + hills(['#caa15a', '#9b7838'], base=300)
    s += water(330, '#4aa3d0', '#2f7da8')
    s += donkey(360, 360, 1.2)
    # salt bags
    s += '<rect x="320" y="320" width="34" height="26" rx="6" fill="#f0ead8"/><rect x="366" y="320" width="34" height="26" rx="6" fill="#f0ead8"/>'
    s += '<g fill="#bfeaff"><circle cx="300" cy="380" r="5"/><circle cx="430" cy="390" r="4"/></g>'
    return P('#bfe3f0', '#7fb0cf', s)

def donkey2():
    s = sun(140, 100, 38) + hills(['#caa15a', '#9b7838'], base=300)
    s += water(330, '#4aa3d0', '#2f7da8')
    s += donkey(400, 350, 1.2)
    s += '<rect x="360" y="312" width="30" height="22" rx="6" fill="#f0ead8"/><rect x="402" y="312" width="30" height="22" rx="6" fill="#f0ead8"/>'
    # happy sparkle
    s += '<g fill="#ffd75e"><path d="M300 230 l4 9 l10 0 l-8 7 l3 10 l-9 -6 l-9 6 l3 -10 l-8 -7 l10 0 z"/></g>'
    return P('#cdeefb', '#88c3df', s)

def donkey3():
    s = sun(660, 100, 40) + hills(['#caa15a', '#9b7838'], base=300)
    s += water(330, '#4aa3d0', '#2f7da8')
    s += donkey(380, 360, 1.2)
    # heavy wet cotton bags (big)
    s += '<ellipse cx="350" cy="318" rx="26" ry="22" fill="#eef2f6"/><ellipse cx="412" cy="318" rx="26" ry="22" fill="#eef2f6"/>'
    s += '<g fill="#9fd0ff"><circle cx="350" cy="296" r="4"/><circle cx="412" cy="296" r="4"/></g>'
    # tired sweat
    s += '<circle cx="470" cy="320" r="5" fill="#9fd0ff"/>'
    return P('#bfe3f0', '#7fb0cf', s)

def hare1():
    s = sun(660, 100, 40) + hills(['#9ccb6a', '#6fa547'])
    s += tree(120, 400, 1.1)
    s += hare(330, 360, 1.7, '#caa07a')
    s += turtle(520, 380, 1.6)
    s += '<text x="300" y="270" font-size="24" fill="#b5532f">ha!</text>'
    return P('#cdeaa6', '#86bd5e', s)

def hare2():
    s = sun(140, 100, 38) + hills(['#9ccb6a', '#6fa547'])
    s += tree(620, 400, 1.4)
    s += hare(560, 350, 1.3, '#caa07a')
    # sleeping zzz
    s += '<text x="600" y="300" font-size="22" fill="#5a7a3a">z</text>'
    s += turtle(180, 380, 1.3)
    # dust trail
    s += '<g fill="#ffffff" opacity="0.4"><circle cx="300" cy="380" r="10"/><circle cx="340" cy="386" r="7"/></g>'
    return P('#cdeaa6', '#86bd5e', s)

def hare3():
    s = sun(660, 100, 40) + hills(['#9ccb6a', '#6fa547'])
    # finish line
    s += '<rect x="500" y="220" width="10" height="180" fill="#c0392b"/>'
    s += '<g>'+''.join(f'<rect x="510" y="{220+r*20}" width="20" height="20" fill="{"#fff" if r%2 else "#222"}"/>' for r in range(4))+'</g>'
    s += turtle(470, 400, 1.7)
    # trophy
    s += '<g transform="translate(470,300)"><path d="M-12 0 h24 l-3 16 h-18 z" fill="#ffd75e"/><ellipse cx="0" cy="-2" rx="14" ry="10" fill="#ffd75e"/><rect x="-8" y="16" width="16" height="6" fill="#caa86a"/></g>'
    s += hare(180, 380, 1.1, '#caa07a')
    return P('#cdeaa6', '#86bd5e', s)

PAGES = {
 'luna-and-the-star-garden': [luna1, luna2, luna3],
 'the-dragon-who-forgot-how-to-fly': [dragon1, dragon2, dragon3],
 'captain-coral-and-the-clean-sea': [coral1, coral2, coral3],
 'the-clever-monkey-and-the-two-cats': [cats1, cats2, cats3],
 'the-thirsty-crow-s-smart-idea': [crow1, crow2, crow3],
 'the-cap-seller-and-the-copycat-monkeys': [caps1, caps2, caps3],
 'the-lazy-donkey-s-wet-trick': [donkey1, donkey2, donkey3],
 'the-hare-and-the-steady-tortoise': [hare1, hare2, hare3],
}

count = 0
for slug, fns in PAGES.items():
    d = os.path.join(OUT, slug)
    os.makedirs(d, exist_ok=True)
    for i, fn in enumerate(fns, 1):
        out = svg(fn(), f'{slug} illustration {i}')
        open(os.path.join(d, f'page{i}.svg'), 'w', encoding='utf-8').write(out)
        count += 1
    print(f'{slug}: 3 pages')
print('TOTAL kids page illustrations:', count)
