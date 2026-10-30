// Isolated input contract test; no browser or game state is simulated as proof.
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const events={},nodes=new Map(),buttons=[];
function node(id){if(!nodes.has(id))nodes.set(id,{id,textContent:'',dataset:{},style:{},handlers:{},hidden:false,addEventListener(n,f){this.handlers[n]=f;},setAttribute(n,v){this[n]=v;},querySelector(){return node('knob');},getBoundingClientRect(){return{left:0,top:0,width:100};},setPointerCapture(){},focus(){},append(){}});return nodes.get(id);}
for(const [id,bit]of[['startbtn',8],['a',4],['b',2]]){const b=node(id);b.dataset.bit=String(bit);buttons.push(b);}
const gas=node('gas');gas.dataset.axis='gas';buttons.push(gas);
let pads=[],axes,pressed=0,calls=0;
const context=vm.createContext({document:{hasFocus:()=>true,querySelector:node,querySelectorAll:()=>buttons,addEventListener(n,f){events[n]=f;}},window:{addEventListener(n,f){events[n]=f;}},navigator:{getGamepads:()=>pads},requestAnimationFrame(){},setTimeout(){},setInterval(){},performance:{now:()=>1000},console:{log(){}}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../runtime/web/browser.js'),'utf8'),context);
context.axisSink=(...v)=>{axes=v;calls++;};context.buttonSink=(b,p)=>{pressed=p?pressed|b:pressed&~b;};
vm.runInContext('Module._port_axes=axisSink;Module._port_button=buttonSink;controllerFrame()',context);
assert.equal(calls,0,'must not call WASM stubs before initialization');
vm.runInContext('Module.onRuntimeInitialized();controllerFrame()',context);assert.deepEqual(axes,[0,0,0,0]);
pads=[{connected:true,mapping:'standard',id:'test pad',axes:[.575,0],buttons:Array.from({length:16},()=>({value:0,pressed:false}))}];pads[0].buttons[7].value=.5;pads[0].buttons[6].value=.25;pads[0].buttons[1].pressed=true;
vm.runInContext('controllerFrame()',context);assert.deepEqual(axes,[64,128,63,0]);assert.equal(pressed&2,2);
pads=[];vm.runInContext('controllerFrame()',context);assert.deepEqual(axes,[0,0,0,0]);assert.equal(pressed,0);
events.keydown({code:'KeyW',preventDefault(){}});assert.equal(axes[1],255,'keyboard input must not wait for an animation frame');events.keydown({code:'ArrowLeft',preventDefault(){}});assert.deepEqual(axes,[0,255,-127,0]);
events.blur();assert.deepEqual(axes,[0,0,0,0]);assert.equal(pressed,0);
events.focus();gas.handlers.pointerdown({preventDefault(){},pointerId:1});assert.equal(axes[1],255,'touch input must not wait for an animation frame');gas.handlers.pointercancel();assert.equal(axes[1],0);
console.log('Input contract passed: initialization, analog triggers/stick, buttons, disconnect, keyboard, blur, touch cancellation.');

vm.runInContext("const boundedTest=new DiagnosticRing(3);for(let i=0;i<5;i++)boundedTest.push('[FRAME] '+i,i);if(boundedTest.snapshot().map(e=>e.sequence).join(',')!=='2,3,4'||boundedTest.dropped!==2)throw Error('diagnostic ring order/overflow');",context);
console.log('Diagnostic ring passed: bounded capacity, ordered wraparound, drop count.');
