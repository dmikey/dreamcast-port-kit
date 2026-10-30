/* The original executable, ARM7, hardware, texture decode and GL run here. */
'use strict';
var Module;let ready=false,started=false,lastInput=null,logs=[];
function flushLogs(){if(logs.length){postMessage({kind:'logs',lines:logs});logs=[];}}
function log(...parts){if(logs.length<512)logs.push(parts.join(' '));}
function fail(reason){flushLogs();postMessage({kind:'error',message:String(reason)});}
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
    portBrowserYield:()=>{flushLogs();return portBrowserScheduler.yield();}
   };
   importScripts('browser-scheduler.js','game.js');
  }catch(error){fail(error.stack||error.message||error);}
 }else if(data.kind==='input'){
  if(!Array.isArray(data.values)||data.values.length!==5||!data.values.every(Number.isFinite))return;
  const v=data.values;lastInput=[v[0]&0xffff,Math.max(0,Math.min(255,v[1]|0)),Math.max(0,Math.min(255,v[2]|0)),Math.max(-128,Math.min(127,v[3]|0)),Math.max(-128,Math.min(127,v[4]|0))];applyInput();
 }else if(data.kind==='capture-render'&&ready&&Module._port_render_capture)Module._port_render_capture();
};
self.addEventListener('error',event=>fail(event.message||'Worker script error'));
self.addEventListener('unhandledrejection',event=>fail(event.reason));
