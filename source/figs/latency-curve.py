import math
W,H=470,190; L,B,T,R=44,34,14,12
pw,ph=W-L-R,H-B-T
def X(u): return L+pw*u
def pts(f,u0=0.02,u1=0.97,n=80):
    return ' '.join(f'{X(u0+(u1-u0)*i/n):.1f},{H-B-ph*min(f(u0+(u1-u0)*i/n),1):.1f}' for i in range(n+1))
lat=lambda u: 0.08+0.9*(u**5)  # shape
thr=lambda u: min(u/0.88,1)*0.9
print(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="{H}pt" viewBox="0 0 {W} {H}" font-family="Inter, sans-serif" font-size="8.5">
<rect x="{L}" y="{T}" width="{pw}" height="{ph}" fill="#fff" stroke="#c9d3dd"/>
<line x1="{X(.88)}" y1="{T}" x2="{X(.88)}" y2="{H-B}" stroke="#b4492f" stroke-dasharray="4 3"/>
<text x="{X(.88)-3}" y="{T+10}" text-anchor="end" fill="#b4492f">capacity limit</text>
<polyline points="{pts(lat)}" fill="none" stroke="#17324D" stroke-width="2"/>
<polyline points="{pts(thr,0.02,0.97)}" fill="none" stroke="#176B87" stroke-width="2" stroke-dasharray="5 3"/>
<text x="{X(.06)}" y="{H-B-ph*0.08-8}" fill="#17324D" font-weight="600">latency</text>
<text x="{X(.42)}" y="{H-B-ph*0.43-8}" fill="#176B87" font-weight="600" transform="rotate(-23 {X(.42)} {H-B-ph*0.43-8})">throughput</text>
<text x="{L+pw/2}" y="{H-8}" text-anchor="middle" fill="#263238">offered load (requests per second) &#8594;</text>
<text x="10" y="{T+ph/2}" transform="rotate(-90 10 {T+ph/2})" text-anchor="middle" fill="#263238">relative value</text>
<text x="{X(.12)}" y="{H-B-ph*0.34}" fill="#263238">latency flat: spare capacity</text>
<text x="{X(.80)}" y="{T+44}" fill="#263238" text-anchor="end">queues build, latency climbs</text>
</svg>''')
