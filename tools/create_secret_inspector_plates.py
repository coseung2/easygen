from pathlib import Path
from PIL import Image, ImageDraw

OUT=Path(r"F:/modal-gui/series/05-secret-inspector/plates");W,H=1344,768
PAPER=(239,231,210);INK=(25,24,30);GOLD=(179,133,55);RED=(158,62,49);BLUE=(46,72,96)
def common(d): d.line((60,88,1284,88),fill=GOLD,width=2);d.line((60,680,1284,680),fill=GOLD,width=2)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for i in range(1,7):
        im=Image.new("RGB",(W,H),PAPER);d=ImageDraw.Draw(im);common(d)
        if i==1:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.line((160,560,1180,260),fill=GOLD,width=5);d.ellipse((420,390,510,480),fill=RED);d.polygon([(500,390),(600,350),(650,440),(540,470)],fill=INK,outline=GOLD)
        elif i==2:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.ellipse((220,180,650,610),outline=GOLD,width=7);d.polygon([(360,260),(520,260),(590,420),(290,420)],fill=INK,outline=GOLD);d.ellipse((790,300,980,490),fill=GOLD,outline=RED,width=6);d.ellipse((840,350,930,440),fill=INK)
        elif i==3:
            d.rectangle((0,0,W,H),fill=BLUE);common(d);d.rectangle((150,170,1180,590),fill=(36,43,52),outline=GOLD,width=6);d.line((250,330,1080,330),fill=GOLD,width=4);d.line((250,470,1080,470),fill=GOLD,width=4);d.ellipse((600,400,650,450),fill=RED)
        elif i==4:
            d.rectangle((0,0,W,H),fill=PAPER);common(d);d.rectangle((180,170,1140,590),fill=INK,outline=GOLD,width=6);d.line((180,300,1140,300),fill=GOLD,width=4);d.line((180,430,1140,430),fill=GOLD,width=4);d.ellipse((940,140,1090,290),fill=RED)
        elif i==5:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.polygon([(240,230),(500,230),(560,520),(180,520)],fill=INK,outline=GOLD);d.ellipse((850,270,1050,470),fill=GOLD,outline=RED,width=6);d.line((560,395,850,395),fill=RED,width=8);d.polygon([(760,365),(840,395),(760,425)],fill=RED)
        else:
            d.rectangle((0,0,W,H),fill=INK);common(d);d.ellipse((470,180,870,580),outline=GOLD,width=8);d.ellipse((580,290,760,470),outline=RED,width=5);d.ellipse((640,350,700,410),fill=GOLD)
        im.save(OUT/f"c{i}.png")
if __name__=="__main__":main()
