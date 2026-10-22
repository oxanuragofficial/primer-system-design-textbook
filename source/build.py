import os, re, sys, glob, hashlib, subprocess, html, json
import markdown, seqdiag
HERE = os.path.dirname(os.path.abspath(__file__))
CH = os.path.join(HERE, 'chapters'); FG = os.path.join(HERE, 'figs'); CA = os.path.join(HERE, 'cache'); OUT = os.path.join(HERE, 'out')
THEME = ('graph [bgcolor=transparent fontname="Inter" pad=0.12 nodesep=0.32 ranksep=0.5]; '
 'node [shape=box style="rounded,filled" fillcolor="#E8EEF4" color="#17324D" fontname="Inter" fontsize=10.5 fontcolor="#263238" penwidth=1.1 margin="0.13,0.07"]; '
 'edge [color="#176B87" fontname="Inter" fontsize=9 fontcolor="#17324D" arrowsize=0.75 penwidth=1.1]; ')
MD = ['tables', 'fenced_code', 'def_list', 'attr_list', 'sane_lists', 'codehilite']
MDC = {'codehilite': {'guess_lang': False, 'noclasses': False}}
TITLES = dict(objectives='Learning objectives', prereq='Prerequisite knowledge', terms='Key terminology', analogy='Everyday analogy', example='Practical example',
  worked='Worked example', warning='Common mistake', note='Clarification', interview='Interview questions', misconception='Common misconception',
  checkpoint='Checkpoint', summary='Chapter summary', supplement='Supplemental material', exercise='Exercises', revision='Revision checklist', failure='Failure modes', tradeoff='Trade-offs')
FIGWARN = []; FIGINFO = []; STRICT = False; MISSING = set()

def md(text):
    return markdown.markdown(text, extensions=MD, extension_configs=MDC, output_format='html5')

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<![\w*])\*([^*]+)\*(?![\w*])', r'<i>\1</i>', s)
    return s

def make_fig(fid):
    base = os.path.join(FG, fid)
    for ext in ('dot', 'seq', 'py', 'svg'):
        p = f'{base}.{ext}'
        if os.path.exists(p): break
    else: raise FileNotFoundError(fid)
    src = open(p).read(); h = hashlib.md5((src + THEME + 'v3').encode()).hexdigest()[:10]
    out = os.path.join(CA, f'{fid}-{h}.svg')
    if not os.path.exists(out):
        if ext == 'dot':
            i = src.index('{'); src2 = src[:i + 1] + '\n' + THEME + '\n' + src[i + 1:]
            r = subprocess.run(['dot', '-Tsvg'], input=src2, capture_output=True, text=True)
            if r.returncode: raise RuntimeError(fid + ': ' + r.stderr)
            svg = r.stdout
        elif ext == 'seq':
            svg, w = seqdiag.render(src)
            FIGWARN.extend(f'{fid}: {x}' for x in w)
        elif ext == 'py':
            svg = subprocess.run([sys.executable, p], capture_output=True, text=True, check=True).stdout
        else: svg = src
        open(out, 'w').write(svg)
    svg = open(out).read()
    m = re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', svg)
    w, h = float(m.group(1)), float(m.group(2))
    return out, w, h

