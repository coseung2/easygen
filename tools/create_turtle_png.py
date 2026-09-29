from pathlib import Path
from PIL import Image, ImageDraw

from lab_paths import series_path
OUT = series_path("02-turtle-ship", "plates")
W, H = 1344, 768
PAPER=(238,230,210); INK=(23,25,31); GOLD=(180,138,66); RED=(169,68,53); BLUE=(38,77,114)

def common(d):
    d.line((70,90,1274,90),fill=GOLD,width=2); d.line((70,678,1274,678),fill=GOLD,width=2)

def ship(d, y=480, scale=1.0):
    pts=[(180,y),(330,y-130),(650,y-110),(1030,y-45),(1180,y+30),(1040,y+100),(270,y+100)]
    d.polygon(pts,fill=INK,outline=GOLD)
    d.line((260,y-40,1000,y-70),fill=GOLD,width=8)
    for x in (360,500,650,800,940): d.line((x,y-80,x+20,y-180),fill=GOLD,width=7)
    d.polygon([(1090,y-65),(1160,y-170),(1190,y-45)],fill=RED,outline=GOLD)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for i in range(1,7):
        im=Image.new("RGB",(W,H),PAPER); d=ImageDraw.Draw(im); common(d)
        if i==1: d.rectangle((0,0,W,H),fill=INK); common(d); ship(d,500)
        elif i==2: ship(d,520); d.line((420,420,420,220),fill=GOLD,width=7); d.line((680,420,680,180),fill=GOLD,width=7); d.line((940,420,940,220),fill=GOLD,width=7)
        elif i==3:
            d.rectangle((0,0,W,H),fill=INK); common(d); cx,cy=700,390
            for r in (180,130,80): d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=GOLD,width=6)
            d.line((cx-220,cy,cx+220,cy),fill=GOLD,width=4); d.line((cx,cy-220,cx,cy+220),fill=GOLD,width=4)
        elif i==4:
            d.rectangle((0,420,W,768),fill=BLUE); d.ellipse((1050,70,1190,210),fill=GOLD); ship(d,500)
            d.rectangle((980,230,1080,500),fill=INK,outline=GOLD,width=6)
        elif i==5:
            d.rectangle((0,0,W,H),fill=INK); common(d); ship(d,560);
            d.ellipse((720,210,1050,540),outline=GOLD,width=6); d.ellipse((820,310,950,440),outline=BLUE,width=5); d.line((560,375,720,375),fill=RED,width=6); d.line((1050,375,1200,375),fill=BLUE,width=6)
        else:
            d.rectangle((0,0,W,H),fill=INK); common(d); ship(d,570); d.ellipse((650,200,1050,600),outline=GOLD,width=6); d.ellipse((820,370,880,430),fill=GOLD)
        im.save(OUT/f"c{i}.png")
    print(OUT)

if __name__=="__main__": main()
