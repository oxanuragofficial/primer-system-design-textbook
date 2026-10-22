spans=[('frontend  GET /checkout',0,480,0),('order-service  create_order',20,455,1),('pricing-service  quote',30,90,2),('inventory-service  reserve',60,370,2),('inventory db  SELECT ... FOR UPDATE',80,330,3),('payment-service  charge',390,440,2)]
W,Lw=470,170; rh=22; H=len(spans)*rh+36; T=500
def X(t): return Lw+(W-Lw-10)*t/T
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="{H}pt" viewBox="0 0 {W} {H}" font-family="Inter, sans-serif" font-size="8.4">']
for t in range(0,501,100):
    o.append(f'<line x1="{X(t):.1f}" y1="6" x2="{X(t):.1f}" y2="{H-22}" stroke="#E0E7EE"/><text x="{X(t):.1f}" y="{H-8}" text-anchor="middle" fill="#455560">{t} ms</text>')
for i,(n,a,b,d) in enumerate(spans):
    y=10+i*rh; col='#b4492f' if 'inventory db' in n else '#176B87' if d else '#17324D'
    o.append(f'<text x="{6+d*8}" y="{y+10}" fill="#263238">{n}</text><rect x="{X(a):.1f}" y="{y+13}" width="{X(b)-X(a):.1f}" height="5" rx="2" fill="{col}"/>')
o.append('</svg>'); print(''.join(o))
