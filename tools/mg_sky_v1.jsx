// 09 "하늘은 왜 보라색이 아닐까?" — native After Effects motion graphics, 120 BPM grid.
(function () {
  var OUT = "F:/modal-gui/series/09-violet-sky/mg";
  var projectPath = OUT + "/09-sky-mg-v1.aep";
  var renderPath = OUT + "/09-sky-mg-v1.avi";
  var logPath = OUT + "/09-sky-mg-v1.log";
  var musicPath = OUT + "/music-30s.wav";
  var W = 1920, H = 1080, FPS = 24, DUR = 30;
  var C = {
    navy: [0.06, 0.07, 0.16], ivory: [0.97, 0.94, 0.87], violet: [0.45, 0.27, 0.85],
    blue: [0.18, 0.45, 0.95], sky: [0.42, 0.72, 1.0], deep: [0.08, 0.16, 0.38],
    gold: [1.0, 0.78, 0.25], red: [0.95, 0.3, 0.25], white: [1, 1, 1],
    ink: [0.08, 0.08, 0.12], earth: [0.12, 0.34, 0.3], air: [0.3, 0.55, 0.95]
  };
  var SPEC = [[0.95, 0.25, 0.22], [1, 0.55, 0.15], [1, 0.85, 0.2], [0.3, 0.8, 0.35],
    [0.2, 0.5, 0.95], [0.3, 0.3, 0.8], [0.55, 0.3, 0.9]];
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
  function span(l, a, b) { l.outPoint = b; l.inPoint = a; }
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
  function pulse(l, from, to, amt) {
    var s = tr(l, "ADBE Scale");
    for (var t = from; t < to - 0.01; t += 0.5) { s.setValueAtTime(t, [100 + amt, 100 + amt]); s.setValueAtTime(t + 0.2, [100, 100]); }
    ease(s);
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
  function reveal(l, a, b) {
    try {
      var group = function () { return l.property("ADBE Text Properties").property("ADBE Text Animators"); };
      group().addProperty("ADBE Text Animator");
      var idx = group().numProperties;
      var A = function () { return group().property(idx); };
      A().property("ADBE Text Animator Properties").addProperty("ADBE Text Opacity");
      A().property("ADBE Text Animator Properties").property("ADBE Text Opacity").setValue(0);
      try {
        A().property("ADBE Text Animator Properties").addProperty("ADBE Text Position 3D");
        A().property("ADBE Text Animator Properties").property("ADBE Text Position 3D").setValue([0, 70, 0]);
      } catch (e2) {}
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
  function wavePts(x0, x1, y, amp, wl) {
    var pts = [], n = 120;
    for (var k = 0; k <= n; k++) { var x = x0 + (x1 - x0) * k / n; pts.push([x, y + amp * Math.sin(2 * Math.PI * (x - x0) / wl)]); }
    return pts;
  }

  function scene1() {
    wipeBg("S1 BG", C.navy, 0, "none", 4);
    var core = circL("S1 violet core", 640, C.violet, [960, 540]); pop(core, 0, 112); pulse(core, 0.5, 4, 5); span(core, 0, 4);
    var ring = circL("S1 ring", 760, C.white, [960, 540], 6); trim(ring, 0, 1.4);
    keys(tr(ring, "ADBE Rotate Z"), [[0, 0], [4, 120]]); span(ring, 0, 4);
    var a = txt("하늘은", 130, C.white, [960, 390]); slam(a, 0.5); span(a, 0.5, 4);
    var b = txt("왜", 280, C.gold, [960, 600]); slam(b, 1.0, 320); keys(tr(b, "ADBE Rotate Z"), [[1.0, -12], [1.3, 0]]); span(b, 1.0, 4);
    var c = txt("보라색이 아닐까?", 96, C.white, [960, 995]); reveal(c, 2.0, 2.8); span(c, 2.0, 4);
    for (var i = 0; i < 10; i++) {
      var ang = i * Math.PI / 5, d = circL("S1 spark " + i, 26, C.gold, [960, 540]);
      keys(tr(d, "ADBE Position"), [[3.0, [960, 540]], [3.6, [960 + Math.cos(ang) * 640, 540 + Math.sin(ang) * 400]]]);
      keys(tr(d, "ADBE Opacity"), [[3.0, 100], [3.95, 0]]); span(d, 3.0, 4);
    }
  }

  function scene2() {
    wipeBg("S2 BG", C.ivory, 4, "right", 8);
    var sun = circL("S2 sun", 220, C.gold, [300, 540]); pop(sun, 4.0); pulse(sun, 4.5, 8, 6); span(sun, 4, 8);
    var prism = pathL("S2 prism", [[0, -190], [170, 120], [-170, 120]], C.ink, 8, true, C.white, [930, 560]);
    pop(prism, 4.25); span(prism, 4.25, 8);
    var beam = pathL("S2 beam", [[410, 540], [860, 540]], C.ink, 10); trim(beam, 4.5, 5.0); span(beam, 4.5, 8);
    for (var i = 0; i < 7; i++) {
      var t = 5.0 + i * 0.25;
      var ray = pathL("S2 ray " + i, [[995, 565], [1820, 260 + i * 90]], SPEC[i], 16); trim(ray, t, t + 0.3); span(ray, t, 8);
    }
    var a = txt("햇빛은 여러 색이 섞여 있어요", 80, C.ink, [960, 140]); reveal(a, 6.0, 6.9); span(a, 6.0, 8);
  }

  function scene3() {
    wipeBg("S3 BG", C.navy, 8, "bottom", 12);
    var rows = [["빨강", C.red, 330, 420, 8.25], ["파랑", C.blue, 540, 220, 8.75], ["보라", C.violet, 750, 150, 9.25]];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var w = pathL("S3 wave " + r[0], wavePts(420, 1720, r[2], 70, r[3]), r[1], 12); trim(w, r[4], r[4] + 1.1); span(w, r[4], 12);
      var label = txt(r[0], 68, r[1], [240, r[2]]); slam(label, r[4] + 0.25, 200); span(label, r[4] + 0.25, 12);
    }
    var a = txt("보라와 파랑은 파장이 짧아요", 80, C.white, [960, 985]); reveal(a, 10.3, 11.1); span(a, 10.3, 12);
  }

  function scene4() {
    var bg = circL("S4 BG", 100, C.deep, [960, 540]);
    keys(tr(bg, "ADBE Scale"), [[11.7, [0, 0]], [12.05, [2500, 2500]]]); span(bg, 11.7, 16);
    var air = circL("S4 atmosphere", 3500, C.air, [960, 2500], 10);
    keys(tr(air, "ADBE Position"), [[12.0, [960, 2900]], [12.4, [960, 2500]]]); span(air, 12, 16);
    var earth = circL("S4 earth", 3200, C.earth, [960, 2500]);
    keys(tr(earth, "ADBE Position"), [[12.0, [960, 2900]], [12.4, [960, 2500]]]); span(earth, 12, 16);
    var red = pathL("S4 red passes", [[0, 190], [1920, 190]], C.red, 10); trim(red, 13.0, 13.6); span(red, 13.0, 16);
    var xs = [360, 660, 960, 1260, 1560], ys = [390, 590], k = 0;
    for (var yi = 0; yi < ys.length; yi++) {
      for (var xi = 0; xi < xs.length; xi++) {
        var mx = xs[xi], my = ys[yi];
        var m = circL("S4 molecule " + k, 36, C.white, [mx, my]); pop(m, 12.5 + k * 0.12); span(m, 12.5 + k * 0.12, 16);
        var ang = ((k * 73) % 360) * Math.PI / 180, t = 13.6 + k * 0.1;
        var s = pathL("S4 scatter " + k, [[mx, my], [mx + Math.cos(ang) * 150, my + Math.sin(ang) * 150]], k % 2 ? C.violet : C.blue, 8);
        trim(s, t, t + 0.25); span(s, t, 16); k++;
      }
    }
    var a = txt("짧은 빛일수록 더 많이 흩어져요", 76, C.white, [960, 1005]); reveal(a, 14.3, 15.1); span(a, 14.3, 16);
  }

  function scene5() {
    wipeBg("S5 BG", C.ivory, 16, "left", 20);
    var sun = circL("S5 sun", 120, C.gold, [300, 300]); pop(sun, 16.2); pulse(sun, 16.5, 20, 8); span(sun, 16.2, 20);
    var base = pathL("S5 baseline", [[420, 820], [1500, 820]], C.ink, 6); trim(base, 16.0, 16.4); span(base, 16.0, 20);
    var bars = [[720, 260, C.violet, 16.5, "보라빛"], [1200, 540, C.blue, 17.0, "파란빛"]];
    for (var i = 0; i < bars.length; i++) {
      var b = bars[i];
      var bar = rectL("S5 bar " + b[4], 230, b[1], b[2], [b[0], 820], [0, -b[1] / 2]);
      keys(tr(bar, "ADBE Scale"), [[b[3], [100, 0]], [b[3] + 0.35, [100, 106]], [b[3] + 0.5, [100, 100]]]); span(bar, b[3], 20);
      var label = txt(b[4], 70, b[2], [b[0], 900]); slam(label, b[3] + 0.1, 200); span(label, b[3] + 0.1, 20);
    }
    var a = txt("햇빛 속엔 보라빛이 더 적어요", 80, C.ink, [960, 150]); reveal(a, 18.0, 18.8); span(a, 18.0, 20);
  }

  function scene6() {
    wipeBg("S6 BG", C.violet, 20, "top", 24);
    var eye = ellL("S6 eye", 760, 380, C.white, [960, 480]); pop(eye, 20.0, 108); span(eye, 20.0, 24);
    var iris = circL("S6 iris", 280, C.blue, [960, 480]); pop(iris, 20.2); span(iris, 20.2, 24);
    var pupil = circL("S6 pupil", 120, C.ink, [960, 480]); pop(pupil, 20.35); pulse(pupil, 20.5, 24, 12); span(pupil, 20.35, 24);
    var glint = circL("S6 glint", 40, C.white, [1010, 430]); pop(glint, 20.5); span(glint, 20.5, 24);
    var a = txt("우리 눈은 파랑에 더 민감해요", 84, C.white, [960, 870]); reveal(a, 21.5, 22.3); span(a, 21.5, 24);
  }

  function scene7() {
    wipeBg("S7 BG", C.navy, 24, "right", DUR);
    var skyFill = circL("S7 sky fill", 100, C.sky, [960, 1080]);
    keys(tr(skyFill, "ADBE Scale"), [[24.5, [0, 0]], [25.4, [3400, 3400]]]); span(skyFill, 24.5, DUR);
    var ring = circL("S7 ring", 1100, C.gold, [960, 540], 8); trim(ring, 27.0, 28.0);
    keys(tr(ring, "ADBE Rotate Z"), [[27.0, -90], [29.0, 0]]); span(ring, 27.0, DUR);
    var a = txt("그래서", 110, C.white, [960, 390]); slam(a, 25.5); span(a, 25.5, DUR);
    var b = txt("하늘은 파랗게 보여요!", 150, C.white, [960, 590]); slam(b, 26.0, 300); pulse(b, 26.5, 28.5, 6); span(b, 26.0, DUR);
  }

  try {
    app.newProject();
    app.beginUndoGroup("09 sky motion graphics");
    comp = app.project.items.addComp("09 SKY / MOTION GRAPHICS", W, H, 1, DUR, FPS);
    scene1(); scene2(); scene3(); scene4(); scene5(); scene6(); scene7();
    var music = app.project.importFile(new ImportOptions(new File(musicPath)));
    comp.layers.add(music).outPoint = DUR;
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
