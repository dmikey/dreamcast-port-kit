const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const script=fs.readFileSync(path.join(__dirname,'../runtime/web/vmu-transport.js'),'utf8');
(async()=>{
 const calls=[],messages=[];let release,reject;
 const context=vm.createContext({Uint8Array,postMessage:message=>messages.push(message),portVmuStorage:{read:async()=>({bytes:new Uint8Array(131072),revision:1}),writePhase:(...args)=>{calls.push(args);return new Promise((resolve,fail)=>{release=resolve;reject=fail;});}}});
 vm.runInContext(script+'\nvar card=portVmu;',context);const card=context.card;
 assert.equal((await card.load()).length,131072);assert.equal(card.revision,1);assert.equal(messages.at(-1).connected,true);
 const before=messages.length,pending=card.write(42,3,new Uint8Array(128));assert.equal(calls[0][3],1);assert.equal(messages.length,before,'no save acknowledgement before commit');release({revision:2});await pending;assert.equal(card.revision,2);assert.equal(messages.at(-1).saved,true);
 const count=messages.length,failed=card.write(42,3,new Uint8Array(128));reject(Error('VMU changed in another session'));await assert.rejects(()=>failed,/another session/);assert.equal(card.revision,2);assert.equal(messages.length,count,'failed saves must not be reported as saved');
 console.log('VMU transport passed: IndexedDB revision ownership, commit-before-acknowledgement and conflict preservation.');
})().catch(error=>{console.error(error);process.exitCode=1;});
