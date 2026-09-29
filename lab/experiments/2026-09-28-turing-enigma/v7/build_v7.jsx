// ENIGMA V5 — one master comp; the thread survives every scene and changes shape.
// Design: DESIGN.md. Run: AfterFX.exe -r build_v5.jsx
(function(){
var DATA_ROOT=$.getenv('MODAL_GUI_DATA_ROOT');
if(!DATA_ROOT) throw new Error('Set MODAL_GUI_DATA_ROOT before running this build');
var R=DATA_ROOT+'/lab/2026-09-28-turing-enigma/v7';
var W=1080,H=1920,FPS=30,DUR=72.5,CX=540;
function hex(h){return [parseInt(h.substr(1,2),16)/255,parseInt(h.substr(3,2),16)/255,parseInt(h.substr(5,2),16)/255];}
var INK=hex('#0B0E0F'),IVORY=hex('#EFEDE3'),GRAY=hex('#7A7F7B'),DIM=hex('#2B3031'),LIME=hex('#B8FF1F'),RED=hex('#E0472F');
var KR='Pretendard-Bold',KRM='Pretendard-Medium',LAT='Bahnschrift';
var LOG=[];function log(s){LOG.push(s);}
var M;

// ---------- primitives ----------
function tr(l,n){return l.property('ADBE Transform Group').property(n);}
function easeAll(p,inf){for(var k=1;k<=p.numKeys;k++){var e=new KeyframeEase(0,inf);try{p.setTemporalEaseAtKey(k,[e],[e]);}catch(a){try{p.setTemporalEaseAtKey(k,[e,e],[e,e]);}catch(b){try{p.setTemporalEaseAtKey(k,[e,e,e],[e,e,e]);}catch(c){}}}}}
function holdAll(p){for(var k=1;k<=p.numKeys;k++)p.setInterpolationTypeAtKey(k,KeyframeInterpolationType.HOLD,KeyframeInterpolationType.HOLD);}
// K(prop, [[t,v],...], mode) mode: number = ease influence, 'hold', 'linear'
function K(p,a,mode){for(var i=0;i<a.length;i++)p.setValueAtTime(a[i][0],a[i][1]);if(mode==='hold')holdAll(p);else if(mode!=='linear')easeAll(p,mode===undefined?72:mode);return p;}
function span(l,a,b){l.inPoint=Math.max(0,a);l.outPoint=Math.min(DUR,b);return l;}
function O(l,a,mode){return K(tr(l,'ADBE Opacity'),a,mode===undefined?60:mode);}
// fade in at a over d, fade out ending at b over d2
function fade(l,a,b,d,d2){d=d||.3;d2=d2===undefined?d:d2;var k=[[a,0],[a+d,100]];if(b<DUR)k.push([b-d2,100],[b,0]);O(l,k);span(l,a,b);return l;}

function shapeLayer(name,x,y,a,b){var l=M.layers.addShape();l.name=name;tr(l,'ADBE Anchor Point').setValue([0,0]);tr(l,'ADBE Position').setValue([x,y]);l.motionBlur=true;span(l,a,b);return l;}
function grp(l,name){var g=l.property('ADBE Root Vectors Group').addProperty('ADBE Vector Group');g.name=name;return g;}
function vec(g){return g.property('ADBE Vectors Group');}
function mkShape(pts,closed,inT,outT){var s=new Shape(),z=[];for(var i=0;i<pts.length;i++)z.push([0,0]);s.vertices=pts;s.inTangents=inT||z;s.outTangents=outT||z;s.closed=!!closed;return s;}
function addPath(g,name,pts,closed,inT,outT){var p=vec(g).addProperty('ADBE Vector Shape - Group');p.name=name;p.property('ADBE Vector Shape').setValue(mkShape(pts,closed,inT,outT));return p;}
function pathProp(l,gname,pname){return l.property('ADBE Root Vectors Group').property(gname).property('ADBE Vectors Group').property(pname).property('ADBE Vector Shape');}
function addEllipse(g,r){var e=vec(g).addProperty('ADBE Vector Shape - Ellipse');e.property('ADBE Vector Ellipse Size').setValue([r*2,r*2]);return e;}
function addTrim(g){var t=vec(g).addProperty('ADBE Vector Filter - Trim');t.name='trim';return t;}
function trimProp(l,gname,which){return l.property('ADBE Root Vectors Group').property(gname).property('ADBE Vectors Group').property('trim').property(which==='start'?'ADBE Vector Trim Start':'ADBE Vector Trim End');}
function addStroke(g,col,w,dash){var s=vec(g).addProperty('ADBE Vector Graphic - Stroke');s.name='stroke';s.property('ADBE Vector Stroke Color').setValue(col);s.property('ADBE Vector Stroke Width').setValue(w);s.property('ADBE Vector Stroke Line Cap').setValue(2);s.property('ADBE Vector Stroke Line Join').setValue(2);
  if(dash){var d=s.property('ADBE Vector Stroke Dashes');d.addProperty('ADBE Vector Stroke Dash 1').setValue(dash[0]);s=g.property('ADBE Vectors Group').property('stroke');s.property('ADBE Vector Stroke Dashes').addProperty('ADBE Vector Stroke Gap 1').setValue(dash[1]);}
  return s;}
function addFill(g,col,op){var f=vec(g).addProperty('ADBE Vector Graphic - Fill');f.name='fill';f.property('ADBE Vector Fill Color').setValue(col);if(op!==undefined)f.property('ADBE Vector Fill Opacity').setValue(op);return f;}
function grpRot(l,gname){return l.property('ADBE Root Vectors Group').property(gname).property('ADBE Vector Transform Group').property('ADBE Vector Rotation');}

// simple stroked polyline/line layer in its own local coords
function lineLayer(name,x,y,pts,col,w,a,b,opt){opt=opt||{};var l=shapeLayer(name,x,y,a,b),g=grp(l,'g');addPath(g,'p',pts,!!opt.closed,opt.inT,opt.outT);if(opt.trim)addTrim(g);addStroke(g,col,w,opt.dash);return l;}
function ringLayer(name,x,y,r,col,w,a,b,opt){opt=opt||{};var l=shapeLayer(name,x,y,a,b),g=grp(l,'g');addEllipse(g,r);if(opt.trim)addTrim(g);if(opt.fillOp!==undefined)addFill(g,col,opt.fillOp);addStroke(g,col,w,opt.dash);return l;}

// text: anchor x at the justification edge, y at cap-height centre, so rows share a baseline logic
function T(s,x,y,size,col,font,a,b,opt){opt=opt||{};var l=M.layers.addText(s),p=l.property('Source Text'),d=p.value;
  try{d.resetCharStyle();d.resetParagraphStyle();}catch(e){}
  d.font=font;d.fontSize=size;d.fillColor=col;d.applyFill=true;d.applyStroke=false;d.tracking=opt.track||0;
  d.justification=opt.align==='left'?ParagraphJustification.LEFT_JUSTIFY:opt.align==='right'?ParagraphJustification.RIGHT_JUSTIFY:ParagraphJustification.CENTER_JUSTIFY;
  p.setValue(d);
  if(LOG.length<40&&font!==p.value.font)log('FONT MISMATCH want='+font+' got='+p.value.font);
  tr(l,'ADBE Anchor Point').setValue([0,-size*(font===LAT?.35:.37)]);tr(l,'ADBE Position').setValue([x,y]);
  if(opt.align==='left')tr(l,'ADBE Anchor Point').expression='var r=sourceRectAtTime(time,false);[r.left,value[1]];';
  if(opt.align==='right')tr(l,'ADBE Anchor Point').expression='var r=sourceRectAtTime(time,false);[r.left+r.width,value[1]];';
  l.name=opt.name||s;l.motionBlur=true;span(l,a,b);return l;}
function setText(l,t,s){var p=l.property('Source Text'),d=p.value;d.text=s;p.setValueAtTime(t,d);}
function parentAll(arr,par){for(var i=0;i<arr.length;i++)arr[i].parent=par;}
function fadeOutAll(arr,a,b){for(var i=0;i<arr.length;i++){var p=tr(arr[i],'ADBE Opacity');var v=p.numKeys?p.valueAtTime(a,false):p.value;p.setValueAtTime(a,v);p.setValueAtTime(b,0);easeAll(p,60);if(arr[i].outPoint>b)arr[i].outPoint=b;}}

// arc vertices for a circle of radius r (layer-local centre 0,0), degrees, increasing angle
function arc(r,from,to,n){var v=[],it=[],ot=[],step=(to-from)/(n-1),k=4/3*Math.tan(step*Math.PI/180/4)*r;
  for(var i=0;i<n;i++){var f=(from+i*step)*Math.PI/180,c=Math.cos(f),s=Math.sin(f);v.push([r*c,r*s]);ot.push([-s*k,c*k]);it.push([s*k,-c*k]);}
  return {v:v,i:it,o:ot};}
function lerpPts(a,b,n){var v=[];for(var i=0;i<n;i++){var t=i/(n-1);v.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]);}return v;}
function zeros(n){var z=[];for(var i=0;i<n;i++)z.push([0,0]);return z;}
// Catmull-Rom tangents for a smooth open route
function smooth(pts,ten){var n=pts.length,it=[],ot=[];for(var i=0;i<n;i++){var a=pts[Math.max(0,i-1)],b=pts[Math.min(n-1,i+1)];var tx=(b[0]-a[0])*ten,ty=(b[1]-a[1])*ten;if(i===0||i===n-1){tx*=.5;ty*=.5;}ot.push([tx,ty]);it.push([-tx,-ty]);}it[0]=[0,0];ot[n-1]=[0,0];return {i:it,o:ot};}

