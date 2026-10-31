from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class BrowserDiscCacheTests(unittest.TestCase):
 def test_alternating_streams_track_keys_lru_and_partial_sector_validation(self):
  source='''#include <assert.h>
#include "browser_disc.h"
static unsigned fetches;static int truncate;
double emscripten_get_now(void){return 0;}
void emscripten_wget_data(const char *url,void **data,int *size,int *error){
 int track;long offset,length;assert(sscanf(url,"/disc/%d?offset=%ld&length=%ld",&track,&offset,&length)==3);
 *size=truncate?2351:(int)length;*data=malloc(*size);*error=0;fetches++;
 for(int i=0;i<*size;i++)((unsigned char*)*data)[i]=(unsigned char)(track+offset/2352+i/2352);
}
int main(int argc,char **argv){
 unsigned char sector[2352];
 if(argc>1){truncate=1;port_disc_read(0,0,sector);return 0;}
 for(int round=0;round<10;round++)for(int i=0;i<16;i++){
  port_disc_read(0,i*PORT_DISC_CHUNK,sector);assert(sector[0]==(unsigned char)(i*128));
  port_disc_read(0,i*PORT_DISC_CHUNK+2352,sector);assert(sector[0]==(unsigned char)(i*128+1));
 }
 assert(fetches==16 && port_disc_misses==16 && port_disc_hits==304);
 // Touch chunk zero, then make room for another track. Chunk one is oldest.
 port_disc_read(0,0,sector);port_disc_read(1,0,sector);assert(sector[0]==1 && fetches==17);
 port_disc_read(0,0,sector);assert(sector[0]==0 && fetches==17);
 port_disc_read(0,PORT_DISC_CHUNK,sector);assert(fetches==18);
 for(int i=0;i<PORT_DISC_CACHE_SLOTS;i++)free(port_disc_cache[i].data);
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'emscripten.h').write_text('double emscripten_get_now(void);void emscripten_wget_data(const char*,void**,int*,int*);\n');(p/'test.c').write_text(source)
   subprocess.run(['clang','-O2','-fsanitize=address,undefined','-I',str(p),'-I',str(ROOT/'runtime'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True,capture_output=True)
   result=subprocess.run([str(p/'test'),'truncated'],capture_output=True)
   self.assertNotEqual(result.returncode,0);self.assertIn(b'truncated sector',result.stderr)
