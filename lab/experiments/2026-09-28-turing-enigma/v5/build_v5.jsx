// ENIGMA V5 — one master comp; the thread survives every scene and changes shape.
// Design: DESIGN.md. Run: AfterFX.exe -r build_v5.jsx
(function(){
var DATA_ROOT=$.getenv('MODAL_GUI_DATA_ROOT');
if(!DATA_ROOT) throw new Error('Set MODAL_GUI_DATA_ROOT before running this build');
var R=DATA_ROOT+'/lab/2026-09-28-turing-enigma/v5';
var W=1080,H=1920,FPS=30,DUR=60,CX=540;
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
if(app.project.numItems>0){var mine=pf.indexOf('/2026-09-28-turing-enigma/v5/')>=0;
  if(!mine)for(var ii=1;ii<=app.project.numItems;ii++)if(app.project.item(ii).name==='ENIGMA / V5 MASTER')mine=true;
  if(!mine)throw Error('Open project is not V5; refusing to modify '+pf);
  while(app.project.numItems>0)app.project.item(1).remove();}
try{app.project.expressionEngine='javascript-1.0';}catch(x){}
M=app.project.items.addComp('ENIGMA / V5 MASTER',W,H,1,DUR,FPS);
M.motionBlur=true;M.shutterAngle=180;M.motionBlurSamplesPerFrame=16;M.bgColor=INK;
var bg=M.layers.addSolid(INK,'BACKGROUND / INK',W,H,1,DUR);bg.locked=false;

// ================= S1 · RULE 0–5 =================
var S1label=T('에니그마의 규칙',CX,300,34,GRAY,KRM,.2,5.0);fade(S1label,.2,5.0,.4);
var bigA=T('A',270,900,240,IVORY,LAT,.15,5.9,{name:'RULE A (left)'});
var bigB=T('K',810,900,240,IVORY,LAT,.7,5.9,{name:'RULE letter (right)'});
(function(){var seq='KQMBXFZTRUPLWDGYC',t=.7,dt=.06,i=0;while(t<2.62){setText(bigB,t,seq.charAt(i%seq.length));t+=dt;dt*=1.14;i++;}setText(bigB,2.85,'A');log('S1 letters cycled: '+i);})();
O(bigA,[[.15,0],[.35,100]]);
O(bigB,[[.7,0],[.72,100]],'linear');
K(tr(bigB,'ADBE Position'),[[2.85,[810,900]],[2.9,[826,900]],[2.96,[798,900]],[3.02,[816,900]],[3.1,[810,900]]],40);

// rotor null (pivot for thread + rotor); zoom keeps the gap fixed in view
var ROT=M.layers.addNull(DUR);ROT.name='CTRL / ROTOR';tr(ROT,'ADBE Anchor Point').setValue([0,0]);tr(ROT,'ADBE Position').setValue([CX,900]);ROT.enabled=true;span(ROT,0,12.2);
var GAP=26,RR=329,gHalf=Math.asin(GAP/RR)*180/Math.PI,NV=9;
// thread halves: line (break at 2.85) -> ring arcs
var Lline=lerpPts([-140,0],[0,0],NV),Lbreak=lerpPts([-140,0],[-GAP,0],NV),Rline=lerpPts([0,0],[140,0],NV),Rbreak=lerpPts([GAP,0],[140,0],NV);
var Larc=arc(RR,90,270-gHalf,NV),Rarc=arc(RR,-90+gHalf,90,NV);
function threadHalf(name,line,brk,ar,a0,a1){var l=shapeLayer(name,CX,900,.3,11.8),g=grp(l,'g');addPath(g,'p',line,false);addTrim(g);addStroke(g,IVORY,10);
  var p=pathProp(l,'g','p');
  p.setValueAtTime(2.82,mkShape(line,false));p.setValueAtTime(2.9,mkShape(brk,false));p.setValueAtTime(4.9,mkShape(brk,false));p.setValueAtTime(6.0,mkShape(ar.v,false,ar.i,ar.o));easeAll(p,70);
  K(trimProp(l,'g','end'),[[a0,0],[a1,100]],50);return l;}
// L then R draw left->right so the arrow reads as one stroke
var thL=threadHalf('THREAD L',Lline,Lbreak,Larc,.3,.52);
var thR=threadHalf('THREAD R',Rline,Rbreak,Rarc,.52,.72);
var head=lineLayer('THREAD HEAD',CX,900,[[108,-32],[142,0],[108,32]],IVORY,10,.6,5.4);fade(head,.62,5.4,.12,.4);
// gap marks: the only lime in S1
function gapMark(name,x){var l=lineLayer(name,CX,900,[[x,-30],[x,30]],LIME,8,2.85,11.8);K(tr(l,'ADBE Scale'),[[2.85,[100,0]],[3.0,[100,100]]],50);K(tr(l,'ADBE Position'),[[4.9,[CX,900]],[6.0,[CX,900-RR]]],70);return l;}
var gmL=gapMark('GAP MARK L',-GAP),gmR=gapMark('GAP MARK R',GAP);
var S1copy=T('하나는 불가능하다.',CX,1480,64,IVORY,KR,3.4,4.8);fade(S1copy,3.4,4.8,.35);
// big letters collapse into the rotor's A
K(tr(bigA,'ADBE Position'),[[4.9,[270,900]],[5.8,[CX,900-392]]],70);K(tr(bigA,'ADBE Scale'),[[4.9,[100,100]],[5.8,[15,15]]],70);
K(tr(bigB,'ADBE Position'),[[4.9,[810,900]],[5.8,[CX,900-392]]],70);K(tr(bigB,'ADBE Scale'),[[4.9,[100,100]],[5.8,[15,15]]],70);
O(bigA,[[5.5,100],[5.85,0]]);O(bigB,[[5.5,100],[5.85,0]]);

// ================= S2 · ROTOR / GAP 5–11 =================
var rotorKids=[thL,thR,head,gmL,gmR];
var ticks=shapeLayer('ROTOR TICKS',CX,900,5.8,11.8);
for(var i=1;i<26;i++){var f=(-90+i*360/26)*Math.PI/180,g=grp(ticks,'t'+i);addPath(g,'p',[[296*Math.cos(f),296*Math.sin(f)],[314*Math.cos(f),314*Math.sin(f)]],false);addStroke(g,GRAY,4);}
fade(ticks,5.8,11.8,.5,.01);rotorKids.push(ticks);
var ABC='ABCDEFGHIJKLMNOPQRSTUVWXYZ';
for(i=0;i<26;i++){var ang=-90+i*360/26,fr=ang*Math.PI/180;
  var lt=T(ABC.charAt(i),CX+392*Math.cos(fr),900+392*Math.sin(fr),34,i===0?LIME:GRAY,LAT,5.6+i*.012,11.8,{name:'ROTOR '+ABC.charAt(i)});
  tr(lt,'ADBE Rotate Z').setValue(ang+90);fade(lt,5.6+i*.012,11.8,.3,.01);rotorKids.push(lt);}
parentAll(rotorKids,ROT);
var S2label=T('에니그마 로터',CX,300,34,GRAY,KRM,6.2,10.6);fade(S2label,6.2,10.6,.4);
var S2copy=T('모든 글자는 다른 글자로.',CX,1480,60,IVORY,KR,7.6,10.5);fade(S2copy,7.6,10.5,.35);
// rotor steps: slow-fast-slow mechanical ticks, full turn so the gap returns to the top
(function(){var p=tr(ROT,'ADBE Rotate Z'),t=6.4,a=0;p.setValueAtTime(t,0);for(var k=0;k<26;k++){var d=.10+.10*Math.abs(k-12.5)/12.5;p.setValueAtTime(t+d*.6,a+360/26);a+=360/26;t+=d;p.setValueAtTime(t,a);}easeAll(p,80);log('rotor steps end '+t.toFixed(2));})();
K(tr(ROT,'ADBE Scale'),[[10.6,[100,100]],[11.8,[1500,1500]]],85);
tr(ROT,'ADBE Position').expression='var s=transform.scale[0]/100;var gy=ease(time,10.6,11.8,'+(900-RR)+',900);['+CX+',gy+s*'+RR+'];';
fadeOutAll(rotorKids.slice(5),10.6,10.95);fadeOutAll([thL,thR,head],10.9,11.3);fadeOutAll([gmL,gmR],11.4,11.75);

// ================= S3 · CRIB / CONTRADICTION 11.5–20 =================
var SP=104,CIPH='QEXPLMRK',CRIB='WETTER';
function colX(k){return CX+(k-3.5)*SP;}
var railT=lineLayer('RAIL TOP',CX,785,[[-444,0],[444,0]],GRAY,3,11.5,18.8,{trim:true}),railB=lineLayer('RAIL BOTTOM',CX,1015,[[-444,0],[444,0]],GRAY,3,11.5,18.8,{trim:true});
K(trimProp(railT,'g','start'),[[11.5,50],[12.1,0]],70);K(trimProp(railT,'g','end'),[[11.5,50],[12.1,100]],70);
K(trimProp(railB,'g','start'),[[11.5,50],[12.1,0]],70);K(trimProp(railB,'g','end'),[[11.5,50],[12.1,100]],70);
fadeOutAll([railT,railB],18.2,18.7);
var labC=T('암호문',colX(0)-30,610,32,GRAY,KRM,12.0,18.6,{align:'left'});fade(labC,12.0,18.6,.3);
var labP=T('예상 문구  WETTER · 날씨',colX(0)-30,1200,32,GRAY,KRM,12.9,18.6,{align:'left'});fade(labP,12.9,18.6,.3);
var ciph=[];for(i=0;i<8;i++){var c=T(CIPH.charAt(i),colX(i),700,96,IVORY,LAT,12.0+i*.05,18.6,{name:'CIPHER '+CIPH.charAt(i)+i});fade(c,12.0+i*.05,18.6,.2,.4);ciph.push(c);}
var CR=M.layers.addNull(DUR);CR.name='CTRL / CRIB';tr(CR,'ADBE Anchor Point').setValue([0,0]);span(CR,0,20);
var crX=function(k){return colX(k);};
K(tr(CR,'ADBE Position'),[[12.7,[crX(-4),900]],[13.35,[crX(0),900]],[13.7,[crX(0),900]],[13.76,[crX(0)+12,900]],[13.83,[crX(0)-9,900]],[13.9,[crX(0)+5,900]],[13.98,[crX(0),900]],
  [14.9,[crX(0),900]],[15.3,[crX(1),900]],[15.4,[crX(1),900]],[15.46,[crX(1)+12,900]],[15.53,[crX(1)-9,900]],[15.6,[crX(1)+5,900]],[15.68,[crX(1),900]],[16.05,[crX(1),900]],[16.35,[crX(2),900]]],70);
var cribL=[],cribLines=[];
for(i=0;i<6;i++){var cl=T(CRIB.charAt(i),0,0,96,IVORY,LAT,12.7,18.6,{name:'CRIB '+CRIB.charAt(i)+i});cl.parent=CR;tr(cl,'ADBE Position').setValue([i*SP,200]);fade(cl,12.7,18.6,.15,.4);cribL.push(cl);
  var gl=lineLayer('CRIB LINK '+i,0,0,[[0,-100],[0,100]],GRAY,4,13.35,18.6,{trim:true});gl.parent=CR;tr(gl,'ADBE Position').setValue([i*SP,0]);K(trimProp(gl,'g','end'),[[13.35+i*.03,0],[13.6+i*.03,100]],60);fade(gl,13.35,18.6,.05,.4);cribLines.push(gl);}
// contradictions: same letter meets itself (the A->A rule again) — lime, instant
function limeText(ch,x,y,t0,t1,parent){var l=T(ch,x,y,96,LIME,LAT,t0,t1,{name:'CONTRA '+ch});if(parent){l.parent=parent;tr(l,'ADBE Position').setValue([x,y]);}return l;}
limeText('E',colX(1),700,13.7,14.9);limeText('E',1*SP,200,13.7,14.9,CR);
lineLayer('CONTRA LINK E',colX(1),900,[[0,-100],[0,100]],LIME,6,13.7,14.9);
limeText('R',colX(6),700,15.4,16.05);limeText('R',5*SP,200,15.4,16.05,CR);
lineLayer('CONTRA LINK R',colX(6),900,[[0,-100],[0,100]],LIME,6,15.4,16.05);
var S3copy=T('모순을 찾아라.',CX,1480,64,IVORY,KR,14.25,17.9);fade(S3copy,14.25,17.9,.3);
// pass: six links survive in lime — they become Bombe needles
var DX=[170,318,466,614,762,910],DY=[492,628,764,900,1036,1172,1308],DR=52,NL=40;
var passLines=[];
for(i=0;i<6;i++){var x0=colX(2+i),pl=shapeLayer('PASS LINK '+i,x0,900,16.45,20.5),g=grp(pl,'g');addPath(g,'p',[[0,-100],[0,100]],false);addStroke(g,LIME,6);
  var pp=pathProp(pl,'g','p');pp.setValueAtTime(18.5,mkShape([[0,-100],[0,100]],false));pp.setValueAtTime(19.5,mkShape([[0,0],[0,-NL]],false));easeAll(pp,75);
  K(tr(pl,'ADBE Position'),[[18.5,[x0,900]],[19.5,[DX[i],900]]],75);O(pl,[[16.45,0],[16.5,100],[19.95,100],[20.45,0]]);passLines.push(pl);}
for(i=0;i<8;i++)fadeOutAll([ciph[i]],18.0+i*.02,18.5+i*.02);
fadeOutAll(cribL.concat(cribLines),18.0,18.5);

// ================= S4 · BOMBE 19.4–32.8 =================
var dials=[],order=[],SURV=9; // row 1 col 3 survives
for(var r=0;r<7;r++)for(var c2=0;c2<6;c2++){var idx=r*6+c2;order.push(idx);}
// elimination order: deterministic shuffle
var seed=281912;function rnd(){seed=(seed*1103515245+12345)%2147483648;return seed/2147483648;}
for(i=order.length-1;i>0;i--){var j=Math.floor(rnd()*(i+1)),tmp=order[i];order[i]=order[j];order[j]=tmp;}
var elim={},kk=0;for(i=0;i<order.length;i++){if(order[i]===SURV)continue;elim[order[i]]=kk++;}
var last2=[],elimT={};
for(var key in elim){var n=elim[key];if(n>=39){last2.push(+key);continue;}elimT[key]=22.6+8.2*Math.sqrt(n/38);}
elimT[last2[0]]=31.4;elimT[last2[1]]=32.1;
for(r=0;r<7;r++)for(c2=0;c2<6;c2++){idx=r*6+c2;var dist=Math.abs(r-3)+Math.abs(c2-2.5);var tIn=r===3?19.35+c2*.03:19.75+dist*.12;
  var dl=shapeLayer('DIAL r'+r+'c'+c2,DX[c2],DY[r],tIn,idx===SURV?42:36),g1=grp(dl,'ring');addEllipse(g1,DR);addTrim(g1);addStroke(g1,IVORY,6);
  var g2=grp(dl,'needle');addPath(g2,'p',[[0,0],[0,-NL]],false);addStroke(g2,IVORY,6);var g3=grp(dl,'hub');addEllipse(g3,5);addFill(g3,IVORY);
  K(trimProp(dl,'ring','end'),[[tIn,0],[tIn+.35,100]],60);
  var nr=grpRot(dl,'needle');
  if(idx===SURV){K(nr,[[20.6,0],[26,1440],[30,3600],[32.2,5220],[32.8,5580]],'linear');var e9=new KeyframeEase(0,90),e0=new KeyframeEase(0,.1);nr.setTemporalEaseAtKey(5,[e9],[e9]);nr.setTemporalEaseAtKey(4,[e0],[e0]);}
  else{var D=(rnd()<.5?-1:1)*(.8+rnd()*.45);nr.expression='var E='+elimT[idx].toFixed(3)+';var u=Math.max(0,Math.min(time,E)-20.6);'+D.toFixed(3)+'*360*(0.35*u+0.11*u*u);';
    var te=elimT[idx];O(dl,[[te,100],[te+.16,24]],50);K(tr(dl,'ADBE Scale'),[[te,[100,100]],[te+.16,[70,70]]],50);}
  if(r===3){var go=dl.property('ADBE Root Vectors Group').property('needle').property('ADBE Vector Transform Group').property('ADBE Vector Group Opacity');go.setValueAtTime(19.95,0);go.setValueAtTime(20.0,100);holdAll(go);}
  dials[idx]=dl;}
// middle-row rings draw around the arriving lime needles; needle layer hides underneath until hand-off
var bLab=T('BOMBE',114,310,40,IVORY,LAT,20.2,35.3,{align:'left',track:250});fade(bLab,20.2,35.3,.3);
var bSub=T('가능한 설정',114,362,34,GRAY,KRM,20.4,35.3,{align:'left'});fade(bSub,20.4,35.3,.3);
var cnt=T('17,576',966,320,56,IVORY,LAT,20.2,32.8,{align:'right',name:'COUNTER'});fade(cnt,20.2,32.8,.3,.01);
var sl=cnt.property('ADBE Effect Parade').addProperty('ADBE Slider Control');sl.name='N';
K(cnt.property('ADBE Effect Parade').property('N').property(1),[[20.2,17576],[22.6,17576],[24,9800],[26,3100],[28,640],[29.5,120],[30.6,9]],50);
(function(){var p=cnt.property('ADBE Effect Parade').property('N').property(1);p.setValueAtTime(30.8,3);p.setValueAtTime(31.4,2);p.setValueAtTime(32.1,1);for(var k=p.numKeys-2;k<=p.numKeys;k++)p.setInterpolationTypeAtKey(k,KeyframeInterpolationType.HOLD,KeyframeInterpolationType.HOLD);})();
cnt.property('Source Text').expression='var v=Math.max(1,Math.round(effect("N")(1)));var s=""+v,o="";while(s.length>3){o=","+s.substr(s.length-3)+o;s=s.substr(0,s.length-3);}s+o;';
var cnt1=T('1',966,320,56,LIME,LAT,32.8,35.3,{align:'right',name:'COUNTER / 1'});fade(cnt1,32.8,35.3,.01,.3);
// survivor locks: lime ring, hard cut, no easing
var sv=ringLayer('SURVIVOR RING',DX[3],DY[1],DR,LIME,7,32.8,41.2);
var svN=lineLayer('SURVIVOR NEEDLE',DX[3],DY[1],[[0,0],[0,NL]],LIME,7,32.8,41.2);
var svHub=ringLayer('SURVIVOR HUB',DX[3],DY[1],5,LIME,0.1,32.8,41.2,{fillOp:100});
var svGroup=[sv,svN,svHub];

// ================= S5 · STOP 32.8–36 =================
var S5copy=T('멈췄다.',CX,1480,64,IVORY,KR,33.6,35.7);O(S5copy,[[35.35,100],[35.7,0]]);
var fadeD=[];for(i=0;i<42;i++)if(i!==SURV)fadeD.push(dials[i]);fadeOutAll(fadeD,34.8,35.3);fadeOutAll([dials[SURV]],32.8,32.84);
fadeOutAll([bLab,bSub,cnt1],34.9,35.3);
for(i=0;i<3;i++){K(tr(svGroup[i],'ADBE Position'),[[35.0,[DX[3],DY[1]]],[35.8,[CX,520]]],75);K(tr(svGroup[i],'ADBE Scale'),[[35.0,[100,100]],[35.8,[130,130]]],75);}

// ================= S6 · CHECK / DECODE 35.9–41 =================
var down=lineLayer('THREAD DOWN',CX,520+DR*1.3,[[0,0],[0,170]],LIME,6,35.9,40.9,{trim:true});K(trimProp(down,'g','end'),[[35.9,0],[36.3,100]],60);fade(down,35.9,40.9,.01,.4);
var S6label=T('사람의 대조',CX,300,34,GRAY,KRM,36.2,40.4);fade(S6label,36.2,40.4,.3);
var DEC='U-BOOT',row=[];
for(i=0;i<8;i++){var t0=36.2+i*.05,dc=T(CIPH.charAt(i),colX(i),900,96,IVORY,LAT,t0,i<6?40.9:38.6,{name:'DECODE '+i});fade(dc,t0,i<6?40.9:38.6,.2,.3);row.push(dc);
  var tf=37.0+i*.22;setText(dc,t0,CIPH.charAt(i));if(i<6){K(tr(dc,'ADBE Scale'),[[tf,[100,100]],[tf+.08,[100,0]],[tf+.16,[100,100]]],40);setText(dc,tf+.08,DEC.charAt(i));
    K(tr(dc,'ADBE Position'),[[38.5,[colX(i),900]],[38.9,[colX(i)+SP,900]]],70);}}
var cur=lineLayer('DECODE CURSOR',colX(0),985,[[-30,0],[30,0]],LIME,6,37.0,38.45);
(function(){var p=tr(cur,'ADBE Position');for(var k=0;k<6;k++)p.setValueAtTime(37.0+k*.22,[colX(k),985]);holdAll(p);})();
var coord=T('4',CX,1080,72,IVORY,LAT,38.9,41.3,{name:'COORD'});
(function(){var s='47°N  28°W';for(var k=1;k<=s.length;k++)setText(coord,38.9+k*.045,s.substr(0,k));})();
K(tr(coord,'ADBE Position'),[[40.6,[CX,1080]],[41.3,[614,764]]],75);K(tr(coord,'ADBE Scale'),[[40.6,[100,100]],[41.3,[8,8]]],75);O(coord,[[41.1,100],[41.3,0]]);
fadeOutAll(svGroup,40.4,40.9);

// ================= S7 · CHART / ROUTE 41–53.5 =================
var chart=shapeLayer('CHART GRID',0,0,41.0,53.6);
for(i=0;i<6;i++){g=grp(chart,'v'+i);addPath(g,'p',[[DX[i],DY[0]-60],[DX[i],DY[6]+60]],false);addStroke(g,DIM,2);}
for(i=0;i<7;i++){g=grp(chart,'h'+i);addPath(g,'p',[[DX[0]-60,DY[i]],[DX[5]+60,DY[i]]],false);addStroke(g,DIM,2);}
fade(chart,41.0,53.6,.8,.6);
var Dz=[614,764];
var dot=ringLayer('UBOAT FIX',Dz[0],Dz[1],7,RED,.1,41.2,53.6,{fillOp:100});fade(dot,41.2,53.6,.05,.5);
var zone=ringLayer('UBOAT ZONE',Dz[0],Dz[1],150,RED,4,41.3,53.6,{fillOp:10,dash:[10,12]});K(tr(zone,'ADBE Scale'),[[41.3,[0,0]],[41.95,[100,100]]],70);fade(zone,41.3,53.6,.1,.5);
var zLab=T('U-보트',Dz[0],Dz[1]-186,34,RED,KRM,41.9,50.6);fade(zLab,41.9,50.6,.3);
var SH=[DX[0],DY[6]],DEST=[DX[5],DY[0]];
var old=lineLayer('ROUTE OLD',0,0,[SH,DEST],IVORY,4,41.8,53.6,{trim:true,dash:[14,14]});K(trimProp(old,'g','end'),[[41.8,0],[42.8,100]],60);O(old,[[41.8,55],[45.2,55],[45.6,18],[53.0,18],[53.5,0]]);
var destM=shapeLayer('DESTINATION',DEST[0],DEST[1],41.8,53.6);g=grp(destM,'g');addPath(g,'p',[[-9,-9],[9,-9],[9,9],[-9,9]],true);addFill(g,IVORY);fade(destM,41.8,53.6,.3,.5);
var dLab=T('영국',DEST[0]-24,DEST[1],34,GRAY,KRM,42.0,50.6,{align:'right'});fade(dLab,42.0,50.6,.3);
var sLab=T('수송선단',DX[0]-30,DY[6]+70,34,GRAY,KRM,42.0,50.6,{align:'left'});fade(sLab,42.0,50.6,.3);
var P0=[SH[0]+(DEST[0]-SH[0])*.3,SH[1]+(DEST[1]-SH[1])*.3];
var NR=[P0,[380,800],[520,545],DEST],nt=smooth(NR,.42);
var nw=lineLayer('ROUTE NEW',0,0,NR,LIME,8,45.2,59.2,{trim:true,inT:nt.i,outT:nt.o});
K(trimProp(nw,'g','end'),[[45.2,0],[46.5,100]],55);
var ships=shapeLayer('CONVOY',SH[0],SH[1],41.8,53.6);
var hull=[[-26,-7],[14,-7],[28,0],[14,7],[-26,7]],offs=[[0,0],[-46,-24],[-46,24]];
for(i=0;i<3;i++){var hp=[];for(var q=0;q<5;q++)hp.push([hull[q][0]+offs[i][0],hull[q][1]+offs[i][1]]);g=grp(ships,'ship'+i);addPath(g,'p',hp,true);addFill(g,IVORY);}
var ep=ships.property('ADBE Effect Parade');var ua=ep.addProperty('ADBE Slider Control');ua.name='uA';var ub=ships.property('ADBE Effect Parade').addProperty('ADBE Slider Control');ub.name='uB';
K(ships.property('ADBE Effect Parade').property('uA').property(1),[[43.0,0],[45.2,30]],60);
K(ships.property('ADBE Effect Parade').property('uB').property(1),[[46.3,0],[50.5,100]],55);
var exprPath='var A=thisComp.layer("ROUTE OLD").content("g").content("p").path;var B=thisComp.layer("ROUTE NEW").content("g").content("p").path;var u1=effect("uA")(1)/100,u2=Math.min(effect("uB")(1)/100,0.999);';
tr(ships,'ADBE Position').expression=exprPath+'time<45.9?A.pointOnPath(u1):B.pointOnPath(u2);';
tr(ships,'ADBE Rotate Z').expression=exprPath+'function ang(t){return Math.atan2(t[1],t[0])*180/Math.PI;}var a1=ang(A.tangentOnPath(u1)),a2=ang(B.tangentOnPath(Math.max(u2,0.001)));var d=a2-a1;if(d>180)d-=360;if(d<-180)d+=360;var k=ease(time,45.6,46.3,0,1);time<46.3?a1+d*k:a2;';
fade(ships,41.8,53.6,.3,.5);
var S7copy=T('정보는 항로를 바꿨다.',CX,1480,64,IVORY,KR,50.8,52.9);fade(S7copy,50.8,52.9,.35);

// ================= S8 · CALLBACK 53–60 =================
var straight=lerpPts([-140+CX,900],[140+CX,900],4);
(function(){var p=pathProp(nw,'g','p');p.setValueAtTime(53.4,mkShape(NR,false,nt.i,nt.o));p.setValueAtTime(54.6,mkShape(straight,false));easeAll(p,78);})();
O(nw,[[45.2,100],[55.15,100],[55.3,0]],'linear');span(nw,45.2,55.3);
var nHead=lineLayer('ROUTE HEAD',CX,900,[[108,-32],[142,0],[108,32]],LIME,8,54.4,55.3);O(nHead,[[54.4,0],[54.6,100],[55.15,100],[55.3,0]],'linear');
var endA=T('A',270,900,240,IVORY,LAT,54.6,59.6,{name:'END A (left)'}),endB=T('A',810,900,240,IVORY,LAT,54.6,59.6,{name:'END A (right)'});
fade(endA,54.6,59.6,.35,.6);fade(endB,54.6,59.6,.35,.6);
K(tr(endB,'ADBE Position'),[[55.2,[810,900]],[55.25,[826,900]],[55.31,[798,900]],[55.37,[816,900]],[55.45,[810,900]]],40);
var eL=lineLayer('END THREAD L',CX,900,Lbreak,IVORY,10,55.15,59.6),eR=lineLayer('END THREAD R',CX,900,Rbreak,IVORY,10,55.15,59.6),eH=lineLayer('END HEAD',CX,900,[[108,-32],[142,0],[108,32]],IVORY,10,55.15,59.6);
var eGL=lineLayer('END GAP L',CX,900,[[-GAP,-30],[-GAP,30]],LIME,8,55.2,60),eGR=lineLayer('END GAP R',CX,900,[[GAP,-30],[GAP,30]],LIME,8,55.2,60);
K(tr(eGL,'ADBE Scale'),[[55.2,[100,0]],[55.35,[100,100]]],50);K(tr(eGR,'ADBE Scale'),[[55.2,[100,0]],[55.35,[100,100]]],50);
fadeOutAll([eL,eR,eH],59.0,59.6);fadeOutAll([eGL,eGR],59.45,59.97);
var c8a=T('하나는 불가능했다.',CX,1480,64,IVORY,KR,55.6,57.3);fade(c8a,55.6,57.3,.35,.3);
var c8b=T('그 하나가 빈틈이었다.',CX,1480,64,IVORY,KR,57.4,59.6);fade(c8b,57.4,59.6,.35,.5);

// grain + audio
var gr=M.layers.addSolid([.5,.5,.5],'GRAIN',W,H,1,DUR);try{var nz=gr.property('ADBE Effect Parade').addProperty('ADBE Noise');nz.property(1).setValue(6);}catch(x){}gr.blendingMode=BlendingMode.OVERLAY;tr(gr,'ADBE Opacity').setValue(7);
var au=new File(R+'/soundtrack.wav');if(au.exists){var al=M.layers.add(app.project.importFile(new ImportOptions(au)));al.name='SOUNDTRACK';span(al,0,DUR);}

app.project.save(new File(R+'/enigma-v5.aep'));M.openInViewer();
log('layers='+M.numLayers);
var f=new File(R+'/built.json');f.encoding='UTF-8';f.open('w');f.write('{"status":"saved","ae":"'+app.version+'","layers":'+M.numLayers+',"log":'+LOG.toSource()+'}');f.close();
}catch(e){var f2=new File(R+'/built.json');f2.encoding='UTF-8';f2.open('w');f2.write('{"status":"error","error":"'+String(e).replace(/"/g,"'")+'","line":'+e.line+',"log":'+LOG.toSource()+'}');f2.close();}
})();
