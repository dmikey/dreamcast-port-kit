"""Prove the DMA control-record stride bug independently of VMU support."""
import os,subprocess,tempfile,unittest
from pathlib import Path

@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class MapleControlRecordTests(unittest.TestCase):
 def test_each_control_record_preserves_following_controller_request(self):
  core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])
  source=(core/'src/hal/dc_hardware.c').read_text()
  dma=source[source.index('void dc_maple_dma('):source.index('MapleController* dc_maple_get_controller')]
  old='addr += 8 + plen * 4;'
  self.assertEqual(dma.count(old),1)
  prelude='''
#include "hal/dc_hardware.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct DCHardware {MapleController controllers[4];bool controller_connected[4];};
static uint8_t ram[16*1024*1024];
uint8_t *sh4_get_ram_ptr(void){return ram;}
'''
  harness='''
int main(int argc,char **argv){
 DCHardware hw={0};hw.controller_connected[0]=true;
 uint32_t *p=(uint32_t*)ram,*response=(uint32_t*)(ram+1024);
 unsigned op=(unsigned)atoi(argv[1]);
 p[0]=op<<8; /* Single-word SDCKB / reset / cancel / NOP. */
 p[1]=0x80000000u; /* Last START, one-word Maple device request. */
 p[2]=0x0c000400u;p[3]=0x00002001u;
 dc_maple_dma(&hw,0x0c000000u);
 return !((response[0]&255)==5 && response[1]==0x01000000u);
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)
   for label,body in [('before',dma),('after',dma.replace(old,'addr += maple_op == 0 ? 8 + plen * 4 : 4;'))]:
    c=folder/(label+'.c');exe=folder/label;c.write_text(prelude+body+harness)
    subprocess.run(['clang','-std=c11','-fsanitize=address,undefined','-I',str(core/'include'),str(c),'-o',str(exe)],check=True,capture_output=True)
    for op in (2,3,4,7):
     with self.subTest(version=label,pattern=op):
      run=subprocess.run([str(exe),str(op)],capture_output=True)
      self.assertEqual(run.returncode,1 if label=='before' else 0,run.stderr.decode())
