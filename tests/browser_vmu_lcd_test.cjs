const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const pixels=[],context2d={fillRect:(...args)=>pixels.push(args)},elements=new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,{getContext:()=>context2d,addEventListener(){},dataset:{}});return elements.get(id);}};
const context=vm.createContext({document,Uint8Array});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../runtime/web/vmu-ui.js'),'utf8')+'\nvar ui=portVmuUI;',context);
pixels.length=0;
const bytes=new Uint8Array(192);
// Asymmetric corner and interior markers catch both mirroring and row/bit order.
bytes[5]=1;bytes[0]=128;bytes[31*6+5]=1;bytes[31*6]=128;bytes[7*6+3]=4;
context.ui.event({kind:'vmu-lcd',bytes});
assert.deepEqual(pixels,[[0,0,48,32],[0,31,1,1],[47,31,1,1],[18,24,1,1],[0,0,1,1],[47,0,1,1]]);
const count=pixels.length;context.ui.event({kind:'vmu-lcd',bytes:new Uint8Array(191)});assert.equal(pixels.length,count);
console.log('VMU LCD passed: upright orientation, row order, byte order, bit order and invalid frame rejection.');
