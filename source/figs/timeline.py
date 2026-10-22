segs=[('Requirements\n& estimates',10,'#17324D'),('High-level\ndesign',10,'#176B87'),('Core components\n(deep dive)',15,'#2d8aa3'),('Scale, failure,\nsummary',10,'#4aa3ba')]
W=470; tot=45; x=0
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="92pt" viewBox="0 0 {W} 92" font-family="Inter, sans-serif" font-size="9">']
for n,m,c in segs:
    w=W*m/tot; a,b=n.split('\n')
    o.append(f'<rect x="{x+1:.1f}" y="8" width="{w-2:.1f}" height="44" rx="4" fill="{c}"/><text x="{x+w/2:.1f}" y="26" text-anchor="middle" fill="#fff" font-weight="700" font-size="11">{m} min</text><text x="{x+w/2:.1f}" y="39" text-anchor="middle" fill="#fff" font-size="8.4">{a}</text><text x="{x+w/2:.1f}" y="49" text-anchor="middle" fill="#fff" font-size="8.4">{b}</text>')
    x+=w
o.append(f'<line x1="2" y1="64" x2="{W-2}" y2="64" stroke="#9fb3c2"/>')
t=0
for n,m,c in segs:
    xx=W*t/tot; o.append(f'<line x1="{xx:.1f}" y1="60" x2="{xx:.1f}" y2="68" stroke="#9fb3c2"/><text x="{xx:.1f}" y="80" font-size="8" fill="#455560" text-anchor="{"start" if t==0 else "middle"}">{t} min</text>'); t+=m
o.append(f'<text x="{W-2}" y="80" font-size="8" fill="#455560" text-anchor="end">45 min</text></svg>')
print(''.join(o))
