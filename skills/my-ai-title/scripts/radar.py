import math
AX=["文脈","委任","検証","自律","効率","仕組"]
def radar(scores,color,label="#E9EDF5",grid="rgba(255,255,255,.18)",axes=None,fs=19):
    ax=axes or AX
    cx,cy,R=134,136,80
    pt=lambda i,r:(cx+r*math.sin(math.pi*2*i/6),cy-r*math.cos(math.pi*2*i/6))
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 268 268">']
    for lv in range(1,6):
        p=" ".join("%.1f,%.1f"%pt(i,R*lv/5) for i in range(6))
        s.append(f'<polygon points="{p}" fill="{"rgba(255,255,255,.04)" if lv==5 else "none"}" stroke="{grid}" stroke-width="{1.6 if lv==5 else 1}"/>')
    for i in range(6):
        x,y=pt(i,R); s.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{grid}"/>')
    p=" ".join("%.1f,%.1f"%pt(i,R*v/5) for i,v in enumerate(scores))
    s.append(f'<polygon points="{p}" fill="{color}" fill-opacity=".45" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>')
    for i,v in enumerate(scores):
        x,y=pt(i,R*v/5); s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#fff" stroke="{color}" stroke-width="2.5"/>')
    for i,(a,v) in enumerate(zip(ax,scores)):
        x,y=pt(i,R+30)
        s.append(f'<text x="{x:.1f}" y="{y-2:.1f}" text-anchor="middle" font-size="{fs}" font-weight="700" fill="{label}" opacity=".8">{a}</text>')
        s.append(f'<text x="{x:.1f}" y="{y+18:.1f}" text-anchor="middle" font-size="22" font-weight="800" fill="#fff">{v}</text>')
    s.append("</svg>"); return "".join(s)
