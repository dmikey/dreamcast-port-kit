// The player must start and accept input without any workbench DOM nodes.
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const html=fs.readFileSync(path.join(__dirname,'../runtime/web/player.html'),'utf8'),nodes=new Map();
for(const match of html.matchAll(/id="([^"]+)"/g))nodes.set('#'+match[1],{dataset:{},style:{},hidden:false,handlers:{},addEventListener(n,fn){this.handlers[n]=fn;},querySelector(){return{style:{}};},setAttribute(){},setPointerCapture(){},getBoundingClientRect(){return{left:0,top:0,width:100};},transferControlToOffscreen(){return{};},focus(){}});
const document={body:{dataset:{player:'true'}},querySelector:s=>nodes.get(s)||null,querySelectorAll:()=>[],hasFocus:()=>true,addEventListener(){}};
const context=vm.createContext({document,window:{addEventListener(){}},navigator:{getGamepads:()=>[]},performance:{now:()=>1000},requestAnimationFrame(){},setInterval(){},setTimeout(){},clearTimeout(){},WebAssembly:{},Worker:function(){},PortWorkerRuntime:class{constructor(canvas,callbacks){this.callbacks=callbacks;}start(){this.callbacks.ready();}button(){}axes(){}pause(){}}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../runtime/web/browser.js'),'utf8'),context);
assert.equal(document.querySelector('#log'),null);nodes.get('#start').handlers.click();assert.equal(document.body.dataset.runtime,'running');
vm.runInContext('controllerFrame()',context);assert.equal(nodes.get('#touch-pad').hidden,false);
(async()=>{await vm.runInContext("portDebugRuntime.command('pause',{paused:true})",context);assert.equal(document.body.dataset.runtime,'paused');await vm.runInContext("portDebugRuntime.command('pause',{paused:false})",context);assert.equal(document.body.dataset.runtime,'running');console.log('Standalone player passed: no workbench nodes, runtime start, overlay, typed pause/resume.');})().catch(error=>{console.error(error);process.exitCode=1;});
