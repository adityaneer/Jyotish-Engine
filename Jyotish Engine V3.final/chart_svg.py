"""
chart_svg.py — SVG chart generation wrapper using jyotichart

Wraps jyotichart to generate SVG strings directly (no file I/O),
styled to match the jyotish_engine dark theme.

Input: planet_table (from compute_chart), lagna_num
Output: SVG string for North or South Indian chart style
"""
import sys, os, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'jyotichart'))

import northindianchart as _nc
import southindianchart as _sc
import support.general as _gen

# PyJHora planet index → jyotichart planet name
_JHORA_TO_JC = {
    0: "Sun", 1: "Moon", 2: "Mars", 3: "Mercury",
    4: "Jupiter", 5: "Venus", 6: "Saturn", 7: "Rahu", 8: "Ketu",
}
_PLANET_ABBREV = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
    "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke",
}
# Rashi index (0-11) → sign name for jyotichart
_RASHI_SIGN = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Saggitarius","Capricorn","Aquarius","Pisces"
]
# jyotichart planet colours (dark-theme friendly)
_COLOURS = {
    "Sun":"#f59e0b","Moon":"#e2e8f0","Mars":"#ef4444","Mercury":"#34d399",
    "Jupiter":"#facc15","Venus":"#f0abfc","Saturn":"#818cf8",
    "Rahu":"#94a3b8","Ketu":"#94a3b8",
}

def _build_house_map(planet_table, lagna_num):
    """Build {planet_name: house_number} from planet_table."""
    h = {}
    for row in planet_table:
        pid = row['id']
        if pid == 'L':
            continue
        pname = _JHORA_TO_JC.get(pid)
        if pname:
            h[pname] = row['house']
    return h

def _svg_string_north(planet_table, lagna_num):
    """Generate North Indian chart SVG as a string."""
    lagna_sign = _RASHI_SIGN[lagna_num % 12]
    house_map = _build_house_map(planet_table, lagna_num)

    # Use jyotichart's SVG skeleton writer but capture to StringIO
    cfg = _nc.reset_chartcfg()
    cfg['background-colour'] = '#0d1117'
    cfg['outerbox-colour'] = '#c9a84c'
    cfg['line-colour'] = '#7b5ea7'
    cfg['sign-colour'] = '#c9a84c'
    # Highlight lagna house
    house_keys = ['tanbhav','dhanbhav','anujbhav','maatabhav','santanbhav','rogbhav',
                  'dampathyabhav','aayubhav','bhagyabhav','karmabhav','laabbhav','karchbhav']
    cfg['house-colour'][house_keys[0]] = '#1a1a3e'  # lagna house slightly highlighted

    # Compute housesigns
    asc_num = _gen.signnum(lagna_sign)
    housesigns = [_gen.compute_nthsignnum(asc_num, h) for h in range(1, 13)]

    buf = io.StringIO()
    buf.write(f'<svg id="NI_chart" height="420" width="420" xmlns="http://www.w3.org/2000/svg" '
              f'viewBox="0 0 420 420" shape-rendering="geometricPrecision" text-rendering="geometricPrecision">\n')
    buf.write('  <style>\n')
    buf.write('    .sign-num { font: bold 18px sans-serif; }\n')
    buf.write('    .planet { font: bold 14px sans-serif; }\n')
    buf.write('    .aspect { font: bold 12px sans-serif; opacity:0.5; }\n')
    buf.write('  </style>\n')

    # Background + skeleton
    buf.write(f'  <rect width="420" height="420" style="fill:{cfg["background-colour"]}"/>\n')
    buf.write(f'  <rect width="410" height="410" x="5" y="5" style="fill:{cfg["background-colour"]};stroke-width:2;stroke:{cfg["outerbox-colour"]}"/>\n')
    _write_ni_skeleton(buf, cfg)
    _write_ni_signs(buf, cfg['sign-colour'], housesigns)

    # Place planets
    planet_idx = [1]*12  # count per house
    for pname, hnum in sorted(house_map.items(), key=lambda x: x[0]):
        if hnum < 1 or hnum > 12: continue
        retro = any(r['retro'] and _JHORA_TO_JC.get(r['id']) == pname for r in planet_table)
        colour = _COLOURS.get(pname, 'white')
        pos = _nc.get_coordniates(hnum, planet_idx[hnum-1])
        if pos == (0, 0): continue
        planet_idx[hnum-1] += 1
        sym = _PLANET_ABBREV.get(pname, pname[:2])
        if retro:
            buf.write(f'  <text y="{pos[1]}" x="{pos[0]}" fill="{colour}" '
                      f'text-decoration="underline" class="planet">({sym})</text>\n')
        else:
            buf.write(f'  <text y="{pos[1]}" x="{pos[0]}" fill="{colour}" class="planet">{sym}</text>\n')

    buf.write('</svg>\n')
    return buf.getvalue()


