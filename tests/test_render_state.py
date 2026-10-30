"""Repeated materials keep correct state while avoiding redundant GL calls."""
from pathlib import Path
import re,subprocess,tempfile,unittest

class RenderStateTests(unittest.TestCase):
    def test_state_changes_and_list_invalidation(self):
        header=(Path(__file__).resolve().parents[1]/'runtime/texture_gl.h').read_text()
        constants=sorted(set(re.findall(r'\bGL_[A-Z0-9_]+\b',header)))
        source='''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef unsigned GLuint;typedef int GLint;typedef unsigned GLenum;
'''+''.join('#define %s %d\n'%(name,i+1) for i,name in enumerate(constants))+'''
#define PVR2_LIST_TRANS 2
#define PVR2_LIST_PUNCHTHRU 4
typedef struct {float x,y,z,u,v,r,g,b,a;uint32_t pcw,tsp,tcw,isp;} PVR2RenderVertex;
typedef struct {PVR2RenderVertex *vertices;int count;} PVR2TriList;
static GLuint g_shader=1;
static unsigned char ram[8*1024*1024];
unsigned char *sh4_get_vram_ptr(void){return ram;}
void *sh4_get_hardware(void){return 0;}
uint32_t dc_hw_read32(void *h,unsigned a){return 0;}
void glDeleteTextures(int n,GLuint *t){}
void glGenTextures(int n,GLuint *t){*t=1;}
void glBindTexture(int a,GLuint b){}
void glTexParameteri(int a,int b,int c){}
void glTexImage2D(int a,int b,int c,int d,int e,int f,int g,int h,void *p){}
void glActiveTexture(int t){}
static int cull_enabled,cull_face;void glEnable(int c){assert(c==GL_CULL_FACE);cull_enabled=1;}void glDisable(int c){assert(c==GL_CULL_FACE);cull_enabled=0;}void glCullFace(int c){cull_face=c;}
static int queries,uniform_calls,depth_calls,mask_calls,blend_calls,draws,values[5],mask;
GLint glGetUniformLocation(GLuint s,const char *name){const char *names[]={"uTextured","uShading","uIgnoreAlpha","uUseAlpha","uPunch"};queries++;for(int i=0;i<5;i++)if(!strcmp(names[i],name))return i;assert(0);return -1;}
void glUniform1i(int loc,int value){uniform_calls++;values[loc]=value;}
void glDepthFunc(int mode){depth_calls++;assert(mode==GL_GEQUAL);}
void glDepthMask(int value){mask_calls++;mask=value;}
void glBlendFunc(int s,int d){blend_calls++;assert((s==GL_SRC_ALPHA && d==GL_ONE_MINUS_SRC_ALPHA)||(s==GL_ZERO && d==GL_SRC_COLOR));}
void glDrawArrays(int mode,int at,int count){draws++;assert(count==(at==0?6:3));assert(values[0]==0 && values[1]==(at<6?1:2));assert(values[2]==0 && values[3]==1);}
'''+header+'''
int main(void){
 PVR2RenderVertex vertices[9]={0};
 for(int i=0;i<9;i++){vertices[i].isp=6u<<29;vertices[i].tcw=i/3;vertices[i].tsp=(i<6?1u:2u)<<6 | 1u<<20 | 4u<<29 | 5u<<26;}
 PVR2RenderVertex a={0},b={0};
 a.pcw=b.pcw=8;a.tcw=b.tcw=123;
 assert(port_same_material(&a,&b));
 b.tsp=1u<<15;assert(!port_same_material(&a,&b));b.tsp=0;
 b.tcw++;assert(!port_same_material(&a,&b));b.tcw=a.tcw;
 b.isp=1u<<26;assert(!port_same_material(&a,&b));b.isp=0;
 b.tsp=1u<<19;assert(!port_same_material(&a,&b));b.tsp=0;
 a.pcw=b.pcw=0;b.tcw++;b.tsp=0x7803f;assert(port_same_material(&a,&b));
 b.tsp|=1u<<6;assert(!port_same_material(&a,&b));
 PVR2TriList list={vertices,9};port_draw_materials(&list,0);
 assert(queries==5 && uniform_calls==6 && depth_calls==1 && mask_calls==1 && mask==GL_TRUE && draws==2);
 port_draw_materials(&list,PVR2_LIST_TRANS);
 assert(queries==5 && uniform_calls==12 && depth_calls==2 && mask_calls==2 && mask==GL_FALSE && blend_calls==2 && draws==4);
 port_draw_materials(&list,PVR2_LIST_PUNCHTHRU);assert(values[4]==1 && mask==GL_TRUE && queries==5);
 for(int i=0;i<9;i++)vertices[i].isp|=2u<<27;
 port_draw_materials(&list,0);assert(cull_enabled && cull_face==GL_FRONT);
 for(int i=0;i<9;i++)vertices[i].isp=(6u<<29)|(3u<<27);
 port_draw_materials(&list,0);assert(cull_enabled && cull_face==GL_BACK);
 for(int i=0;i<9;i++)vertices[i].isp=6u<<29;
 port_draw_materials(&list,0);assert(!cull_enabled);
 for(int i=0;i<9;i++)vertices[i].tsp=(vertices[i].tsp&0x03ffffffu)|(2u<<26);
 int before_blends=blend_calls;port_draw_materials(&list,0);assert(blend_calls==before_blends+1);
 g_shader=2;port_draw_materials(&list,0);assert(queries==10 && values[4]==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'test.c').write_text(source)
            subprocess.run(['clang','-std=c11',str(path/'test.c'),'-o',str(path/'test')],check=True,capture_output=True)
            subprocess.run([str(path/'test')],check=True)
