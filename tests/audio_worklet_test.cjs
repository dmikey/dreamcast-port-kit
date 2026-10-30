const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../runtime/web/audio-worklet.js'),'utf8');
function create(rate){let Type;const stats=[];const context={AudioWorkletProcessor:class{constructor(){this.port={postMessage:s=>stats.push(s)};}},Float32Array,sampleRate:rate,registerProcessor:(name,type)=>{Type=type;}};vm.runInNewContext(source,context);return {node:new Type(),stats};}
for(const rate of [32000,44100,48000,96000]){
 const {node}=create(rate),a=new Float32Array(4096*2);for(let i=0;i<4096;i++){a[2*i]=.25;a[2*i+1]=-.5;}
 node.port.onmessage({data:{samples:a}});let played=0;
 while(node.primed||node.count>=2048){const out=[new Float32Array(128),new Float32Array(128)];node.process([],[out]);for(let i=0;i<128;i++)if(out[0][i]){assert.equal(out[0][i],.25);assert.equal(out[1][i],-.5);played++;}assert(node.count>=0);}
 assert(Math.abs(played-4095*rate/44100)<3,'duration must follow device sample rate');assert.equal(node.underruns,1);
 node.port.onmessage({data:{reset:true}});assert.equal(node.count,0);
 node.port.onmessage({data:{samples:new Float32Array(16000*2)}});node.port.onmessage({data:{samples:new Float32Array(16000*2)}});assert.equal(node.count,16384);assert.equal(node.overruns,1);
}
console.log('Audio worklet passed: stereo, 32/44.1/48/96 kHz duration, underrun re-prime, bounded overflow, reset.');
