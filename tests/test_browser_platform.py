"""Execute the actual adapted platform clock past the old 5.1-hour overflow."""
from pathlib import Path
import importlib.util,os,re,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
CORE=Path(os.environ.get('DC_PORT_TEST_TOOLCHAIN',ROOT/'.local/dcrecomp'))
spec=importlib.util.spec_from_file_location('browser_adapter',ROOT/'browser.py')
browser=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser)
class BrowserPlatformTests(unittest.TestCase):
    @unittest.skipUnless((CORE/'src/platform/platform_sdl2.c').exists(),'Needs pinned toolchain')
    def test_monotonic_microseconds_after_six_hours_and_thirty_days(self):
        adapted=browser.adapt_platform((CORE/'src/platform/platform_sdl2.c').read_text())
        body=re.findall(r'uint64_t platform_get_ticks_us\(void\) \{([^}]+)\}',adapted)[-1]
        source='''#include <stdint.h>
#include <assert.h>
static double now;double emscripten_get_now(void){return now;}
uint64_t platform_get_ticks_us(void){'''+body+'''}
int main(void){
now=21600000;assert(platform_get_ticks_us()==21600000000ull);
now=2592000000;assert(platform_get_ticks_us()==2592000000000ull);
uint64_t a=platform_get_ticks_us();now+=.125;assert(platform_get_ticks_us()-a==125);
return 0;}'''
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'case.c').write_text(source)
            subprocess.run(['clang','-O2',str(p/'case.c'),'-o',str(p/'case')],check=True,capture_output=True)
            subprocess.run([str(p/'case')],check=True)