def process(files, collect=None, labels=None, final=False):
    """returns html; collect is dict for pass 1 (labels, toc, index)."""
    body = []; toc = []; labels = labels if labels is not None else {}
    ixmap = {}; ixc = [0]
    chn = 0; appn = 0
    for f in files:
        lines = open(f).read().split('\n')
        part = None; label = None; derived = added = ''
        k = 0
        while k < len(lines) and lines[k].startswith('%'):
            d = lines[k]
            if d.startswith('%part '): part = d[6:].split('|')
            elif d.startswith('%label '): label = d[7:].strip()
            elif d.startswith('%derived '): derived = d[9:].strip()
            elif d.startswith('%added '): added = d[7:].strip()
            k += 1
        lines = lines[k:]
        if part:
            body.append(f'<section class="part" id="part-{len(toc)}"><div class="pn">{html.escape(part[0].strip())}</div><h1>{html.escape(part[1].strip())}</h1><p>{html.escape(part[2].strip()) if len(part)>2 else ""}</p></section>')
            toc.append(('part', part[0].strip() + ' · ' + part[1].strip(), f'part-{len(toc)-0}'))
            toc[-1] = ('part', part[0].strip() + ' — ' + part[1].strip(), f'part-{len(toc)-1}')
            body[-1] = body[-1].replace(f'id="part-{len(toc)-1+0}"', f'id="part-{len(toc)-1}"')
        if label: ctag = label; isapp = True
        else: chn += 1; ctag = str(chn); isapp = False
        sec = 0; fig = 0; tab = 0; buf = []; infence = False
        def flush():
            if buf:
                t = '\n'.join(buf).strip('\n')
                if t.strip(): body.append(md(t))
                buf.clear()
        def sub(t):
            # references and index markers
            def ref(m):
                kind, key = m.group(1), m.group(2)
                if kind in ('fig', 'tab'): key = f'{kind}-{key}'
                if final and STRICT and key not in labels: raise KeyError(f'{f}: unresolved {kind}:{key}')
                if final and key not in labels: MISSING.add(key)
                v = labels.get(key, ('?', key))
                name = {'fig': 'Figure', 'tab': 'Table', 'sec': 'Section', 'ch': 'Chapter'}[kind]
                if kind == 'ch' and v[0][0].isalpha() and len(v[0]) == 1: name = 'Appendix'
                return f'<a href="#{key}">{name}&nbsp;{v[0]}</a>'
            t = re.sub(r'(?:Chapters?|Sections?|Figures?|Tables?|Appendix)\s+(?=\{(?:fig|tab|sec|ch):)', '', t)
            t = re.sub(r'\{(fig|tab|sec|ch):([\w-]+)\}', ref, t)
            def ix(m):
                shown, _, entry = m.group(1).partition('|'); entry = entry or shown
                ixc[0] += 1; i = f'ix-{ixc[0]}'
                ixmap.setdefault(entry.strip(), []).append(i)
                return f'<span class="ix" id="{i}">{shown}</span>'
            return re.sub(r'\[\[(.+?)\]\]', ix, t)
        i = 0; boxlines = None
        while i < len(lines):
            ln = lines[i]
            if ln.startswith('```'): infence = not infence
            if infence or ln.startswith('```') or boxlines is not None and not ln.startswith(':::') :
                if boxlines is not None: boxlines.append(ln)
                else: buf.append(ln)
                i += 1; continue
            m = re.match(r'^:::\s*(\w+)(\s+long)?\s*(.*)$', ln)
            if m and boxlines is None:
                flush(); boxkind = m.group(1); boxlong = bool(m.group(2)); boxtitle = m.group(3).strip() or TITLES.get(boxkind, boxkind.title())
                boxlines = []; i += 1; continue
            if ln.strip() == ':::' and boxlines is not None:
                inner = md(re.sub(r'(\*\*Answers?\.\*\*)\n', r'\1\n\n', sub('\n'.join(boxlines))))
                if boxkind == 'terms': inner = f'<div class="terms">{inner}</div>'
                body.append(f'<div class="box {boxkind}{" long" if boxlong else ""}"><div class="bt">{html.escape(boxtitle)}</div>{inner}</div>')
                boxlines = None; i += 1; continue
            m = re.match(r'^# (.+?)(?:\s*\{#([\w-]+)\})?\s*$', ln)
            if m:
                flush(); key = m.group(2) or f'ch-{ctag}'
                labels[key] = (ctag, m.group(1))
                kick = (f'Appendix {ctag}' if isapp else f'Chapter {ctag}')
                src = ''
                if derived or added:
                    src = '<p class="srcline">' + (f'<b>Derived from your notes:</b> {html.escape(derived)}. ' if derived else '') + (f'<b>Added in this book:</b> {html.escape(added)}.' if added else '') + '</p>'
                body.append(f'<section class="chapter-open" id="{key}"><div class="kicker">{kick}</div><h1>{inline(m.group(1))}</h1>{src}</section>')
                toc.append(('ch', f'{ctag}&ensp;{inline(m.group(1))}' if not isapp else f'Appendix {ctag}&ensp;{inline(m.group(1))}', key)); i += 1; continue
            m = re.match(r'^## (.+?)(?:\s*\{#([\w-]+)\})?\s*$', ln)
            if m:
                flush(); sec += 1; key = m.group(2) or f'sec-{ctag}-{sec}'
                labels[key] = (f'{ctag}.{sec}', m.group(1))
                body.append(f'<h2 id="{key}"><span class="secnum">{ctag}.{sec}</span>&ensp;{inline(m.group(1))}</h2>')
                toc.append(('sec', f'{ctag}.{sec}&ensp;{inline(m.group(1))}', key)); i += 1; continue
            m = re.match(r'^### (.+?)\s*$', ln)
            if m: flush(); body.append(f'<h3>{inline(m.group(1))}</h3>'); i += 1; continue
            m = re.match(r'^#### (.+?)\s*$', ln)
            if m: flush(); body.append(f'<h4>{inline(m.group(1))}</h4>'); i += 1; continue
            m = re.match(r'^\{\{fig\s+([\w-]+)\s*\|\s*(.+?)\}\}\s*$', ln)
            if m:
                flush(); fig += 1; fid = m.group(1); key = f'fig-{fid}'; labels[key] = (f'{ctag}.{fig}', m.group(2))
                if final:
                    path, w, h = make_fig(fid)
                    cap_w = 470; scale = min(1, cap_w / w); eff = 10.5 * scale
                    hh = h * scale
                    FIGINFO.append((fid, round(w), round(h), round(scale, 2)))
                    if scale < 0.8 and not fid.startswith('seq'): FIGWARN.append(f'{fid}: scaled to {scale:.2f} (labels ~{eff:.1f}pt)')
                    if hh > 560: FIGWARN.append(f'{fid}: too tall {hh:.0f}pt')
                    wd = w * scale
                    body.append(f'<figure id="{key}"><img src="file://{path}" style="width:{wd:.0f}pt"/><div class="fcap"><b>Figure {ctag}.{fig}</b>&ensp;{sub(inline(m.group(2)))}</div></figure>')
                else: body.append('')
                i += 1; continue
            m = re.match(r'^Table(?:\[([\w-]+)\])?:\s*(.+)$', ln)
            if m:
                flush(); tab += 1; key = f'tab-{m.group(1)}' if m.group(1) else f'tab-{ctag}-{tab}'
                labels[key] = (f'{ctag}.{tab}', m.group(2))
                body.append(f'<div class="tcap" id="{key}"><b>Table {ctag}.{tab}</b>&ensp;{sub(inline(m.group(2)))}</div>'); i += 1; continue
            buf.append(sub(ln)); i += 1
        flush()
    return '\n'.join(body), toc, labels, ixmap

