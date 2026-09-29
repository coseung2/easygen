// 21 "무적의 암호가 풀린 날 — 에니그마와 튜링" — native After Effects motion graphics, sepia archive.
(function () {
  var DATA_ROOT = $.getenv("MODAL_GUI_DATA_ROOT");
  if (!DATA_ROOT) DATA_ROOT = new File($.fileName).parent.parent.fsName + "/data";
  var ROOT = DATA_ROOT + "/series/21-enigma-turing";
  var OUT = ROOT + "/ae";
  var projectPath = OUT + "/21-enigma-master.aep";
  var renderPath = OUT + "/21-enigma-master.avi";
  var logPath = OUT + "/21-enigma-master.log";
  var musicPath = OUT + "/music-30s.wav";
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
  function ellL(name, w, h, color, pos, strokeW) {
    var l = shapeLayer(name);
    vectors(l).addProperty("ADBE Vector Shape - Ellipse").property("ADBE Vector Ellipse Size").setValue([w, h]);
    if (strokeW) addStroke(l, color, strokeW); else addFill(l, color);
    tr(l, "ADBE Position").setValue(pos); return l;
  }
  function circL(name, d, color, pos, strokeW) { return ellL(name, d, d, color, pos, strokeW); }
  function pathL(name, pts, color, w, closed, fillColor, pos) {
    var l = shapeLayer(name);
    var s = new Shape(); s.vertices = pts; s.closed = !!closed;
    vectors(l).addProperty("ADBE Vector Shape - Group").property("ADBE Vector Shape").setValue(s);
    if (fillColor) addFill(l, fillColor);
    if (color) addStroke(l, color, w);
    tr(l, "ADBE Position").setValue(pos || [0, 0]); return l;
  }
  function trim(l, a, b) {
    var t = vectors(l).addProperty("ADBE Vector Filter - Trim");
    keys(t.property("ADBE Vector Trim End"), [[a, 0], [b, 100]]);
  }
  function pop(l, t, peak) { peak = peak || 115; keys(tr(l, "ADBE Scale"), [[t, [0, 0]], [t + 0.22, [peak, peak]], [t + 0.38, [100, 100]]]); }
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
  function reveal(l, a, b) {
    try {
      var group = function () { return l.property("ADBE Text Properties").property("ADBE Text Animators"); };
      group().addProperty("ADBE Text Animator");
      var idx = group().numProperties;
      var A = function () { return group().property(idx); };
      A().property("ADBE Text Animator Properties").addProperty("ADBE Text Opacity");
      A().property("ADBE Text Animator Properties").property("ADBE Text Opacity").setValue(0);
      A().property("ADBE Text Selectors").addProperty("ADBE Text Selector");
      keys(A().property("ADBE Text Selectors").property(1).property("ADBE Text Percent Start"), [[a, 0], [b, 100]]);
    } catch (e) {
      note("reveal fallback " + e.toString());
      keys(tr(l, "ADBE Opacity"), [[a, 0], [b, 100]]);
    }
  }
  function wipeBg(name, color, t, dir, end) {
    var l = rectL(name, W + 40, H + 40, color, [960, 540]);
    var from = null;
    if (dir == "right") from = [960 + W + 40, 540];
    if (dir == "left") from = [960 - W - 40, 540];
    if (dir == "bottom") from = [960, 540 + H + 40];
    if (dir == "top") from = [960, 540 - H - 40];
    if (from) { keys(tr(l, "ADBE Position"), [[t - 0.3, from], [t, [960, 540]]]); span(l, t - 0.3, end); }
    else span(l, t, end);
    return l;
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

  function scene1() {
    wipeBg("S1 BG", C.deep, 0, "none", 5);
    var jamo = ["가", "나", "다", "라", "마", "바", "사", "아"];
    var rowX = [420, 575, 730, 885, 1040, 1195, 1350, 1505];
    for (var i = 0; i < jamo.length; i++) {
      var ch = txt(jamo[i], 150, C.gold, [rowX[i], 540]);
      keys(tr(ch, "ADBE Position"), [[0.1 + i * 0.05, [rowX[(i * 5 + 2) % 8], 300 + ((i * 137) % 420)]], [0.5 + i * 0.09, [rowX[i], 540]]]);
      span(ch, 0.1, 1.9);
      keys(tr(ch, "ADBE Opacity"), [[1.5 + i * 0.04, 100], [1.85 + i * 0.04, 0]]);
    }
    var rule = rectL("S1 rule", 1120, 6, C.gold, [960, 640], null);
    keys(tr(rule, "ADBE Scale"), [[1.2, [0, 100]], [1.7, [100, 100]]]); span(rule, 1.2, 5);
    var a = txt("이 암호, 풀 수 있을까요?", 128, C.cream, [960, 480]); slam(a, 1.45, 300); span(a, 1.45, 5);
    var cursor = rectL("S1 cursor", 8, 120, C.gold, [960, 700], null);
    keys(tr(cursor, "ADBE Opacity"), [[1.45, 100], [1.75, 0], [2.05, 100], [2.35, 0], [2.65, 100], [2.95, 0], [3.25, 100], [3.55, 0], [3.85, 100], [4.15, 0]]);
    span(cursor, 1.45, 5);
    var cap = txt("가장 강한 암호, 에니그마", 54, C.gold, [960, 860]); reveal(cap, 2.6, 3.4); span(cap, 2.6, 5);
  }

  function scene2() {
    wipeBg("S2 BG", C.paper, 5, "right", 10);
    var rot = clipLayer(CLIPS.rotor, 5, 10, 118, 126, [1310, 545]);
    circleMask(rot, 672, 384, 370, 50);
    var ring = circL("S2 ring", 780, C.gold, [1310, 545], 6); trim(ring, 5.4, 6.4);
    keys(tr(ring, "ADBE Rotate Z"), [[5.4, -30], [10, 30]]); span(ring, 5.4, 10);
    var d1 = circL("S2 disk1", 300, C.ink, [560, 420], 5); pop(d1, 5.5); span(d1, 5.5, 10);
    var d2 = circL("S2 disk2", 300, C.gold, [650, 420], 5); pop(d2, 5.65); span(d2, 5.65, 10);
    var d3 = circL("S2 disk3", 300, C.ink, [740, 420], 5); pop(d3, 5.8); span(d3, 5.8, 10);
    var slot = rectL("S2 slot", 46, 46, C.rust, [740, 420], null); pop(slot, 6.2); span(slot, 6.2, 10);
    keys(tr(slot, "ADBE Position"), [[6.6, [740, 420]], [7.0, [650, 420]], [7.4, [560, 420]]]);
    var key = rectL("S2 key", 120, 40, C.ink, [470, 690], null); pop(key, 6.4); span(key, 6.4, 10);
    keys(tr(key, "ADBE Scale"), [[6.9, [100, 100]], [7.0, [100, 70]], [7.2, [100, 100]]]);
    var wire = pathL("S2 wire", [[520, 660], [560, 500], [660, 470], [740, 460]], C.ink, 7); trim(wire, 6.6, 7.2); span(wire, 6.6, 10);
    var letters = ["가", "나", "다", "라"];
    for (var i = 0; i < letters.length; i++) {
      var t = 7.6 + i * 0.35;
      var ch = txt(letters[i], 110, C.rust, [560 + i * 95, 540]);
      keys(tr(ch, "ADBE Scale"), [[t, [0, 0]], [t + 0.2, [120, 120]], [t + 0.34, [100, 100]]]); span(ch, t, 10);
    }
    var a = txt("글쇠를 누를 때마다 글자가 달라져요", 84, C.ink, [960, 950]); reveal(a, 8.1, 8.9); span(a, 8.1, 10);
  }

  function scene3() {
    wipeBg("S3 BG", C.paper, 10, "none", 15);
    var rule = rectL("S3 rule", 1500, 5, C.gold, [960, 250], null);
    keys(tr(rule, "ADBE Scale"), [[10.0, [0, 100]], [10.5, [100, 100]]]); span(rule, 10.0, 15);
    var num = txt("약 0경 가지", 165, C.ink, [960, 470]);
    var steps = [[10.40, "약 0경 가지"], [10.60, "약 1,800경 가지"], [10.78, "약 4,200경 가지"], [10.96, "약 6,800경 가지"],
      [11.14, "약 9,200경 가지"], [11.32, "약 11,500경 가지"], [11.50, "약 13,400경 가지"], [11.68, "약 14,800경 가지"],
      [11.86, "약 15,500경 가지"], [12.04, "약 15,900경 가지"]];
    for (var si = 0; si < steps.length; si++) { keyText(num, steps[si][0], steps[si][1]); }
    pop(num, 10.35, 108); span(num, 10.35, 15);
    var sub = txt("하루가 지나면 설정표가 통째로 바뀌어요", 64, C.rust, [960, 620]); reveal(sub, 12.3, 13.0); span(sub, 12.3, 15);
    var clock = circL("S3 clock", 260, C.ink, [240, 780], 8); pop(clock, 10.6); span(clock, 10.6, 15);
    var handH = rectL("S3 handH", 6, 70, C.ink, [240, 780], [0, -35]); pop(handH, 10.75); span(handH, 10.75, 15);
    var handM = rectL("S3 handM", 5, 100, C.rust, [240, 780], [0, -50]); pop(handM, 10.85); span(handM, 10.85, 15);
    keys(tr(handM, "ADBE Rotate Z"), [[10.85, 0], [15, 1440]]);
    for (var s = 0; s < 3; s++) {
      var t = 13.2 + s * 0.55;
      var sheet = rectL("S3 sheet " + s, 360, 440, C.cream, [1420, 700], null);
      var edge = rectOutlineL("S3 edge " + s, 360, 440, C.ink, 4, [1420, 700]);
      for (var r2 = 0; r2 < 6; r2++) {
        var ly = 560 + r2 * 46;
        var line = rectL("S3 line " + s + "-" + r2, 260, 8, (r2 % 2 ? C.rust : C.ink), [1420, ly], null);
        keys(tr(line, "ADBE Position"), [[t, [1420, ly]], [t + 1.05, [1420, ly]], [t + 1.35, [2380, ly]]]);
        span(line, t, t + 1.35);
      }
      pop(sheet, t); pop(edge, t); span(sheet, t, t + 0.5); span(edge, t, t + 0.5);
      keys(tr(sheet, "ADBE Position"), [[t + 0.5, [1420, 700]], [t + 1.05, [1420, 700]], [t + 1.35, [2380, 700]]]);
      keys(tr(edge, "ADBE Position"), [[t + 0.5, [1420, 700]], [t + 1.05, [1420, 700]], [t + 1.35, [2380, 700]]]);
    }
  }

  function scene4() {
    wipeBg("S4 BG", C.paper, 15, "none", 20);
    var rule = rectL("S4 rule", 1500, 5, C.ink, [960, 960], null);
    keys(tr(rule, "ADBE Scale"), [[15.1, [0, 100]], [15.6, [100, 100]]]); span(rule, 15.1, 20);
    var body = rectL("S4 manor body", 520, 300, C.cream, [520, 660], null);
    var edge = rectOutlineL("S4 manor edge", 520, 300, C.ink, 5, [520, 660]);
    var roof = pathL("S4 roof", [[-320, 0], [0, -190], [320, 0]], C.ink, 6, true, C.rust, [520, 510]);
    var chimney = rectL("S4 chimney", 60, 120, C.ink, [640, 400], null);
    pop(body, 15.3); pop(edge, 15.3); pop(roof, 15.42); pop(chimney, 15.5);
    span(body, 15.3, 20); span(edge, 15.3, 20); span(roof, 15.42, 20); span(chimney, 15.5, 20);
    for (var w2 = 0; w2 < 4; w2++) {
      var win = rectL("S4 window " + w2, 74, 96, C.gold, [340 + w2 * 120, 650], null);
      pop(win, 15.7 + w2 * 0.12); span(win, 15.7 + w2 * 0.12, 20);
    }
    var door = rectL("S4 door", 90, 150, C.ink, [520, 735], null); pop(door, 16.2); span(door, 16.2, 20);
    var sketch = ["S4 sketch1", "S4 sketch2", "S4 sketch3"];
    for (var k = 0; k < sketch.length; k++) {
      var ln = pathL(sketch[k], [[900, 640 + k * 70], [1250 + k * 60, 640 + k * 70]], C.ink, 5);
      trim(ln, 16.4 + k * 0.3, 16.9 + k * 0.3); span(ln, 16.4 + k * 0.3, 20);
    }
    var tape = clipLayer(CLIPS.tape, 16, 20, 62, 66, [1470, 700]);
    var tapeEdge = rectOutlineL("S4 tape edge", 640, 380, C.gold, 5, [1470, 700]); pop(tapeEdge, 16.5); span(tapeEdge, 16.5, 20);
    var a = txt("폴란드 수학자들이 먼저 실마리를 찾았어요", 78, C.ink, [960, 170]); reveal(a, 17.4, 18.2); span(a, 17.4, 20);
    var card = rectL("S4 card", 560, 200, C.deep, [1430, 300], null);
    var cardEdge = rectOutlineL("S4 card edge", 560, 200, C.gold, 4, [1430, 300]);
    keys(tr(card, "ADBE Rotate Z"), [[18.4, -4], [18.7, -2]]);
    keys(tr(cardEdge, "ADBE Rotate Z"), [[18.4, -4], [18.7, -2]]);
    pop(card, 18.4); pop(cardEdge, 18.4); span(card, 18.4, 20); span(cardEdge, 18.4, 20);
    var name = txt("앨런 튜링", 96, C.gold, [1430, 285]); slam(name, 18.7, 240); span(name, 18.7, 20);
    var who = txt("블레츨리 파크의 수학자", 46, C.cream, [1430, 370]); reveal(who, 19.0, 19.6); span(who, 19.0, 20);
  }

  function scene5() {
    wipeBg("S5 BG", C.deep, 20, "none", 25);
    var room = clipLayer(CLIPS.room, 20, 25, 145, 150, [960, 540]);
    keys(tr(room, "ADBE Opacity"), [[20, 0], [20.5, 78]]);
    var tint = rectL("S5 tint", W + 40, H + 40, C.deep, [960, 540]);
    keys(tr(tint, "ADBE Opacity"), [[20, 0], [20.5, 42]]); span(tint, 20, 25);
    var rows = 6, cols = 12, bars = [];
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        var t = 20.6 + (r * cols + c) * 0.02;
        var b = rectL("S5 bar " + r + "-" + c, 56, 16, (c == 9 ? C.gold : C.paper), [420 + c * 96, 520 + r * 52], null);
        keys(tr(b, "ADBE Scale"), [[t, [0, 100]], [t + 0.12, [100, 100]]]); span(b, t, 25);
        keys(tr(b, "ADBE Opacity"), [[t, 60], [t + 0.12, 100]]);
      }
    }
    var scan = rectL("S5 scan", 96, 360, C.gold, [420, 660], null);
    keys(tr(scan, "ADBE Position"), [[21.2, [420, 660]], [22.4, [420 + 9 * 96, 660]]]);
    keys(tr(scan, "ADBE Opacity"), [[21.2, 0], [21.4, 60], [22.4, 60], [22.5, 0]]);
    span(scan, 21.2, 25);
    var lock = rectOutlineL("S5 lock", 120, 420, C.gold, 6, [420 + 9 * 96, 660]); pop(lock, 22.45); span(lock, 22.45, 25);
    var burst = circL("S5 burst", 300, C.gold, [420 + 9 * 96, 660]);
    keys(tr(burst, "ADBE Scale"), [[22.5, [0, 0]], [22.9, [220, 220]]]);
    keys(tr(burst, "ADBE Opacity"), [[22.5, 70], [22.95, 0]]); span(burst, 22.5, 25);
    var a = txt("기계로 기계를 이겼어요", 110, C.cream, [960, 170]); slam(a, 22.7, 280); span(a, 22.7, 25);
    var b = txt("전쟁을 2년 이상 앞당겼다고 해요", 66, C.gold, [960, 950]); reveal(b, 23.6, 24.3); span(b, 23.6, 25);
  }

  function scene6() {
    wipeBg("S6 BG", C.deep, 25, "none", 30);
    var sea = clipLayer(CLIPS.sea, 25, 30, 148, 154, [960, 540]);
    keys(tr(sea, "ADBE Opacity"), [[25, 0], [25.5, 86]]);
    var tint = rectL("S6 tint", W + 40, H + 40, C.deep, [960, 540]);
    keys(tr(tint, "ADBE Opacity"), [[25, 0], [25.5, 30]]); span(tint, 25, 30);
    var card = rectL("S6 card", 1280, 620, C.paper, [960, 520], null);
    var cardEdge = rectOutlineL("S6 card edge", 1280, 620, C.ink, 6, [960, 520]);
    pop(card, 25.4, 104); pop(cardEdge, 25.4, 104); span(card, 25.4, 30); span(cardEdge, 25.4, 30);
    var l1 = txt("이 비밀은 그가 세상을 떠난 뒤에야 풀렸어요", 62, C.ink, [960, 360]); reveal(l1, 25.9, 26.7); span(l1, 25.9, 30);
    var l2 = txt("당시 법은 그의 사생활을 처벌했어요", 62, C.ink, [960, 470]); reveal(l2, 26.9, 27.6); span(l2, 26.9, 30);
    var l3 = txt("2013년, 영국이 공식으로 사면했어요", 62, C.ink, [960, 580]); reveal(l3, 27.8, 28.5); span(l3, 27.8, 30);
    var end = txt("컴퓨터의 아버지, 앨런 튜링", 108, C.rust, [960, 760]); slam(end, 28.6, 200); span(end, 28.6, 30);
    var stamp = circL("S6 stamp", 190, C.rust, [1560, 780], 10);
    keys(tr(stamp, "ADBE Scale"), [[29.1, [260, 260]], [29.35, [100, 100]]]);
    keys(tr(stamp, "ADBE Opacity"), [[29.1, 0], [29.25, 100]]);
    keys(tr(stamp, "ADBE Rotate Z"), [[29.1, -14], [29.4, -8]]); span(stamp, 29.1, 30);
  }

  try {
    app.newProject();
    app.beginUndoGroup("21 enigma motion graphics");
    comp = app.project.items.addComp("21 ENIGMA / MOTION GRAPHICS", W, H, 1, DUR, FPS);
    scene1(); scene2(); scene3(); scene4(); scene5(); scene6();
    var music = app.project.importFile(new ImportOptions(new File(musicPath)));
    var ml = comp.layers.add(music); ml.outPoint = DUR;
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
