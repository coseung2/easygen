from pathlib import Path
from PIL import Image, ImageDraw

from lab_paths import series_path
OUT=series_path("03-kim-jeong-ho", "plates");W,H=1344,768
PAPER=(239,232,214);INK=(24,28,32);GOLD=(169,128,57);RED=(157,61,48);BLUE=(45,82,104)
def common(d):
    d.line((60,86,1284,86),fill=GOLD,width=2);d.line((60,682,1284,682),fill=GOLD,width=2)
def map_shape(d,off=0):
    pts=[(190+off,540),(260+off,470),(300+off,390),(370+off,350),(420+off,270),(500+off,320),(560+off,260),(640+off,330),(700+off,245),(760+off,310),(850+off,280),(920+off,360),(1010+off,330),(1080+off,410),(1160+off,480),(1090+off,570),(890+off,600),(690+off,575),(500+off,620),(300+off,590)]
    d.polygon(pts,fill=PAPER,outline=GOLD);d.line(pts+[pts[0]],fill=INK,width=4)
    for x in range(270,1070,105): d.line((x,360,x+80,570),fill=BLUE,width=3)
    for y in range(350,600,75): d.line((240,y,1110,y+30),fill=RED,width=3)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for i in range(1,7):
        im=Image.new("RGB",(W,H),PAPER);d=ImageDraw.Draw(im);common(d)
        if i==1:
            d.rectangle((0,0,W,H),fill=INK);common(d);map_shape(d,-20)
            for x,y in [(250,590),(410,540),(600,490),(780,430),(970,380)]:d.ellipse((x-10,y-10,x+10,y+10),fill=RED)
        elif i==2:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.rectangle((180,170,780,600),fill=(72,48,31),outline=GOLD,width=6)
            for y in range(230,560,65):d.line((230,y,730,y-30),fill=GOLD,width=4)
            for x in range(250,720,95):d.line((x,210,x-35,560),fill=RED,width=3)
            d.line((900,250,1160,520),fill=GOLD,width=8);d.ellipse((1040,380,1080,420),fill=RED)
        elif i==3:
            map_shape(d,0);d.line((300,600,1040,260),fill=GOLD,width=8);d.line((300,260,1040,600),fill=GOLD,width=8)
            for x,y in [(300,600),(500,500),(720,400),(1040,260)]:d.ellipse((x-12,y-12,x+12,y+12),fill=RED)
        elif i==4:
            d.rectangle((0,0,W,H),fill=BLUE);d.ellipse((1010,70,1160,220),fill=GOLD);map_shape(d,0)
            d.line((240,600,1030,300),fill=PAPER,width=6);d.line((300,620,1120,340),fill=GOLD,width=4)
        elif i==5:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.rectangle((160,170,560,590),fill=(75,48,31),outline=GOLD,width=5);map_shape(d,360)
            for y in range(240,540,70):d.line((200,y,520,y-25),fill=GOLD,width=3)
        else:
            d.rectangle((0,0,W,H),fill=INK);common(d);map_shape(d,0)
            d.ellipse((620,290,860,530),outline=GOLD,width=7);d.ellipse((700,370,780,450),fill=GOLD)
        im.save(OUT/f"c{i}.png")
if __name__=="__main__":main()
