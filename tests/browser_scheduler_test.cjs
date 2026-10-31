const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../runtime/web/browser-scheduler.js'),'utf8');
(async()=>{
 const tasks=[],timers=[],document={hidden:false};let created=0;
 class Channel{constructor(){created++;this.port1={};this.port2={postMessage:()=>tasks.push(()=>this.port1.onmessage({}))};}}
 const context=vm.createContext({document,MessageChannel:Channel,setTimeout:resolve=>timers.push(resolve)});vm.runInContext(source+'\nvar scheduler=portBrowserScheduler;',context);
 let done=0;const a=context.scheduler.yield().then(()=>done++),b=context.scheduler.yield().then(()=>done++);
 assert.equal(done,0,'must leave the synchronous task');assert.equal(timers.length,0,'active tabs must avoid nested timers');assert.equal(created,1);
 tasks.shift()();await a;assert.equal(done,1);tasks.shift()();await b;assert.equal(done,2);
 document.hidden=true;const c=context.scheduler.yield();assert.equal(timers.length,1);timers.shift()();await c;
 const fallback=vm.createContext({document:{hidden:false},setTimeout:resolve=>timers.push(resolve)});vm.runInContext(source+'\nvar scheduler=portBrowserScheduler;',fallback);const d=fallback.scheduler.yield();timers.shift()();await d;
 const worker=vm.createContext({MessageChannel:Channel,setTimeout:resolve=>timers.push(resolve)});vm.runInContext(source+'\nvar scheduler=portBrowserScheduler;',worker);const workerYield=worker.scheduler.yield();assert.equal(timers.length,0,'workers have no document and must use task messages');tasks.shift()();await workerYield;
 const idleTask=worker.scheduler.idle();assert.equal(timers.length,1,'idle yields must wait for a short timer');timers.shift()();assert.equal(tasks.length,1,'idle continuation must resume through a message task');tasks.shift()();await idleTask;
 console.log('Scheduler passed: asynchronous task, FIFO, channel reuse, no active-tab timer, hidden/unsupported fallback.');
})().catch(error=>{console.error(error);process.exitCode=1;});
