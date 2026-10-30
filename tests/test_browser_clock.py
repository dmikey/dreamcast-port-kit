from pathlib import Path
import subprocess,tempfile,unittest
class BrowserClockTests(unittest.TestCase):
 def test_sixty_hz_and_no_disc_or_stall_burst(self):
  header=Path(__file__).resolve().parents[1]/'runtime/browser_clock.h'
  source='#include <assert.h>\n#include "'+str(header)+'"\n'+'''int main(void){int frames=0;for(int t=0;t<=1000;t++)frames+=port_vblank_ready(t);assert(frames==60);assert(port_vblank_ready(10000)==1);for(int n=0;n<20;n++)assert(port_vblank_ready(10000)==0);assert(port_vblank_ready(10017)==1);return 0;}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(source);subprocess.run(['clang',str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True);subprocess.run([str(p/'t')],check=True)
