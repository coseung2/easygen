from pathlib import Path
from PIL import Image, ImageDraw

from lab_paths import series_path
OUT=series_path("04-joseon-exam", "plates");W,H=1344,768
PAPER=(239,231,210);INK=(28,25,28);GOLD=(172,128,56);RED=(156,57,47);BLUE=(48,73,104)
def common(d): d.line((60,88,1284,88),fill=GOLD,width=2);d.line((60,680,1284,680),fill=GOLD,width=2)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for i in range(1,7):
        im=Image.new("RGB",(W,H),PAPER);d=ImageDraw.Draw(im);common(d)
        if i==1:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.rectangle((170,190,900,570),fill=PAPER,outline=GOLD,width=6);d.line((250,480,820,480),fill=INK,width=4);d.line((320,300,760,300),fill=RED,width=4);d.polygon([(1010,240),(1160,240),(1130,510),(1040,510)],fill=BLUE)
        elif i==2:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.ellipse((230,170,620,560),outline=GOLD,width=8);d.line((425,210,425,520),fill=GOLD,width=4);d.line((280,365,570,365),fill=GOLD,width=4);d.rectangle((780,250,1130,510),fill=PAPER,outline=GOLD,width=6);d.line((830,340,1080,340),fill=INK,width=4)
        elif i==3:
            d.rectangle((0,0,W,H),fill=BLUE);common(d);d.rectangle((160,180,1180,570),fill=(38,48,63),outline=GOLD,width=6);d.line((160,300,1180,300),fill=GOLD,width=4);d.line((160,420,1180,420),fill=GOLD,width=4)
            for x in range(250,1100,130):d.ellipse((x-16,330,x+16,362),fill=RED)
        elif i==4:
            d.rectangle((0,0,W,H),fill=PAPER);common(d);d.rectangle((180,220,1150,570),fill=INK,outline=GOLD,width=6);d.line((180,310,1150,310),fill=GOLD,width=4);d.line((180,400,1150,400),fill=GOLD,width=4);d.line((180,490,1150,490),fill=GOLD,width=4);d.ellipse((920,130,1120,330),fill=RED)
        elif i==5:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.rectangle((160,180,530,590),fill=PAPER,outline=GOLD,width=6);d.rectangle((700,180,1110,590),fill=PAPER,outline=GOLD,width=6);d.line((530,380,700,380),fill=RED,width=8);d.polygon([(590,350),(650,380),(590,410)],fill=RED);d.ellipse((825,270,985,430),outline=GOLD,width=6)
        else:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.ellipse((360,170,980,790),outline=GOLD,width=8);d.ellipse((530,340,810,620),outline=RED,width=5);d.line((670,170,670,790),fill=GOLD,width=4);d.line((360,480,980,480),fill=GOLD,width=4)
        im.save(OUT/f"c{i}.png")
if __name__=="__main__":main()
