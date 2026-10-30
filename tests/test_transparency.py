from pathlib import Path
import tempfile,subprocess,unittest
class TransparencyTests(unittest.TestCase):
 def test_far_first_and_equal_depth_order_is_stable(self):
  header=Path(__file__).resolve().parents[1]/'runtime/transparency.h'
  source='''#include <assert.h>
typedef struct {float z;int id;}PVR2RenderVertex;
typedef struct {PVR2RenderVertex *vertices;int count;}PVR2TriList;
#include "'''+str(header)+'''"
int main(void){PVR2RenderVertex v[15];float d[5]={3,1,2,1,4};for(int t=0;t<5;t++)for(int n=0;n<3;n++){v[t*3+n].z=d[t];v[t*3+n].id=t;}PVR2TriList l={v,15};port_sort_transparent(&l);int expected[5]={1,3,2,0,4};for(int t=0;t<5;t++)for(int n=0;n<3;n++)assert(v[t*3+n].id==expected[t]);port_sort_transparent(&l);for(int t=0;t<5;t++)assert(v[t*3].id==expected[t]);return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(source);subprocess.run(['clang',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True);subprocess.run([str(p/'t')],check=True)
