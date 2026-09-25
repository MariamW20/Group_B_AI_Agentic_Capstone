/**
 * Week 4 architecture: current PNG source, geometry checks and local rendering.
 * Run: node docs/architecture/build-week4-architecture.mjs
 * Check only: node docs/architecture/build-week4-architecture.mjs --check
 * No network or model requests. Requires a local Chromium browser to render.
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
const DIR = path.dirname(fileURLToPath(import.meta.url));
const W = 2800, H = 2340;
const nodes = new Map(), edges = [], labels = [];
const esc = s => String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
function node(id,x,y,w,h,title,body=[],opts={}) {
  nodes.set(id,{id,x,y,w,h,title,body,...opts});
}
function joint(id,x,y) { nodes.set(id,{id,x,y,w:0,h:0,junction:true}); }
function p(id,side="c",offset) {
  const n=nodes.get(id); if(!n) throw Error("Unknown node "+id);
  if(n.junction) return [n.x,n.y];
  if(side==="t") return [offset??n.x+n.w/2,n.y];
  if(side==="b") return [offset??n.x+n.w/2,n.y+n.h];
  if(side==="l") return [n.x,offset??n.y+n.h/2];
  if(side==="r") return [n.x+n.w,offset??n.y+n.h/2];
  throw Error("A node connector must attach to its boundary");
}
function edge(a,b,opts={}) {
  const [aid,as,ao]=a, [bid,bs,bo]=b;
  edges.push({a:aid,b:bid,points:[p(aid,as,ao),...(opts.via??[]),p(bid,bs,bo)],arrow:true,...opts});
}
function label(x,y,text,opts={}) { labels.push({x,y,text,...opts}); }

// The Week 2 route is an independent, implemented request/response path.
node("client",110,330,410,112,"API client",["Test customer message","Reply or HTTP error"],{role:"entry"});
node("api",710,330,460,112,"Express /api/chat",["Validate message; map errors","Return reply + latencyMs"]);
node("service",1370,330,530,112,"geminiService.js",["Versioned system prompt","Model call, timeout and latency"]);
node("gemini",2160,330,470,112,"Gemini API",["Foundation-model response"],{role:"external"});
edge(["client","r"],["api","l"],{twoWay:true});
edge(["api","r"],["service","l"],{twoWay:true});
edge(["service","r"],["gemini","l"],{twoWay:true});
label(615,365,"message / reply");
label(1270,365,"askGemini / text");
label(2030,365,"request / response");

// Week 3: RAG builds messages and a source trace. It does not call the LLM.
node("corpus",115,755,520,110,"Controlled FAQ corpus",["24 registered evaluation records","Selected from the CSV seed"],{role:"source"});
node("ingest",115,945,520,110,"Ingest and chunk",["Documents + provenance","200 words; 30-word overlap"]);
node("index",115,1135,520,110,"TF-IDF index",["Unigrams / bigrams","Cosine similarity"]);
node("retrieve",115,1325,520,110,"Retrieve for a question",["Top k = 4; minimum score = 0.05","Query + indexed chunks"]);
node("context",115,1515,520,110,"Build grounded context",["[S1] source markers and evidence","No evidence: instruct abstention"]);
node("messages",115,1705,520,125,"RagAnswerContext",["messages + retrieved sources","No model call inside pipeline.py"]);
node("evidence",115,1910,520,125,"Retrieval evaluation evidence",["Saved sources, scores and prompts","evidence/traces/rag-evaluation.json"],{role:"sink"});
for(const [a,b] of [["corpus","ingest"],["ingest","index"],["index","retrieve"],["retrieve","context"],["context","messages"],["messages","evidence"]])
  edge([a,"b"],[b,"t"]);
label(505,900,"load / segment");
label(505,1090,"build index");
label(505,1280,"search");
label(505,1470,"matching chunks");
label(505,1660,"package");
label(505,1870,"evaluation saves");

// Week 4 demo caller and trusted application-context fixtures.
node("caller",1130,755,800,118,"Demo caller / test harness",["demo.py and tests/week4","call(tool_name, arguments, CallerContext)"],{role:"entry"});
node("identity",2160,755,470,118,"Trusted context fixture",["auth_level + customer_id","human_approved + approval token"],{role:"source"});
edge(["identity","l"],["caller","r"]);
label(2045,788,"supplies");
node("guard",1130,965,1120,218,"ToolOrchestrator.call: pre-execution checks",[
 "1  Resolve the registered tool; reject unknown names.",
 "2  Bind session / approval fields; reject argument overrides.",
 "3  Validate required fields, types, enums, bounds and auth_level.",
 "4  For higher-impact calls, require human_approved = True."
],{leftText:true});
edge(["caller","b",1690],["guard","t",1690]);
label(1800,920,"request");

// Dispatch uses explicit junctions; every branch meets its own tool.
joint("d1",1080,1260);joint("d2",1500,1260);joint("dc",1690,1260);
joint("d3",1920,1260);joint("d4",2340,1260);
edge(["guard","b",1690],["dc"]);
for(const [a,b] of [["d1","d2"],["d2","dc"],["dc","d3"],["d3","d4"]])
  edge([a],[b],{arrow:false});
label(1950,1220,"permitted call: select one registered function");
node("status",900,1350,360,140,"get_service_status",["auth_level >= 1","Read synthetic service status"],{code:true});
node("lookup",1320,1350,360,140,"get_ticket_status",["auth_level >= 2","Enforce ticket ownership"],{code:true});
node("create",1740,1350,360,140,"create_support_ticket",["auth_level >= 2","Low-risk simulated write"],{code:true});
node("escalate",2160,1350,360,140,"escalate_support_case",["auth_level >= 2 + approval","Match and consume valid token"],{code:true});
for(const [j,n] of [["d1","status"],["d2","lookup"],["d3","create"],["d4","escalate"]])
  edge([j],[n,"t"]);

// Backend accesses and returned outcomes use different ports and corridors.
node("services",935,1570,330,112,"Service-status data",["Six supported services","Demo values only"],{role:"store"});
node("tickets",1390,1570,690,112,"Shared in-memory ticket_store",["Lookup reads; creation writes this same dictionary","No live customer accounts"],{role:"store"});
node("approval",2190,1570,350,112,"Approval map + case list",["Exact approved request match","Simulated team assignment"],{role:"store"});
edge(["status","b",1100],["services","t",1100],{twoWay:true});
edge(["lookup","b",1500],["tickets","t",1500],{twoWay:true});
edge(["create","b",1920],["tickets","t",1920],{twoWay:true});
edge(["escalate","b",2350],["approval","t",2350],{twoWay:true});
label(1190,1530,"read"); label(1570,1530,"read");label(2000,1530,"write");label(2440,1530,"verify / write");

joint("r1",875,1770);joint("r2",1340,1770);joint("rc",1690,1770);joint("r3",2120,1770);joint("r4",2570,1770);
edge(["status","l",1420],["r1"],{via:[[875,1420]],arrow:false});
edge(["lookup","b",1340],["r2"],{arrow:false});
edge(["create","r",1420],["r3"],{via:[[2120,1420]],arrow:false});
edge(["escalate","r",1420],["r4"],{via:[[2570,1420]],arrow:false});
for(const [a,b] of [["r1","r2"],["r2","rc"],["rc","r3"],["r3","r4"]])
  edge([a],[b],{arrow:false});
label(1960,1740,"returned result / execution exception");
node("outcome",1130,1855,1120,160,"Execution and output handling",[
 "Catch execution exceptions as service_unavailable.",
 "Validate returned fields / types; malformed -> unexpected_response.",
 "Otherwise wrap the result with status = success."
],{leftText:true});
edge(["rc"],["outcome","t",1690]);
node("result",1130,2110,1120,125,"Return structured outcome to caller",[
 "status + result.status_code, or error_type / pending_approval",
 "Demo prints outcomes; automated tests assert behaviour."
]);
edge(["outcome","b",1690],["result","t",1690]);
label(1890,2065,"validated outcome");
edge(["guard","r",1074],["result","r",2170],{via:[[2670,1074],[2670,2170]]});
label(2470,1018,["Rejected / waiting","unknown, invalid, unauthorized","or pending_approval"],{size:20});
edge(["result","l",2170],["caller","l",814],{via:[[840,2170],[840,814]]});
label(985,790,"returned dict");

// Planned integrations are distinct from implemented edges and land on nodes.
edge(["messages","r",1765],["service","b",1500],{planned:true,via:[[740,1765],[740,555],[1500,555]]});
label(1060,529,"PLANNED: grounded messages into chat",{size:22});
edge(["service","b",1770],["caller","t",1690],{planned:true,via:[[1770,590],[1690,590]]});
label(2190,575,"PLANNED: model function-call adapter",{size:22});

function isBoundary(n,q) {
 if(n.junction) return q[0]===n.x && q[1]===n.y;
 const [x,y]=q;
 return ((x===n.x||x===n.x+n.w)&&y>=n.y&&y<=n.y+n.h)||
        ((y===n.y||y===n.y+n.h)&&x>=n.x&&x<=n.x+n.w);
}
function overlap(a,b) {return a.x<b.x+b.w && a.x+a.w>b.x && a.y<b.y+b.h && a.y+a.h>b.y;}
function interiorHit(a,b,n) {
 if(a[0]===b[0]) return a[0]>n.x && a[0]<n.x+n.w && Math.max(a[1],b[1])>n.y && Math.min(a[1],b[1])<n.y+n.h;
 return a[1]>n.y && a[1]<n.y+n.h && Math.max(a[0],b[0])>n.x && Math.min(a[0],b[0])<n.x+n.w;
}
function intersection(a,b,c,d) {
 const ah=a[1]===b[1], ch=c[1]===d[1];
 if(ah===ch) {
  const axis=ah?0:1, fixed=1-axis;
  if(a[fixed]!==c[fixed]) return null;
  const lo=Math.max(Math.min(a[axis],b[axis]),Math.min(c[axis],d[axis]));
  const hi=Math.min(Math.max(a[axis],b[axis]),Math.max(c[axis],d[axis]));
  if(hi<lo) return null;
  if(hi>lo) return "overlap";
  return ah?[lo,a[fixed]]:[a[fixed],lo];
 }
 if(!ah) return intersection(c,d,a,b);
 const x=c[0],y=a[1];
 return x>=Math.min(a[0],b[0])&&x<=Math.max(a[0],b[0])&&y>=Math.min(c[1],d[1])&&y<=Math.max(c[1],d[1])?[x,y]:null;
}
function validate() {
 const boxes=[...nodes.values()].filter(n=>!n.junction);
 for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++)
   if(overlap(boxes[i],boxes[j]))throw Error("Overlapping boxes: "+boxes[i].id+" / "+boxes[j].id);
 for(const e of edges) {
  if(!isBoundary(nodes.get(e.a),e.points[0])||!isBoundary(nodes.get(e.b),e.points.at(-1))) throw Error("Floating endpoint: "+e.a+" -> "+e.b);
  for(let i=1;i<e.points.length;i++) {
   const a=e.points[i-1],b=e.points[i];
   if(a[0]!==b[0]&&a[1]!==b[1])throw Error("Non-orthogonal route "+e.a+" -> "+e.b);
   for(const n of boxes)if(interiorHit(a,b,n))throw Error("Route crosses box "+n.id+" on "+e.a+" -> "+e.b);
  }
 }
 for(let i=0;i<edges.length;i++)for(let j=i+1;j<edges.length;j++) {
  const e=edges[i],f=edges[j],common=[e.a,e.b].filter(id=>[f.a,f.b].includes(id)&&nodes.get(id).junction);
  for(let a=1;a<e.points.length;a++)for(let b=1;b<f.points.length;b++) {
   const q=intersection(e.points[a-1],e.points[a],f.points[b-1],f.points[b]);
   if(q===null)continue;
   if(q!=="overlap"&&common.some(id=>{const n=nodes.get(id);return n.x===q[0]&&n.y===q[1];}))continue;
   throw Error("Connector crossing: "+e.a+" -> "+e.b+" / "+f.a+" -> "+f.b+" at "+JSON.stringify(q));
  }
 }
 // Every non-junction node participates; tools receive approved calls and return outcomes.
 for(const n of boxes)if(!edges.some(e=>e.a===n.id||e.b===n.id))throw Error("Unconnected node "+n.id);
 for(const id of ["status","lookup","create","escalate"]) {
  if(!edges.some(e=>e.b===id)||!edges.some(e=>e.a===id))throw Error("Incomplete tool "+id);
 }
 console.log("Geometry PASS: "+boxes.length+" boxes; "+edges.length+" connectors; all endpoints attached; zero box overlaps, route/box collisions or unintended connector crossings.");
}
validate();
if(process.argv.includes("--check"))process.exit(0);

const text=(x,y,s,size=24,weight=400,anchor="middle")=>'<text x="'+x+'" y="'+y+'" text-anchor="'+anchor+'" font-size="'+size+'" font-weight="'+weight+'" fill="#000">'+esc(s)+'</text>';
let svg='<svg xmlns="http://www.w3.org/2000/svg" width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'"><rect width="100%" height="100%" fill="#fff"/><g font-family="Arial, sans-serif">';
svg+=text(70,72,"CENTENARY BANK CUSTOMER SUPPORT AI",46,700,"start");
svg+=text(70,118,"Week 4 architecture | Tools, authorization and human approval",29,400,"start");
svg+=text(2730,70,"GROUP B / BSE4104",25,700,"end");
svg+=text(2730,112,"Walusimbi Ashraf | Task 123tp5x7wt6",23,400,"end");
svg+='<path d="M70 148H2730" stroke="#000" stroke-width="2"/>';
svg+=text(70,193,"Solid: implemented call / data flow   |   Double arrows: request + response   |   Dashed: planned integration",23,400,"start");
const panel=(x,y,w,h,title,subtitle)=>'<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="#fff" stroke="#000" stroke-width="2"/>'+text(x+25,y+38,title,26,700,"start")+(subtitle?text(x+25,y+70,subtitle,20,400,"start"):"");
svg+=panel(60,235,2680,255,"01  MODEL INTERACTION / WEEK 2","Existing Node.js baseline: this chat route does not invoke the Python RAG or tool modules.");
svg+=panel(60,650,630,1605,"02  KNOWLEDGE / WEEK 3","RAG build, query and evidence pipeline");
svg+=panel(800,650,1940,1605,"03  CONTROLLED TOOL CALLING / WEEK 4","Python implementation; service data, caller identity, approvals and side effects are fixtures.");
for(const n of nodes.values()) {
 if(n.junction)continue;
 svg+='<rect x="'+n.x+'" y="'+n.y+'" width="'+n.w+'" height="'+n.h+'" fill="#fff" stroke="#000" stroke-width="2.6"/>';
 const lineHeight=n.leftText?32:27;
 const bodySize=n.code?21:22;
 const titleSize=n.code?24:26;
 const total=titleSize+n.body.length*lineHeight+12;
 const first=n.y+(n.h-total)/2+titleSize*0.78;
 svg+=text(n.leftText?n.x+30:n.x+n.w/2,first,n.title,titleSize,700,n.leftText?"start":"middle");
 n.body.forEach((s,i)=>svg+=text(n.leftText?n.x+30:n.x+n.w/2,first+8+(i+1)*lineHeight,s,bodySize,400,n.leftText?"start":"middle"));
}
function arrowHead(from,to) {
 const ang=Math.atan2(to[1]-from[1],to[0]-from[0]),sz=13;
 const l=[to[0]-sz*Math.cos(ang-.43),to[1]-sz*Math.sin(ang-.43)];
 const r=[to[0]-sz*Math.cos(ang+.43),to[1]-sz*Math.sin(ang+.43)];
 return '<polygon points="'+[to,l,r].map(q=>q.join(",")).join(" ")+'" fill="#000"/>';
}
for(const e of edges) {
 svg+='<polyline points="'+e.points.map(q=>q.join(",")).join(" ")+'" fill="none" stroke="#000" stroke-width="2.4"'+(e.planned?' stroke-dasharray="12 9"':"")+'/>';
 if(e.arrow)svg+=arrowHead(e.points.at(-2),e.points.at(-1));
 if(e.twoWay)svg+=arrowHead(e.points[1],e.points[0]);
}
for(const n of nodes.values())if(n.junction)svg+='<circle cx="'+n.x+'" cy="'+n.y+'" r="4.5" fill="#000"/>';
for(const l of labels) {
 const lines=Array.isArray(l.text)?l.text:[l.text], size=l.size??21;
 lines.forEach((s,i)=>svg+=text(l.x,l.y+i*(size+7),s,size,400));
}
svg+=text(90,2105,"RAG output is context and source evidence.",22,400,"start");
svg+=text(90,2143,"The dashed link is not implemented in chat.",22,400,"start");
svg+=text(90,2181,"Empty context gives an abstention instruction;",22,400,"start");
svg+=text(90,2219,"it does not prove the model will abstain.",22,400,"start");
svg+=text(70,2305,"No live bank access or real handoff. Persistent memory, audit storage and the autonomous loop remain future work.",22,400,"start");
svg+=text(2730,2305,"Code baseline: 4d511f0",21,400,"end");
svg+='</g></svg>';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),"week4-architecture-"));
const html=path.join(temp,"architecture.html");
const svgFile=path.join(temp,"architecture.svg");
fs.writeFileSync(svgFile,svg);
fs.writeFileSync(html,'<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:white;width:'+W+'px;height:'+H+'px}svg{display:block}</style>'+svg);
const browser=process.env.ARCHITECTURE_BROWSER??[
"C:/Program Files/Google/Chrome/Application/chrome.exe",
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
].find(p=>fs.existsSync(p));
if(!browser)throw Error("Set ARCHITECTURE_BROWSER to a local Chromium executable.");
const output=path.join(DIR,"agentarchitecture-week4-final.png");
const result=spawnSync(browser,["--headless","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=1","--no-first-run","--no-default-browser-check","--user-data-dir="+path.join(temp,"profile"),"--screenshot="+output,"--window-size="+W+","+H,"file:///"+html.replaceAll("\\","/")],{encoding:"utf8",timeout:60000,windowsHide:true});
if(result.status!==0)throw Error("Rendering failed: "+(result.error??result.stderr));
console.log("Rendered "+output);
console.log("Temporary render workspace: "+temp);
