"""Feed actual TA packets through the browser parser adapter."""
from pathlib import Path
import os,sys,tempfile,subprocess,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import graphics

@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class GraphicsTests(unittest.TestCase):
    def test_float_color_16bit_uv_vertex_packets(self):
        core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);include=path/'include';include.mkdir()
            graphics.adapt(core,path,include,'')
            (path/'test.c').write_text('''
#include "hal/pvr2.h"
#include <assert.h>
#include <string.h>
#include <math.h>
void dc_hw_raise_istnrm(int bit) {}
static unsigned bits(float f) {unsigned b;memcpy(&b,&f,4);return b;}
int main(void) {
    pvr2_ta_init();unsigned header[8]={0x80000019,0,0,0,0,0,0,0};pvr2_ta_write(header);
    for(int n=0;n<3;n++) {unsigned v[16]={0};v[0]=0xe0000000|(n==2?0x10000000:0);v[1]=bits(n==1?2:0);v[2]=bits(n==2?2:0);v[3]=bits(1);v[4]=0x3f003e80;v[8]=bits(1);v[9]=bits(.2f);v[10]=bits(.4f);v[11]=bits(.6f);pvr2_ta_write(v);pvr2_ta_write(v+8);}
    const PVR2TriList *list=pvr2_ta_get_list(0);assert(list->count==3);
    assert(list->vertices[0].u==.5f && list->vertices[0].v==.25f);
    assert(fabsf(list->vertices[0].r-.2f)<.0001f && list->vertices[0].a==1);
    pvr2_ta_destroy();return 0;
}''')
            subprocess.run(['clang','-std=c11','-I',str(include),'-I',str(core/'include'),str(path/'ta.c'),str(path/'test.c'),'-o',str(path/'test')],check=True,capture_output=True)
            subprocess.run([str(path/'test')],check=True,capture_output=True)
