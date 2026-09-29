(function () {
var dataRoot = $.getenv("MODAL_GUI_DATA_ROOT") || new File($.fileName).parent.parent.fsName + "/data";
var root = dataRoot + "/series/09-violet-sky";
  var projectPath = root + "/ae/09-violet-sky-kinetic-master.aep";
  var renderPath = root + "/ae/09-violet-sky-kinetic-master.avi";
  var logPath = root + "/ae/09-violet-sky-kinetic-master.log";
  var W = 1920, H = 1080, FPS = 24, SHOT = 5, TOTAL = 30;
  var ivory = [0.97, 0.94, 0.86], violet = [0.38, 0.22, 0.69], ink = [0.06, 0.08, 0.13];
  var clips = [
    root + "/clips-plate/c1-plate-ref2v.mp4",
    root + "/clips/c2.mp4", root + "/clips/c3.mp4", root + "/clips/c4.mp4",
    root + "/clips/c5.mp4", root + "/clips/c6.mp4"
  ];
  var texts = [
    ["하늘은 왜", "보라색이 아닐까?"],
    ["햇빛이", "대기로 들어와요"],
    ["햇빛에는 여러 색", "보랏빛은 상대적으로 적어요"],
    ["보랏빛과 파란빛은", "대기에서 흩어져요"],
    ["우리 눈은", "파랑에 더 민감해요"],
    ["그래서 하늘은", "파랗게 보여요"]
  ];
  var positions = [[1120,400],[150,220],[150,790],[1100,170],[110,245],[960,780]];
  var size1 = [72,66,64,60,64,86], size2 = [78,72,64,70,74,104];
  var colors = [[ink,violet],[ivory,ivory],[ink,violet],[ivory,ivory],[ink,violet],[ivory,ivory]];
  function note(s) { var f=new File(logPath); f.open("a"); f.writeln(new Date().toString()+" "+s); f.close(); }
  function addType(comp, value, x, y, size, color, start, end, holdEnd, align) {
    var layer=comp.layers.addText(value), src=layer.property("Source Text"), doc=src.value;
    doc.font="BMJUA"; doc.fontSize=size; doc.fillColor=color; doc.applyFill=true;
    doc.applyStroke=true; doc.strokeColor=[0.02,0.02,0.02]; doc.strokeWidth=2.5;
    doc.justification=align === "center" ? ParagraphJustification.CENTER_JUSTIFY : ParagraphJustification.LEFT_JUSTIFY; src.setValue(doc);
    layer.name="Kinetic Type / "+value;
    var tr=layer.property("ADBE Transform Group"), pos=tr.property("ADBE Position"), op=tr.property("ADBE Opacity"), sc=tr.property("ADBE Scale");
    pos.setValueAtTime(0,[x,y+65]); pos.setValueAtTime(start,[x,y+65]); pos.setValueAtTime(end,[x,y]); pos.setValueAtTime(holdEnd,[x,y]);
    sc.setValueAtTime(0,[72,72]); sc.setValueAtTime(start,[72,72]); sc.setValueAtTime(end,[108,108]); sc.setValueAtTime(end+0.12,[100,100]); sc.setValueAtTime(holdEnd,[100,100]);
    op.setValueAtTime(0,0); op.setValueAtTime(start,0); op.setValueAtTime(end,100); op.setValueAtTime(holdEnd,100);
  }
  function addShot(index, footageItems) {
    var comp=app.project.items.addComp("SHOT "+(index+1),W,H,1,SHOT,FPS);
    var footage=footageItems[index], layer=comp.layers.add(footage);
    var cover=Math.max(W/footage.width,H/footage.height)*100;
    layer.property("ADBE Transform Group").property("ADBE Scale").setValue([cover,cover]); layer.inPoint=0; layer.outPoint=SHOT;
    var p=positions[index], c=colors[index];
    addType(comp,texts[index][0],p[0],p[1],size1[index],c[0],0.45,0.78,3.9,index===5?"center":"left");
    addType(comp,texts[index][1],p[0],p[1]+105,size2[index],c[1],0.78,1.18,4.25,index===5?"center":"left");
    return comp;
  }
  try {
    app.newProject(); app.beginUndoGroup("09 Violet Sky kinetic typography master");
    var footageItems=[];
    for(var i=0;i<clips.length;i++){var f=new File(clips[i]); if(!f.exists) throw new Error("Missing clip "+clips[i]); footageItems.push(app.project.importFile(new ImportOptions(f)));}
    var shots=[]; for(i=0;i<6;i++) shots.push(addShot(i,footageItems));
    var master=app.project.items.addComp("09 VIOLET SKY / MASTER",W,H,1,TOTAL,FPS);
    for(i=0;i<6;i++){var sl=master.layers.add(shots[i]);sl.startTime=i*SHOT;sl.inPoint=i*SHOT;sl.outPoint=(i+1)*SHOT;}
    var musicFile=new File(root+"/ae/master-music-30s.wav");
    if(musicFile.exists){var mi=app.project.importFile(new ImportOptions(musicFile));var ml=master.layers.add(mi);ml.outPoint=TOTAL;}
    var q=app.project.renderQueue.items.add(master);q.outputModule(1).file=new File(renderPath);
    app.project.save(new File(projectPath)); app.endUndoGroup(); note("SAVED "+projectPath+" master_layers="+master.numLayers); app.quit();
  } catch(e){note("ERROR "+e.toString()+" line="+e.line);try{app.endUndoGroup();}catch(ignored){}app.quit();}
})();
