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
messages[0].onmessage({data:{kind:'input-applied',bits:8,sequence:messages[0].sent[1].message.sequence}});
runtime.button(8,false);runtime.axes(0,0,0,0);assert.deepEqual(Array.from(messages[0].sent[2].message.values),[0,0,0,0,0]);
messages[0].onmessage({data:{kind:'input-applied',bits:8}});assert.equal(canvas.dataset.inputApplied,'8');
runtime.capture();assert.equal(messages[0].sent.at(-1).message.kind,'capture-render');
messages[0].onmessage({data:{kind:'logs',lines:['one','two']}});assert.deepEqual(events.slice(-2),['one','two']);
messages[0].onmessage({data:{kind:'error',message:'failed'}});assert.equal(events.at(-1),'failed');runtime.start();assert.equal(transferred,1);
// Worker-side handshake, buffered input, batched logs and transferable audio.
const posted=[],imports=[],self={addEventListener(){}},input=[];class OffscreenCanvas{}
const timers=new Map();let timerId=0;
const worker=vm.createContext({performance:{now:()=>123},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),self,OffscreenCanvas,GL:{offscreenCanvases:{}},postMessage:(message,transfers)=>posted.push({message,transfers}),importScripts:(...names)=>imports.push(names),portBrowserScheduler:{yield:()=>Promise.resolve()}});
vm.runInContext(read('runtime-worker.js'),worker);
self.onmessage({data:{kind:'input',values:[8,300,-1,999,-999]}});
self.onmessage({data:{kind:'start',canvas:new OffscreenCanvas()}});assert.equal(imports.length,1);assert.deepEqual(imports[0],['vmu-format.js','vmu-storage.js','vmu-transport.js','browser-scheduler.js','game.js']);
worker.Module._port_input=(...values)=>input.push(values);worker.Module.onRuntimeInitialized();assert.deepEqual(input[0],[8,255,0,127,-128]);
worker.Module.preRun[0]();assert.equal(worker.GL.offscreenCanvases.canvas,worker.Module.canvas);
const samples=new Float32Array([.25,-.25]);worker.Module.portAudioPush(samples);assert.equal(posted.at(-1).message.samples,samples);assert.equal(posted.at(-1).transfers[0],samples.buffer);
worker.Module.print('line');worker.Module.portBrowserYield();assert.equal(posted.at(-1).message.lines[0],'line');
self.onmessage({data:{kind:'pulse',values:[8,0,0,0,0],duration:800}});assert.deepEqual(input.at(-1),[8,0,0,0,0]);
assert.equal(timers.size,1);const release=timers.values().next().value;timers.clear();release();assert.deepEqual(input.at(-1),[0,0,0,0,0]);
self.onmessage({data:{kind:'pulse',values:[2,0,255,0,0],duration:30000}});self.onmessage({data:{kind:'input',values:[4,0,0,0,0]}});assert.equal(timers.size,0);assert.deepEqual(input.at(-1),[4,0,0,0,0]);
const count=input.length;self.onmessage({data:{kind:'pulse',values:[8,0,0,0,0],duration:60001}});assert.equal(input.length,count);
let captured=0;worker.Module._port_frame_capture=()=>captured++;self.onmessage({data:{kind:'capture-frame'}});assert.equal(captured,1);
worker.Module._port_render_snapshot=()=>captured++;self.onmessage({data:{kind:'capture-snapshot'}});assert.equal(captured,2);
runtime.snapshot();assert.equal(messages[0].sent.at(-1).message.kind,'capture-snapshot');
let snapshotBytes;runtime.callbacks.snapshot=bytes=>snapshotBytes=bytes;const snapshot=new ArrayBuffer(8);messages[0].onmessage({data:{kind:'snapshot',bytes:snapshot}});assert.equal(snapshotBytes,snapshot);
self.onmessage({data:{kind:'replay',steps:[{atMs:0,values:[8,0,0,0,0]},{atMs:1000,values:[0,0,0,0,0]}]}});assert.equal(timers.size,3);timers.values().next().value();assert.deepEqual(input.at(-1),[8,0,0,0,0]);
self.onmessage({data:{kind:'input',values:[2,0,0,0,0]}});assert.equal(timers.size,0,'manual input cancels replay');
self.onmessage({data:{kind:'replay',steps:[{atMs:180001,values:[8,0,0,0,0]}]}});assert.equal(timers.size,0,'unbounded replays are rejected');
self.onmessage({data:{kind:'replay',steps:[{atMs:1,values:[8,0,0,0,0]},{atMs:0,values:[0,0,0,0,0]}]}});assert.equal(timers.size,0,'out-of-order replays are rejected');
// A pause cancels input and partial measurements rather than reporting false FPS.
worker.Module._port_frame_count=()=>100;
self.onmessage({data:{kind:'benchmark'}});assert.equal(timers.size,1);
self.onmessage({data:{kind:'benchmark'}});assert.equal(timers.size,1,'only one measurement may run');
self.onmessage({data:{kind:'pause',value:true}});assert.equal(timers.size,0);assert.deepEqual(input.at(-1),[0,0,0,0,0]);
self.onmessage({data:{kind:'benchmark'}});assert.equal(timers.size,0,'paused execution cannot be measured');
const pausedYield=worker.Module.portBrowserYield();
self.onmessage({data:{kind:'pause',value:false}});
pausedYield.then(()=>assert.equal(timers.size,0)).catch(error=>{console.error(error);process.exitCode=1;});
console.log('Worker contract passed: canvas transfer, input batching/release, ready handshake, logs, audio transfer, diagnostics.');

