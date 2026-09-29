// 21 "무적의 암호가 풀린 날 — 에니그마와 튜링" v2 — illustration plates + beat-grid kinetic type.
(function () {
  var DATA_ROOT = $.getenv("MODAL_GUI_DATA_ROOT");
  if (!DATA_ROOT) DATA_ROOT = new File($.fileName).parent.parent.fsName + "/data";
  var ROOT = DATA_ROOT + "/series/21-enigma-turing";
  var OUT = ROOT + "/ae";
  var projectPath = OUT + "/21-enigma-master-v2.aep";
  var renderPath = OUT + "/21-enigma-master-v2.avi";
  var logPath = OUT + "/21-enigma-master-v2.log";
  var audioPath = OUT + "/music-mix-30s.wav";
  var PLATES = {
    paper: ROOT + "/plates/plate-paper.png",
    manor: ROOT + "/plates/plate-manor.png",
    rotor: ROOT + "/plates/plate-rotor.png",
    bombe: ROOT + "/plates/plate-bombe.png",
    wheel: ROOT + "/plates/plate-wheel.png",
    props: ROOT + "/plates/plate-props.png"
  };
  var CLIPS = {
    rotor: ROOT + "/clips/c1-rotor.mp4",
    tape: ROOT + "/clips/c2-tape.mp4",
    room: ROOT + "/clips/c3-room.mp4",
    sea: ROOT + "/clips/c4-sea.mp4"
  };
  var W = 1920, H = 1080, FPS = 24, DUR = 30;
  var C = {
    paper: [0.94, 0.92, 0.86], ink: [0.06, 0.06, 0.06], gold: [0.72, 0.60, 0.33],
    deep: [0.08, 0.15, 0.11], cream: [0.98, 0.96, 0.91], rust: [0.42, 0.24, 0.15]
  };
  var comp;

  function note(s) { var f = new File(logPath); f.open("a"); f.writeln(new Date().toString() + " " + s); f.close(); }
  function tr(l, n) { return l.property("ADBE Transform Group").property(n); }
  function ease(prop) {
    try {
      var dims = 1, t = prop.propertyValueType;
      if (t == PropertyValueType.TwoD) dims = 2;
      if (t == PropertyValueType.ThreeD) dims = 3;
      for (var k = 1; k <= prop.numKeys; k++) {
        var e = []; for (var d = 0; d < dims; d++) e.push(new KeyframeEase(0, 80));
        prop.setTemporalEaseAtKey(k, e, e);
      }
    } catch (err) {}
  }
  function keys(prop, arr) { for (var i = 0; i < arr.length; i++) prop.setValueAtTime(arr[i][0], arr[i][1]); ease(prop); }
  function span(l, a, b) { l.inPoint = a; l.outPoint = b; }
  function shapeLayer(name) { var l = comp.layers.addShape(); l.name = name; return l; }
  function vectors(l) { return l.property("ADBE Root Vectors Group"); }
  function addFill(l, color) { vectors(l).addProperty("ADBE Vector Graphic - Fill").property("ADBE Vector Fill Color").setValue(color); }
  function addStroke(l, color, w) {
    var s = vectors(l).addProperty("ADBE Vector Graphic - Stroke");
    s.property("ADBE Vector Stroke Color").setValue(color);
    s.property("ADBE Vector Stroke Width").setValue(w);
    try { s.property("ADBE Vector Stroke Line Cap").setValue(2); } catch (e) {}
  }
  function rectL(name, w, h, color, pos, offset) {
    var l = shapeLayer(name);
    var r = vectors(l).addProperty("ADBE Vector Shape - Rect");
    r.property("ADBE Vector Rect Size").setValue([w, h]);
    if (offset) r.property("ADBE Vector Rect Position").setValue(offset);
    addFill(l, color); tr(l, "ADBE Position").setValue(pos); return l;
  }
  function rectOutlineL(name, w, h, color, strokeW, pos) {
    var l = shapeLayer(name);
    var r = vectors(l).addProperty("ADBE Vector Shape - Rect");
    r.property("ADBE Vector Rect Size").setValue([w, h]);
    addStroke(l, color, strokeW); tr(l, "ADBE Position").setValue(pos); return l;
  }
  function circL(name, d, color, pos, strokeW) {
    var l = shapeLayer(name);
    vectors(l).addProperty("ADBE Vector Shape - Ellipse").property("ADBE Vector Ellipse Size").setValue([d, d]);
    if (strokeW) addStroke(l, color, strokeW); else addFill(l, color);
    tr(l, "ADBE Position").setValue(pos); return l;
  }
  function txt(str, size, color, pos) {
    var l = comp.layers.addText(str);
    var sp = l.property("Source Text"), d = sp.value;
    d.font = "BMJUA"; d.fontSize = size; d.fillColor = color; d.applyFill = true; d.applyStroke = false;
    d.justification = ParagraphJustification.CENTER_JUSTIFY; sp.setValue(d);
    var r = l.sourceRectAtTime(0, false);
    tr(l, "ADBE Anchor Point").setValue([r.left + r.width / 2, r.top + r.height / 2]);
    tr(l, "ADBE Position").setValue(pos); l.name = "TYPE " + str; return l;
  }
  function slam(l, t, from) {
    from = from || 260;
    keys(tr(l, "ADBE Scale"), [[t, [from, from]], [t + 0.18, [92, 92]], [t + 0.32, [100, 100]]]);
    keys(tr(l, "ADBE Opacity"), [[t, 0], [t + 0.08, 100]]);
  }
  function word(str, size, color, pos, t) {
    var l = txt(str, size, color, pos);
    keys(tr(l, "ADBE Scale"), [[t, [148, 148]], [t + 0.16, [93, 93]], [t + 0.30, [100, 100]]]);
    keys(tr(l, "ADBE Opacity"), [[t, 0], [t + 0.07, 100]]);
    keys(tr(l, "ADBE Position"), [[t, [pos[0], pos[1] + 30]], [t + 0.24, [pos[0], pos[1] - 6]], [t + 0.36, pos]]);
    return l;
  }
  function popIn(l, t, peak) {
    peak = peak || 104;
    keys(tr(l, "ADBE Scale"), [[t, [0, 0]], [t + 0.16, [peak, peak]], [t + 0.28, [100, 100]]]);
    keys(tr(l, "ADBE Opacity"), [[t, 0], [t + 0.06, 100]]);
  }
  function punch(l, t, amt) {
    amt = amt || 106;
    keys(tr(l, "ADBE Scale"), [[t, [100, 100]], [t + 0.10, [amt, amt]], [t + 0.22, [100, 100]]]);
  }
  function flash(t) {
    var l = rectL("FLASH " + t, 2100, 8, C.gold, [960, 540]);
    keys(tr(l, "ADBE Scale"), [[t - 0.12, [0, 100]], [t, [100, 100]], [t + 0.12, [0, 100]]]);
    span(l, t - 0.12, t + 0.12);
  }
  function circleMask(l, cx, cy, r, feather) {
    var parade = l.property("ADBE Mask Parade");
    var m = parade.addProperty("ADBE Mask Atom");
    var pts = [], n = 64;
    for (var i = 0; i < n; i++) { var a = i / n * Math.PI * 2; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); }
    var s = new Shape(); s.vertices = pts; s.closed = true;
    m.property("ADBE Mask Shape").setValue(s);
    if (feather) m.property("ADBE Mask Feather").setValue([feather, feather]);
    return m;
  }
  function plate(file, start, end, scalePct, pos) {
    var f = app.project.importFile(new ImportOptions(new File(file)));
    var l = comp.layers.add(f);
    span(l, start, end);
    tr(l, "ADBE Position").setValue(pos || [960, 540]);
    if (scalePct) tr(l, "ADBE Scale").setValue([scalePct, scalePct]);
    return l;
  }
  function coverScale(l) {
    var s = l.source;
    if (!s || !s.width || !s.height) return 100;
    return Math.max(W / s.width, H / s.height) * 100;
  }
  function clipLayer(file, start, end, startScale, endScale, pos) {
    var f = app.project.importFile(new ImportOptions(new File(file)));
    var l = comp.layers.add(f);
    l.startTime = start;
    span(l, start, end);
    try { l.audioEnabled = false; } catch (e) { note("audio mute failed " + e.toString()); }
    if (startScale) keys(tr(l, "ADBE Scale"), [[start, [startScale, startScale]], [end, [endScale || startScale, endScale || startScale]]]);
    if (pos) tr(l, "ADBE Position").setValue(pos);
    return l;
  }
  function keyText(l, t, str) {
    var sp = l.property("Source Text");
    var d = sp.value;
    d.text = str;
    sp.setValueAtTime(t, d);
  }

  function sceneBase() {
    var paper = plate(PLATES.paper, 0, DUR, 0, [960, 540]);
    paper.name = "BASE paper";
    tr(paper, "ADBE Scale").setValue([coverScale(paper), coverScale(paper)]);
    keys(tr(paper, "ADBE Scale"), [[0, [coverScale(paper), coverScale(paper)]], [DUR, [coverScale(paper) * 1.06, coverScale(paper) * 1.06]]]);
  }

  function scene1() {
    var panel = rectL("S1 panel", W + 40, H + 40, C.deep, [960, 540]);
    keys(tr(panel, "ADBE Position"), [[0, [960, -600]], [0.1, [960, 540]]]);
    span(panel, 0, 5.1);
    var a = word("무적의", 120, C.cream, [960, 400], 0.6); span(a, 0.6, 5.1);
    var b = word("암호", 190, C.gold, [960, 570], 1.1); span(b, 1.1, 5.1);
    var q = word("이 암호, 풀 수 있을까요?", 96, C.cream, [960, 770], 1.6); span(q, 1.6, 5.1);
    var tag = txt("1940년, 영국", 56, C.gold, [960, 250]); slam(tag, 2.6, 200); span(tag, 2.6, 5.1);
    var ghosts = ["가", "나", "다", "라", "마", "바"];
    for (var i = 0; i < ghosts.length; i++) {
      var g = txt(ghosts[i], 92, C.rust, [640 + i * 128, 940]);
      keys(tr(g, "ADBE Opacity"), [[3.1 + i * 0.06, 0], [3.35 + i * 0.06, 45]]);
      span(g, 3.1, 5.1);
    }
    flash(5.1);
  }

  function scene2() {
    var rot = plate(PLATES.rotor, 5.1, 10.1, 86, [1310, 560]);
    keys(tr(rot, "ADBE Scale"), [[5.1, [80, 80]], [5.35, [88, 88]], [10.1, [92, 92]]]);
    keys(tr(rot, "ADBE Opacity"), [[5.1, 0], [5.25, 100]]);
    keys(tr(rot, "ADBE Rotate Z"), [[5.1, -2.5], [10.1, 0.5]]);
    var clip = clipLayer(CLIPS.rotor, 6.1, 10.1, 100, 105, [1310, 560]);
    circleMask(clip, 672, 384, 300, 40);
    var ring = circL("S2 ring", 640, C.gold, [1310, 560], 5);
    keys(tr(ring, "ADBE Rotate Z"), [[6.1, -20], [10.1, 25]]); span(ring, 6.1, 10.1);
    popIn(ring, 6.1, 108);
    var words = [["글쇠를", 5.6, 430], ["누르면", 6.1, 540], ["글자가", 6.6, 650], ["달라져요", 7.1, 760]];
    for (var i = 0; i < words.length; i++) {
      var col = (i == 3) ? C.rust : C.ink;
      var l = word(words[i][0], 100, col, [470, words[i][2]], words[i][1]);
      span(l, words[i][1], 10.1);
    }
    var sub = txt("같은 글자가 다시 나오지 않아요", 58, C.ink, [470, 880]);
    keys(tr(sub, "ADBE Opacity"), [[8.1, 0], [8.45, 100]]); span(sub, 8.1, 10.1);
    flash(10.1);
  }

  function scene3() {
    var wheel = plate(PLATES.wheel, 10.1, 15.1, 0, [1520, 560]);
    var wl = wheel.source.width;
    var ws = 820 / wl * 100;
    keys(tr(wheel, "ADBE Scale"), [[10.1, [ws * 0.94, ws * 0.94]], [10.4, [ws, ws]], [15.1, [ws * 1.05, ws * 1.05]]]);
    keys(tr(wheel, "ADBE Rotate Z"), [[10.1, -7], [15.1, 9]]);
    keys(tr(wheel, "ADBE Opacity"), [[10.1, 0], [10.3, 100]]);
    var numCard = rectL("S3 num card", 1500, 320, C.paper, [700, 470]);
    keys(tr(numCard, "ADBE Opacity"), [[10.3, 0], [10.45, 88]]); span(numCard, 10.3, 15.1);
    var numEdge = rectOutlineL("S3 num edge", 1500, 320, C.ink, 3, [700, 470]);
    keys(tr(numEdge, "ADBE Opacity"), [[10.3, 0], [10.45, 70]]); span(numEdge, 10.3, 15.1);
    var cap = txt("가능한 설정의 수", 54, C.gold, [700, 280]); slam(cap, 10.6, 200); span(cap, 10.6, 15.1);
    var num = txt("약 0경 가지", 132, C.ink, [700, 470]);
    var steps = [[10.6, "약 1,800경 가지"], [11.1, "약 4,200경 가지"], [11.6, "약 7,400경 가지"], [12.1, "약 11,200경 가지"], [12.6, "약 15,900경 가지"]];
    for (var si = 0; si < steps.length; si++) {
      keyText(num, steps[si][0], steps[si][1]);
      punch(num, steps[si][0], 107);
    }
    span(num, 10.6, 15.1);
    var props = plate(PLATES.props, 12.9, 15.1, 50, [560, 880]);
    keys(tr(props, "ADBE Scale"), [[12.9, [0, 0]], [13.06, [53, 53]], [13.18, [50, 50]]]);
    keys(tr(props, "ADBE Opacity"), [[12.9, 0], [12.96, 100]]);
    var edge = rectOutlineL("S3 props edge", 768, 512, C.gold, 4, [560, 880]);
    keys(tr(edge, "ADBE Scale"), [[12.9, [0, 0]], [13.06, [104, 104]], [13.18, [100, 100]]]);
    keys(tr(edge, "ADBE Opacity"), [[12.9, 0], [12.96, 100]]);
    span(edge, 12.9, 15.1);
    var w1 = word("하루가 지나면", 58, C.rust, [1470, 950], 13.6); span(w1, 13.6, 15.1);
    var w2 = word("설정표가 통째로 바뀌어요", 58, C.rust, [1470, 1010], 14.1); span(w2, 14.1, 15.1);
    flash(15.1);
  }

  function scene4() {
    var manor = plate(PLATES.manor, 15.1, 20.1, 0, [960, 540]);
    var ms = coverScale(manor) * 0.98;
    keys(tr(manor, "ADBE Scale"), [[15.1, [ms, ms]], [20.1, [ms * 1.07, ms * 1.07]]]);
    keys(tr(manor, "ADBE Position"), [[15.1, [1120, 540]], [15.6, [960, 540]]]);
    keys(tr(manor, "ADBE Opacity"), [[15.1, 0], [15.25, 94]]);
    var band = rectL("S4 band", 780, H + 40, C.deep, [370, 540]);
    keys(tr(band, "ADBE Position"), [[15.1, [120, 540]], [15.5, [370, 540]]]);
    keys(tr(band, "ADBE Opacity"), [[15.1, 0], [15.3, 92]]);
    span(band, 15.1, 20.1);
    var words = [["폴란드", 15.6, 400], ["수학자들이", 16.1, 520], ["먼저", 16.6, 640], ["실마리를 찾았어요", 17.1, 760]];
    for (var i = 0; i < words.length; i++) {
      var col = (i == 3) ? C.gold : C.cream;
      var l = word(words[i][0], (i == 3 ? 66 : 92), col, [380, words[i][2]], words[i][1]);
      span(l, words[i][1], 20.1);
    }
    var card = rectL("S4 card", 640, 220, C.deep, [1430, 320]);
    var cardEdge = rectOutlineL("S4 card edge", 640, 220, C.gold, 4, [1430, 320]);
    popIn(card, 17.6, 106); popIn(cardEdge, 17.6, 106);
    span(card, 17.6, 20.1); span(cardEdge, 17.6, 20.1);
    var name = txt("앨런 튜링", 92, C.gold, [1430, 305]); slam(name, 17.6, 220); span(name, 17.6, 20.1);
    var who = txt("블레츨리 파크의 수학자", 44, C.cream, [1430, 400]);
    keys(tr(who, "ADBE Opacity"), [[18.1, 0], [18.45, 100]]); span(who, 18.1, 20.1);
    var tape = clipLayer(CLIPS.tape, 18.6, 20.1, 50, 53, [1430, 780]);
    var tapeEdge = rectOutlineL("S4 tape edge", 660, 380, C.gold, 4, [1430, 780]);
    popIn(tapeEdge, 18.6, 106); span(tapeEdge, 18.6, 20.1);
    flash(20.1);
  }

  function scene5() {
    var room = clipLayer(CLIPS.room, 20.1, 25.1, 145, 152, [960, 540]);
    keys(tr(room, "ADBE Opacity"), [[20.1, 0], [20.45, 82]]);
    var tint = rectL("S5 tint", W + 40, H + 40, C.deep, [960, 540]);
    keys(tr(tint, "ADBE Opacity"), [[20.1, 0], [20.45, 38]]); span(tint, 20.1, 25.1);
    var bombe = plate(PLATES.bombe, 20.1, 25.1, 0, [960, 640]);
    var bs = bombe.source.width;
    var bsc = 1120 / bs * 100;
    keys(tr(bombe, "ADBE Scale"), [[20.1, [bsc * 0.9, bsc * 0.9]], [20.5, [bsc, bsc]], [25.1, [bsc * 1.06, bsc * 1.06]]]);
    keys(tr(bombe, "ADBE Opacity"), [[20.1, 0], [20.3, 100]]);
    var scan = rectL("S5 scan", 96, 560, C.gold, [560, 640]);
    keys(tr(scan, "ADBE Position"), [[20.6, [560, 640]], [22.1, [1370, 640]]]);
    keys(tr(scan, "ADBE Opacity"), [[20.6, 0], [20.75, 55], [22.05, 55], [22.15, 0]]);
    span(scan, 20.6, 25.1);
    var burst = circL("S5 burst", 300, C.gold, [1370, 640]);
    keys(tr(burst, "ADBE Scale"), [[22.6, [0, 0]], [22.95, [230, 230]]]);
    keys(tr(burst, "ADBE Opacity"), [[22.6, 65], [23.0, 0]]); span(burst, 22.6, 25.1);
    var lock = rectOutlineL("S5 lock", 130, 600, C.gold, 6, [1370, 640]);
    popIn(lock, 22.6, 108); span(lock, 22.6, 25.1);
    var a = txt("기계로 기계를 이겼어요", 120, C.cream, [960, 180]); slam(a, 22.6, 300); span(a, 22.6, 25.1);
    var strip = rectL("S5 strip", 2200, 240, C.deep, [960, 960]);
    keys(tr(strip, "ADBE Opacity"), [[23.2, 0], [23.4, 72]]); span(strip, 23.2, 25.1);
    var s1 = word("전쟁을", 64, C.gold, [660, 960], 23.6); span(s1, 23.6, 25.1);
    var s2 = word("2년 이상", 64, C.gold, [960, 960], 24.1); span(s2, 24.1, 25.1);
    var s3 = word("앞당겼다고 해요", 64, C.gold, [1300, 960], 24.6); span(s3, 24.6, 25.1);
    flash(25.1);
  }

  function scene6() {
    var sea = clipLayer(CLIPS.sea, 25.1, DUR, 148, 154, [960, 540]);
    keys(tr(sea, "ADBE Opacity"), [[25.1, 0], [25.45, 86]]);
    var tint = rectL("S6 tint", W + 40, H + 40, C.deep, [960, 540]);
    keys(tr(tint, "ADBE Opacity"), [[25.1, 0], [25.45, 30]]); span(tint, 25.1, DUR);
    var card = rectL("S6 card", 1320, 660, C.paper, [960, 520]);
    var cardEdge = rectOutlineL("S6 card edge", 1320, 660, C.ink, 6, [960, 520]);
    popIn(card, 25.1, 104); popIn(cardEdge, 25.1, 104);
    span(card, 25.1, DUR); span(cardEdge, 25.1, DUR);
    var l1 = txt("이 비밀은 그가 세상을 떠난 뒤에야 풀렸어요", 60, C.ink, [960, 330]); popIn(l1, 25.6, 103); span(l1, 25.6, DUR);
    var l2 = txt("당시 법은 그의 사생활을 처벌했어요", 60, C.ink, [960, 450]); popIn(l2, 26.6, 103); span(l2, 26.6, DUR);
    var l3 = txt("2013년, 영국이 공식으로 사면했어요", 60, C.ink, [960, 570]); popIn(l3, 27.6, 103); span(l3, 27.6, DUR);
    var end = txt("컴퓨터의 아버지, 앨런 튜링", 96, C.rust, [960, 730]); slam(end, 28.6, 200); span(end, 28.6, DUR);
    keys(tr(end, "ADBE Scale"), [[28.92, [100, 100]], [DUR, [104, 104]]]);
    var fade = rectL("S6 fade", W + 40, H + 40, C.deep, [960, 540]);
    keys(tr(fade, "ADBE Opacity"), [[29.2, 0], [29.9, 100]]); span(fade, 29.2, DUR);
  }

  try {
    app.newProject();
    app.beginUndoGroup("21 enigma v2 motion graphics");
    comp = app.project.items.addComp("21 ENIGMA / MOTION GRAPHICS V2", W, H, 1, DUR, FPS);
    sceneBase(); scene1(); scene2(); scene3(); scene4(); scene5(); scene6();
    var audio = app.project.importFile(new ImportOptions(new File(audioPath)));
    var ml = comp.layers.add(audio); ml.outPoint = DUR;
    var q = app.project.renderQueue.items.add(comp);
    q.outputModule(1).file = new File(renderPath);
    app.project.save(new File(projectPath));
    app.endUndoGroup();
    note("SAVED " + projectPath + " layers=" + comp.numLayers);
    app.quit();
  } catch (e) {
    note("ERROR " + e.toString() + " line=" + e.line);
    try { app.endUndoGroup(); } catch (ignore) {}
    app.quit();
  }
})();
