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
    for(int kind=9;kind<=14;kind++) {
      pvr2_ta_reset();unsigned h[16]={0};h[0]=0x80000040u|(kind>=11?8:0)|((kind==10||kind>=13)?32:0)|((kind==12||kind==14)?1:0);h[1]=0xC0000000;h[2]=0x1234;h[3]=0x5678;h[8]=bits(1);h[9]=bits(.2f);h[10]=bits(.4f);h[11]=bits(.6f);pvr2_ta_write(h);if(kind==10||kind>=13)pvr2_ta_write(h+8);
      for(int n=0;n<3;n++){unsigned v[16]={0};v[0]=0xe0000000|(n==2?0x10000000:0);v[1]=bits(n==1?2:0);v[2]=bits(n==2?2:0);v[3]=bits(1);v[4]=(kind==12||kind==14)?0x3f003e80:bits(.5f);v[5]=bits(.25f);v[kind==9||kind==10?4:6]=(kind==10||kind>=13)?bits(.5f):0xff336699;pvr2_ta_write(v);if(kind>=11)pvr2_ta_write(v+8);}
      const PVR2TriList *l=pvr2_ta_get_list(0);assert(l->count==3);assert(l->vertices[0].isp==0xc0000000);assert(l->vertices[0].tcw==0x5678);assert(fabsf(l->vertices[0].r-((kind==10||kind>=13)?.1f:.2f))<.0001f);if(kind>=11){assert(l->vertices[0].u==.5f);assert(l->vertices[0].v==.25f);}
    }
    pvr2_ta_reset();unsigned intensity[8]={0x80000028,0,0,0};intensity[4]=bits(1);intensity[5]=bits(.2f);intensity[6]=bits(.4f);intensity[7]=bits(.6f);pvr2_ta_write(intensity);
    unsigned reused[8]={0x80000038,0,0,0,0xdeadbeef,0x12345678,0x87654321,0};pvr2_ta_write(reused);
    for(int n=0;n<3;n++){unsigned v[8]={0};v[0]=0xe0000000|(n==2?0x10000000:0);v[1]=bits(n==1?2:0);v[2]=bits(n==2?2:0);v[3]=bits(1);v[4]=bits(.5f);v[5]=bits(.25f);v[6]=bits(.5f);pvr2_ta_write(v);}
    const PVR2TriList *reuse=pvr2_ta_get_list(0);assert(reuse->count==3);assert(fabsf(reuse->vertices[0].r-.1f)<.0001f);assert(fabsf(reuse->vertices[0].g-.2f)<.0001f);assert(fabsf(reuse->vertices[0].b-.3f)<.0001f);assert(reuse->vertices[0].a==1);
    pvr2_ta_reset();unsigned mod[8]={0x81000000};pvr2_ta_write(mod);unsigned mv[16]={0xe0000000,0,0,0,0,0,0,0,0x80000000,0,0,0,0,0,0,0};for(int i=0;i<3;i++){mv[0]=0xe0000000|(i==2?0x10000000:0);pvr2_ta_write(mv);pvr2_ta_write(mv+8);}assert(pvr2_ta_get_list(0)->count==0);assert(pvr2_ta_get_list(1)->count==0);
    pvr2_ta_destroy();return 0;
}''')
            subprocess.run(['clang','-std=c11','-I',str(include),'-I',str(core/'include'),str(path/'ta.c'),str(path/'test.c'),'-o',str(path/'test')],check=True,capture_output=True)
            subprocess.run([str(path/'test')],check=True,capture_output=True)
