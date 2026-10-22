W,H=470,150
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="{H}pt" viewBox="0 0 {W} {H}" font-family="Inter, sans-serif" font-size="8.6"><defs><marker id="a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="#176B87"/></marker></defs>']
rows=[('Strong',[(80,'1'),(150,'1'),(240,'1'),(330,'1')],'#17324D'),('Eventual',[(80,'0'),(150,'0'),(240,'1'),(330,'1')],'#176B87'),('Weak',[(80,'0'),(150,'0'),(240,'0'),(330,'1?')],'#b4492f')]
x0=70; t0=110
o.append(f'<line x1="{x0}" y1="128" x2="{W-10}" y2="128" stroke="#9fb3c2" marker-end="url(#a)"/><text x="{W-12}" y="141" text-anchor="end" fill="#455560">time</text>')
o.append(f'<line x1="{t0}" y1="6" x2="{t0}" y2="124" stroke="#176B87" stroke-dasharray="4 3"/><text x="{t0+4}" y="14" fill="#176B87" font-weight="600">t0: write x = 1 completes</text>')
for i,(n,pts,c) in enumerate(rows):
    y=44+i*34
    o.append(f'<text x="8" y="{y+4}" font-weight="700" fill="{c}">{n}</text><line x1="{x0}" y1="{y}" x2="{W-10}" y2="{y}" stroke="#E0E7EE"/>')
    for x,v in pts:
        xx=x+60
        o.append(f'<circle cx="{xx}" cy="{y}" r="9" fill="#fff" stroke="{c}" stroke-width="1.4"/><text x="{xx}" y="{y+3.2}" text-anchor="middle" fill="{c}" font-weight="700">{v}</text>')
o.append(f'<text x="{x0}" y="141" fill="#455560">circles = value returned by a read</text></svg>')
print(''.join(o))
