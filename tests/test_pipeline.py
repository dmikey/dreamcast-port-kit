"""Optional real compiler integration using an original eight-byte synthetic program."""
from pathlib import Path
import contextlib
import io
import json
import os
import struct
import subprocess
import tempfile
import unittest
from test_disc import fixture
import port
import native


@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN to the pinned local toolchain')
class PipelineTests(unittest.TestCase):
    def test_non_crazy_taxi_input_can_prepare_translate_compile_and_run(self):
        with tempfile.TemporaryDirectory(prefix='dc-pipeline-') as temp:
            base=Path(temp);descriptor=fixture(base,raw=True,title='PORT KIT SYNTHETIC TEST')
            track=base/'Different title track.bin';data=bytearray(track.read_bytes())
            data[21*2352+16:21*2352+24]=struct.pack('<4H',0x000b,0x0009,0x000b,0x0009)
            track.write_bytes(data)
            project=base/'project'
            class Args: pass
            args=Args();args.input=str(descriptor);args.project=str(project);args.descriptor=None;args.all_files=False
            args.toolchain=os.environ['DC_PORT_TEST_TOOLCHAIN'];args.base=None;args.abi=True;args.seconds=2
            with contextlib.redirect_stdout(io.StringIO()):
                port.prepare(args)
                profile=json.loads((project/'title-profile.json').read_text())
                profile.update(id='synthetic-return-test',loadAddress='0x8c010000',runtimeEntry='0x8c010000',
                    irqEntry='0x8c010000',irqPushRegisters=[8],stackPointer='0x8c00fc00',vectorBase='0x8c00f400',ramBytes=16777216)
                port.write_json(project/'title-profile.json',profile)
                port.translate(args)
                native.build(args,port.KIT,port.PortError,port.verify_project,port.write_json)
                self.check_bios_reads_frame_address(project,track,Path(args.toolchain))
                code=native.run(args,port.PortError,port.verify_project,port.write_json)
            self.assertEqual(code,0)
            result=json.loads((project/'.local/native/run-result.json').read_text())
            self.assertTrue(result['titleCodeEntered'])
            self.assertFalse(result['playable'])
            dispatch=(project/'.local/generated/src/dispatch_table.c').read_text()
            self.assertNotIn('0x0C004000',dispatch)
            self.assertNotIn('0xC100',dispatch)
            self.assertFalse(json.loads((project/'port.json').read_text())['evidence']['bootedToMenu'])

    def check_bios_reads_frame_address(self,project,track,toolchain):
        path=project/'.local/native'
        source='''
#include "recompiler/sh4_cpu.h"
#include "hal/dc_hardware.h"
#include "hal/dc_bios.h"
#include <assert.h>
#include <string.h>
void sh4_call_indirect(SH4CPU *c) {assert(!"Unexpected game call in BIOS test");}
void sh4_jump_indirect(SH4CPU *c) {assert(!"Unexpected game jump in BIOS test");}
void port_runtime_trace(void) {assert(!"Unexpected native fault in BIOS test");}
int main(int argc,char **argv) {
SH4CPU c={0};sh4_init_ex(&c,16777216);DCHardware *hw=dc_hw_init();
sh4_set_hardware(hw);sh4_set_cpu_ref(&c);sh4_bios_set_gdrom_track(argv[1],45000);
sh4_write32(&c,0x0c005000,45166);sh4_write32(&c,0x0c005004,1);sh4_write32(&c,0x0c005008,0x0c006000);
c.pc=0x8c0000bc;c.r[7]=0;c.r[4]=17;c.r[5]=0x0c005000;
assert(sh4_bios_syscall(&c));assert(memcmp(c.ram+0x6001,"CD001",5)==0);
return 0;
}'''
        (path/'bios-test.c').write_text(source)
        stems={'cpu','sh4_task','arm7','dc_hardware','dc_bios','naomi_io','pvr2_ta','pvr2_render','platform_sdl2','posix'}
        objects=[p for p in (path/'obj').glob('*.o') if p.stem.split('_',1)[1] in stems]
        subprocess.run(['clang','-std=c11','-I',str(toolchain/'include'),str(path/'bios-test.c'),
                        *map(str,objects),'-lm','-o',str(path/'bios-test')],check=True,capture_output=True)
        subprocess.run([str(path/'bios-test'),str(track)],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
