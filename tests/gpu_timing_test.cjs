const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const header=fs.readFileSync(path.join(__dirname,'../runtime/gpu_timing.h'),'utf8');
function body(name){const marker='EM_JS(void,'+name+',(),{',start=header.indexOf(marker)+marker.length;return header.slice(start,header.indexOf('\n});',start));}
function fixture(enabled=true){
 let now=0,next=0,available=false,disjoint=false,lost=false,begins=0,reads=0,deletes=0;
 const logs=[],ext={GPU_DISJOINT_EXT:1,TIME_ELAPSED_EXT:2},GLctx={QUERY_RESULT_AVAILABLE:3,QUERY_RESULT:4,
  getExtension:()=>enabled?ext:null,isContextLost:()=>lost,getParameter:()=>disjoint,
  createQuery:()=>++next,beginQuery:()=>begins++,endQuery(){},deleteQuery:()=>deletes++,
  getQueryParameter(q,what){if(what===3)return available;assert.ok(available,'result must never be read before availability');reads++;return 1500000;}};
 const context=vm.createContext({Module:{print:line=>logs.push(line)},GLctx,performance:{now:()=>now}});
 vm.runInContext('function begin(){'+body('port_gpu_begin')+'}\nfunction end(){'+body('port_gpu_end')+'}',context);
 return {context,logs,frames(n){for(let i=0;i<n;i++){context.begin();context.end();}},set(values){if('now'in values)now=values.now;if('available'in values)available=values.available;if('disjoint'in values)disjoint=values.disjoint;if('lost'in values)lost=values.lost;},stats:()=>({begins,reads,deletes})};
}
let f=fixture();f.frames(180);assert.equal(f.context.Module.portGpuTrace.pending.length,4);assert.equal(f.stats().begins,4);assert.equal(f.stats().reads,0);
f.set({available:true,now:6000});f.frames(30);assert.equal(f.stats().reads,4);assert.ok(f.logs.some(line=>line.includes('avg_ms=1.500')));
const reads=f.stats().reads;f.set({available:false,disjoint:true});f.frames(30);assert.equal(f.stats().reads,reads,'disjoint results are discarded without reading');
const begins=f.stats().begins;f.set({lost:true});f.frames(60);assert.equal(f.stats().begins,begins);
f=fixture(false);f.frames(1000);assert.equal(f.stats().begins,0);assert.equal(f.logs.length,1);
console.log('GPU timing passed: bounded asynchronous sampling, availability-before-result, disjoint discard, context loss and absent-extension fallback.');