def toc_html(toc):
    o = ['<section class="toc"><h1>Contents</h1>']
    for kind, text, key in toc:
        cls = {'part': 'tp', 'ch': 'tc', 'sec': 'ts'}[kind]
        o.append(f'<div class="{cls}"><a href="#{key}">{text}</a></div>')
    o.append('</section>'); return '\n'.join(o)


def auto_index(body):
    """Insert anchors at the first occurrence of each glossary term per chapter; returns (body, ixmap)."""
    terms = {}
    for ln in open(os.path.join(CH, '42-appendix-glossary.md')):
        if ln.startswith('|') and not ln.startswith('|---') and not ln.startswith('| Term'):
            c = ln.split('|')[1].strip()
            for part in c.split(' / '):
                base = re.sub(r'\s*\(.*?\)', '', part).strip()
                if base: terms[part.strip()] = base
    for extra in ['Paxos', 'Kafka', 'DNS', 'TLS', 'OAuth', 'Snowflake', 'SimHash', 'MinHash', 'HyperLogLog', 'B-tree', 'PageRank', 'MapReduce', 'TCP', 'UDP', 'REST', 'GraphQL', 'Cassandra', 'DynamoDB', 'Redis', 'Memcached', 'Zipf', 'canary deployment', 'blue-green', 'feature flag', 'two-phase locking', 'write-through', 'write-behind', 'read-your-writes', 'linearizability', 'sticky session', 'heap', 'hash table', 'sharding key', 'long polling', 'WebSocket']:
        terms.setdefault(extra, extra)
    chunks = re.split(r'(?=<section class="chapter-open")', body)
    ixmap = {}; n = [0]
    para = re.compile(r'(<(?:p|li)>)(.*?)(</(?:p|li)>)', re.S)
    for ci, ch in enumerate(chunks):
        if ch[:300].find('Appendix') >= 0 or 'class="part"' in ch[:60]: continue
        pending = dict(terms)
        def fix(m):
            pieces = re.split(r'(<[^>]+>)', m.group(2)); incode = 0; out = []
            for p in pieces:
                if p.startswith('<'):
                    if p.startswith('<code'): incode += 1
                    elif p.startswith('</code'): incode -= 1
                    out.append(p); continue
                if incode or not pending: out.append(p); continue
                for key in list(pending):
                    base = pending[key]
                    flags = 0 if (base.isupper() and len(base) <= 5) else re.I
                    mm = re.search(r'(?<![\w-])' + re.escape(base) + r'(?![\w-])', p, flags)
                    if mm:
                        n[0] += 1; i = f'ixa-{n[0]}'
                        ixmap.setdefault(key, []).append(i)
                        p = p[:mm.start()] + f'<span class="ixa" id="{i}">\u200b</span>' + p[mm.start():]
                        del pending[key]
                out.append(p)
            return m.group(1) + ''.join(out) + m.group(3)
        chunks[ci] = para.sub(fix, ch)
    return ''.join(chunks), ixmap

