#!/usr/bin/env python3
# Generate Interstate '76 Steam library artwork: a 70s-southwest desert-sunset scene
# (sky gradient, layered mountains, a vanishing interstate, sun) + title lettering.
# Outputs the 5 Steam slots at correct dimensions.
import os, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = "/private/tmp/claude-501/-Users-jamesvalentine-Documents-Repositories-mac-gaming-ports/b50977da-e002-449c-b723-ede354c6d910/scratchpad/i76-deck-bundle/artwork"
os.makedirs(OUT, exist_ok=True)
FONT = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

def lerp(a, b, t): return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

def scene(W, H, horizon_frac=0.62):
    """Desert sunset scene sized W x H."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    hz = int(H * horizon_frac)
    # sky: purple -> red -> amber down to horizon
    sky = [(0.0,(26,18,48)),(0.45,(150,40,40)),(0.8,(214,90,30)),(1.0,(245,175,70))]
    for y in range(hz):
        t = y/max(1,hz)
        # find segment
        for i in range(len(sky)-1):
            if sky[i][0] <= t <= sky[i+1][0]:
                lt = (t-sky[i][0])/(sky[i+1][0]-sky[i][0])
                c = lerp(sky[i][1], sky[i+1][1], lt); break
        else: c = sky[-1][1]
        for x in range(W): px[x,y] = c
    # sun
    d = ImageDraw.Draw(img, "RGBA")
    sun_r = int(H*0.13); sx=int(W*0.5); sy=int(hz-sun_r*0.15)
    for r in range(sun_r*3, 0, -2):
        a = int(70*(1-r/(sun_r*3)))
        d.ellipse([sx-r,sy-r,sx+r,sy+r], fill=(255,210,120,a))
    d.ellipse([sx-sun_r,sy-sun_r,sx+sun_r,sy+sun_r], fill=(255,235,170,255))
    # mountains (layered silhouettes), darker toward foreground
    import random; random.seed(76)
    layers = [(0.0,(96,52,40)),(0.5,(66,34,26)),(1.0,(38,20,15))]
    for li,(off,col) in enumerate(layers):
        base = hz + int(off*(H-hz)*0.35)
        pts=[(0,H)]
        x=0
        peak = int((0.10+0.06*li)*H)
        while x<=W:
            pts.append((x, base - random.randint(0,peak)))
            x += random.randint(int(W*0.06), int(W*0.14))
        pts.append((W,H))
        d.polygon(pts, fill=col+(255,))
    # the interstate: trapezoid road to the sun
    road=(30,26,26)
    d.polygon([(int(W*0.5-W*0.02),hz),(int(W*0.5+W*0.02),hz),(int(W*0.72),H),(int(W*0.28),H)], fill=road)
    # dashes
    for i in range(6):
        t=i/6.0; yy=int(hz+(H-hz)*t); w=int((2+t*10)); seg=int((4+t*22))
        d.rectangle([int(W*0.5-w/2),yy,int(W*0.5+w/2),yy+seg], fill=(230,200,90))
    # foreground darken vignette
    vig=Image.new("L",(W,H),0); vd=ImageDraw.Draw(vig)
    vd.ellipse([-W*0.3,-H*0.3,W*1.3,H*1.4], fill=90)
    vig=vig.filter(ImageFilter.GaussianBlur(W*0.15))
    dark=Image.new("RGB",(W,H),(8,5,10))
    img=Image.composite(img,dark,vig)
    return img

def title(draw, cx, cy, main_px, sub=True, w=None):
    f=ImageFont.truetype(FONT, main_px)
    t1="INTERSTATE '76"
    # shadow + red outline + cream fill
    for dx,dy in [(-3,-3),(3,3),(0,4)]:
        draw.text((cx+dx,cy+dy), t1, font=f, fill=(10,5,5), anchor="mm")
    for dx,dy in [(-2,0),(2,0),(0,-2),(0,2)]:
        draw.text((cx+dx,cy+dy), t1, font=f, fill=(150,25,20), anchor="mm")
    draw.text((cx,cy), t1, font=f, fill=(248,238,214), anchor="mm")
    if sub:
        fs=ImageFont.truetype(FONT, int(main_px*0.5))
        draw.text((cx,cy+int(main_px*0.85)), "A R S E N A L", font=fs, fill=(230,180,90), anchor="mm")

def fit_title(img, frac_y, main_px):
    d=ImageDraw.Draw(img); W,H=img.size
    title(d, W//2, int(H*frac_y), main_px)
    return img

# --- Portrait capsule 600x900 (p.png) ---
p = scene(600,900,0.55)
p = fit_title(p, 0.80, 60)
p.save(f"{OUT}/capsule_p.png")

# --- Landscape/header 920x430 (.png) ---
l = scene(920,430,0.66)
l = fit_title(l, 0.80, 62)
l.save(f"{OUT}/header.png")

# --- Hero 1920x620 (_hero.png) ---
h = scene(1920,620,0.7)
# hero title lower-left third so the page UI sits over the rest
d=ImageDraw.Draw(h); title(d, int(1920*0.32), int(620*0.5), 92)
h.save(f"{OUT}/hero.png")

# --- Logo (transparent) 1280x480 (_logo.png) ---
lg=Image.new("RGBA",(1280,480),(0,0,0,0)); d=ImageDraw.Draw(lg)
title(d, 640, 210, 110)
lg.save(f"{OUT}/logo.png")

# --- Icon 256x256 (_icon.png) ---
ic = scene(256,256,0.6)
d=ImageDraw.Draw(ic)
f=ImageFont.truetype(FONT, 92)
for dx,dy in [(-2,-2),(2,2)]: d.text((128+dx,120+dy),"76",font=f,fill=(10,5,5),anchor="mm")
d.text((128,120),"76",font=f,fill=(248,238,214),anchor="mm")
fs=ImageFont.truetype(FONT,26); d.text((128,180),"INTERSTATE",font=fs,fill=(230,180,90),anchor="mm")
ic.save(f"{OUT}/icon.png")

print("wrote:", sorted(os.listdir(OUT)))
