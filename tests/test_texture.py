"""Known direct and palette colors exercise runtime VRAM texture decoding."""
from pathlib import Path
import subprocess,tempfile,unittest

class TextureTests(unittest.TestCase):
    def test_rgb565_and_palette8888(self):
        source=Path(__file__).resolve().parents[1]/'runtime/texture_gl.h'
        decoder=source.read_text().split('static void port_draw_materials')[0]
        harness='''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef unsigned GLuint;
#define GL_TEXTURE_2D 0
#define GL_TEXTURE_MIN_FILTER 0
#define GL_TEXTURE_MAG_FILTER 0
#define GL_LINEAR 0
#define GL_TEXTURE_WRAP_S 0
#define GL_TEXTURE_WRAP_T 0
#define GL_CLAMP_TO_EDGE 0
#define GL_MIRRORED_REPEAT 0
#define GL_REPEAT 0
#define GL_RGBA 0
#define GL_UNSIGNED_BYTE 0
static unsigned char ram[8*1024*1024];
static uint32_t palette[1024];
unsigned char *sh4_get_vram_ptr(void) {return ram;}
void *sh4_get_hardware(void) {return 0;}
uint32_t dc_hw_read32(void *h,unsigned addr) {return addr==0x5f8108?3:palette[(addr-0x5f9000)/4];}
void glDeleteTextures(int n,GLuint *t) {}
void glGenTextures(int n,GLuint *t) {*t=1;}
void glBindTexture(int a,GLuint b) {}
void glTexParameteri(int a,int b,int c) {}
static int uploads;
void glTexImage2D(int a,int b,int c,int d,int e,int f,int g,int h,void *p) {uploads++;}
'''+decoder+'''
int main(void) {
    for(int i=0;i<64;i++){ram[i*2]=0;ram[i*2+1]=0xf8;}
    port_begin_textures();port_texture((1u<<27)|(1u<<26),0);
    assert(port_texels[0]==255 && port_texels[1]==0 && port_texels[2]==0 && port_texels[3]==255);
    port_begin_textures();port_texture((1u<<27)|(1u<<26),0);assert(uploads==1);
    port_texture((1u<<27)|(1u<<26),(5u<<26)|(3u<<6)|(1u<<19)|(1u<<20));assert(uploads==1);
    for(unsigned x=0;x<1024;x++){unsigned expected=0;for(unsigned bit=0;bit<10;bit++)expected|=((x>>bit)&1)<<(bit*2);assert(port_spread(x)==expected);}

    memset(ram,0,sizeof ram);palette[0]=0xff12ab34;port_begin_textures();
    port_texture(6u<<27,0);
    assert(port_texels[0]==0x12 && port_texels[1]==0xab && port_texels[2]==0x34 && port_texels[3]==255);
    port_begin_textures();port_texture(6u<<27,0);assert(uploads==2);
    palette[0]=0xffaabbcc;port_begin_textures();port_texture(6u<<27,0);assert(uploads==3 && port_texels[0]==0xaa);
    ram[0]=1;palette[1]=0xff123456;port_begin_textures();port_texture(6u<<27,0);assert(uploads==4 && port_texels[0]==0x12);
    memset(ram,0,sizeof ram);ram[48]=0;ram[49]=0xf8;port_begin_textures();port_texture((1u<<31)|(1u<<27),0);assert(port_texels[0]==255 && port_texels[1]==0);
    memset(ram,0,sizeof ram);ram[24]=1;palette[0]=0;palette[1]=0xff123456;port_begin_textures();port_texture((1u<<31)|(6u<<27),0);assert(port_texels[0]==0x12 && port_texels[3]==255);
    // A scene with more than 128 textures must retain its working set.
    port_begin_textures();
    for(unsigned i=0;i<200;i++)port_texture((1u<<27)|(1u<<26)|i*16,0);
    int before=uploads;port_begin_textures();
    for(unsigned i=0;i<200;i++)port_texture((1u<<27)|(1u<<26)|i*16,0);
    assert(uploads==before);
    // Compressed 1024-square textures force GPU-budget eviction, not growth.
    for(unsigned i=0;i<20;i++){port_begin_textures();port_texture((1u<<30)|(1u<<27)|i*32768,63);assert(port_texture_gpu_bytes<=PORT_TEXTURE_GPU_BUDGET && port_texture_source_bytes<=PORT_TEXTURE_SOURCE_BUDGET);}
    assert(port_texture_gpu_bytes<=64u*1024*1024);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'test.c').write_text(harness)
            subprocess.run(['clang','-std=c11',str(path/'test.c'),'-o',str(path/'test')],check=True,capture_output=True)
            subprocess.run([str(path/'test')],check=True)
