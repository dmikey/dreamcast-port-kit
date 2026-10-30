from pathlib import Path
import tempfile,subprocess,unittest
class TransparencyTests(unittest.TestCase):
 def test_far_first_and_equal_depth_order_is_stable(self):
  header=Path(__file__).resolve().parents[1]/'runtime/transparency.h'
  source='''#include <assert.h>
typedef struct {float z;int id;}PVR2RenderVertex;
typedef struct {PVR2RenderVertex *vertices;int count;}PVR2TriList;
#include "'''+str(header)+'''"
int main(void){PVR2RenderVertex v[15];float d[5]={3,1,2,1,4};for(int t=0;t<5;t++)for(int n=0;n<3;n++){v[t*3+n].z=d[t];v[t*3+n].id=t;}PVR2TriList l={v,15};port_sort_transparent(&l);int expected[5]={1,3,2,0,4};for(int t=0;t<5;t++)for(int n=0;n<3;n++)assert(v[t*3+n].id==expected[t]);port_sort_transparent(&l);for(int t=0;t<5;t++)assert(v[t*3].id==expected[t]);
 // Larger duplicate-depth workload checks stable order, complete triangle
 // payload preservation, growth and reuse of scratch allocations.
 PVR2RenderVertex big[1503];
 for(int t=0;t<501;t++)for(int n=0;n<3;n++){big[t*3+n].z=(t*37)%23;big[t*3+n].id=t*3+n;}
 PVR2TriList many={big,1503};port_sort_transparent(&many);
 for(int t=0;t<501;t++){
  int original=big[t*3].id/3;
  for(int n=0;n<3;n++){assert(big[t*3+n].id==original*3+n);assert(big[t*3+n].z==(original*37)%23);}
  if(t){assert(big[t*3].z>=big[(t-1)*3].z);if(big[t*3].z==big[(t-1)*3].z)assert(big[t*3].id>big[(t-1)*3].id);}
 }
 port_sort_transparent(&l);assert(v[0].id==1);return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(source);subprocess.run(['clang','-fsanitize=address,undefined',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True);subprocess.run([str(p/'t')],check=True)
