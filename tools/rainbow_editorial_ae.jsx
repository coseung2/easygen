/* Native 30-second editorial rainbow pilot. Run in an empty AE 2021 instance. */
(function () {
  var dataRoot = $.getenv("MODAL_GUI_DATA_ROOT") || new File($.fileName).parent.parent.fsName + "/data";
  var root = dataRoot + "/series/08-rainbow";
  var projectFile = new File(root + "/out/rainbow-editorial-v3.aep");
  var logFile = new File(root + "/out/rainbow-editorial-v3.log");
  var renderFile = new File(root + "/out/rainbow-editorial-v3.avi");
  var W = 1920, H = 1080, FPS = 24;
  var ink = [0.063, 0.063, 0.063], ivory = [0.941, 0.922, 0.867];
  var gold = [0.718, 0.596, 0.329];
  var spectrum = [
    [0.86, 0.16, 0.14], [0.97, 0.45, 0.12], [0.96, 0.76, 0.18],
    [0.31, 0.69, 0.34], [0.19, 0.55, 0.81], [0.28, 0.31, 0.70], [0.55, 0.31, 0.68]
  ];
  function log(s) {
    logFile.open("a"); logFile.writeln(new Date().toString() + " " + s); logFile.close();
  }
  function keys(p, pairs) {
    for (var i = 0; i < pairs.length; i++) p.setValueAtTime(pairs[i][0], pairs[i][1]);
  }
  function bg(comp, color) {
    var layer = comp.layers.addSolid(color, "Background", W, H, 1, 5);
    layer.moveToEnd(); return layer;
  }
  function group(comp, name) {
    var l = comp.layers.addShape(); l.name = name;
    return [l, l.property("ADBE Root Vectors Group")];
  }
  function stroke(g, color, width, opacity) {
    var s = g.addProperty("ADBE Vector Graphic - Stroke");
    s.property("ADBE Vector Stroke Color").setValue(color);
    s.property("ADBE Vector Stroke Width").setValue(width);
    if (opacity !== undefined) s.property("ADBE Vector Stroke Opacity").setValue(opacity);
  }
  function fill(g, color) {
    g.addProperty("ADBE Vector Graphic - Fill").property("ADBE Vector Fill Color").setValue(color);
  }
  function circle(comp, name, x, y, diameter, color, width, filled) {
    var a = group(comp, name), g = a[1];
    g.addProperty("ADBE Vector Shape - Ellipse").property("ADBE Vector Ellipse Size").setValue([diameter, diameter]);
    if (filled) fill(g, color); else stroke(g, color, width);
    a[0].property("ADBE Transform Group").property("ADBE Position").setValue([x, y]);
    return a[0];
  }
  function line(comp, name, points, color, width) {
    var a = group(comp, name), g = a[1], sh = new Shape();
    sh.vertices = points; sh.inTangents = []; sh.outTangents = []; sh.closed = false;
    for (var i = 0; i < points.length; i++) {
      sh.inTangents.push([0, 0]); sh.outTangents.push([0, 0]);
    }
    g.addProperty("ADBE Vector Shape - Group").property("ADBE Vector Shape").setValue(sh);
    stroke(g, color, width);
    a[0].property("ADBE Transform Group").property("ADBE Position").setValue([0, 0]);
    return a[0];
  }
  function reveal(layer, start, end) {
    var g = layer.property("ADBE Root Vectors Group");
    var trim = g.addProperty("ADBE Vector Filter - Trim");
    keys(trim.property("ADBE Vector Trim End"), [[start, 0], [end, 100]]);
  }
  function fade(layer, start, end) {
    keys(layer.property("ADBE Transform Group").property("ADBE Opacity"), [[0, 0], [start, 0], [end, 100]]);
  }
  function text(comp, value, x, y, size, color, time, align) {
    var l = comp.layers.addText(value), prop = l.property("Source Text"), d = prop.value;
    d.font = "MalgunGothic-Bold"; d.fontSize = size; d.fillColor = color;
    d.applyFill = true; d.applyStroke = false;
    d.justification = align === "center" ? ParagraphJustification.CENTER_JUSTIFY : ParagraphJustification.LEFT_JUSTIFY;
    prop.setValue(d);
    l.name = "Type / " + value;
    l.property("ADBE Transform Group").property("ADBE Position").setValue([x, y]);
    fade(l, time, time + 0.35);
    return l;
  }
  function rules(comp, dark) {
    var c = dark ? ivory : ink;
    line(comp, "Top rule", [[80, 78], [1840, 78]], c, 2);
    line(comp, "Bottom rule", [[80, 1002], [1840, 1002]], c, 2);
    circle(comp, "Registration / left", 80, 78, 9, gold, 2, true);
    circle(comp, "Registration / right", 1840, 1002, 9, gold, 2, true);
  }
  function rainbow(comp, x, y, diameter, width, start, end) {
    for (var i = 0; i < 7; i++) {
      var arc = circle(comp, "Spectrum / " + (i + 1), x, y, diameter - i * (width + 2), spectrum[i], width, false);
      reveal(arc, start + i * 0.055, end + i * 0.055);
    }
  }
  function scene(name, dark) {
    var c = app.project.items.addComp(name, W, H, 1, 5, FPS);
    bg(c, dark ? ink : ivory); rules(c, dark); return c;
  }
  function marker(comp, x, y, color) {
    circle(comp, "Measurement point", x, y, 16, color, 2, true);
  }
  var existing = app.project.file || app.project.numItems > 0;
  if (existing) { log("ABORT: nonempty After Effects session"); return; }
  try {
    app.beginUndoGroup("Rainbow editorial pilot");
    var c1 = scene("01 / The arc", true);
    rainbow(c1, 460, 1020, 1550, 19, 0.25, 2.4);
    circle(c1, "Construction circle", 460, 1020, 1740, ivory, 2, false);
    text(c1, "무지개는 반원일까?", 1130, 460, 83, ivory, 0.7);
    text(c1, "보이는 모양과 진짜 모양", 1130, 545, 35, gold, 1.45);

    var c2 = scene("02 / Light and water", false);
    circle(c2, "Sun", 280, 382, 96, gold, 2, true);
    circle(c2, "Droplet outline", 1050, 520, 380, ink, 4, false);
    circle(c2, "Droplet glint", 995, 455, 48, ivory, 2, true);
    for (var j = 0; j < 4; j++) {
      var ray = line(c2, "Incident ray " + j, [[340, 340 + j * 43], [860, 340 + j * 43]], gold, 5);
      reveal(ray, 0.25 + j * 0.15, 1.6 + j * 0.15);
    }
    for (j = 0; j < 7; j++) {
      var out = line(c2, "Refracted ray " + j,
        [[1160, 510], [1670, 330 + j * 51]], spectrum[j], 8);
      reveal(out, 1.85 + j * 0.06, 3.15 + j * 0.06);
    }
    text(c2, "햇빛 + 물방울", 180, 856, 82, ink, 0.55);

    var c3 = scene("03 / Horizon masks the circle", true);
    rainbow(c3, 980, 690, 980, 13, 0.4, 2.35);
    line(c3, "Horizon", [[130, 685], [1790, 685]], ivory, 3);
    circle(c3, "Observer", 980, 785, 36, ivory, 2, true);
    line(c3, "Observer axis", [[980, 780], [980, 900]], ivory, 7);
    var mask = c3.layers.addSolid(ink, "Ground hides lower arc", W, 400, 1, 5);
    mask.property("ADBE Transform Group").property("ADBE Position").setValue([960, 885]);
    fade(mask, 1.95, 2.65);
    text(c3, "땅이 아래쪽을 가려요", 110, 170, 65, ivory, 0.75);

    var c4 = scene("04 / Circle from above", false);
    rainbow(c4, 955, 540, 820, 12, 0.3, 2.7);
    circle(c4, "Outer construction circle", 955, 540, 970, ink, 2, false);
    marker(c4, 955, 540, gold);
    line(c4, "Sight line", [[955, 540], [955, 170]], gold, 3);
    text(c4, "높은 곳에선", 105, 200, 56, ink, 0.7);
    text(c4, "원이 보여요", 105, 272, 56, ink, 1.05);

    var c5 = scene("05 / Viewing geometry", false);
    marker(c5, 250, 540, ink);
    circle(c5, "Raindrop", 1270, 540, 350, ink, 4, false);
    marker(c5, 1245, 538, gold);
    var upper = line(c5, "Upper sight line", [[250, 540], [1260, 310]], ink, 4);
    var lower = line(c5, "Lower sight line", [[250, 540], [1260, 770]], ink, 4);
    reveal(upper, 0.6, 2.2); reveal(lower, 0.85, 2.45);
    for (j = 0; j < 7; j++) {
      var fan = line(c5, "Spectrum fan " + j, [[1265, 540], [1780, 350 + j * 53]], spectrum[j], 6);
      reveal(fan, 2.0 + j * 0.04, 3.0 + j * 0.04);
    }
    text(c5, "무지개는 보는 사람을", 170, 190, 60, ink, 0.8);
    text(c5, "중심으로 생겨요", 170, 270, 60, ink, 1.3);

    var c6 = scene("06 / Complete circle", true);
    rainbow(c6, 960, 540, 820, 12, 0.25, 2.55);
    circle(c6, "Inner orbit", 960, 540, 480, gold, 2, false);
    marker(c6, 960, 540, gold);
    line(c6, "Vertical axis", [[960, 96], [960, 984]], ivory, 2);
    text(c6, "무지개는 원!", 960, 520, 93, ivory, 2.55, "center");
    text(c6, "땅에서는 일부만 보일 뿐", 960, 620, 39, gold, 2.9, "center");

    var master = app.project.items.addComp("RAINBOW / 30s MASTER", W, H, 1, 30, FPS);
    var scenes = [c1, c2, c3, c4, c5, c6];
    for (j = 0; j < scenes.length; j++) {
      var segment = master.layers.add(scenes[j]);
      segment.startTime = j * 5; segment.inPoint = j * 5; segment.outPoint = (j + 1) * 5;
    }
    // AE 2021 cannot import the YuE2 FLAC on this host. Mix it into the
    // rendered video with ffmpeg after validating the native composition.
    var queued = app.project.renderQueue.items.add(master);
    queued.outputModule(1).file = renderFile;
    app.project.save(projectFile);
    app.endUndoGroup();
    log("SAVED " + projectFile.fsName + " master layers=" + master.numLayers);
    app.quit();
  } catch (e) {
    log("ERROR " + e.toString() + " line=" + e.line);
    try { app.endUndoGroup(); } catch (ignored) {}
    app.quit();
  }
})();
