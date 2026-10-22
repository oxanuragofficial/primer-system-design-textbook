import math
rows=[('L1 cache reference',0.5),('Main memory reference',100),('Read 4 KB from SSD',150000),('Same-datacentre round trip',500000),('Read 1 MB from SSD',1000000),('Disk seek',10000000),('Read 1 MB from disk',30000000),('CA - Netherlands round trip',150000000)]
W,Lw,R=470,150,60; rh=19; H=len(rows)*rh+40
lo,hi=math.log10(0.5),math.log10(2e8)
def X(v): return Lw+(W-Lw-R)*(math.log10(v)-lo)/(hi-lo)
def fmt(v):
    for n,d in (('ms',1e6),('µs',1e3)):
        if v>=d: return f'{v/d:g} {n}'
    return f'{v:g} ns'
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="{H}pt" viewBox="0 0 {W} {H}" font-family="Inter, sans-serif" font-size="8.6">']
for e in range(0,9):
    x=X(10**e); o.append(f'<line x1="{x:.1f}" y1="6" x2="{x:.1f}" y2="{H-26}" stroke="#E0E7EE"/>')
    lab={0:'1 ns',3:'1 µs',6:'1 ms',9:'1 s'}.get(e)
    if lab: o.append(f'<text x="{x:.1f}" y="{H-12}" text-anchor="middle" fill="#455560">{lab}</text>')
for i,(n,v) in enumerate(rows):
    y=10+i*rh; x=X(v); col='#176B87' if v<1e6 else '#17324D'
    o.append(f'<text x="{Lw-6}" y="{y+10}" text-anchor="end" fill="#263238">{n}</text><rect x="{Lw}" y="{y+1}" width="{x-Lw:.1f}" height="12" fill="{col}" rx="2"/><text x="{x+4:.1f}" y="{y+10.5}" fill="#17324D" font-weight="600">{fmt(v)}</text>')
o.append(f'<text x="{(Lw+W-R)/2}" y="{H-1}" text-anchor="middle" fill="#455560" font-size="8">time (logarithmic scale)</text></svg>')
print(''.join(o))
