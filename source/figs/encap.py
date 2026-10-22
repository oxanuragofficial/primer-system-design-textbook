W,H=470,118
layers=[('Link frame','#E8EEF4',0,'Ethernet / Wi-Fi header ... trailer'),('IP packet','#d5e7ef',22,'source and destination IP address'),('TCP segment','#bcd9e5',44,'ports, sequence numbers, ACKs'),('HTTP request','#ffffff',66,'GET /users/42 HTTP/1.1  Host: api.example.com')]
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="{H}pt" viewBox="0 0 {W} {H}" font-family="Inter, sans-serif" font-size="9">']
for name,c,i,t in layers:
    x=6+i*0.9; w=W-12-i*1.8; y=4+i*0.75*1.0; h=H-8-i*1.5
    o.append(f'<rect x="{6+i*1.7}" y="{4+i*1.2}" width="{W-12-i*3.4}" height="{H-8-i*2.4}" rx="5" fill="{c}" stroke="#17324D" stroke-width="1"/>')
    o.append(f'<text x="{14+i*1.7}" y="{16+i*1.2+ (0)}" fill="#17324D" font-weight="700">{name}</text><text x="{110+i*1.7}" y="{16+i*1.2}" fill="#263238">{t}</text>')
o.append('</svg>'); print(''.join(o))
