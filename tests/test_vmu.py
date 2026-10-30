"""VMU format, durable conflict-safe saves and real Maple DMA protocol."""
import json,os,struct,subprocess,tempfile,unittest
from pathlib import Path
from vmu import VmuStore,VmuConflict,blank_image,etag,SIZE
ROOT=Path(__file__).resolve().parents[1]
class VmuStorageTests(unittest.TestCase):
 def test_format_roundtrip_and_stale_writer_preserves_save(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=VmuStore(tmp);original=store.load();self.assertEqual(len(original),SIZE);self.assertEqual(store.status()['freeBlocks'],200)
   root=255*512;self.assertEqual(struct.unpack_from('<6H',original,root+70),(254,1,253,13,0,200))
   first=etag(original);next_tag=store.write_phase(199,3,b'A'*128,first)
   self.assertNotEqual(first,next_tag);self.assertEqual(VmuStore(tmp).load()[199*512+384:200*512],b'A'*128)
   with self.assertRaises(VmuConflict):store.write_phase(199,3,b'B'*128,first)
   self.assertEqual(store.load()[199*512+384:200*512],b'A'*128)
   self.assertEqual(store.path.stat().st_mode&0o777,0o600)
 def test_invalid_ranges_and_corrupt_existing_image_are_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=VmuStore(tmp);data=store.load()
   for block,phase,length in [(256,0,128),(0,4,128),(-1,0,128),(0,0,127)]:
    with self.assertRaises(ValueError):store.write_phase(block,phase,b'x'*length,etag(data))
   store.path.write_bytes(b'existing broken image')
   with self.assertRaises(ValueError):store.load()
   self.assertEqual(store.path.read_bytes(),b'existing broken image')

@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class VmuMapleTests(unittest.TestCase):
 def test_discovery_phased_writes_readback_lcd_and_io_failure(self):
  import maple
  core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN']);source=maple.adapt((core/'src/hal/dc_hardware.c').read_text());dma=source[source.index('void dc_maple_dma('):source.index('MapleController* dc_maple_get_controller')]
  harness=r'''
#include "hal/dc_hardware.h"
#include "vmu.h"
#include "project.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
struct DCHardware {MapleController controllers[4];bool controller_connected[4];};
static uint8_t ram[16*1024*1024];
uint8_t *sh4_get_ram_ptr(void){return ram;}
uint32_t sh4_get_ram_mask(void){return sizeof ram-1;}
'''+dma+r'''
static DCHardware h;static uint32_t *r=(uint32_t*)(ram+1024);
static void command(unsigned unit,unsigned cmd,unsigned count,const uint32_t *payload){uint32_t *p=(uint32_t*)ram;p[0]=0x80000000u|count;p[1]=0x0c000400;p[2]=cmd|(unit<<8)|(count<<24);if(count)memcpy(p+3,payload,count*4);memset(r,0,600);dc_maple_dma(&h,0);}
int main(void){h.controller_connected[0]=true;assert(port_vmu_init());command(0x20,1,0,NULL);assert(((r[0]>>16)&255)==0x21);assert(((r[0]>>8)&255)==0);assert(r[1]==0x01000000);
command(1,1,0,NULL);assert((r[0]&255)==5&&r[1]==0x0e000000&&r[2]==0x403f7e7e&&r[4]==0x00410f00);assert(((r[0]>>16)&255)==1);
command(2,1,0,NULL);assert(r[0]==~0u);
/* NOP, reset and SDCKB are four-byte control records, not START frames. */
for(unsigned op=2;op<=7;op++){if(op==5||op==6)continue;uint32_t *p=(uint32_t*)ram;p[0]=op<<8;p[1]=0x80000000u;p[2]=0x0c000400;p[3]=0x101;memset(r,0,600);dc_maple_dma(&h,0x0c000000);assert((r[0]&255)==5&&r[1]==0x0e000000);}
/* Invalid response pointers must not corrupt RAM zero. */
uint32_t *p=(uint32_t*)ram;p[0]=0x80000000u;p[1]=0;p[2]=0x2001;dc_maple_dma(&h,0x0c000000);assert(p[0]==0x80000000u);
uint32_t input[50]={0x02000000,0};command(1,10,1,input);assert((r[0]&255)==8&&r[2]==255&&r[3]==0x00fe00ff);
for(unsigned phase=0;phase<4;phase++){input[1]=(199u<<24)|(phase<<8);memset(input+2,phase+1,128);command(1,12,34,input);assert((r[0]&255)==7);}
input[1]=199u<<24;command(1,11,2,input);assert((r[0]&255)==8&&(r[0]>>24)==130);for(unsigned i=0;i<512;i++)assert(((uint8_t*)(r+3))[i]==i/128+1);
input[1]=1u<<16;command(1,11,2,input);assert((r[0]&255)==0xfb);input[1]=0;command(1,12,3,input);assert((r[0]&255)==0xfb);
input[0]=0x04000000;input[1]=0;memset(input+2,0xa5,192);command(1,12,50,input);assert((r[0]&255)==7);command(1,11,2,input);assert((r[0]&255)==8&&r[3]==0xa5a5a5a5);
input[0]=0x08000000;command(1,11,2,input);assert((r[0]&255)==8&&(r[0]>>24)==3);assert(((uint8_t*)(r+2))[2]>=1&&((uint8_t*)(r+2))[2]<=12);
input[0]=0x02000000;input[1]=199u<<24;assert(rename(PORT_VMU_PATH,PORT_VMU_PATH ".backup")==0);assert(mkdir(PORT_VMU_PATH,0700)==0);memset(input+2,0xff,128);command(1,12,34,input);assert((r[0]&255)==0xfb&&r[1]==8);command(1,11,2,input);assert(r[3]==0x01010101);assert(rmdir(PORT_VMU_PATH)==0);assert(rename(PORT_VMU_PATH ".backup",PORT_VMU_PATH)==0);
return 0;}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);store=VmuStore(p);store.load();(p/'project.h').write_text('#define PORT_VMU_PATH '+json.dumps(str(store.path))+'\n');(p/'test.c').write_text(harness)
   subprocess.run(['clang','-std=c11','-fsanitize=address,undefined','-g','-I',str(p),'-I',str(core/'include'),'-I',str(ROOT/'runtime'),str(p/'test.c'),str(ROOT/'runtime/vmu.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True,capture_output=True)
   disk=store.load();self.assertEqual(disk[199*512:199*512+4],b'\1'*4);self.assertEqual(disk[199*512+384:200*512],b'\4'*128)
