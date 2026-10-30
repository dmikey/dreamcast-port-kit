/* The original executable, ARM7, hardware, texture decode and GL run here. */
'use strict';
var Module;let ready=false,started=false,lastInput=null,logs=[],paused=false,resumeWorker=null;
function flushLogs(){if(logs.length){postMessage({kind:'logs',lines:logs});logs=[];}}
function log(...parts){if(logs.length<512)logs.push(parts.join(' '));}
function fail(reason){flushLogs();postMessage({kind:'error',message:String(reason)});}
let pulseTimer=null,replayTimers=[],benchmarkTimer=null;
function cancelReplay(){for(const timer of replayTimers)clearTimeout(timer);replayTimers=[];}
function endPulse(){if(pulseTimer!==null){clearTimeout(pulseTimer);pulseTimer=null;}lastInput=[0,0,0,0,0];applyInput();}
function applyInput(){if(ready&&lastInput&&Module._port_input){const bits=Module._port_input(...lastInput);postMessage({kind:"input-applied",bits,values:lastInput});}}
self.onmessage=event=>{
 const data=event.data;
 if(data.kind==='start'){
  if(started)return;started=true;
  try{
   if(!(data.canvas instanceof OffscreenCanvas))throw new Error('A transferred OffscreenCanvas is required.');
   Module={canvas:data.canvas,
    preRun:[()=>{GL.offscreenCanvases.canvas=Module.canvas;}],
    print:log,printErr:log,
    onRuntimeInitialized:()=>{ready=true;postMessage({kind:'ready'});applyInput();},
    onAbort:fail,onExit:code=>{if(code)fail('Worker runtime exited with code '+code);},
    portAudioPush:samples=>postMessage({kind:'audio',samples},[samples.buffer]),
    portBrowserYield:async()=>{flushLogs();if(paused)await new Promise(resolve=>resumeWorker=resolve);return portBrowserScheduler.yield();}
   };
   importScripts('browser-scheduler.js','game.js');
  }catch(error){fail(error.stack||error.message||error);}
 }else if(data.kind==='pause'&&ready){
  paused=!!data.value;if(paused){cancelReplay();endPulse();if(benchmarkTimer!==null){clearTimeout(benchmarkTimer);benchmarkTimer=null;log('[BENCHMARK] cancelled by pause');}}else if(resumeWorker){const resume=resumeWorker;resumeWorker=null;resume();}log('[RUNTIME] '+(paused?'paused':'resumed'));
 }else if(data.kind==='replay'&&ready&&!paused){
  const steps=data.steps;
  if(!Array.isArray(steps)||steps.length>128||!steps.every(s=>s&&Number.isFinite(s.atMs)&&s.atMs>=0&&s.atMs<=180000&&Array.isArray(s.values)&&s.values.length===5&&s.values.every(Number.isInteger)&&s.values[0]>=0&&s.values[0]<=65535&&s.values[1]>=0&&s.values[1]<=255&&s.values[2]>=0&&s.values[2]<=255&&s.values[3]>=-128&&s.values[3]<=127&&s.values[4]>=-128&&s.values[4]<=127)||steps.some((s,i)=>i&&s.atMs<steps[i-1].atMs)){log('[INPUT-REPLAY] Invalid replay');return;}
  cancelReplay();endPulse();const start=performance.now();
  for(const step of steps)replayTimers.push(setTimeout(()=>{lastInput=step.values.slice();applyInput();log('[INPUT-REPLAY] at='+Math.round(performance.now()-start)+' values='+lastInput.join(','));},step.atMs));
  const last=steps.length?steps[steps.length-1].atMs:0;replayTimers.push(setTimeout(()=>{replayTimers=[];lastInput=[0,0,0,0,0];applyInput();log('[INPUT-REPLAY] complete');},last+1000));
 }else if(data.kind==='benchmark'&&ready&&!paused&&benchmarkTimer===null&&Module._port_frame_count){
  const start=performance.now(),frame=Module._port_frame_count();log('[BENCHMARK] started 30-second presentation count');
  benchmarkTimer=setTimeout(()=>{benchmarkTimer=null;const durationMs=performance.now()-start,frames=Module._port_frame_count()-frame;postMessage({kind:'benchmark',result:{durationMs,frames,fps:frames*1000/durationMs,metric:'platform presentations',execution:'dedicated-worker',gpuCompletionMeasured:false}});},30000);
 }else if(data.kind==='pulse'&&ready){
  cancelReplay();
  if(!Array.isArray(data.values)||data.values.length!==5||!data.values.every(Number.isFinite)||!Number.isFinite(data.duration)||data.duration<16||data.duration>60000)return;
  endPulse();const v=data.values;lastInput=[v[0]&0xffff,Math.max(0,Math.min(255,v[1]|0)),Math.max(0,Math.min(255,v[2]|0)),Math.max(-128,Math.min(127,v[3]|0)),Math.max(-128,Math.min(127,v[4]|0))];applyInput();
  log('[INPUT-REPLAY] hold '+lastInput.join(',')+' for '+data.duration+'ms');pulseTimer=setTimeout(()=>{pulseTimer=null;lastInput=[0,0,0,0,0];applyInput();log('[INPUT-REPLAY] released');},data.duration);
 }else if(data.kind==='render-mode'&&ready&&Module._port_render_mode&&Number.isInteger(data.value))Module._port_render_mode(data.value&15);
 else if(data.kind==='capture-snapshot'&&ready&&Module._port_render_snapshot)Module._port_render_snapshot();
 else if(data.kind==='capture-vram'&&ready&&Module._port_vram_capture)Module._port_vram_capture();
 else if(data.kind==='capture-frame'&&ready&&Module._port_frame_capture)Module._port_frame_capture();
 else if(data.kind==='input'){
  if(!Array.isArray(data.values)||data.values.length!==5||!data.values.every(Number.isFinite))return;
  cancelReplay();if(pulseTimer!==null)endPulse();
  const v=data.values;lastInput=[v[0]&0xffff,Math.max(0,Math.min(255,v[1]|0)),Math.max(0,Math.min(255,v[2]|0)),Math.max(-128,Math.min(127,v[3]|0)),Math.max(-128,Math.min(127,v[4]|0))];applyInput();
 }else if(data.kind==='capture-render'&&ready&&Module._port_render_capture)Module._port_render_capture();
};
self.addEventListener('error',event=>fail(event.message||'Worker script error'));
self.addEventListener('unhandledrejection',event=>fail(event.reason));
