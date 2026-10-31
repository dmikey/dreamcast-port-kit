from pathlib import Path
import importlib.util,os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class IdleWaitTests(unittest.TestCase):
 def test_only_unchanged_ram_cycles_cooperate_before_deadline(self):
  core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])
  source='''#include <assert.h>
#include "recompiler/sh4_cpu.h"
#include "idle_wait.h"
int main(void){
 SH4CPU cpu={0};cpu.ram_size=16*1024*1024;PortIdleDetector d={0};
 for(int n=0;n<32;n++){cpu.r[0]=n;assert(!port_idle_probe(&d,&cpu,0,0x0c001000,n+1,n*.1,100,0));}
 int idle=0;for(int n=32;n<96;n++){cpu.r[0]=n%7;idle+=port_idle_probe(&d,&cpu,0,0x0c001000+(n%7)*4,n+1,n*.1,100,0);}assert(idle>0);
 assert(!port_idle_probe(&d,&cpu,1,0x0c001000,97,10,100,0));
 for(int n=98;n<130;n++){cpu.fr[0]=(float)n;assert(!port_idle_probe(&d,&cpu,1,0x0c001000,n,10+n*.1,100,0));}
 assert(!port_idle_probe(&d,&cpu,1,0x005f8000,130,24,100,0));
 for(int n=131;n<160;n++)assert(!port_idle_probe(&d,&cpu,1,0x0c001000,n,25,26,0));
 assert(!port_idle_probe(&d,&cpu,1,0x0c001000,161,25,100,1));
 assert(port_idle_probe(&d,&cpu,1,0x0c001000,161,30,100,0));
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(source)
   subprocess.run(['clang','-O2','-fsanitize=address,undefined','-I',str(core/'include'),'-I',str(ROOT/'runtime'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True)
