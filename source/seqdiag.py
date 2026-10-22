"""Tiny sequence-diagram renderer -> SVG (navy/teal theme)."""
import re, html
NAVY, TEAL, LIGHT, TXT = '#17324D', '#176B87', '#E8EEF4', '#263238'
def cw(s, fs=9): return len(s) * fs * 0.55
def render(src, width=470):
    parts = []; items = []
    for ln in src.strip().splitlines():
        ln = ln.rstrip()
        if not ln.strip() or ln.strip().startswith('#'): continue
        if ln.startswith('participants:'):
            parts = [p.strip() for p in ln.split(':', 1)[1].split(',')]; continue
        m = re.match(r'^==\s*(.+?)\s*==$', ln.strip())
        if m: items.append(('phase', m.group(1))); continue
        m = re.match(r'^note over ([^:]+):\s*(.+)$', ln.strip())
        if m: items.append(('note', [x.strip() for x in m.group(1).split(',')], m.group(2))); continue
        m = re.match(r'^(.+?)\s*(-->|<--|->|<-)\s*(.+?):\s*(.+)$', ln.strip())
        if m:
            a, arrow, b, t = m.groups()
            if arrow.startswith('<'): a, b = b, a
            items.append(('msg', a, b, t, arrow.endswith('-->') or arrow == '<--')); continue
        if ln.strip().startswith('self '):
            m = re.match(r'^self ([^:]+):\s*(.+)$', ln.strip()); items.append(('self', m.group(1), m.group(2))); continue
        raise ValueError('bad seq line: ' + ln)
    n = len(parts); pad = 14; step = (width - 2 * pad) / n
    X = {p: pad + step * (i + .5) for i, p in enumerate(parts)}
    warns = []; y = 8; out = []
    boxw = min(step - 8, 110)
    for p in parts:
        out.append(f'<rect x="{X[p]-boxw/2:.1f}" y="{y}" width="{boxw:.1f}" height="22" rx="4" fill="{NAVY}"/>'
                   f'<text x="{X[p]:.1f}" y="{y+14.5}" text-anchor="middle" font-size="9.5" font-weight="600" fill="#fff">{html.escape(p)}</text>')
        if cw(p, 9.5) > boxw: warns.append('participant label wide: ' + p)
    top = y + 22; y = top + 16; body = []
    for it in items:
        if it[0] == 'phase':
            body.append(f'<rect x="{pad}" y="{y-9}" width="{width-2*pad}" height="15" fill="{LIGHT}"/><text x="{pad+5}" y="{y+2}" font-size="8.5" font-weight="700" fill="{TEAL}" letter-spacing=".6">{html.escape(it[1].upper())}</text>')
            y += 20
        elif it[0] == 'note':
            xs = [X[p] for p in it[1]]; x0 = min(xs) - 36; x1 = max(xs) + 36
            if len(xs) == 1: x0, x1 = xs[0] - 58, xs[0] + 58
            x0 = max(x0, pad); x1 = min(x1, width - pad)
            lines = wrap(it[2], int((x1 - x0 - 10) / (8.3 * .53)))
            h = 8 + 10.5 * len(lines)
            body.append(f'<rect x="{x0:.1f}" y="{y-8}" width="{x1-x0:.1f}" height="{h}" rx="3" fill="#FFF8E6" stroke="#c58f12" stroke-width=".7"/>')
            for i, l in enumerate(lines):
                body.append(f'<text x="{(x0+x1)/2:.1f}" y="{y+3+10.5*i}" text-anchor="middle" font-size="8.3" fill="{TXT}">{html.escape(l)}</text>')
            y += h + 8
        elif it[0] == 'self':
            x = X[it[1]]
            body.append(f'<path d="M{x:.1f} {y} h26 v12 h-26" fill="none" stroke="{TEAL}" stroke-width="1.2" marker-end="url(#ah)"/>'
                        f'<text x="{x+30:.1f}" y="{y+8}" font-size="8.5" fill="{TXT}">{html.escape(it[2])}</text>')
            if x + 30 + cw(it[2], 8.5) > width: warns.append('self label overflow: ' + it[2])
            y += 24
        else:
            _, a, b, t, dash = it
            xa, xb = X[a], X[b]; d = ' stroke-dasharray="4 3"' if dash else ''
            if a == b: raise ValueError('use self')
            sgn = 1 if xb > xa else -1
            lines = wrap(t, max(8, int((abs(xb - xa) - 10) / (8.5 * .53))))
            y += 10.5 * (len(lines) - 1)
            ty = y - 3 - 10.5 * (len(lines) - 1)
            for i, l in enumerate(lines):
                body.append(f'<text x="{(xa+xb)/2:.1f}" y="{ty+10.5*i:.1f}" text-anchor="middle" font-size="8.5" fill="{TXT}">{html.escape(l)}</text>')
            body.append(f'<line x1="{xa:.1f}" y1="{y+3}" x2="{xb-sgn*1:.1f}" y2="{y+3}" stroke="{TEAL}" stroke-width="1.2"{d} marker-end="url(#ah)"/>')
            y += 20
    H = y + 6
    for p in parts:
        out.insert(0, f'<line x1="{X[p]:.1f}" y1="{top}" x2="{X[p]:.1f}" y2="{H-4}" stroke="#9fb3c2" stroke-width=".8" stroke-dasharray="3 3"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}pt" height="{H:.0f}pt" viewBox="0 0 {width} {H:.0f}" font-family="Inter, sans-serif">'
           f'<defs><marker id="ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="{TEAL}"/></marker></defs>'
           + ''.join(out) + ''.join(body) + '</svg>')
    return svg, warns
def wrap(s, n):
    words, lines, cur = s.split(), [], ''
    for w in words:
        if len(cur) + len(w) + 1 > n and cur: lines.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    if cur: lines.append(cur)
    return lines or ['']
