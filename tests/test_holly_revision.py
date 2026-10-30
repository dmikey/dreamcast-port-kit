"""The real register read path must identify the Dreamcast Holly revision."""
from pathlib import Path
import os, subprocess, tempfile, unittest

@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'), 'Set DC_PORT_TEST_TOOLCHAIN')
class HollyRevisionTests(unittest.TestCase):
    def test_readonly_revision_and_address_mirrors(self):
        core = Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])
        source = (core / 'src/hal/dc_hardware.c').read_text()
        state = source[source.index('struct DCHardware {'):source.index('DCHardware* dc_hw_init')]
        read = source[source.index('static uint32_t poll_last_addr'):source.index('#define DMA_OFF_DEVICE')]
        harness = '''
#include "hal/dc_hardware.h"
#include <assert.h>
#include <stdio.h>
uint64_t platform_get_ticks_ms(void){return 0;}
void dc_g2_retire_finished(DCHardware *hw){}
''' + state + read + '''
int main(void){
 DCHardware hw={0};
 assert(dc_hw_read32(&hw,0x005f689c)==0x0b);
 assert(dc_hw_read32(&hw,0xa05f689c)==0x0b);
 assert(dc_hw_read32(&hw,0x805f689c)==0x0b);
 hw.hw_regs[hw_reg_idx(0x005f689c)]=0xffffffff;
 assert(dc_hw_read32(&hw,0x005f689c)==0x0b);
 assert(dc_hw_read32(&hw,0x005f6898)==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'test.c').write_text(harness)
            compiled=subprocess.run(['clang','-std=c11','-I',str(core/'include'),str(path/'test.c'),'-o',str(path/'test')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            subprocess.run([str(path/'test')],check=True,capture_output=True)
