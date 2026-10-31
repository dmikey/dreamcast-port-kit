const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const template=fs.readFileSync(path.join(__dirname,'../runtime/web/runtime-loader.js'),'utf8');
const fallback={loader:'game.js',suspension:'asyncify',wasmSHA256:'compatibility'},native={loader:'game-jspi.js',suspension:'jspi',wasmSHA256:'native'};
function load(WebAssembly,variants){
 const self={},scripts=[],logs=[];
 vm.runInNewContext(template.replace('/*PORT_RUNTIME_BUILDS*/{}',JSON.stringify({asyncify:fallback,...variants})),{self,WebAssembly,importScripts:name=>scripts.push(name),Module:{print:line=>logs.push(line)}});
 return {build:self.portSelectedBuild,scripts,logs};
}
const supported={Suspending(){},promising(){}};
assert.equal(load(supported,{jspi:native}).build.suspension,'jspi');
for(const capabilities of [{},{Suspending(){}},{promising(){}},{Suspending:true,promising(){}}]){
 const result=load(capabilities,{jspi:native});assert.equal(result.build.suspension,'asyncify');assert.deepEqual(result.scripts,['game.js']);
}
assert.equal(load(supported,{}).build.suspension,'asyncify','support alone cannot select a missing bundle');
assert.match(load(supported,{jspi:native}).logs[0],/suspension=jspi wasm=native/);
console.log('Browser bundle selection passed: native stack capability, partial/absent API fallback, missing companion and accurate identity.');
