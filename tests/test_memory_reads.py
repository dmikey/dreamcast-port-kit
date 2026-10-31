"""Execute the original and optimized RAM readers with identical poll side effects."""
from pathlib import Path
import importlib.util,os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('memory_access',ROOT/'memory_access.py');memory=importlib.util.module_from_spec(spec);spec.loader.exec_module(memory)
PREFIX=r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "recompiler/sh4_cpu.h"
#include "hal/dc_hardware.h"
static SH4CPU *g_cpu_ref;static DCHardware *g_hardware;
static uint32_t g_read_seq,tmu_write_time_ms[3];
static uint64_t g_irq_delivered,g_irq_reentrant,g_irq_masked;
static int g_aica_published_n,g_in_irq;
static struct {uint32_t offset,value,after_ms;}g_aica_published[16];
uint64_t platform_get_ticks_ms(void){return 0;}
uint64_t dc_aica_arm_instructions(void){return 0;}
static unsigned polls;
void sh4_poll_irq(SH4CPU *cpu){polls++; cpu->ram[4]++;}
void sh4_dump_native_stack(const char *tag){}
static int aica_driver_up_for(unsigned after){return 0;}
uint32_t dc_hw_read32(DCHardware *hw,uint32_t addr){return 0x12345678;}
uint32_t dc_aica_reg_read(uint32_t offset){return 0;}
'''
MAIN=r'''
int main(void){
 SH4CPU cpu={0};g_cpu_ref=&cpu;cpu.ram_size=16*1024*1024;cpu.ram_mask=cpu.ram_size-1;cpu.ram=calloc(1,cpu.ram_size);cpu.vram=calloc(1,8*1024*1024);cpu.aica_ram=calloc(1,2*1024*1024);
 for(unsigned i=0;i<cpu.ram_size;i++)cpu.ram[i]=(unsigned char)(i*37);
 uint32_t seed=17;
 for(int mmu=0;mmu<2;mmu++){
  cpu.mmucr=mmu;
  for(int i=0;i<64;i++){cpu.utlb_addr[i]=0x0c000100u+i*4096;cpu.utlb_data1[i]=0x0c000010u+i*4096;}
  for(int i=0;i<200000;i++){
   seed=seed*1664525u+1013904223u;uint32_t addr=0x0c000000u|(seed&0xfffffcu)|((i%4)*0x40000000u);
   unsigned seq=g_read_seq,p=polls;unsigned char value=cpu.ram[4];
   uint32_t a=reference_read32(&cpu,addr);unsigned expected_seq=g_read_seq,expected_polls=polls;unsigned char expected=cpu.ram[4];
   g_read_seq=seq;polls=p;cpu.ram[4]=value;
   uint32_t b=candidate_read32(&cpu,addr);
   assert(a==b && g_read_seq==expected_seq && polls==expected_polls && cpu.ram[4]==expected);
  }
 }

 // The original translator belongs to g_cpu_ref. A different argument CPU
 // must not bypass that translator even when its own MMU is disabled.
 SH4CPU other=cpu;other.mmucr=0;cpu.mmucr=1;
 cpu.utlb_addr[0]=0x0c000100;cpu.utlb_data1[0]=0x04000010;
 g_read_seq=100;uint32_t cross=reference_read32(&other,0x0c000000);
 g_read_seq=100;assert(candidate_read32(&other,0x0c000000)==cross && g_read_seq==101);
 uint32_t devices[]={0x005f6800u,0x04000000u,0x05000000u,0xff000010u,0xffd8000cu,0xf6000000u};
 g_hardware=(DCHardware*)1;
 for(unsigned i=0;i<sizeof devices/sizeof *devices;i++){
  unsigned seq=g_read_seq,p=polls;
  uint32_t a=reference_read32(&cpu,devices[i]);unsigned after=g_read_seq;
  g_read_seq=seq;polls=p;uint32_t b=candidate_read32(&cpu,devices[i]);
  assert(a==b && g_read_seq==after);
 }
 for(unsigned seq=0xfffffffeu;seq!=1;seq++){
  g_read_seq=seq;unsigned p=polls;unsigned char value=cpu.ram[4];
  uint32_t a=reference_read32(&cpu,0x8c000004);unsigned after=g_read_seq,expected=polls;unsigned char data=cpu.ram[4];
  g_read_seq=seq;polls=p;cpu.ram[4]=value;
  uint32_t b=candidate_read32(&cpu,0x8c000004);
  assert(a==b && after==g_read_seq && polls==expected && cpu.ram[4]==data);
 }
 free(cpu.ram);free(cpu.vram);free(cpu.aica_ram);return 0;
}
'''
@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class MemoryReadTests(unittest.TestCase):
 def test_ram_mmu_devices_poll_side_effects_and_counter_wrap(self):
  core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])
  source=(core/'src/recompiler/sh4_cpu.c').read_text()
  translator=source[source.index('static uint32_t translate_addr_cpu('):source.index('/* Memory traffic is what advances time')]
  reader=source[source.index('uint32_t sh4_read32(SH4CPU *cpu, uint32_t addr) {'):source.index('\nvoid sh4_write8(')]
  reader=reader[:reader.index('\nfloat sh4_read_float(')]+'\nfloat sh4_read_float(SH4CPU *cpu, uint32_t addr) { return 0; }\n'
  reference=reader.replace('sh4_read32','reference_read32').replace('sh4_read_float','reference_float')
  candidate=memory.adapt_reads(reader).replace('sh4_read32','candidate_read32').replace('sh4_read_float','candidate_float')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(PREFIX+translator+reference+candidate+MAIN)
   subprocess.run(['clang','-O2','-fsanitize=address,undefined','-I',str(core/'include'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True,capture_output=True)