try{
// reuse the open project when it is empty or ours; never close/new (that raises a modal save dialog)
if(!app.project)app.newProject();
var pf=app.project.file?app.project.file.fsName.split(String.fromCharCode(92)).join('/'):'';
if(app.project.numItems>0){var mine=pf.indexOf('/2026-09-28-turing-enigma/')>=0;
  if(!mine)for(var ii=1;ii<=app.project.numItems;ii++)if(String(app.project.item(ii).name).indexOf('ENIGMA / V')===0)mine=true;
  if(!mine)throw Error('Open project is not an Enigma lab project; refusing to modify '+pf);
  while(app.project.numItems>0)app.project.item(1).remove();}
try{app.project.expressionEngine='javascript-1.0';}catch(x){}
M=app.project.items.addComp('ENIGMA / V7 GRAPHICS',W,H,1,DUR,FPS);
M.motionBlur=true;M.shutterAngle=180;M.motionBlurSamplesPerFrame=16;M.bgColor=INK;
M.layers.addSolid(INK,'BACKGROUND / INK',W,H,1,DUR);

var GAP=26,WIDE=182,LX=252,AX=178,BX=902,RR=329,NV=9,gHalf=Math.asin(GAP/RR)*180/Math.PI;
var HEADPTS=[[LX-34,-32],[LX,0],[LX-34,32]];

// ================= S1 · HOOK / RULE 0–5.6 =================
var S1label=T('독일군 암호기, 에니그마',CX,300,34,GRAY,KRM,.2,5.4);fade(S1label,.2,5.4,.4);
var bigA=T('A',AX,900,220,IVORY,LAT,.15,6.3,{name:'RULE A (left)'});
var bigB=T('K',BX,900,220,IVORY,LAT,.7,6.3,{name:'RULE letter (right)'});
(function(){var seq='KQMBXFZTRUPLWDGYC',t=.7,dt=.06,i=0;while(t<2.62){setText(bigB,t,seq.charAt(i%seq.length));t+=dt;dt*=1.14;i++;}setText(bigB,2.85,'A');})();
O(bigA,[[.15,0],[.35,100]]);O(bigB,[[.7,0],[.72,100]],'linear');
K(tr(bigB,'ADBE Position'),[[2.85,[BX,900]],[2.9,[BX+16,900]],[2.96,[BX-12,900]],[3.02,[BX+6,900]],[3.1,[BX,900]]],40);

var ROT=M.layers.addNull(DUR);ROT.name='CTRL / ROTOR';tr(ROT,'ADBE Anchor Point').setValue([0,0]);tr(ROT,'ADBE Position').setValue([CX,900]);span(ROT,0,16.4);
var Lline=lerpPts([-LX,0],[0,0],NV),Lbrk=lerpPts([-LX,0],[-GAP,0],NV),Lwide=lerpPts([-LX,0],[-WIDE,0],NV);
var Rline=lerpPts([0,0],[LX,0],NV),Rbrk=lerpPts([GAP,0],[LX,0],NV),Rwide=lerpPts([WIDE,0],[LX,0],NV);
var Larc=arc(RR,90,270-gHalf,NV),Rarc=arc(RR,-90+gHalf,90,NV);
function threadHalf(name,line,brk,wide,ar,a0,a1){var l=shapeLayer(name,CX,900,.3,16.0),g=grp(l,'g');addPath(g,'p',line,false);addTrim(g);addStroke(g,IVORY,10);
  var p=pathProp(l,'g','p');
  p.setValueAtTime(2.82,mkShape(line,false));p.setValueAtTime(2.9,mkShape(brk,false));p.setValueAtTime(3.1,mkShape(brk,false));p.setValueAtTime(3.5,mkShape(wide,false));
  p.setValueAtTime(4.5,mkShape(wide,false));p.setValueAtTime(4.9,mkShape(brk,false));p.setValueAtTime(5.2,mkShape(brk,false));p.setValueAtTime(6.3,mkShape(ar.v,false,ar.i,ar.o));easeAll(p,72);
  K(trimProp(l,'g','end'),[[a0,0],[a1,100]],50);return l;}
var thL=threadHalf('THREAD L',Lline,Lbrk,Lwide,Larc,.3,.52),thR=threadHalf('THREAD R',Rline,Rbrk,Rwide,Rarc,.52,.72);
var head=lineLayer('THREAD HEAD',CX,900,HEADPTS,IVORY,10,.6,5.7);fade(head,.62,5.7,.12,.4);
function gapMark(name,sg){var l=lineLayer(name,CX,900,[[0,-30],[0,30]],LIME,8,2.85,16.0);
  K(tr(l,'ADBE Scale'),[[2.85,[100,0]],[3.0,[100,100]]],50);
  K(tr(l,'ADBE Position'),[[3.1,[CX+sg*GAP,900]],[3.5,[CX+sg*WIDE,900]],[4.5,[CX+sg*WIDE,900]],[4.9,[CX+sg*GAP,900]],[5.2,[CX+sg*GAP,900]],[6.3,[CX+sg*GAP,900-RR]]],72);return l;}
var gmL=gapMark('GAP MARK L',-1),gmR=gapMark('GAP MARK R',1);
// English hook unfolds out of the gap: the line becomes the sentence
var hook=T('IS NEVER',CX,900,64,IVORY,LAT,3.15,4.95,{name:'HOOK / IS NEVER',track:20});
K(tr(hook,'ADBE Scale'),[[3.15,[0,100]],[3.55,[100,100]],[4.5,[100,100]],[4.9,[0,100]]],72);O(hook,[[3.15,0],[3.3,100],[4.75,100],[4.95,0]]);
var S1copy=T('A를 눌러도, A는 절대 안 나옴',CX,1480,60,IVORY,KR,3.6,5.2);fade(S1copy,3.6,5.2,.35);
K(tr(bigA,'ADBE Position'),[[5.2,[AX,900]],[6.1,[CX,900-392]]],70);K(tr(bigA,'ADBE Scale'),[[5.2,[100,100]],[6.1,[15,15]]],70);
K(tr(bigB,'ADBE Position'),[[5.2,[BX,900]],[6.1,[CX,900-392]]],70);K(tr(bigB,'ADBE Scale'),[[5.2,[100,100]],[6.1,[15,15]]],70);
O(bigA,[[5.8,100],[6.15,0]]);O(bigB,[[5.8,100],[6.15,0]]);

// ================= S2 · ROTOR / WIRING / GAP 5.9–16.3 =================
var rotorKids=[thL,thR,head,gmL,gmR];
var ticks=shapeLayer('ROTOR TICKS',CX,900,6.1,16.0);
for(var i=1;i<26;i++){var f=(-90+i*360/26)*Math.PI/180,g=grp(ticks,'t'+i);addPath(g,'p',[[296*Math.cos(f),296*Math.sin(f)],[314*Math.cos(f),314*Math.sin(f)]],false);addStroke(g,GRAY,4);}
fade(ticks,6.1,16.0,.5,.01);rotorKids.push(ticks);
var ABC='ABCDEFGHIJKLMNOPQRSTUVWXYZ';
for(i=0;i<26;i++){var ang=-90+i*360/26,fr=ang*Math.PI/180;
  var lt=T(ABC.charAt(i),CX+392*Math.cos(fr),900+392*Math.sin(fr),34,i===0?LIME:GRAY,LAT,5.9+i*.012,16.0,{name:'ROTOR '+ABC.charAt(i)});
  tr(lt,'ADBE Rotate Z').setValue(ang+90);fade(lt,5.9+i*.012,16.0,.3,.01);rotorKids.push(lt);}
parentAll(rotorKids,ROT);
var S2label=T('에니그마 로터, 반사 배선',CX,300,34,GRAY,KRM,6.5,14.8);fade(S2label,6.5,14.8,.4);
(function(){var p=tr(ROT,'ADBE Rotate Z'),t=6.7,a=0;p.setValueAtTime(t,0);for(var k=0;k<26;k++){var d=.08+.08*Math.abs(k-12.5)/12.5;p.setValueAtTime(t+d*.6,a+360/26);a+=360/26;t+=d;p.setValueAtTime(t,a);}easeAll(p,80);log('rotor steps end '+t.toFixed(2));})();
// reflector wiring: every letter pairs with a different one; A->K is the one we follow
var seed=281912;function rnd(){seed=(seed*1103515245+12345)%2147483648;return seed/2147483648;}
var rest=[];for(i=1;i<26;i++)if(i!==10)rest.push(i);
for(i=rest.length-1;i>0;i--){var j=Math.floor(rnd()*(i+1)),tmp=rest[i];rest[i]=rest[j];rest[j]=tmp;}
var pairs=[[0,10]];for(i=0;i<rest.length;i+=2)pairs.push([rest[i],rest[i+1]]);
function ringPt(k,r){var f=(-90+k*360/26)*Math.PI/180;return [r*Math.cos(f),r*Math.sin(f)];}
var chords=[];
for(i=0;i<pairs.length;i++){var pa=ringPt(pairs[i][0],286),pb=ringPt(pairs[i][1],286),t0=i===0?10.1:11.0+(i-1)*.1;
  var ch=lineLayer('WIRE '+ABC.charAt(pairs[i][0])+'-'+ABC.charAt(pairs[i][1]),CX,900,[pa,pb],i===0?LIME:GRAY,i===0?6:3,t0,14.4,{trim:true,inT:[[0,0],[-pb[0]*.62,-pb[1]*.62]],outT:[[-pa[0]*.62,-pa[1]*.62],[0,0]]});
  K(trimProp(ch,'g','end'),[[t0,0],[t0+(i===0?.7:.35),100]],60);fade(ch,t0,14.4,.05,.5);chords.push(ch);}
var kLime=T('K',CX+392*Math.cos((-90+10*360/26)*Math.PI/180),900+392*Math.sin((-90+10*360/26)*Math.PI/180),34,LIME,LAT,10.7,14.4,{name:'ROTOR K lime'});tr(kLime,'ADBE Rotate Z').setValue(-90+10*360/26+90);fade(kLime,10.7,14.4,.1,.5);
var S2copy=T('모든 글자는 반드시 다른 글자로',CX,1480,60,IVORY,KR,12.4,15.6);fade(S2copy,12.4,15.6,.35);
K(tr(gmL,'ADBE Scale'),[[14.4,[100,100]],[14.55,[100,150]],[14.75,[100,100]]],60);K(tr(gmR,'ADBE Scale'),[[14.4,[100,100]],[14.55,[100,150]],[14.75,[100,100]]],60);
K(tr(ROT,'ADBE Scale'),[[14.9,[100,100]],[16.1,[1500,1500]]],85);
tr(ROT,'ADBE Position').expression='var s=transform.scale[0]/100;var gy=ease(time,14.9,16.1,'+(900-RR)+',900);['+CX+',gy+s*'+RR+'];';
fadeOutAll(rotorKids.slice(5),14.9,15.25);fadeOutAll([thL,thR,head],15.2,15.6);fadeOutAll([gmL,gmR],15.7,16.05);

// ================= S3 · CRIB / CONTRADICTION 15.8–23.4 =================
var SP=104,CIPH='QEXPLMRK',CRIB='WETTER';
function colX(k){return CX+(k-3.5)*SP;}
var railT=lineLayer('RAIL TOP',CX,785,[[-444,0],[444,0]],GRAY,3,15.8,23.2,{trim:true}),railB=lineLayer('RAIL BOTTOM',CX,1015,[[-444,0],[444,0]],GRAY,3,15.8,23.2,{trim:true});
K(trimProp(railT,'g','start'),[[15.8,50],[16.4,0]],70);K(trimProp(railT,'g','end'),[[15.8,50],[16.4,100]],70);
K(trimProp(railB,'g','start'),[[15.8,50],[16.4,0]],70);K(trimProp(railB,'g','end'),[[15.8,50],[16.4,100]],70);
fadeOutAll([railT,railB],22.7,23.2);
var labC=T('가로챈 암호문',colX(0)-30,610,32,GRAY,KRM,16.3,23.0,{align:'left'});fade(labC,16.3,23.0,.3);
var labP=T('예상 문구  WETTER (날씨)',colX(0)-30,1200,32,GRAY,KRM,17.6,23.0,{align:'left'});fade(labP,17.6,23.0,.3);
var ciph=[];for(i=0;i<8;i++){var c=T(CIPH.charAt(i),colX(i),700,96,IVORY,LAT,16.3+i*.05,23.4,{name:'CIPHER '+CIPH.charAt(i)+i});fade(c,16.3+i*.05,23.4,.2,.4);ciph.push(c);}
var CR=M.layers.addNull(DUR);CR.name='CTRL / CRIB';tr(CR,'ADBE Anchor Point').setValue([0,0]);span(CR,0,24);
K(tr(CR,'ADBE Position'),[[17.6,[colX(-4),900]],[18.25,[colX(0),900]],[18.6,[colX(0),900]],[18.66,[colX(0)+12,900]],[18.73,[colX(0)-9,900]],[18.8,[colX(0)+5,900]],[18.88,[colX(0),900]],
  [19.8,[colX(0),900]],[20.2,[colX(1),900]],[20.3,[colX(1),900]],[20.36,[colX(1)+12,900]],[20.43,[colX(1)-9,900]],[20.5,[colX(1)+5,900]],[20.58,[colX(1),900]],[20.95,[colX(1),900]],[21.25,[colX(2),900]]],70);
var cribL=[],cribLines=[];
for(i=0;i<6;i++){var cl=T(CRIB.charAt(i),0,0,96,IVORY,LAT,17.6,23.4,{name:'CRIB '+CRIB.charAt(i)+i});cl.parent=CR;tr(cl,'ADBE Position').setValue([i*SP,200]);fade(cl,17.6,23.4,.15,.4);cribL.push(cl);
  var gl=lineLayer('CRIB LINK '+i,0,0,[[0,-100],[0,100]],GRAY,4,18.25,23.4,{trim:true});gl.parent=CR;tr(gl,'ADBE Position').setValue([i*SP,0]);K(trimProp(gl,'g','end'),[[18.25+i*.03,0],[18.5+i*.03,100]],60);fade(gl,18.25,23.4,.05,.4);cribLines.push(gl);}
function limeText(ch,x,y,t0,t1,parent){var l=T(ch,x,y,96,LIME,LAT,t0,t1,{name:'CONTRA '+ch});if(parent){l.parent=parent;tr(l,'ADBE Position').setValue([x,y]);}return l;}
limeText('E',colX(1),700,18.6,19.8);limeText('E',1*SP,200,18.6,19.8,CR);lineLayer('CONTRA LINK E',colX(1),900,[[0,-100],[0,100]],LIME,6,18.6,19.8);
limeText('R',colX(6),700,20.3,20.95);limeText('R',5*SP,200,20.3,20.95,CR);lineLayer('CONTRA LINK R',colX(6),900,[[0,-100],[0,100]],LIME,6,20.3,20.95);
var S3b=T('같은 글자가 겹치면 탈락',CX,1480,64,IVORY,KR,19.15,22.8);fade(S3b,19.15,22.8,.3);
for(i=0;i<8;i++)fadeOutAll([ciph[i]],22.9+i*.02,23.3+i*.02);
fadeOutAll(cribL.concat(cribLines),22.9,23.3);

// ================= S4 · CHECKLIST + BOMBE 21.3–41.6 =================
var DX=[170,318,466,614,762,910],DY=[560,696,832,968,1104,1240],DR=52,NL=40,MID=2;
// the six surviving links: their letter pairs become the checklist each setting must satisfy
var PAIRS=['W→X','E→P','T→L','T→M','E→R','R→K'];
var passLines=[],tokG=[],tokI=[],tokL=[];
for(i=0;i<6;i++){var x0=colX(2+i),pl=shapeLayer('PASS LINK '+i,x0,900,21.35,25.3),g2=grp(pl,'g');addPath(g2,'p',[[0,-100],[0,100]],false);addStroke(g2,LIME,6);
  var pp=pathProp(pl,'g','p');pp.setValueAtTime(23.4,mkShape([[0,-100],[0,100]],false));pp.setValueAtTime(24.4,mkShape([[0,0],[0,-NL]],false));easeAll(pp,75);
  K(tr(pl,'ADBE Position'),[[23.4,[x0,900]],[24.4,[DX[i],DY[MID]]]],75);O(pl,[[21.35,0],[21.4,100],[24.85,100],[25.3,0]]);passLines.push(pl);
  // checklist token under each column: gray = untested, ivory = holds, lime = contradiction found
  var tg=T(PAIRS[i],DX[i],1372,40,GRAY,LAT,23.0,31.0,{name:'CHECK '+PAIRS[i]});fade(tg,23.0,31.0,.4,.4);K(tr(tg,'ADBE Position'),[[23.0,[x0,1080]],[23.6,[DX[i],1372]]],70);tokG.push(tg);}
function tokState(arr,i,col,t0,t1){var l=T(PAIRS[i],DX[i],1372,40,col,LAT,t0,t1,{name:'CHECK '+PAIRS[i]+(col===LIME?' ✗':' ✓')});arr.push(l);return l;}
var dials=[],order=[],SURV=9;
for(var r=0;r<6;r++)for(var c2=0;c2<6;c2++)order.push(r*6+c2);
for(i=order.length-1;i>0;i--){j=Math.floor(rnd()*(i+1));tmp=order[i];order[i]=order[j];order[j]=tmp;}
var DEMO=[MID*6+2,MID*6+3];
var elim={},kk=0;for(i=0;i<order.length;i++){if(order[i]===SURV||order[i]===DEMO[0]||order[i]===DEMO[1])continue;elim[order[i]]=kk++;}
var NE=kk,cand=[],elimT={};
for(var key in elim){var n=elim[key];if(n>=NE-2){cand.push(+key);continue;}elimT[key]=31.4+8.2*Math.sqrt(n/(NE-3));}
elimT[DEMO[0]]=27.1;elimT[DEMO[1]]=28.1;
var CANDS=[cand[0],cand[1],SURV],FINAL=[130,280,180];
var SPIN0=29.4,STOP=41.6;
function candKeys(nr,fin){K(nr,[[SPIN0,0],[34.8,1440],[38.8,3600],[41.0,5220],[STOP,5400+fin]],'linear');var e9=new KeyframeEase(0,90),e0=new KeyframeEase(0,.1);nr.setTemporalEaseAtKey(5,[e9],[e9]);nr.setTemporalEaseAtKey(4,[e0],[e0]);}
for(r=0;r<6;r++)for(c2=0;c2<6;c2++){var idx=r*6+c2;var dist=Math.abs(r-MID)+Math.abs(c2-2.5);var tIn=r===MID?24.25+c2*.03:24.65+dist*.12;
  var dl=shapeLayer('DIAL r'+r+'c'+c2,DX[c2],DY[r],tIn,46),g3=grp(dl,'ring');addEllipse(g3,DR);addTrim(g3);addStroke(g3,IVORY,6);
  var g4=grp(dl,'needle');addPath(g4,'p',[[0,0],[0,-NL]],false);addStroke(g4,IVORY,6);var g5=grp(dl,'hub');addEllipse(g5,5);addFill(g5,IVORY);
  K(trimProp(dl,'ring','end'),[[tIn,0],[tIn+.35,100]],60);
  var nr=grpRot(dl,'needle'),ci=-1;for(var q=0;q<3;q++)if(CANDS[q]===idx)ci=q;
  var op=tr(dl,'ADBE Opacity');
  if(ci>=0){candKeys(nr,FINAL[ci]);}
  else if(idx===DEMO[0]||idx===DEMO[1]){var td=idx===DEMO[0]?25.9:27.6;K(nr,[[td,0],[td+.2,idx===DEMO[0]?100:-140]],70);}
  else{var D=(rnd()<.5?-1:1)*(.8+rnd()*.45);nr.expression='var E='+elimT[idx].toFixed(3)+';var u=Math.max(0,Math.min(time,E)-'+SPIN0+');'+D.toFixed(3)+'*360*(0.35*u+0.11*u*u);';}
  // demo: the rest wait at 45% while two settings are tested slowly
  var isDemo=(idx===DEMO[0]||idx===DEMO[1]);
  if(!isDemo&&ci<0){var te=elimT[idx];op.setValueAtTime(25.7,100);op.setValueAtTime(26.0,45);op.setValueAtTime(28.8,45);op.setValueAtTime(29.2,100);op.setValueAtTime(te,100);op.setValueAtTime(te+.16,24);easeAll(op,50);K(tr(dl,'ADBE Scale'),[[te,[100,100]],[te+.16,[70,70]]],50);}
  else if(ci>=0){op.setValueAtTime(25.7,100);op.setValueAtTime(26.0,45);op.setValueAtTime(28.8,45);op.setValueAtTime(29.2,100);easeAll(op,50);}
  else{var te2=elimT[idx];op.setValueAtTime(te2,100);op.setValueAtTime(te2+.2,24);easeAll(op,50);K(tr(dl,'ADBE Scale'),[[te2-.9,[100,100]],[te2-.7,[112,112]],[te2,[112,112]],[te2+.2,[70,70]]],50);}
  if(r===MID){var go=dl.property('ADBE Root Vectors Group').property('needle').property('ADBE Vector Transform Group').property('ADBE Vector Group Opacity');go.setValueAtTime(24.85,0);go.setValueAtTime(24.9,100);holdAll(go);}
  dials[idx]=dl;}
// demo checks: setting 1 passes W→X, fails E→P; setting 2 fails W→X at once
tokState(tokI,0,IVORY,26.3,27.4);tokState(tokL,1,LIME,26.8,27.4);
tokState(tokL,0,LIME,27.9,28.4);
var S4copy=T('하나라도 어긋나면 탈락',CX,1480,60,IVORY,KR,28.3,30.8);fade(S4copy,28.3,30.8,.35);
var bLab=T('BOMBE',114,310,40,IVORY,LAT,25.0,44.8,{align:'left',track:250});fade(bLab,25.0,44.8,.3);
var bSub=T('가능한 로터 설정',114,362,34,GRAY,KRM,25.2,44.8,{align:'left'});fade(bSub,25.2,44.8,.3);
var cnt=T('17,576',966,320,56,IVORY,LAT,25.0,STOP,{align:'right',name:'COUNTER'});fade(cnt,25.0,STOP,.3,.01);
var sl=cnt.property('ADBE Effect Parade').addProperty('ADBE Slider Control');sl.name='N';
(function(){var p=cnt.property('ADBE Effect Parade').property('N').property(1);K(p,[[25.0,17576],[27.1,17576],[27.3,17575],[28.1,17575],[28.3,17574],[31.4,17574],[32.8,9800],[34.8,3100],[36.8,640],[38.3,120],[39.4,9]],50);p.setValueAtTime(39.6,3);p.setInterpolationTypeAtKey(p.numKeys,KeyframeInterpolationType.HOLD,KeyframeInterpolationType.HOLD);})();
cnt.property('Source Text').expression='var v=Math.max(3,Math.round(effect("N")(1)));var s=""+v,o="";while(s.length>3){o=","+s.substr(s.length-3)+o;s=s.substr(0,s.length-3);}s+o;';
var cnt3=T('3',966,320,56,LIME,LAT,STOP,44.8,{align:'right',name:'COUNTER / 3'});fade(cnt3,STOP,44.8,.01,.3);

// ================= S5 · STOP (three candidates) 41.6–44.6 =================
var cGroups=[],CX3=[300,540,780],CY3=560;
for(q=0;q<3;q++){var id=CANDS[q],px=DX[id%6],py=DY[Math.floor(id/6)];
  var rg=ringLayer('CANDIDATE '+(q+1)+' RING',px,py,DR,LIME,7,STOP,53.4);
  var nd=lineLayer('CANDIDATE '+(q+1)+' NEEDLE',px,py,[[0,0],[0,-NL]],LIME,7,STOP,53.4);tr(nd,'ADBE Rotate Z').setValue(FINAL[q]);
  var hb=ringLayer('CANDIDATE '+(q+1)+' HUB',px,py,5,LIME,.1,STOP,53.4,{fillOp:100});
  var grpq=[rg,nd,hb];for(var z=0;z<3;z++){K(tr(grpq[z],'ADBE Position'),[[44.6,[px,py]],[45.4,[CX3[q],CY3]]],75);K(tr(grpq[z],'ADBE Scale'),[[44.6,[100,100]],[45.4,[120,120]]],75);}
  cGroups.push(grpq);fadeOutAll([dials[id]],STOP,STOP+.04);}
var S5a=T('기계는 여기까지',CX,1480,64,IVORY,KR,42.4,43.6);O(S5a,[[43.35,100],[43.6,0]]);
var S5b=T('남은 후보 3개',CX,1480,64,IVORY,KR,43.7,45.4);fade(S5b,43.7,45.4,.3,.3);
var fadeD=[];for(i=0;i<36;i++){var isC=false;for(q=0;q<3;q++)if(CANDS[q]===i)isC=true;if(!isC)fadeD.push(dials[i]);}fadeOutAll(fadeD,43.9,44.4);
fadeOutAll([bLab,bSub,cnt3],44.4,44.8);

// ================= S6 · HUMAN CHECK / DECODE 44.6–53.9 =================
var S6label=T('남은 후보, 사람이 직접 대조',CX,300,34,GRAY,KRM,45.0,52.9);fade(S6label,45.0,52.9,.3);
var GIB=['KVZMQWLD','RPAXTOEH'],DEC='U-BOOT',row=[];
var TEST=[46.0,47.8,49.6];
for(i=0;i<8;i++){var t1=45.4+i*.05,dc=T(CIPH.charAt(i),colX(i),900,96,IVORY,LAT,t1,i<6?53.2:51.5,{name:'DECODE '+i});fade(dc,t1,i<6?53.2:51.5,.2,.3);row.push(dc);
  setText(dc,t1,CIPH.charAt(i));var sc=tr(dc,'ADBE Scale');
  for(q=0;q<2;q++){var tf=TEST[q]+.4+i*.1;sc.setValueAtTime(tf,[100,100]);sc.setValueAtTime(tf+.06,[100,0]);sc.setValueAtTime(tf+.12,[100,100]);setText(dc,tf+.06,GIB[q].charAt(i));}
  if(i<6){var tf3=TEST[2]+.4+i*.2;sc.setValueAtTime(tf3,[100,100]);sc.setValueAtTime(tf3+.08,[100,0]);sc.setValueAtTime(tf3+.16,[100,100]);setText(dc,tf3+.08,DEC.charAt(i));
    K(tr(dc,'ADBE Position'),[[51.3,[colX(i),900]],[51.7,[colX(i)+SP,900]]],70);}
  easeAll(sc,40);}
// gibberish rows read dimmer; the real one reads bright
for(q=0;q<3;q++){var xq=CX3[q],ln=lineLayer('TEST LINE '+(q+1),xq,CY3+DR*1.2+8,[[0,0],[0,170]],q===2?LIME:IVORY,4,TEST[q],q===2?53.0:TEST[q]+1.7,{trim:true});
  K(trimProp(ln,'g','end'),[[TEST[q],0],[TEST[q]+.3,100]],60);fade(ln,TEST[q],q===2?53.0:TEST[q]+1.7,.01,.3);
  if(q<2){for(z=0;z<3;z++){O(cGroups[q][z],[[TEST[q]+1.4,100],[TEST[q]+1.6,22]]);}}}
// the stopped dial becomes the letter O of the message (morph-to-type)
var oX=colX(3)+SP,oRing=cGroups[2][0];
K(tr(oRing,'ADBE Position'),[[51.8,[CX3[2],CY3]],[52.35,[oX,900]]],75);K(tr(oRing,'ADBE Scale'),[[51.8,[120,120]],[52.35,[60,66]]],75);
fadeOutAll([cGroups[2][1],cGroups[2][2]],51.7,51.95);
fadeOutAll([row[3]],52.2,52.35);
var coord=T('4',CX,1080,72,IVORY,LAT,52.4,53.9,{name:'COORD'});
(function(){var s='47°N  28°W';for(var k=1;k<=s.length;k++)setText(coord,52.4+k*.04,s.substr(0,k));})();
K(tr(coord,'ADBE Position'),[[53.2,[CX,1080]],[53.9,[614,832]]],75);K(tr(coord,'ADBE Scale'),[[53.2,[100,100]],[53.9,[8,8]]],75);O(coord,[[53.7,100],[53.9,0]]);
fadeOutAll([cGroups[0][0],cGroups[0][1],cGroups[0][2],cGroups[1][0],cGroups[1][1],cGroups[1][2],oRing],52.9,53.3);
fadeOutAll(row.slice(0,3).concat(row.slice(4,6)),52.9,53.3);

// ================= S7 · CHART / ROUTE 53.6–66.2 =================
var OFF=12.6; // v5 map times + OFF
var chart=shapeLayer('CHART GRID',0,0,41.0+OFF,53.6+OFF);
for(i=0;i<6;i++){g=grp(chart,'v'+i);addPath(g,'p',[[DX[i],DY[0]-60],[DX[i],DY[5]+60]],false);addStroke(g,DIM,2);}
for(i=0;i<6;i++){g=grp(chart,'h'+i);addPath(g,'p',[[DX[0]-60,DY[i]],[DX[5]+60,DY[i]]],false);addStroke(g,DIM,2);}
fade(chart,41.0+OFF,53.6+OFF,.8,.6);
var Dz=[614,832];
var dot=ringLayer('UBOAT FIX',Dz[0],Dz[1],7,RED,.1,41.2+OFF,53.6+OFF,{fillOp:100});fade(dot,41.2+OFF,53.6+OFF,.05,.5);
var zone=ringLayer('UBOAT ZONE',Dz[0],Dz[1],150,RED,4,41.3+OFF,53.6+OFF,{fillOp:10,dash:[10,12]});K(tr(zone,'ADBE Scale'),[[41.3+OFF,[0,0]],[41.95+OFF,[100,100]]],70);fade(zone,41.3+OFF,53.6+OFF,.1,.5);
var zLab=T('U-보트',Dz[0],Dz[1]-186,34,RED,KRM,41.9+OFF,50.6+OFF);fade(zLab,41.9+OFF,50.6+OFF,.3);
var SH=[DX[0],DY[5]],DEST=[DX[5],DY[0]];
var old=lineLayer('ROUTE OLD',0,0,[SH,DEST],IVORY,4,41.8+OFF,53.6+OFF,{trim:true,dash:[14,14]});K(trimProp(old,'g','end'),[[41.8+OFF,0],[42.8+OFF,100]],60);O(old,[[41.8+OFF,55],[45.2+OFF,55],[45.6+OFF,18],[53.0+OFF,18],[53.5+OFF,0]]);
var destM=shapeLayer('DESTINATION',DEST[0],DEST[1],41.8+OFF,53.6+OFF);g=grp(destM,'g');addPath(g,'p',[[-9,-9],[9,-9],[9,9],[-9,9]],true);addFill(g,IVORY);fade(destM,41.8+OFF,53.6+OFF,.3,.5);
var dLab=T('영국',DEST[0]-24,DEST[1],34,GRAY,KRM,42.0+OFF,50.6+OFF,{align:'right'});fade(dLab,42.0+OFF,50.6+OFF,.3);
var sLab=T('수송선단',DX[0]-30,DY[5]+70,34,GRAY,KRM,42.0+OFF,50.6+OFF,{align:'left'});fade(sLab,42.0+OFF,50.6+OFF,.3);
var P0=[SH[0]+(DEST[0]-SH[0])*.3,SH[1]+(DEST[1]-SH[1])*.3];
var NR=[P0,[380,860],[520,640],DEST],nt=smooth(NR,.42);
var nw=lineLayer('ROUTE NEW',0,0,NR,LIME,8,45.2+OFF,DUR,{trim:true,inT:nt.i,outT:nt.o});
K(trimProp(nw,'g','end'),[[45.2+OFF,0],[46.5+OFF,100]],55);
var ships=shapeLayer('CONVOY',SH[0],SH[1],41.8+OFF,53.6+OFF);
var hull=[[-26,-7],[14,-7],[28,0],[14,7],[-26,7]],offs=[[0,0],[-46,-24],[-46,24]];
for(i=0;i<3;i++){var hp=[];for(q=0;q<5;q++)hp.push([hull[q][0]+offs[i][0],hull[q][1]+offs[i][1]]);g=grp(ships,'ship'+i);addPath(g,'p',hp,true);addFill(g,IVORY);}
ships.property('ADBE Effect Parade').addProperty('ADBE Slider Control').name='uA';ships.property('ADBE Effect Parade').addProperty('ADBE Slider Control').name='uB';
K(ships.property('ADBE Effect Parade').property('uA').property(1),[[43.0+OFF,0],[45.2+OFF,30]],60);
K(ships.property('ADBE Effect Parade').property('uB').property(1),[[46.3+OFF,0],[50.5+OFF,100]],55);
var exprPath='var A=thisComp.layer("ROUTE OLD").content("g").content("p").path;var B=thisComp.layer("ROUTE NEW").content("g").content("p").path;var u1=effect("uA")(1)/100,u2=Math.min(effect("uB")(1)/100,0.999);';
tr(ships,'ADBE Position').expression=exprPath+'time<'+(45.9+OFF)+'?A.pointOnPath(u1):B.pointOnPath(u2);';
tr(ships,'ADBE Rotate Z').expression=exprPath+'function ang(t){return Math.atan2(t[1],t[0])*180/Math.PI;}var a1=ang(A.tangentOnPath(u1)),a2=ang(B.tangentOnPath(Math.max(u2,0.001)));var d=a2-a1;if(d>180)d-=360;if(d<-180)d+=360;var k=ease(time,'+(45.6+OFF)+','+(46.3+OFF)+',0,1);time<'+(46.3+OFF)+'?a1+d*k:a2;';
fade(ships,41.8+OFF,53.6+OFF,.3,.5);
var S7copy=T('해독된 한 줄, 바뀐 항로',CX,1480,64,IVORY,KR,50.8+OFF,52.9+OFF);fade(S7copy,50.8+OFF,52.9+OFF,.35);

// ================= S8 · CALLBACK 65.8–72.5 =================
var E0=53.0+OFF; // 65.6
var straight=lerpPts([-LX+CX,900],[LX+CX,900],4);
(function(){var p=pathProp(nw,'g','p');p.setValueAtTime(E0+.4,mkShape(NR,false,nt.i,nt.o));p.setValueAtTime(E0+1.6,mkShape(straight,false));easeAll(p,78);})();
O(nw,[[45.2+OFF,100],[E0+2.15,100],[E0+2.3,0]],'linear');span(nw,45.2+OFF,E0+2.3);
var nHead=lineLayer('ROUTE HEAD',CX,900,HEADPTS,LIME,8,E0+1.4,E0+2.3);O(nHead,[[E0+1.4,0],[E0+1.6,100],[E0+2.15,100],[E0+2.3,0]],'linear');
var endA=T('A',AX,900,220,IVORY,LAT,E0+1.6,DUR-.4,{name:'END A (left)'}),endB=T('A',BX,900,220,IVORY,LAT,E0+1.6,DUR-.4,{name:'END A (right)'});
fade(endA,E0+1.6,DUR-.4,.35,.6);fade(endB,E0+1.6,DUR-.4,.35,.6);
K(tr(endB,'ADBE Position'),[[E0+2.2,[BX,900]],[E0+2.25,[BX+16,900]],[E0+2.31,[BX-12,900]],[E0+2.37,[BX+6,900]],[E0+2.45,[BX,900]]],40);
var tb=E0+2.15; // break
function endHalf(name,brk,wide){var l=shapeLayer(name,CX,900,tb,DUR-.4),g6=grp(l,'g');addPath(g6,'p',brk,false);addStroke(g6,IVORY,10);var p=pathProp(l,'g','p');
  p.setValueAtTime(tb+.3,mkShape(brk,false));p.setValueAtTime(tb+.7,mkShape(wide,false));p.setValueAtTime(tb+3.3,mkShape(wide,false));p.setValueAtTime(tb+3.7,mkShape(brk,false));easeAll(p,72);return l;}
var eL=endHalf('END THREAD L',Lbrk,Lwide),eR=endHalf('END THREAD R',Rbrk,Rwide),eH=lineLayer('END HEAD',CX,900,HEADPTS,IVORY,10,tb,DUR-.4);
function endGap(name,sg){var l=lineLayer(name,CX,900,[[0,-30],[0,30]],LIME,8,tb+.05,DUR);K(tr(l,'ADBE Scale'),[[tb+.05,[100,0]],[tb+.2,[100,100]]],50);
  K(tr(l,'ADBE Position'),[[tb+.3,[CX+sg*GAP,900]],[tb+.7,[CX+sg*WIDE,900]],[tb+3.3,[CX+sg*WIDE,900]],[tb+3.7,[CX+sg*GAP,900]]],72);return l;}
var eGL=endGap('END GAP L',-1),eGR=endGap('END GAP R',1);
var hook2=T('IS NEVER',CX,900,64,IVORY,LAT,tb+.35,tb+3.75,{name:'HOOK / IS NEVER (end)',track:20});
K(tr(hook2,'ADBE Scale'),[[tb+.35,[0,100]],[tb+.75,[100,100]],[tb+3.3,[100,100]],[tb+3.7,[0,100]]],72);O(hook2,[[tb+.35,0],[tb+.5,100],[tb+3.55,100],[tb+3.75,0]]);
fadeOutAll([eL,eR,eH],DUR-1.0,DUR-.4);fadeOutAll([eGL,eGR],DUR-.55,DUR-.03);
var c8=T('빈틈은 하나면 충분',CX,1480,64,IVORY,KR,tb+.9,DUR-.4);fade(c8,tb+.9,DUR-.4,.35,.6);

// grain + audio
var gr=M.layers.addSolid([.5,.5,.5],'GRAIN',W,H,1,DUR);try{var nz=gr.property('ADBE Effect Parade').addProperty('ADBE Noise');nz.property(1).setValue(6);}catch(x){}gr.blendingMode=BlendingMode.OVERLAY;tr(gr,'ADBE Opacity').setValue(7);

// ================= V7 EDIT: v6 graphics segments + H3 documentary inserts =================
var FOOT=R+'/h3/clips/',ED=84.6;
var E=app.project.items.addComp('ENIGMA / V7 EDIT',W,H,1,ED,FPS);E.motionBlur=true;E.shutterAngle=180;E.motionBlurSamplesPerFrame=16;E.bgColor=INK;
E.layers.addSolid(INK,'BG',W,H,1,ED);
var FS=143;
function seg(s0,s1,T0,fadeIn){var l=E.layers.add(M);l.startTime=T0-s0;l.inPoint=T0;l.outPoint=T0+(s1-s0);l.name='GRAPHICS s'+s0+'-'+s1;
  if(fadeIn)K(tr(l,'ADBE Opacity'),[[T0,0],[T0+fadeIn,100]],50);return l;}
var imported={};
function foot(id){if(!imported[id])imported[id]=app.project.importFile(new ImportOptions(new File(FOOT+id+'.mp4')));return imported[id];}
function clip(id,src0,T0,T1){var l=E.layers.add(foot(id));l.audioEnabled=false;l.startTime=T0-src0;l.inPoint=T0;l.outPoint=T1;l.name='FOOTAGE '+id;
  tr(l,'ADBE Anchor Point').setValue([384,672]);tr(l,'ADBE Position').setValue([540,960]);tr(l,'ADBE Scale').setValue([FS,FS]);l.motionBlur=true;
  var t=l.property('ADBE Effect Parade').addProperty('ADBE Tint');t.property(1).setValue(INK);t.property(2).setValue(IVORY);t.property(3).setValue(85);return l;}
function fadeIO(l,a,b,fi,fo){var k=[];if(fi){k.push([a,0],[a+fi,100]);}else k.push([a,100]);if(fo)k.push([b-fo,100],[b,0]);K(tr(l,'ADBE Opacity'),k,50);}
// A · cold open: key press, lamp flares, push into the lamp
var cA=clip('r1-keys',.6,0,2.45);tr(cA,'ADBE Anchor Point').setValue([520,516]);tr(cA,'ADBE Position').setValue([540+FS/100*(520-384),960+FS/100*(516-672)]);
K(tr(cA,'ADBE Scale'),[[0,[FS,FS]],[1.9,[FS*1.06,FS*1.06]],[2.45,[FS*3.2,FS*3.2]]],60);K(tr(cA,'ADBE Position'),[[1.9,[540+FS/100*136,960-FS/100*156]],[2.45,[540,760]]],60);fadeIO(cA,0,2.45,.3,.25);
// B · v6 0–15.75, real rotors breathing behind the ring
seg(0,15.75,2.4,0);
var cB=clip('r2-rotors',.2,8.4,12.4);cB.blendingMode=BlendingMode.SCREEN;K(tr(cB,'ADBE Opacity'),[[8.4,0],[9.0,38],[11.7,38],[12.4,0]],50);
// C · listening station -> hut; the morning weather report
var cC1=clip('r3-radio',.3,18.15,20.15);K(tr(cC1,'ADBE Scale'),[[18.15,[FS*1.08,FS*1.08]],[20.15,[FS,FS]]],30);
var cC2=clip('r4-hut',1.4,20.15,22.85);K(tr(cC2,'ADBE Scale'),[[20.15,[FS,FS]],[22.85,[FS*1.12,FS*1.12]]],30);fadeIO(cC2,20.15,22.85,0,.3);
var capC=E.layers.addText('매일 아침 날씨 보고, 늘 같은 단어');(function(){var p=capC.property('Source Text'),d=p.value;d.font=KR;d.fontSize=60;d.fillColor=IVORY;d.applyFill=true;d.applyStroke=false;d.justification=ParagraphJustification.CENTER_JUSTIFY;p.setValue(d);})();
tr(capC,'ADBE Anchor Point').setValue([0,-60*.37]);tr(capC,'ADBE Position').setValue([CX,1480]);capC.inPoint=20.35;capC.outPoint=22.6;fadeIO(capC,20.35,22.6,.3,.25);
var ds=capC.property('ADBE Effect Parade').addProperty('ADBE Drop Shadow');ds.property('ADBE Drop Shadow-0002').setValue(85);ds.property('ADBE Drop Shadow-0004').setValue(0);ds.property('ADBE Drop Shadow-0005').setValue(40);
// D · v6 15.75–29.4
seg(15.75,29.4,22.55,.3);
// E · the real Bombe: drum grid locked onto the graphic dial grid at both seams
var cE=clip('r5-bombe',.5,35.9,38.5);var AL=[155.8,133.3],ALP=[540-1.558*(396.5-384),900-1.333*(629.5-672)];
K(tr(cE,'ADBE Scale'),[[35.9,AL],[36.5,[FS,FS]],[37.9,[FS,FS]],[38.5,AL]],70);K(tr(cE,'ADBE Position'),[[35.9,ALP],[36.5,[540,960]],[37.9,[540,960]],[38.5,ALP]],70);fadeIO(cE,35.9,38.5,.3,0);
// F · v6 29.4–53.5
seg(29.4,53.5,38.2,.3);
// G · convoy from above, dissolving into the chart
var cG=clip('r6-convoy',.3,62.0,65.1);K(tr(cG,'ADBE Scale'),[[62.0,[FS,FS]],[65.1,[FS*1.08,FS*1.08]]],30);fadeIO(cG,62.0,65.1,.3,0);
// H · v6 53.5–65.6
seg(53.5,65.6,64.8,.3);
// I · the wake turns ninety degrees and becomes the line
var cI=clip('r7-wake',.5,76.6,79.65);tr(cI,'ADBE Anchor Point').setValue([378,870]);
K(tr(cI,'ADBE Position'),[[76.6,[540+FS/100*(378-384),960+FS/100*(870-672)]],[78.4,[540+FS/100*(378-384),960+FS/100*(870-672)]],[79.3,[CX,900]]],75);
K(tr(cI,'ADBE Scale'),[[78.4,[FS,FS]],[79.3,[53,53]]],75);K(tr(cI,'ADBE Rotate Z'),[[78.4,0],[79.3,90]],75);fadeIO(cI,76.6,79.65,.3,.35);
// J · v6 67.2–72.5 ending
seg(67.2,72.5,79.3,.3);
var gr2=E.layers.addSolid([.5,.5,.5],'GRAIN',W,H,1,ED);try{var nz2=gr2.property('ADBE Effect Parade').addProperty('ADBE Noise');nz2.property(1).setValue(5);}catch(x){}gr2.blendingMode=BlendingMode.OVERLAY;tr(gr2,'ADBE Opacity').setValue(7);
var au=new File(R+'/soundtrack.wav');if(au.exists){var al=E.layers.add(app.project.importFile(new ImportOptions(au)));al.name='SOUNDTRACK';al.inPoint=0;al.outPoint=ED;}
E.openInViewer();
app.project.save(new File(R+'/enigma-v7.aep'));
log('layers='+M.numLayers+' cands='+CANDS.toString());
var f=new File(R+'/built.json');f.encoding='UTF-8';f.open('w');f.write('{"status":"saved","ae":"'+app.version+'","layers":'+M.numLayers+',"log":'+LOG.toSource()+'}');f.close();
}catch(e){var f2=new File(R+'/built.json');f2.encoding='UTF-8';f2.open('w');f2.write('{"status":"error","error":"'+String(e).replace(/"/g,"'")+'","line":'+e.line+',"log":'+LOG.toSource()+'}');f2.close();}
})();
