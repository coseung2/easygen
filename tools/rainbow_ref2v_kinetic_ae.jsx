(function () {
  var root="F:/modal-gui/series/08-rainbow";
  var project=root+"/out/rainbow-ref2v-kinetic-v2.aep";
  var output=root+"/out/rainbow-ref2v-kinetic-v2.avi";
  var log=root+"/out/rainbow-ref2v-kinetic-v2.log";
  var W=1920,H=1080,FPS=24,SHOT=5;
  var ivory=[0.97,0.94,0.87],gold=[0.73,0.59,0.33],ink=[0.06,0.06,0.06];
  // Each word is placed to answer a visual action, rather than making a
  // uniform lower-third sentence. Time values are local to the 5s shot.
  var beats=[
    [
      ["무지개는",1160,370,86,ivory,0.25,0.62],
      ["반원일까?",1160,535,142,gold,1.55,1.92]
    ],
    [
      ["햇빛",160,770,112,ink,0.40,0.75],
      ["+",490,765,106,gold,1.25,1.55],
      ["물방울",590,770,112,ink,2.08,2.43]
    ],
    [
      ["땅이",190,200,86,ivory,0.28,0.62],
      ["아래쪽을",190,315,111,gold,1.35,1.68],
      ["가려요",190,430,90,ivory,2.43,2.76]
    ],
    [
      ["높은 곳에선",130,175,79,ink,0.37,0.70],
      ["원",235,325,158,gold,1.52,1.83],
      ["이 보여요",390,320,74,ink,1.93,2.25]
    ],
    [
      ["보는 사람을",150,190,73,ink,0.28,0.62],
      ["중심으로",150,305,109,gold,1.42,1.78],
      ["생겨요",150,420,89,ink,2.32,2.66]
    ],
    [
      ["무지개는 원!",960,580,128,ivory,0.58,0.92],
      ["땅에서는 일부만 보일 뿐",960,695,55,gold,2.05,2.37]
    ]
  ];
  function note(s){var f=new File(log);f.open("a");f.writeln(new Date().toString()+" "+s);f.close();}
  function type(comp,str,x,y,size,color,begin,end,center){
    var l=comp.layers.addText(str),sp=l.property("Source Text"),d=sp.value;
    d.font="BMJUA";d.fontSize=size;d.fillColor=color;d.applyFill=true;
    d.applyStroke=true;d.strokeColor=color===ink?ivory:ink;d.strokeWidth=1.6;
    d.justification=center?ParagraphJustification.CENTER_JUSTIFY:ParagraphJustification.LEFT_JUSTIFY;sp.setValue(d);l.name="Kinetic Type / "+str;
    var t=l.property("ADBE Transform Group"),p=t.property("ADBE Position"),o=t.property("ADBE Opacity"),s=t.property("ADBE Scale");
    p.setValueAtTime(0,[x,y+65]);p.setValueAtTime(begin,[x,y+65]);p.setValueAtTime(end,[x,y]);
    o.setValueAtTime(0,0);o.setValueAtTime(begin,0);o.setValueAtTime(end,100);
    s.setValueAtTime(0,[65,65]);s.setValueAtTime(begin,[65,65]);s.setValueAtTime(end,[114,114]);s.setValueAtTime(end+0.17,[100,100]);
  }
  try{
    app.newProject();app.beginUndoGroup("Rainbow Ref2V kinetic master");
    var master=app.project.items.addComp("08 RAINBOW / REF2V KINETIC",W,H,1,30,FPS);
    for(var i=0;i<6;i++){
      var f=new File(root+"/clips-ref2v/c"+(i+1)+"-ref2v.mp4");if(!f.exists)throw new Error("Missing "+f.fsName);
      var footage=app.project.importFile(new ImportOptions(f)),comp=app.project.items.addComp("SHOT "+(i+1),W,H,1,SHOT,FPS);
      var v=comp.layers.add(footage),cover=Math.max(W/footage.width,H/footage.height)*100;
      v.property("ADBE Transform Group").property("ADBE Scale").setValue([cover,cover]);v.outPoint=SHOT;
      for(var j=0;j<beats[i].length;j++){
        var beat=beats[i][j];
        type(comp,beat[0],beat[1],beat[2],beat[3],beat[4],beat[5],beat[6],i===5);
      }
      var sl=master.layers.add(comp);sl.startTime=i*SHOT;sl.inPoint=i*SHOT;sl.outPoint=(i+1)*SHOT;
    }
    var musicFile=new File(root+"/music/es-bed-02.wav");if(!musicFile.exists)throw new Error("Missing music WAV");
    var mi=app.project.importFile(new ImportOptions(musicFile)),ml=master.layers.add(mi);ml.outPoint=30;
    var q=app.project.renderQueue.items.add(master);q.outputModule(1).file=new File(output);
    app.project.save(new File(project));app.endUndoGroup();note("SAVED "+project+" layers="+master.numLayers);app.quit();
  }catch(e){note("ERROR "+e.toString()+" line="+e.line);try{app.endUndoGroup();}catch(ignore){}app.quit();}
})();
