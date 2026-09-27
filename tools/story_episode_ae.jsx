(function () {
  var slug="11-tardigrade", number="11", titleText="물곰은 우주에서도 산다";
  var root="F:/modal-gui/series/"+slug, outRoot=root+"/ae";
  var projectPath=outRoot+"/"+number+"-kinetic-master.aep", renderPath=outRoot+"/"+number+"-kinetic-master.avi", logPath=outRoot+"/"+number+"-kinetic-master.log";
  var clips=[root+"/clips/c1.mp4",root+"/clips/c2.mp4",root+"/clips/c3.mp4",root+"/clips/c4.mp4",root+"/clips/c5.mp4"];
  var titlePath=root+"/title/title.mp4", endPath=root+"/title/title.mp4", musicPath=outRoot+"/music-31s.wav";
  var captions=["이름은 곰이지만 곰이 아니에요 물곰이에요","다리가 여덟 개인 통통한 몸으로 물속을 기어다녀요","물이 없으면 몸을 말려서 몇 년이고 잠들어 있어요","우주 실험에서도 살아남았어요 진공과 방사선 속에서도요","물 한 방울이면 다시 깨어나요 물곰은 진짜 슈퍼히어로예요"];
  var W=1920,H=1080,FPS=24;
  function note(s){var f=new File(logPath);f.open("a");f.writeln(new Date().toString()+" "+s);f.close();}
  function addType(comp,value,x,y,size,start,end){var l=comp.layers.addText(value),s=l.property("Source Text"),d=s.value;d.font="BMJUA";d.fontSize=size;d.fillColor=[1,0.82,0.32];d.applyFill=true;d.applyStroke=true;d.strokeColor=[0.03,0.03,0.03];d.strokeWidth=2;d.justification=ParagraphJustification.CENTER_JUSTIFY;s.setValue(d);l.name="Kinetic Type / "+value;var t=l.property("ADBE Transform Group"),p=t.property("ADBE Position"),o=t.property("ADBE Opacity"),sc=t.property("ADBE Scale");p.setValueAtTime(start,[x,y+50]);p.setValueAtTime(end,[x,y]);o.setValueAtTime(start,0);o.setValueAtTime(end,100);sc.setValueAtTime(start,[80,80]);sc.setValueAtTime(end,[106,106]);sc.setValueAtTime(end+0.15,[100,100]);}
  try{
    app.newProject();app.beginUndoGroup("Story episode kinetic type");
    var master=app.project.items.addComp(number+" "+titleText+" / MASTER",W,H,1,31,FPS);
    var title=app.project.importFile(new ImportOptions(new File(titlePath))),tl=master.layers.add(title);tl.outPoint=3;
    for(var i=0;i<5;i++){var f=app.project.importFile(new ImportOptions(new File(clips[i]))),v=master.layers.add(f);v.startTime=3+i*5;v.inPoint=3+i*5;v.outPoint=8+i*5;var x=960,y=875;addType(master,captions[i],x,y,58,3+i*5+0.45,3+i*5+0.9);}
    var end=app.project.importFile(new ImportOptions(new File(endPath))),el=master.layers.add(end);el.startTime=28;el.inPoint=28;el.outPoint=31;
    var music=app.project.importFile(new ImportOptions(new File(musicPath))),ml=master.layers.add(music);ml.outPoint=31;
    var q=app.project.renderQueue.items.add(master);q.outputModule(1).file=new File(renderPath);app.project.save(new File(projectPath));app.endUndoGroup();note("SAVED "+projectPath+" layers="+master.numLayers);app.quit();
  }catch(e){note("ERROR "+e.toString()+" line="+e.line);try{app.endUndoGroup();}catch(ignore){}app.quit();}
})();
