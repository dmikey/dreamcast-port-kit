from pathlib import Path
import subprocess,tempfile,unittest
class FrameTimingTests(unittest.TestCase):
 def test_sixty_hz_spikes_pause_and_bounded_storage(self):
  header=Path(__file__).resolve().parents[1]/'runtime/frame_timing.h'
  source='#include <assert.h>\n#include "'+str(header)+'"\n'+'''int main(void){
   PortFrameTiming s={0};double now=2000;port_frame_timing(&s,now);
   int reports=0;for(int i=0;i<301;i++){now+=1000.0/60;if(port_frame_timing(&s,now))reports++;}
   assert(reports==1 && s.fps>59.99 && s.fps<60.01 && s.p99<16.67 && !s.slow);
   now+=2000;assert(!port_frame_timing(&s,now) && s.count==0);
   for(int i=0;i<300;i++){now+=i==100?60:1000.0/60;port_frame_timing(&s,now);}
   assert(s.slow==1 && s.maximum==60 && s.p99<16.67 && s.fps<60);
   now+=2000;port_frame_timing(&s,now);reports=0;
   for(int i=0;i<1024;i++){now+=1;reports+=port_frame_timing(&s,now);assert(s.count<512);}
   assert(reports==2 && s.fps==1000);return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(source)
   subprocess.run(['clang','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True)
