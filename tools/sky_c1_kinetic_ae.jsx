(function () {
  var root = "F:/modal-gui/series/09-violet-sky";
  var clipPath = root + "/clips-plate/c1-plate-ref2v.mp4";
  var musicPath = root + "/ae/c1-music.wav";
  var projectPath = root + "/ae/c1-kinetic-v3.aep";
  var renderPath = root + "/ae/c1-kinetic-v3.avi";
  var logPath = root + "/ae/c1-kinetic-v3.log";
  var W = 1920, H = 1080, D = 5, FPS = 24;
  var ink = [0.07, 0.09, 0.15], violet = [0.38, 0.22, 0.69];

  function note(s) {
    var f = new File(logPath); f.open("a"); f.writeln(new Date().toString() + " " + s); f.close();
  }
  function textLayer(comp, value, position, size, color, start, end) {
    var layer = comp.layers.addText(value);
    var source = layer.property("Source Text"), doc = source.value;
    doc.font = "BMJUA"; doc.fontSize = size; doc.fillColor = color;
    doc.applyFill = true; doc.applyStroke = false;
    doc.justification = ParagraphJustification.CENTER_JUSTIFY;
    source.setValue(doc);
    layer.name = "Kinetic Type / " + value.replace(/\n/g, " ");
    var transform = layer.property("ADBE Transform Group");
    var pos = transform.property("ADBE Position");
    var opacity = transform.property("ADBE Opacity");
    var scale = transform.property("ADBE Scale");
    pos.setValueAtTime(0, [position[0], position[1] + 64]);
    pos.setValueAtTime(start, [position[0], position[1] + 64]);
    pos.setValueAtTime(end, position);
    scale.setValueAtTime(0, [72, 72]);
    scale.setValueAtTime(start, [72, 72]);
    scale.setValueAtTime(end, [108, 108]);
    scale.setValueAtTime(end + 0.16, [100, 100]);
    opacity.setValueAtTime(0, 0); opacity.setValueAtTime(start, 0); opacity.setValueAtTime(end, 100);
    return layer;
  }

  try {
    var clip = new File(clipPath);
    if (!clip.exists) throw new Error("Missing MiniMax clip: " + clipPath);
    app.newProject();
    app.beginUndoGroup("Sky clip 01 kinetic typography");
    var comp = app.project.items.addComp("09 SKY / C01 / KINETIC TYPE", W, H, 1, D, FPS);
    var footage = app.project.importFile(new ImportOptions(clip));
    var video = comp.layers.add(footage);
    video.startTime = 0; video.inPoint = 0; video.outPoint = D;
    // Cover the 16:9 master with the 1344x768 MiniMax clip. The slight
    // aspect-ratio difference crops a few pixels vertically, without bars.
    var cover = Math.max(W / footage.width, H / footage.height) * 100;
    video.property("ADBE Transform Group").property("ADBE Scale").setValue([cover, cover]);
    var music = new File(musicPath);
    if (!music.exists) throw new Error("Missing audio: " + musicPath);
    var musicItem = app.project.importFile(new ImportOptions(music));
    var musicLayer = comp.layers.add(musicItem);
    musicLayer.startTime = 0; musicLayer.inPoint = 0; musicLayer.outPoint = D;
    // The reference's visual journey drives the beat. These words land in
    // the negative space to the right of the prism, never as bottom captions.
    textLayer(comp, "하늘은 사실", [1390, 410], 84, ink, 1.05, 1.32);
    textLayer(comp, "보라색이어야 해요", [1390, 545], 93, violet, 1.48, 1.78);
    var queue = app.project.renderQueue.items.add(comp);
    queue.outputModule(1).file = new File(renderPath);
    app.project.save(new File(projectPath));
    app.endUndoGroup();
    note("SAVED " + projectPath + " layers=" + comp.numLayers);
    app.quit();
  } catch (e) {
    note("ERROR " + e.toString() + " line=" + e.line);
    try { app.endUndoGroup(); } catch (ignored) {}
    app.quit();
  }
})();
