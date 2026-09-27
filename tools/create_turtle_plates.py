"""Create deterministic text-free historical infographic plates for episode 02."""
from pathlib import Path

OUT = Path(r"F:/modal-gui/series/02-turtle-ship/plates")
W, H = 1344, 768
P = {"paper": "#eee6d2", "ink": "#17191f", "gold": "#b48a42", "red": "#a94435", "blue": "#264d72"}

def svg(scene: int) -> str:
    paper, ink, gold, red, blue = P["paper"], P["ink"], P["gold"], P["red"], P["blue"]
    bg = f'<rect width="{W}" height="{H}" fill="{paper}"/>'
    rules = f'<path d="M70 90H1274M70 678H1274" stroke="{gold}" stroke-width="2" opacity=".8"/>'
    if scene == 1:
        body = f'<path d="M180 470 Q330 330 650 355 L1030 420 Q1130 440 1180 500 L1040 570 L270 570 Q180 540 180 470Z" fill="{ink}" stroke="{gold}" stroke-width="8"/><path d="M260 430 Q500 290 1000 395" fill="none" stroke="{gold}" stroke-width="8"/><path d="M360 385 L390 290 M500 365 L520 260 M650 370 L660 250 M800 380 L805 270 M940 400 L945 300" stroke="{gold}" stroke-width="7"/><path d="M1090 405 L1160 300 L1190 420" fill="{red}" stroke="{gold}" stroke-width="5"/><circle cx="280" cy="520" r="18" fill="{red}"/><circle cx="1040" cy="520" r="18" fill="{red}"/>'
    elif scene == 2:
        body = f'<path d="M170 540 Q320 350 650 380 Q980 350 1170 540" fill="{ink}" stroke="{gold}" stroke-width="8"/><path d="M230 490H1110M300 440H1040" stroke="{gold}" stroke-width="5"/><path d="M400 470V260M670 470V220M930 470V270" stroke="{gold}" stroke-width="7"/><path d="M320 330 L670 200 L1020 330" fill="none" stroke="{red}" stroke-width="6"/><path d="M410 250H930" stroke="{blue}" stroke-width="5"/>'
    elif scene == 3:
        body = f'<path d="M180 540 Q360 330 660 350 Q960 330 1160 540" fill="{ink}" stroke="{gold}" stroke-width="8"/><path d="M260 470 L350 270 L460 470 M540 470 L630 270 L740 470 M820 470 L910 270 L1020 470" fill="none" stroke="{gold}" stroke-width="7"/><path d="M260 270H1020" stroke="{red}" stroke-width="8"/><path d="M350 240 L350 190 M630 240 L630 190 M910 240 L910 190" stroke="{blue}" stroke-width="5"/>'
    elif scene == 4:
        body = f'<rect x="0" y="420" width="1344" height="250" fill="{blue}" opacity=".9"/><path d="M0 470 Q160 390 320 475 T650 465 T1000 475 T1344 460" fill="none" stroke="{paper}" stroke-width="7"/><path d="M170 400 Q310 260 570 300 L980 350 Q1100 370 1170 430 L1030 500 L250 500Z" fill="{ink}" stroke="{gold}" stroke-width="8"/><path d="M340 340 L450 210 L530 340 M700 350 L800 220 L880 350" stroke="{gold}" stroke-width="7" fill="none"/><circle cx="1080" cy="150" r="70" fill="{gold}" opacity=".7"/>'
    else:
        body = f'<rect x="145" y="185" width="420" height="340" fill="{ink}" stroke="{gold}" stroke-width="6"/><path d="M185 475 Q280 335 490 350 Q550 360 530 420 L475 475Z" fill="{red}" stroke="{gold}" stroke-width="5"/><circle cx="890" cy="355" r="155" fill="none" stroke="{gold}" stroke-width="7"/><circle cx="890" cy="355" r="80" fill="none" stroke="{blue}" stroke-width="5"/><path d="M735 355H1045M890 200V510" stroke="{gold}" stroke-width="4"/><path d="M565 355H735" stroke="{red}" stroke-width="6" stroke-dasharray="18 14"/><path d="M1045 355H1190" stroke="{blue}" stroke-width="6" stroke-dasharray="18 14"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{bg}{rules}{body}</svg>'

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i in range(1, 7):
        (OUT / f"c{i}.svg").write_text(svg(i), encoding="utf-8")
    print(OUT)

if __name__ == "__main__":
    main()
