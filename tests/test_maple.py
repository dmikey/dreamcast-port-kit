"""Exercise real controller DMA device discovery and condition bytes."""
from pathlib import Path
import os,subprocess,tempfile,unittest
@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class MapleTests(unittest.TestCase):
 def test_capabilities_and_analog_condition(self):
  core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN']);source=(core/'src/hal/dc_hardware.c').read_text();dma=source[source.index('void dc_maple_dma('):source.index('MapleController* dc_maple_get_controller')]
  harness='''
#include "hal/dc_hardware.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct DCHardware {MapleController controllers[4];bool controller_connected[4];};
static uint8_t ram[16*1024*1024];
uint8_t *sh4_get_ram_ptr(void){return ram;}
'''+dma+'''
int main(void){DCHardware h={0};h.controller_connected[0]=true;uint32_t *cmd=(uint32_t*)ram,*r=(uint32_t*)(ram+256);cmd[0]=0x80000001;cmd[1]=256;cmd[2]=0x2001;dc_maple_dma(&h,0);
assert(r[1]==0x01000000&&r[2]==0xfe060f00&&r[3]==0&&r[4]==0);assert(((unsigned char*)&r[1])[16]==255);assert(!memcmp((unsigned char*)&r[1]+18,"Dreamcast Controller",20));
h.controllers[0].buttons=0xfffd;h.controllers[0].rtrig=128;h.controllers[0].ltrig=64;h.controllers[0].joyx=-64;h.controllers[0].joyy=32;cmd[2]=0x2009;cmd[3]=0x01000000;dc_maple_dma(&h,0);assert(r[2]==0x4080fffd);assert(r[3]==0x8080a040);return 0;}
'''
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);(p/'test.c').write_text(harness);subprocess.run(['clang','-std=c11','-I',str(core/'include'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True);subprocess.run([str(p/'test')],check=True,capture_output=True)