def index_html(ixmap):
    o = ['<section class="chapter-open" id="idx"><div class="kicker">Reference</div><h1>Index</h1></section><div class="index">']
    cur = ''
    for term in sorted(ixmap, key=lambda s: s.lower()):
        L = term[0].upper()
        if L != cur: cur = L; o.append(f'<div class="il">{L}</div>')
        links = ''.join(f'<a href="#{i}"></a>' for i in ixmap[term][:4])
        o.append(f'<div class="ie">{html.escape(term)}&ensp;{links}</div>')
    o.append('</div>'); return '\n'.join(o)

def main(argv):
    allf = sorted(glob.glob(os.path.join(CH, '*.md')))
    files = [f for f in allf if not argv or any(os.path.basename(f).startswith(a) for a in argv)]
    full = not argv
    global STRICT; STRICT = full
    _, toc, labels, _ = process(files)
    body, toc, labels, ixmap = process(files, labels=labels, final=True)
    cover = open(os.path.join(HERE, 'cover.html')).read()
    metapage = open(os.path.join(HERE, 'meta.html')).read()
    if full:
        body, ix2 = auto_index(body)
        for k, v in ix2.items(): ixmap.setdefault(k, []).extend(v)
    idx = index_html(ixmap) if full else ''
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>System Design: From First Principles to Production</title>
<meta name="author" content="Prepared from the System Design Primer notes"><meta name="description" content="A complete beginner-to-professional textbook on system design">
<meta name="keywords" content="system design, distributed systems, scalability, databases, caching, interviews"><link rel="stylesheet" href="file://{HERE}/style.css"></head><body>
{cover}{metapage}{toc_html(toc)}<div class="bodystart"></div>{body}{idx}</body></html>'''
    open(os.path.join(OUT, 'book.html'), 'w').write(doc)
    import weasyprint
    pdf = os.path.join(OUT, 'book.pdf' if full else 'part.pdf')
    weasyprint.HTML(string=doc, base_url=HERE).write_pdf(pdf, optimize_images=True)
    print('pdf', pdf)
    for w in FIGWARN: print('FIGWARN', w)
    print('figs', len(FIGINFO)); print('MISSING REFS', sorted(MISSING))
    json.dump(dict(toc=toc, labels={k: v[0] for k, v in labels.items()}), open(os.path.join(OUT, 'meta.json'), 'w'))
if __name__ == '__main__': main(sys.argv[1:])
