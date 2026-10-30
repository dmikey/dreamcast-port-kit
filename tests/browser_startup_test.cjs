const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../runtime/web/browser.js'),'utf8');
function fixture(webgl){const nodes=new Map(),events={},scripts=[],reports=[];
 const node=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:true,dataset:{},style:{},handlers:{},addEventListener(n,f){this.handlers[n]=f;},querySelector(){return node('knob');},setAttribute(){},focus(){}});return nodes.get(id);};
 const context=vm.createContext({document:{querySelector:node,querySelectorAll:()=>[],hasFocus:()=>true,addEventListener(){},createElement:()=>node('script'),body:{append:s=>scripts.push(s)}},window:{addEventListener:(n,f)=>events[n]=f},navigator:{userAgent:'test Safari/1'},performance:{now:()=>1000},setInterval(){},setTimeout(){},requestAnimationFrame(){},WebAssembly:{},WebGL2RenderingContext:webgl,fetch:(url,options)=>{if(options?.body)reports.push(JSON.parse(options.body));return Promise.resolve({json:()=>Promise.resolve({abiChecks:false})});}});
 vm.runInContext(source,context);return {context,nodes,scripts,reports,node,events};
}
let f=fixture(undefined);f.node('#start').handlers.click();assert.equal(f.scripts.length,0);assert.equal(f.node('#runtime-error').hidden,false);assert.match(f.node('#runtime-error').textContent,/WebGL 2/);
f=fixture(function(){});f.node('#start').handlers.click();assert.equal(f.scripts.length,1);assert.equal(f.scripts[0].src,'game.js');assert.equal(f.node('#start').disabled,true);assert.equal(f.reports[0].reason,'Starting runtime');
f.scripts[0].handlers.error();assert.match(f.node('#runtime-error').textContent,/could not load/);
f.context.Module.onAbort('wasm stack overflow');assert.match(f.node('#runtime-error').textContent,/wasm stack overflow/);
f.context.Module.onRuntimeInitialized();assert.equal(f.reports.at(-1).reason,'Runtime initialized');
f.context.Module.printErr('[PVR2] Shader compile error: unsupported precision');assert.match(f.node('#runtime-error').textContent,/unsupported precision/);
console.log('Startup contract passed: unsupported graphics, script load, WASM abort, initialization report, shader errors.');
