"""Execute the shared BIOS TOC implementation against both GD-ROM areas."""
import os,subprocess,tempfile,unittest
from pathlib import Path
from gdrom import adapt

@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class TocTests(unittest.TestCase):
 def test_density_track_numbers_and_leadout(self):
  source=adapt((Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])/'src/hal/dc_bios.c').read_text())
  begin=source.index('    case GDC_CMD_GETTOC:');end=source.index('    default:',begin)
  body=source[begin:end]
  code=r'''
#include <assert.h>
#include <stdint.h>
#define GDC_CMD_GETTOC 18
#define GDC_CMD_GETTOC2 19
typedef int SH4CPU;
static uint32_t mem[2048];
static struct {uint32_t start_lba,sectors;} g_tracks[]={{0,10957},{45000,504150}};
static int g_track_count=2;
static uint32_t g_disc_start_lba=0;
uint32_t sh4_read32(SH4CPU*c,uint32_t a){return mem[a/4];}
void sh4_write32(SH4CPU*c,uint32_t a,uint32_t v){mem[a/4]=v;}
int toc(SH4CPU*cpu,unsigned cmd,unsigned param){switch(cmd){
'''+body+r'''
default:return -2;}}
int main(void){mem[1]=1;mem[2]=1024;assert(toc(0,19,4)==0);
assert(mem[256]==0xffffffff);assert(mem[258]==(0x41000000|45150));
assert(mem[355]==0x41030000);assert(mem[356]==0x41030000);
assert(mem[357]==(0x41000000|549300));
mem[1]=0;assert(toc(0,18,4)==0);assert(mem[256]==(0x41000000|150));
assert(mem[258]==0xffffffff);assert(mem[355]==0x41010000);
assert(mem[356]==0x41010000);assert(mem[357]==(0x41000000|11107));
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.c').write_text(code)
   subprocess.run(['clang',str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True)
