const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const read=name=>fs.readFileSync(path.join(__dirname,'../runtime/web',name),'utf8');
let transferred=0;const offscreen={},canvas={dataset:{},transferControlToOffscreen(){transferred++;return offscreen;}},messages=[],events=[];
class Worker{constructor(url){this.url=url;this.sent=[];messages.push(this);}postMessage(message,transfers){this.sent.push({message,transfers});}}
const page=vm.createContext({Worker});vm.runInContext(read('runtime-bridge.js')+'\nvar Runtime=PortWorkerRuntime;',page);
const runtime=new page.Runtime(canvas,{ready:()=>events.push('ready'),log:s=>events.push(s),audio:s=>events.push(s),error:s=>events.push(s)});
runtime.start();assert.equal(transferred,1);assert.equal(messages[0].url,'runtime-worker.js');assert.equal(messages[0].sent[0].transfers[0],offscreen);
runtime.button(8,true);runtime.axes(64,128,-90,0);assert.equal(messages[0].sent.length,1,'input must wait for runtime');
messages[0].onmessage({data:{kind:'ready'}});assert.deepEqual(Array.from(messages[0].sent[1].message.values),[8,64,128,-90,0]);
runtime.axes(64,128,-90,0);assert.equal(messages[0].sent.length,2,'unchanged input must not flood worker');
runtime.button(8,false);runtime.axes(0,0,0,0);assert.deepEqual(Array.from(messages[0].sent[2].message.values),[0,0,0,0,0]);
messages[0].onmessage({data:{kind:'input-applied',bits:8}});assert.equal(canvas.dataset.inputApplied,'8');
runtime.capture();assert.equal(messages[0].sent.at(-1).message.kind,'capture-render');
messages[0].onmessage({data:{kind:'logs',lines:['one','two']}});assert.deepEqual(events.slice(-2),['one','two']);
messages[0].onmessage({data:{kind:'error',message:'failed'}});assert.equal(events.at(-1),'failed');runtime.start();assert.equal(transferred,1);
// Worker-side handshake, buffered input, batched logs and transferable audio.
const posted=[],imports=[],self={addEventListener(){}},input=[];class OffscreenCanvas{}
const worker=vm.createContext({self,OffscreenCanvas,GL:{offscreenCanvases:{}},postMessage:(message,transfers)=>posted.push({message,transfers}),importScripts:(...names)=>imports.push(names),portBrowserScheduler:{yield:()=>Promise.resolve()}});
vm.runInContext(read('runtime-worker.js'),worker);
self.onmessage({data:{kind:'input',values:[8,300,-1,999,-999]}});
self.onmessage({data:{kind:'start',canvas:new OffscreenCanvas()}});assert.equal(imports.length,1);assert.deepEqual(imports[0],['browser-scheduler.js','game.js']);
worker.Module._port_input=(...values)=>input.push(values);worker.Module.onRuntimeInitialized();assert.deepEqual(input[0],[8,255,0,127,-128]);
worker.Module.preRun[0]();assert.equal(worker.GL.offscreenCanvases.canvas,worker.Module.canvas);
const samples=new Float32Array([.25,-.25]);worker.Module.portAudioPush(samples);assert.equal(posted.at(-1).message.samples,samples);assert.equal(posted.at(-1).transfers[0],samples.buffer);
worker.Module.print('line');worker.Module.portBrowserYield();assert.equal(posted.at(-1).message.lines[0],'line');
console.log('Worker contract passed: canvas transfer, input batching/release, ready handshake, logs, audio transfer, diagnostics.');
