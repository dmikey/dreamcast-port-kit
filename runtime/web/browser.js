'use strict';
const status=document.querySelector('#status'),log=document.querySelector('#log');
// Bounded diagnostic history. Rendering logs is batched outside the hot path.
class DiagnosticRing {
 constructor(capacity){this.capacity=capacity;this.slots=new Array(capacity);this.total=0;}
 push(message,time){const event={sequence:this.total,timeMs:time,kind:message.match(/^\[([^\]]+)\]/)?.[1]||'runtime',message};this.slots[this.total++%this.capacity]=event;return event;}
 snapshot(){const start=Math.max(0,this.total-this.capacity);return Array.from({length:this.total-start},(_,i)=>this.slots[(start+i)%this.capacity]);}
 get dropped(){return Math.max(0,this.total-this.capacity);}
}
const diagnostics=new DiagnosticRing(2048);
let logDirty=false,lastProgress=0,freezeReported=false;
function flushLog(){if(!logDirty)return;const details=document.querySelector('details');if(!details.open&&!status.textContent.startsWith('Execution stopped'))return;log.textContent=diagnostics.snapshot().slice(-350).map(e=>e.message).join('\n');log.scrollTop=log.scrollHeight;logDirty=false;}
function output(...parts){
 const text=parts.join(' '),now=performance.now();diagnostics.push(text,now);logDirty=true;
 if(text.includes('[MATERIAL]')){const samples=document.querySelector('#render-log');if(samples)samples.textContent+=text+'\n';}
 if(text.includes('[FRAME]')||text.includes('[HEARTBEAT]')){lastProgress=now;freezeReported=false;}
 if(text.includes('[DISPATCH] unresolved')||text.includes('[UNIMPLEMENTED]')){status.textContent='Execution stopped: '+text;flushLog();}
 if(text.includes('entering title code'))status.textContent='Running original game code. Local development build.';
 if(!text.startsWith('[STARTUP]')&&(/\[PVR2\] Shader (compile|link) error/.test(text)||/\[PLATFORM\].*failed:/.test(text)))startupFailure(text);
}
setInterval(()=>{flushLog();if(runtimeReady&&lastProgress&&!freezeReported&&performance.now()-lastProgress>4000){freezeReported=true;output('[WATCHDOG] No execution progress for 4 seconds.');}},250);
let runtimeReady=false,buildInfo=null;
function reportStartup(reason){
 if(typeof fetch!=='function')return;
 const payload={schemaVersion:1,reason:String(reason).slice(0,1000),userAgent:navigator.userAgent||'',runtimeReady,events:diagnostics.snapshot().slice(-40).map(e=>({kind:e.kind,message:e.message.slice(0,1000)}))};
 fetch('/diagnostics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(()=>{});
}
function startupFailure(reason){const error=document.querySelector('#runtime-error');error.hidden=false;error.textContent='Game could not start: '+reason;output('[STARTUP] '+reason);reportStartup(reason);}
var Module={onRuntimeInitialized:()=>{runtimeReady=true;reportStartup('Runtime initialized');},canvas:document.querySelector('#canvas'),print:output,printErr:output,setStatus:text=>{if(text)status.textContent=text;},onAbort:reason=>{status.textContent='Execution stopped. See runtime output.';output('Runtime aborted:',reason);}};
Module.onAbort=reason=>startupFailure(String(reason));
Module.onExit=code=>{if(code)startupFailure('Runtime exited with code '+code+'. Expand Runtime output for details.');};
Module.portAudioPush=samples=>{if(typeof portAudio!=='undefined')portAudio.push(samples);};
Module.portBrowserYield=()=>typeof portBrowserScheduler!=='undefined'?portBrowserScheduler.yield():new Promise(resolve=>setTimeout(resolve,0));
document.querySelector('#start').addEventListener('click',()=>{
 if(typeof WebAssembly==='undefined'){startupFailure('This browser does not provide WebAssembly.');return;}
 if(typeof WebGL2RenderingContext==='undefined'){startupFailure('WebGL 2 is unavailable. Check Safari’s graphics settings.');return;}
 if(typeof portAudio!=='undefined')portAudio.start().catch(error=>{output('[AUDIO] '+error.message);reportStartup('Audio: '+error.message);});
 if(typeof fetch==='function')fetch('build.json').then(response=>response.json()).then(info=>{buildInfo=info;}).catch(()=>{});
 document.querySelector('#start').disabled=true;status.textContent='Loading browser runtime…';reportStartup('Starting runtime');const script=document.createElement('script');script.src='game.js';script.addEventListener('error',()=>startupFailure('The game runtime script could not load.'));document.body.append(script);Module.canvas.focus();
});

// One browser input owner combines keyboard, touch and the standard Gamepad API.
const keys=new Set(),touch=new Set();
const keyButtons={Enter:8,KeyZ:4,KeyX:2,KeyA:1024,KeyS:512,ArrowUp:16,ArrowDown:32,ArrowLeft:64,ArrowRight:128};
const gamepadButtons={0:4,1:2,2:1024,3:512,9:8,12:16,13:32,14:64,15:128};
const gameBits=[2,4,8,16,32,64,128,512,1024];
let inputActive=document.hasFocus(),lastController='',lastInput='';
let stickX=0,stickY=0,stickPointer=null;
const controllerStatus=document.querySelector('#controller');
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
function stick(v){const n=Number.isFinite(v)?clamp(v,-1,1):0;return Math.abs(n)<.15?0:Math.sign(n)*(Math.abs(n)-.15)/.85;}
function controllerFrame(){
 let bits=0,left=0,right=0,x=0,y=0;
 let pads=[];try{pads=navigator.getGamepads?Array.from(navigator.getGamepads()):[];}catch{}
 const pad=pads.find(p=>p&&p.connected&&p.mapping==='standard');
 const other=pads.find(p=>p&&p.connected);
 const name=pad?'Controller connected: '+pad.id:other?'Controller detected; standard mapping unavailable. Use keyboard or touch.':'Controller: connect a gamepad and press a button.';
 if(name!==lastController){controllerStatus.textContent=name;lastController=name;}
 if(inputActive){
  for(const code of keys)bits|=keyButtons[code]||0;
  for(const b of document.querySelectorAll('[data-bit]'))if(touch.has(b))bits|=Number(b.dataset.bit);
  const held=name=>Array.from(touch).some(b=>b.dataset.axis===name);
  left=keys.has('KeyQ')||held('brake')?255:0;right=keys.has('KeyW')||held('gas')?255:0;
  x=(keys.has('ArrowRight')||held('right')?127:0)-(keys.has('ArrowLeft')||held('left')?127:0);
  if(!x)x=stickX;y=stickY;
  if(!x)x=(bits&128?127:0)-(bits&64?127:0);
  if(pad){
   for(const [i,bit] of Object.entries(gamepadButtons))if(pad.buttons[i]?.pressed)bits|=bit;
   left=Math.max(left,Math.round(clamp(pad.buttons[6]?.value||0,0,1)*255));
   right=Math.max(right,Math.round(clamp(pad.buttons[7]?.value||0,0,1)*255));
   if(!x)x=Math.round(stick(pad.axes[0])*127);
   if(!y)y=Math.round(stick(pad.axes[1])*127);
   if(!x)x=(bits&128?127:0)-(bits&64?127:0);
  }
 }
 if(runtimeReady&&Module._port_axes&&Module._port_button){
  for(const bit of gameBits)Module._port_button(bit,(bits&bit)?1:0);
  Module._port_axes(left,right,x,y);
  const signature=[bits,left,right,x,y].join(',');
  if(signature!==lastInput){lastInput=signature;document.querySelector('#canvas').dataset.input=signature;}
 }
 requestAnimationFrame(controllerFrame);
}
function release(){resetStick();inputActive=false;keys.clear();touch.clear();for(const b of document.querySelectorAll('[aria-pressed]'))b.setAttribute('aria-pressed','false');if(runtimeReady&&Module._port_axes){Module._port_axes(0,0,0,0);for(const bit of gameBits)Module._port_button(bit,0);}}
window.addEventListener('keydown',event=>{if(keyButtons[event.code]||['KeyQ','KeyW'].includes(event.code)){event.preventDefault();inputActive=true;keys.add(event.code);}});
window.addEventListener('keyup',event=>keys.delete(event.code));
window.addEventListener('blur',release);window.addEventListener('focus',()=>inputActive=true);
document.addEventListener('visibilitychange',()=>{if(document.hidden)release();else inputActive=document.hasFocus();});
for(const button of document.querySelectorAll('[data-bit],[data-axis]')){
 button.setAttribute('aria-pressed','false');
 const up=()=>{touch.delete(button);button.setAttribute('aria-pressed','false');};
 button.addEventListener('pointerdown',event=>{event.preventDefault();inputActive=true;button.setPointerCapture(event.pointerId);touch.add(button);button.setAttribute('aria-pressed','true');});
 for(const name of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(name,up);
 // Keyboard/assistive clicks have no pointer hold; give them a short press.
 button.addEventListener('click',event=>{if(!touch.has(button)){inputActive=true;touch.add(button);button.setAttribute('aria-pressed','true');setTimeout(up,200);}});
}
requestAnimationFrame(controllerFrame);

window.addEventListener('error',event=>startupFailure(event.message||'A browser script failed.'));
window.addEventListener('unhandledrejection',event=>startupFailure(String(event.reason)));

const stickElement=document.querySelector('#stick'),stickKnob=stickElement.querySelector('span');
function resetStick(){stickX=0;stickY=0;stickPointer=null;if(stickKnob)stickKnob.style.transform='translate(0,0)';}
function moveStick(event){const r=stickElement.getBoundingClientRect(),radius=r.width/2;let x=(event.clientX-r.left-radius)/radius,y=(event.clientY-r.top-radius)/radius;const length=Math.hypot(x,y);if(length>1){x/=length;y/=length;}stickX=Math.round(x*127);stickY=Math.round(y*127);stickKnob.style.transform=`translate(${x*radius*.55}px,${y*radius*.55}px)`;}
stickElement.addEventListener('pointerdown',event=>{if(stickPointer!==null)return;event.preventDefault();inputActive=true;stickPointer=event.pointerId;stickElement.setPointerCapture(event.pointerId);moveStick(event);});
stickElement.addEventListener('pointermove',event=>{if(event.pointerId===stickPointer)moveStick(event);});
for(const name of ['pointerup','pointercancel','lostpointercapture'])stickElement.addEventListener(name,event=>{if(event.pointerId===stickPointer)resetStick();});
document.querySelector('#toggle-pad').addEventListener('click',event=>{const pad=document.querySelector('#touch-pad');pad.hidden=!pad.hidden;event.currentTarget.setAttribute('aria-pressed',String(!pad.hidden));event.currentTarget.textContent='On-screen controls: '+(pad.hidden?'off':'on');touch.clear();resetStick();});

document.querySelector('#capture-render').addEventListener('click',()=>{if(runtimeReady&&Module._port_render_capture){document.querySelector('#render-log').textContent='';Module._port_render_capture();}});

document.querySelector('details').addEventListener('toggle',flushLog);
document.querySelector('#download-diagnostics').addEventListener('click',()=>{
 const report={schemaVersion:1,source:'dreamcast-port-kit browser runtime',userAgent:navigator.userAgent||'',build:buildInfo,status:status.textContent,eventsDropped:diagnostics.dropped,events:diagnostics.snapshot(),audioOutputImplemented:true,audio:typeof portAudio==='undefined'?null:{...portAudio.stats,received:portAudio.received,nonzeroReceived:portAudio.nonzero,contextState:portAudio.context?.state,muted:portAudio.muted}};
 const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='dreamcast-diagnostics.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