def _svg_string_south(planet_table, lagna_num):
    """Generate South Indian chart SVG as a string."""
    lagna_sign = _RASHI_SIGN[lagna_num % 12]
    house_map = _build_house_map(planet_table, lagna_num)

    cfg = _sc.reset_chartcfg()
    cfg['background-colour'] = '#0d1117'
    cfg['outerbox-colour'] = '#c9a84c'
    cfg['innerbox-colour'] = '#7b5ea7'
    cfg['line-colour'] = '#7b5ea7'
    cfg['sign-colour'] = '#c9a84c'

    buf = io.StringIO()
    buf.write('<svg id="SI_chart" height="330" width="490" xmlns="http://www.w3.org/2000/svg" '
              'viewBox="0 0 490 340" shape-rendering="geometricPrecision" text-rendering="geometricPrecision">\n')
    buf.write('  <style>\n')
    buf.write('    .sign-num { font: bold 14px sans-serif; }\n')
    buf.write('    .planet { font: bold 13px sans-serif; }\n')
    buf.write('  </style>\n')

    # Use _sc to draw skeleton
    buf.write(f'  <rect id="border" width="486" height="327" x="0" y="7" '
              f'style="fill:{cfg["background-colour"]};stroke-width:2;stroke:{cfg["outerbox-colour"]}"/>\n')
    buf.write(f'  <rect id="center" width="235" height="156" x="126" y="92" '
              f'style="fill:{cfg["background-colour"]};stroke-width:2;stroke:{cfg["innerbox-colour"]}"/>\n')
    
    sign_cells = [
        ("aries",123,10),("taurus",243,10),("gemini",363,10),
        ("cancer",363,90),("leo",363,170),("virgo",363,250),
        ("libra",243,250),("scorpio",123,250),("sagittarius",3,250),
        ("capricorn",3,170),("aquarius",3,90),("pisces",3,10),
    ]
    for sign, sx, sy in sign_cells:
        clr = cfg['house-colour'].get(sign, cfg['background-colour'])
        buf.write(f'  <rect id="{sign}" width="120" height="80" x="{sx}" y="{sy}" '
                  f'style="fill:{clr};stroke:{cfg["line-colour"]};stroke-width:1.5"/>\n')

    # Lagna marker
    asc_px = _sc.SouthChart_AscendantPositionAries["x"] + _sc.SouthChart_offsets4mAries[lagna_sign.lower()]["x"]
    asc_py = _sc.SouthChart_AscendantPositionAries["y"] + _sc.SouthChart_offsets4mAries[lagna_sign.lower()]["y"]
    buf.write(f'  <text id="Asc" x="{asc_px}" y="{asc_py}" fill="{cfg["sign-colour"]}" class="sign-num">Asc</text>\n')

    # Place planets by sign
    planet_idx = [1]*12
    asc_num = _gen.signnum(lagna_sign)
    for pname, hnum in sorted(house_map.items(), key=lambda x: x[0]):
        if hnum < 1 or hnum > 12: continue
        sign = _gen.get_signofsign(hnum, lagna_sign)
        retro = any(r['retro'] and _JHORA_TO_JC.get(r['id']) == pname for r in planet_table)
        colour = _COLOURS.get(pname, 'white')
        pos = _sc.get_coordniates(sign, planet_idx[hnum-1])
        if pos == (0, 0): continue
        planet_idx[hnum-1] += 1
        sym = _PLANET_ABBREV.get(pname, pname[:2])
        if retro:
            buf.write(f'  <text y="{pos[1]}" x="{pos[0]}" fill="{colour}" '
                      f'text-decoration="underline" class="planet">({sym})</text>\n')
        else:
            buf.write(f'  <text y="{pos[1]}" x="{pos[0]}" fill="{colour}" class="planet">{sym}</text>\n')

    buf.write('</svg>\n')
    return buf.getvalue()


def _write_ni_skeleton(buf, cfg):
    lc = cfg['line-colour']
    hc = cfg['house-colour']
    buf.write(f'  <polygon id="tanbhav" points="210,10 110,110 210,210 310,110" style="fill:{hc["tanbhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="dhanbhav" points="10,10 210,10 110,110" style="fill:{hc["dhanbhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="anujbhav" points="10,10 10,210 110,110" style="fill:{hc["anujbhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="maatabhav" points="110,110 10,210 110,310 210,210" style="fill:{hc["maatabhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="santanbhav" points="10,210 110,310 10,410" style="fill:{hc["santanbhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="rogbhav" points="210,410 110,310 10,410" style="fill:{hc["rogbhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="dampathyabhav" points="210,410 110,310 210,210 310,310" style="fill:{hc["dampathyabhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="aayubhav" points="210,410 310,310 410,410" style="fill:{hc["aayubhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="bhagyabhav" points="310,310 410,410 410,210" style="fill:{hc["bhagyabhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="karmabhav" points="310,310 410,210 310,110 210,210" style="fill:{hc["karmabhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="laabbhav" points="410,210 310,110 410,10" style="fill:{hc["laabbhav"]};stroke:{lc};stroke-width:1.5"/>\n')
    buf.write(f'  <polygon id="karchbhav" points="310,110 410,10 210,10" style="fill:{hc["karchbhav"]};stroke:{lc};stroke-width:1.5"/>\n')


def _write_ni_signs(buf, clr, housesigns):
    positions = [
        (193,195),(97,95),(70,118),(170,218),(75,316),(97,335),
        (195,240),(296,337),(320,318),(220,218),(318,118),(298,98)
    ]
    for i, (x, y) in enumerate(positions):
        buf.write(f'  <text x="{x}" y="{y}" fill="{clr}" class="sign-num">{housesigns[i]:02d}</text>\n')


def generate_chart_svg(planet_table, lagna_num, style='north'):
    """
    Generate chart SVG string.
    style: 'north' or 'south'
    Returns SVG string.
    """
    try:
        if style == 'south':
            return _svg_string_south(planet_table, lagna_num)
        return _svg_string_north(planet_table, lagna_num)
    except Exception as e:
        return f'<svg><text x="10" y="20" fill="red">Chart error: {e}</text></svg>'
