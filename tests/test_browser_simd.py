"""Execute the real triangle sorter as scalar and SIMD WebAssembly."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('DC_PORT_TEST_EMSDK'),'Set DC_PORT_TEST_EMSDK')
class BrowserSIMDTests(unittest.TestCase):
 def test_strict_scalar_and_simd_sort_results_match(self):
  sdk=Path(os.environ['DC_PORT_TEST_EMSDK']).resolve()
  nodes=list((sdk/'node').glob('*/bin/node'));self.assertTrue(nodes)
  code=r'''
#include <stdint.h>
#include <string.h>
typedef struct {float x,y,z,u,v,r,g,b,a;uint32_t pcw,tsp,tcw,isp;} PVR2RenderVertex;
typedef struct {PVR2RenderVertex *vertices;int count;} PVR2TriList;
#include "transparency.h"
static PVR2RenderVertex vertices[1800];
uintptr_t data(void){return (uintptr_t)vertices;}
unsigned test(unsigned seed){
 for(unsigned i=0;i<1800;i++){
  uint32_t words[13];for(int j=0;j<13;j++){seed=seed*1664525u+1013904223u;words[j]=seed;}
  words[2]=(i%31==0)?0x7fc00000u:(i%29==0)?0x80000000u:0x3f000000u+(seed&0xffffffu);
  memcpy(vertices+i,words,sizeof words);
 }
 PVR2TriList list={vertices,1800};port_sort_transparent(&list);
 unsigned hash=2166136261u;const unsigned char *bytes=(const unsigned char*)vertices;
 for(unsigned i=0;i<sizeof vertices;i++)hash=(hash^bytes[i])*16777619u;
 return hash;
}
'''
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);(p/'test.c').write_text(code)
   env={**os.environ,'EMSDK_PYTHON':sys.executable,'PATH':str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH']}
   for name,extra in (('scalar',[]),('simd',['-msimd128'])):
    command=[sys.executable,str(sdk/'upstream/emscripten/emcc.py'),'-O3','-fno-strict-aliasing','-fwrapv',*extra,'-I',str(ROOT/'runtime'),str(p/'test.c'),'-sSTANDALONE_WASM=1','--no-entry','-sEXPORTED_FUNCTIONS=["_test","_data"]','-o',str(p/(name+'.wasm'))]
    subprocess.run(command,check=True,capture_output=True,env=env)
   subprocess.run([str(sdk/'upstream/bin/wasm-dis'),str(p/'simd.wasm'),'-o',str(p/'simd.wat')],check=True,capture_output=True)
   self.assertIn('v128.',(p/'simd.wat').read_text(),'SIMD build must contain actual vector instructions')
   (p/'compare.cjs').write_text('''const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{const imports={wasi_snapshot_preview1:{proc_exit(){throw Error('abort');}}};
const a=(await WebAssembly.instantiate(fs.readFileSync(process.argv[2]),imports)).instance.exports;
const b=(await WebAssembly.instantiate(fs.readFileSync(process.argv[3]),imports)).instance.exports;
for(let seed=1;seed<=200;seed++){
 assert.equal(a.test(seed),b.test(seed),'sort result differs for seed '+seed);
 assert.ok(Buffer.from(a.memory.buffer,a.data(),1800*52).equals(Buffer.from(b.memory.buffer,b.data(),1800*52)),'vertex bytes differ for seed '+seed);
}
console.log(JSON.stringify({cases:200,trianglesPerCase:600,identical:true}));})().catch(e=>{console.error(e);process.exitCode=1;});''')
   result=subprocess.run([str(nodes[0]),str(p/'compare.cjs'),str(p/'scalar.wasm'),str(p/'simd.wasm')],check=True,capture_output=True,text=True)
   self.assertTrue(json.loads(result.stdout)['identical'])
