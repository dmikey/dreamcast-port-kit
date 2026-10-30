from pathlib import Path
import importlib.util,os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audio_clock',ROOT/'audio_clock.py');clock=importlib.util.module_from_spec(spec);spec.loader.exec_module(clock)
class AudioClockTests(unittest.TestCase):
 def test_exact_sample_rate_independent_of_poll_frequency(self):
  source='''#include <assert.h>
#include "audio_clock.h"
int main(void){
 for(unsigned step=1;step<=10000;step*=10){PortAudioClock c={0};uint64_t total=0;port_audio_clock_step(&c,0);for(unsigned t=step;t<=1000000;t+=step)total+=port_audio_clock_step(&c,t);assert(total==44100 && c.remainder==0);}
 PortAudioClock c={0};uint64_t now=0,total=0;port_audio_clock_step(&c,now);
 for(unsigned i=0;i<100000;i++){now+=(i*37)%1000;total+=port_audio_clock_step(&c,now);}
 assert(total==now*441/10000);assert(c.remainder==now*441%10000);
 assert(port_audio_clock_step(&c,1)==0 && c.remainder==0);return 0;}
'''
  self.run_c(source)
 def run_c(self,source):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(source)
   subprocess.run(['clang','-O2','-fsanitize=address,undefined','-I',str(ROOT/'runtime'),str(p/'t.c'),'-o',str(p/'t')],check=True,capture_output=True)
   return subprocess.run([str(p/'t')],check=True,capture_output=True,text=True).stdout
 @unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
 def test_original_timer_drift_reproduced_and_adapter_removes_it(self):
  hardware=(Path(os.environ['DC_PORT_TEST_TOOLCHAIN'])/'src/hal/dc_hardware.c').read_text()
  source=hardware[hardware.index('static void aica_advance_timer_a(void) {'):hardware.index('/* FIQ tracks pending-and-enabled')]
  source=source[:source.rfind('/*') ] if source.rstrip().endswith('*/') else source
  original=source.replace('aica_advance_timer_a','old_timer').replace('    uint32_t *ta =','    observed+=samples;\n    uint32_t *ta =')
  modified=source.replace('static void aica_advance_timer_a(void)', 'static void aica_advance_timer_a(uint64_t now_us)').replace('    uint64_t now_us = platform_get_ticks_us();\n','')
  modified=clock.adapt(modified).replace('    uint32_t *ta =','    observed+=samples;\n    uint32_t *ta =')
  harness='''#include <assert.h>
#include <stdio.h>
#include "audio_clock.h"
#define AICA_TIMER_A 0
#define AICA_SCIPD 1
#define AICA_SCIEB 2
#define AICA_INT_TIMER_A 0
static uint32_t regs[3];static unsigned g_timer_a_fires,g_arm7;static uint64_t ticks,observed;
static uint32_t *aica_reg(unsigned n){return regs+n;}
static void arm7_set_fiq(void *cpu,int value){}
static uint64_t platform_get_ticks_us(void){return ticks;}
'''+original+modified+'''
int main(void){for(ticks=1;ticks<=1000001;ticks++)old_timer();assert(observed==45454);observed=0;for(ticks=1;ticks<=1000001;ticks++)aica_advance_timer_a(ticks);assert(observed==44100);return 0;}
'''
  self.run_c(harness)
