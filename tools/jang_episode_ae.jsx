(function () {
  var root="F:/modal-gui/series/01-jang-yeong-sil";
  var project=root+"/ae/01-jang-yeong-sil-master.aep";
  var output=root+"/ae/01-jang-yeong-sil-master.avi";
  var log=root+"/ae/01-jang-yeong-sil-master.log";
  var W=1920,H=1080,FPS=24,SHOT=5;
  var ivory=[0.96,0.91,0.78],gold=[0.89,0.68,0.30];
  var order=[2,1,3,4,5,6];
  var copy=[
    ["동래 관노 장영실","재주를 인정받다"],
    ["물의 흐름으로","시간을 재다"],
    ["하늘의 움직임도","기구로 살피다"],
    ["세종 시대의","과학기술자"],
    ["물시계와 천문기구","함께 만든 기술"],
    ["장영실","조선의 발명을 이끌다"]
  ];
  var spots=[[1250,380],[1250,760],[1240,790],[1210,770],[960,800],[960,790]];
  function note(s){var f=new File(log);f.open("a");f.writeln(new Date().toString()+" "+s);f.close();}
  function type(comp,value,x,y,size,color,begin,finish,center){
    var l=comp.layers.addText(value),sp=l.property("Source Text"),d=sp.value;
    d.font="BMJUA";d.fontSize=size;d.fillColor=color;d.applyFill=true;d.applyStroke=true;d.strokeColor=[0.03,0.03,0.03];d.strokeWidth=2;
    d.justification=center?ParagraphJustification.CENTER_JUSTIFY:ParagraphJustification.LEFT_JUSTIFY;sp.setValue(d);
    l.name="Kinetic Type / "+value;
    var t=l.property("ADBE Transform Group"),p=t.property("ADBE Position"),o=t.property("ADBE Opacity"),s=t.property("ADBE Scale");
    p.setValueAtTime(0,[x,y+50]);p.setValueAtTime(begin,[x,y+50]);p.setValueAtTime(finish,[x,y]);
    o.setValueAtTime(0,0);o.setValueAtTime(begin,0);o.setValueAtTime(finish,100);
    s.setValueAtTime(0,[70,70]);s.setValueAtTime(begin,[70,70]);s.setValueAtTime(finish,[106,106]);s.setValueAtTime(finish+0.14,[100,100]);
  }
  try {
    app.newProject();app.beginUndoGroup("Jang Yeong-sil kinetic master");
    var master=app.project.items.addComp("01 JANG YEONG SIL / MASTER",W,H,1,30,FPS);
    for(var i=0;i<6;i++){
      var file=new File(root+"/clips/c"+order[i]+".mp4");if(!file.exists)throw new Error("Missing "+file.fsName);
      var footage=app.project.importFile(new ImportOptions(file));
      var comp=app.project.items.addComp("SHOT "+(i+1),W,H,1,SHOT,FPS);
      var v=comp.layers.add(footage);
      var cover=Math.max(W/footage.width,H/footage.height)*100;
      v.property("ADBE Transform Group").property("ADBE Scale").setValue([cover,cover]);v.outPoint=SHOT;
      var pos=spots[i],center=i>=4;
      type(comp,copy[i][0],pos[0],pos[1],i===5?96:72,ivory,0.4,0.75,center);
      type(comp,copy[i][1],pos[0],pos[1]+105,i===5?84:82,gold,0.8,1.2,center);
      var sl=master.layers.add(comp);sl.startTime=i*SHOT;sl.inPoint=i*SHOT;sl.outPoint=(i+1)*SHOT;
    }
    var musicFile=new File(root+"/music-30s.wav");if(!musicFile.exists)throw new Error("Missing music");
    var music=app.project.importFile(new ImportOptions(musicFile)),ml=master.layers.add(music);ml.outPoint=30;
    var q=app.project.renderQueue.items.add(master);q.outputModule(1).file=new File(output);
    app.project.save(new File(project));app.endUndoGroup();note("SAVED "+project+" layers="+master.numLayers);app.quit();
  }catch(e){note("ERROR "+e.toString()+" line="+e.line);try{app.endUndoGroup();}catch(ignore){}app.quit();}
})();
