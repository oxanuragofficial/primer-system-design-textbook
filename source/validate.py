import sys, re, json, subprocess, collections
from pypdf import PdfReader
P = sys.argv[1]
r = PdfReader(P); n = len(r.pages); res = {}
res['pages'] = n
sizes = collections.Counter((round(float(p.mediabox.width)), round(float(p.mediabox.height))) for p in r.pages)
res['page_sizes'] = dict((f'{k[0]}x{k[1]}', v) for k, v in sizes.items())
md = r.metadata or {}
res['metadata'] = {k: str(v) for k, v in md.items()}
# bookmarks
def walk(o, d=0):
    c = 0
    for x in o:
        if isinstance(x, list): c += walk(x, d + 1)
        else: c += 1
    return c
res['bookmarks'] = walk(r.outline)
# links
internal = external = broken = 0
names = set(r.named_destinations.keys()) if r.named_destinations else set()
for p in r.pages:
    for a in p.get('/Annots') or []:
        a = a.get_object()
        if a.get('/Subtype') != '/Link': continue
        act = a.get('/A'); 
        if '/Dest' in a: internal += 1; continue
        if act is None: continue
        act = act.get_object()
        if act.get('/S') == '/URI': external += 1
        elif act.get('/S') == '/GoTo':
            internal += 1
            d = act.get('/D')
            if isinstance(d, str) and names and d not in names: broken += 1
res['links'] = dict(internal=internal, external=external, broken_named=broken)
# text per page
texts = []
empty = []; low = []
for i in range(n):
    t = subprocess.run(['pdftotext', '-f', str(i+1), '-l', str(i+1), '-layout', P, '-'], capture_output=True, text=True).stdout
    texts.append(t); k = len(re.sub(r'\s', '', t))
    if k < 40: empty.append(i+1)
    elif k < 400: low.append((i+1, k))
res['empty_pages(<40 chars)'] = empty
res['low_text_pages(<400 chars)'] = low
res['total_words'] = sum(len(t.split()) for t in texts)
# fonts
f = subprocess.run(['pdffonts', P], capture_output=True, text=True).stdout.splitlines()[2:]
unemb = [l for l in f if l.split()[-5:-4] and l.split()[-5] == 'no']
res['fonts'] = len(f); res['unembedded_fonts'] = unemb
# replacement chars / tofu
bad = [i+1 for i, t in enumerate(texts) if '�' in t or '□' in t]
res['pages_with_replacement_chars'] = bad
# unresolved markers
mk = [i+1 for i, t in enumerate(texts) if re.search(r'\{(fig|tab|sec|ch):|\{\{|%derived|:::|\?\?', t)]
res['pages_with_unresolved_markers'] = mk
# TOC check: every chapter heading present on page claimed? check meta toc titles appear in text
meta = json.load(open('out/meta.json'))
miss = []
for kind, text, key in meta['toc']:
    if kind == 'ch':
        title = re.sub(r'^(Appendix )?[A-Z0-9]+(&ensp;|\s)+', '', text).replace('&amp;','&')[:30]
        if not any(title.lower()[:25] in t.replace('\n', ' ').lower() for t in texts[8:]): miss.append(text)
res['toc_chapters'] = sum(1 for k in meta['toc'] if k[0] == 'ch'); res['toc_parts'] = sum(1 for k in meta['toc'] if k[0] == 'part')
res['toc_chapter_titles_not_found_in_text'] = miss
json.dump(res, open('out/validation.json', 'w'), indent=1)
print(json.dumps(res, indent=1)[:4000])
