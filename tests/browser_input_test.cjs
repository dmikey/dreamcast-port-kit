// Isolated input contract test; no browser or game state is simulated as proof.
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const events={},nodes=new Map(),buttons=[],timers=new Map();let timerId=0;
function listen(n,f){const previous=events[n];events[n]=previous?e=>{previous(e);f(e);}:f;}
const pointer=(pointerId=1)=>({pointerId,preventDefault(){}});
function node(id){if(!nodes.has(id))nodes.set(id,{id,textContent:'',dataset:{},style:{},handlers:{},hidden:false,addEventListener(n,f){this.handlers[n]=f;},setAttribute(n,v){this[n]=v;},querySelector(){return node('knob');},getBoundingClientRect(){return{left:0,top:0,width:100};},setPointerCapture(){},focus(){},append(){}});return nodes.get(id);}
for(const [id,bit]of[['startbtn',8],['a',4],['b',2],['up-left',80],['up-right',144],['down-left',96],['down-right',160]]){const b=node(id);b.dataset.bit=String(bit);buttons.push(b);}
const gas=node('gas');gas.dataset.axis='gas';buttons.push(gas);
let pads=[],axes,pressed=0,calls=0;
const context=vm.createContext({document:{hasFocus:()=>true,querySelector:node,querySelectorAll:()=>buttons,addEventListener:listen},window:{addEventListener:listen},navigator:{getGamepads:()=>pads},requestAnimationFrame(){},setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},setInterval(){},performance:{now:()=>1000},console:{log(){}}});
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
events.focus();gas.handlers.pointerdown({preventDefault(){},pointerId:1});assert.equal(axes[1],255,'touch input must not wait for an animation frame');gas.handlers.pointercancel(pointer());assert.equal(axes[1],0);
console.log('Input contract passed: initialization, analog triggers/stick, buttons, disconnect, keyboard, blur, touch cancellation.');

vm.runInContext("const boundedTest=new DiagnosticRing(3);for(let i=0;i<5;i++)boundedTest.push('[FRAME] '+i,i);if(boundedTest.snapshot().map(e=>e.sequence).join(',')!=='2,3,4'||boundedTest.dropped!==2)throw Error('diagnostic ring order/overflow');",context);
console.log('Diagnostic ring passed: bounded capacity, ordered wraparound, drop count.');

// Pointer clicks must not re-press a released control or create stale timers.
gas.handlers.pointerdown(pointer());gas.handlers.pointerup(pointer());gas.handlers.click({detail:1,pointerType:'mouse'});assert.equal(axes[1],0);assert.equal(timers.size,0);
for(let i=0;i<1000;i++){gas.handlers.pointerdown(pointer(i));gas.handlers.pointerup(pointer(i));gas.handlers.click({detail:1});}
assert.equal(axes[1],0);assert.equal(timers.size,0,'rapid pointer clicks never create synthetic hold timers');
gas.handlers.pointerdown(pointer(1));gas.handlers.pointerdown(pointer(2));gas.handlers.lostpointercapture(pointer(1));assert.equal(axes[1],255,'another finger still owns the trigger');gas.handlers.pointerup(pointer(2));assert.equal(axes[1],0);
gas.setPointerCapture=()=>{throw Error('Safari capture already lost');};gas.handlers.pointerdown(pointer(3));assert.equal(axes[1],255);events.pointerup(pointer(3));assert.equal(axes[1],0,'window release handles rejected capture');
gas.handlers.pointerdown(pointer(4));gas.handlers.lostpointercapture(pointer(3));assert.equal(axes[1],255,'late capture loss cannot release a newer pointer');gas.handlers.pointercancel(pointer(4));
gas.handlers.click({detail:0});gas.handlers.click({detail:0});assert.equal(timers.size,1,'assistive repeat replaces its own release timer');assert.equal(axes[1],255);gas.handlers.pointerdown(pointer(5));const clickRelease=timers.values().next().value;timers.clear();clickRelease();assert.equal(axes[1],255,'assistive timer cannot release a real hold');gas.handlers.pointerup(pointer(5));assert.equal(axes[1],0);
gas.handlers.click({detail:0});events.blur();assert.equal(timers.size,0);assert.equal(axes[1],0);events.focus();
gas.handlers.pointerdown(pointer(6));node('#toggle-pad').handlers.click({currentTarget:node('#toggle-pad')});assert.equal(axes[1],0,'hiding the overlay releases immediately');
const joystick=node('#stick');joystick.handlers.pointerdown({...pointer(7),clientX:100,clientY:50});assert.equal(axes[2],127);events.pointerup(pointer(7));assert.equal(axes[2],0);
console.log('Rapid input regression passed: 1,000 taps, multi-pointer ownership, stale capture, capture failure, assistive clicks, immediate stick release and hidden controls.');

vm.runInContext("const clearTest=new DiagnosticRing(3);clearTest.push('first',1);clearTest.clear();if(clearTest.snapshot().length)throw Error('clear must discard old entries');clearTest.push('second',2);if(clearTest.snapshot()[0].sequence!==1)throw Error('clear must preserve the debug cursor sequence');",context);
console.log('Console clear passed: entries released without reusing MCP event sequence numbers.');

context.document.body={dataset:{player:'true'}};pads=[];vm.runInContext('controllerFrame()',context);assert.equal(node('#touch-pad').hidden,false,'standalone player exposes overlay without a gamepad');
gas.handlers.pointerdown(pointer(101));pads=[{connected:true,mapping:'standard',id:'auto overlay pad',axes:[0,0],buttons:Array.from({length:16},()=>({value:0,pressed:false}))}];vm.runInContext('controllerFrame()',context);assert.equal(node('#touch-pad').hidden,true);assert.equal(axes[1],0,'controller takeover releases held overlay triggers');
pads=[];vm.runInContext('controllerFrame()',context);assert.equal(node('#touch-pad').hidden,false,'disconnect restores the player overlay');
console.log('Player overlay passed: visible by default, hidden for supported gamepad, restored on disconnect.');

pads=[];for(const [id,bits,x] of [['up-left',80,-127],['up-right',144,127],['down-left',96,-127],['down-right',160,127]]){const b=node(id);b.handlers.pointerdown(pointer(200));assert.equal(pressed,bits,id+' must press both cardinal bits');assert.equal(axes[2],x);b.handlers.pointerup(pointer(200));assert.equal(pressed,0);assert.equal(axes[2],0);}
console.log('D-pad corners passed: all four invisible diagonal regions press both directions and release cleanly.');
