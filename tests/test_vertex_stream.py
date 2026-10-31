"""GPU uploads reuse independent stores, orphan busy stores, never wait."""
from pathlib import Path
import subprocess,tempfile,unittest
class VertexStreamTests(unittest.TestCase):
 def test_reuse_growth_inflight_orphan_and_cleanup(self):
  root=Path(__file__).resolve().parents[1]
  code=r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
typedef unsigned GLuint;typedef unsigned GLenum;typedef void *GLsync;typedef ptrdiff_t GLsizeiptr;
typedef struct {float x,y,z,u,v,r,g,b,a;uint32_t pcw,tsp,tcw,isp;} PVR2RenderVertex;
enum {GL_ARRAY_BUFFER,GL_FLOAT,GL_FALSE,GL_STREAM_DRAW,GL_ALREADY_SIGNALED,GL_CONDITION_SATISFIED,GL_TIMEOUT_EXPIRED,GL_SYNC_GPU_COMMANDS_COMPLETE};
static unsigned next,allocations,updates,attributes,waits,deleted_syncs,deleted_buffers,deleted_vaos;
static GLuint bound,vao,vao_buffer[64];static GLsizeiptr size[64];static GLenum fence_result=GL_ALREADY_SIGNALED;
void glGenVertexArrays(int n,GLuint *id){*id=++next;}void glGenBuffers(int n,GLuint *id){*id=++next;}
void glBindVertexArray(GLuint id){vao=id;}void glBindBuffer(GLenum t,GLuint id){bound=id;}
void glVertexAttribPointer(int i,int n,GLenum type,int normalized,int stride,void *offset){assert(stride==sizeof(PVR2RenderVertex));assert((uintptr_t)offset==(i==0?0:i==1?12:20));vao_buffer[vao]=bound;attributes++;}
void glEnableVertexAttribArray(int i){}
GLenum glClientWaitSync(GLsync s,unsigned flags,uint64_t timeout){assert(s && flags==0 && timeout==0);waits++;return fence_result;}
void glDeleteSync(GLsync s){assert(s);deleted_syncs++;}
void glBufferData(GLenum t,GLsizeiptr bytes,void *data,GLenum usage){assert(!data && bytes>0);size[bound]=bytes;allocations++;}
void glBufferSubData(GLenum t,GLsizeiptr offset,GLsizeiptr bytes,const void *data){assert(offset==0 && bytes<=size[bound] && data && vao_buffer[vao]==bound);updates++;}
GLsync glFenceSync(GLenum type,unsigned flags){assert(flags==0);return (void*)1;}
void glDeleteBuffers(int n,GLuint *id){deleted_buffers++;}void glDeleteVertexArrays(int n,GLuint *id){deleted_vaos++;}
#include "vertex_stream.h"
int main(void){
 PVR2RenderVertex v[60]={0};
 for(int i=0;i<6;i++){port_stream_vertices(v,30);port_stream_submitted();}
 assert(allocations==3 && attributes==9 && updates==6 && waits==3);
 fence_result=GL_TIMEOUT_EXPIRED;port_stream_vertices(v,30);port_stream_submitted();assert(allocations==4);
 fence_result=GL_CONDITION_SATISFIED;port_stream_vertices(v,60);port_stream_submitted();assert(allocations==5);
 port_stream_destroy();assert(deleted_buffers==3 && deleted_vaos==3 && deleted_syncs==8);
 port_stream_destroy();assert(deleted_buffers==3 && deleted_vaos==3);return 0;
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.c').write_text(code)
   subprocess.run(['clang','-O2','-fsanitize=address,undefined','-I',str(root/'runtime'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True,capture_output=True)