// A busy worker cannot accumulate an unbounded input-message backlog.
const stress=new page.Runtime({dataset:{}},{});stress.worker=new Worker('test');stress.ready=true;stress.axes(0,0,0,0);
for(let i=0;i<10000;i++){stress.button(4,i%2===0);stress.axes(0,i%256,0,0);}
stress.button(4,false);stress.axes(0,0,0,0);assert.equal(stress.worker.sent.length,1);assert.ok(stress.inputQueue.length<=16);assert.ok(stress.inputDropped>0);
while(stress.inputInFlight!==null){stress.inputInFlight=null;stress.sendInput();}
assert.deepEqual(Array.from(stress.worker.sent.at(-1).message.values),[0,0,0,0,0],'release survives queue overflow');
const analog=new page.Runtime({dataset:{}},{});analog.worker=new Worker('test');analog.ready=true;analog.axes(0,0,0,0);for(let i=0;i<10000;i++)analog.axes(0,i%256,0,0);assert.equal(analog.inputQueue.length,1);assert.ok(analog.inputCoalesced>0);
self.onmessage({data:{kind:'input',values:[0,0,0,0,0],sequence:1234}});assert.equal(posted.at(-1).message.sequence,1234,'worker acknowledges the exact input message');
console.log('Input backpressure passed: bounded 10,000-event burst, final release, analog coalescing and sequenced acknowledgements.');

// Concurrent project/build workers must stream their own project's disc.
const fetches=[],scopedSelf={location:{href:'http://127.0.0.1:4390/projects/pso/artifacts/build-1/runtime-worker.js'},fetch:(url,options)=>{fetches.push(url);return Promise.resolve({});},addEventListener(){}};
vm.runInNewContext(read('runtime-worker.js'),{self:scopedSelf,URL});
scopedSelf.fetch('/disc/0?offset=10&length=20');scopedSelf.fetch('game.wasm');
assert.equal(fetches[0],'http://127.0.0.1:4390/projects/pso/artifacts/build-1/disc/0?offset=10&length=20');assert.equal(fetches[1],'game.wasm');
console.log('Project disc routing passed: worker disc requests stay scoped to the selected project/build.');
