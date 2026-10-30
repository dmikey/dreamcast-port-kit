from pathlib import Path
import importlib.util,os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('memory_access',ROOT/'memory_access.py');memory=importlib.util.module_from_spec(spec);spec.loader.exec_module(memory)
@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class MemoryAccessTests(unittest.TestCase):
 def test_guard_matches_original_mmu_mirrors_boundaries_and_devices(self):
  source=(Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])/'src/recompiler/sh4_cpu.c').read_text()
  source=source[source.index('static uint32_t translate_addr_cpu('):source.index('static uint32_t translate_addr(uint32_t')]
  candidate=memory.adapt(source).replace('translate_addr_cpu','candidate')
  source=source.replace('translate_addr_cpu','reference')
  harness='''#include <stdint.h>
#include <assert.h>
#include <stdbool.h>
#define ADDR_MASK_P1 0x1fffffffu
#define DC_RAM_BASE 0x0c000000u
#define DC_RAM_SIZE 0x1000000u
#define DC_RAM_MASK_16MB 0xffffffu
#define DC_VRAM_BASE 0x04000000u
#define DC_VRAM_SIZE 0x800000u
typedef struct {uint32_t ram_size,ram_mask,mmucr,utlb_addr[64],utlb_data1[64];} SH4CPU;
'''+source+candidate+'''
int main(void){
 SH4CPU cpu={0};uint32_t random=123;
 uint32_t edges[]={0,0xbffffff,0xc000000,0xcffffff,0xd000000,0xdffffff,0xe000000,0x4000000,0x5000000,0x5f8000,0x700000,0xff000028,0xf6000000};
 for(int size=16;size<=32;size+=16)for(int enabled=0;enabled<2;enabled++){
  cpu.ram_size=size*1024*1024;cpu.ram_mask=cpu.ram_size-1;cpu.mmucr=enabled;
  for(int i=0;i<64;i++){cpu.utlb_addr[i]=0x0c000100u+i*4096;cpu.utlb_data1[i]=0x04000010u+i*4096;}
  for(unsigned i=0;i<sizeof edges/sizeof *edges;i++)for(unsigned segment=0;segment<8;segment++){
   uint32_t a=edges[i]|(segment<<29);assert(reference(&cpu,a)==candidate(&cpu,a));
  }
  for(int i=0;i<200000;i++){random=random*1664525u+1013904223u;assert(reference(&cpu,random)==candidate(&cpu,random));}
  // Valid translated P0 RAM page must still resolve to VRAM with MMU enabled.
  if(enabled)assert(candidate(&cpu,0x0c000000u)==0x04000000u);
 }
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(harness)
   subprocess.run(['clang','-O2','-fsanitize=address,undefined',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   subprocess.run([str(p/'t')],check=True)
