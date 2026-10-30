const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../runtime/web/boot.js'),'utf8');
function fixture(){const overlay={dataset:{},hidden:false},stage={dataset:{bootSound:'local.mp3'},querySelector:()=>overlay},timers=[],audio=[];
 class Audio{constructor(url){this.url=url;this.played=false;this.paused=false;audio.push(this);}play(){this.played=true;return Promise.resolve();}pause(){this.paused=true;}}
 const ctx=vm.createContext({Audio,setTimeout:(fn,ms)=>timers.push({fn,ms})});vm.runInContext(source+'\nvar Intro=PortBootIntro;',ctx);return{intro:new ctx.Intro(stage),overlay,stage,timers,audio};
}
let f=fixture();f.intro.start();assert.equal(f.audio[0].played,true,'sound starts inside the user gesture');assert.equal(f.timers[0].ms,8000);f.intro.ready();assert.equal(f.overlay.hidden,false,'fast load does not cut off intro');f.timers[0].fn();assert.equal(f.overlay.hidden,true);assert.equal(f.stage.dataset.booting,'false');assert.equal(f.intro.active,false);assert.equal(f.audio[0].paused,true);
f=fixture();f.intro.start();f.timers[0].fn();assert.equal(f.overlay.hidden,false,'slow load retains intro until runtime ready');f.intro.ready();assert.equal(f.overlay.hidden,true);
f=fixture();f.intro.start();f.intro.fail();assert.equal(f.overlay.hidden,true,'startup errors are not hidden');assert.equal(f.audio[0].paused,true);
f=fixture();f.stage.dataset.bootSound='';f.intro.start();assert.equal(f.audio.length,0,'local sound is optional');
console.log('Boot intro contract passed: gesture audio, minimum duration, delayed runtime, error handoff and optional private audio.');
