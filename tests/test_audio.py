"""Execute real mixer against original synthetic RAM; no commercial audio assets."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class AudioTests(unittest.TestCase):
    def test_pcm_pitch_loop_stereo_key_execution_and_adpcm(self):
        source=r'''
#include "aica_mixer.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
 static uint8_t ram[2*1024*1024];uint32_t r[0x8000/4]={0};PortAicaMixer m;float out[512];
 port_aica_init(&m);r[0x2800/4]=15;
 r[0]=0xc000;r[3]=4;r[4]=31;r[5]=15<<10;r[9]=15<<8;r[10]=64;
 int16_t pcm[]={4096,8192,12288,16384};memcpy(ram,pcm,sizeof pcm);
 port_aica_key_execute(&m,r,0);assert(!(r[0]&0x8000));
 port_aica_render(&m,r,ram,out,4);
 for(int i=0;i<4;i++){assert(fabsf(out[i*2]-pcm[i]/32768.f)<.00001);assert(out[i*2]==out[i*2+1]);}
 assert(!m.voices[0].active);
 // PCM8, loop at sample 1, double source pitch, hard right.
 port_aica_init(&m);memset(r,0,sizeof r);r[0x2800/4]=15;
 ram[0]=16;ram[1]=32;ram[2]=64;ram[3]=96;
 r[0]=0xc280;r[2]=1;r[3]=4;r[4]=31;r[5]=15<<10;r[6]=1<<11;r[9]=(15<<8)|15;r[10]=64;
 port_aica_key_execute(&m,r,0);port_aica_render(&m,r,ram,out,3);
 assert(out[0]==0&&out[1]==.125f);assert(out[2]==0&&out[3]==.5f);assert(out[4]==0&&out[5]==.25f);
 unsigned position=m.voices[0].position;r[0]|=0x8000;port_aica_key_execute(&m,r,0);assert(position==m.voices[0].position);
 r[0]=0x8280;r[5]|=31;port_aica_key_execute(&m,r,0);assert(m.voices[0].stage==3);
 port_aica_render(&m,r,ram,out,256);assert(!m.voices[0].active);
 // Known Yamaha ADPCM nibbles, low nibble first; no IMA step table.
 int p=0,q=127;assert(port_aica_adpcm(7,&p,&q)==238&&q==304);
 assert(port_aica_adpcm(15,&p,&q)==-332&&q==729);
 port_aica_init(&m);memset(r,0,sizeof r);r[0x2800/4]=15;ram[0]=0xf7;
 r[0]=0xc100;r[3]=2;r[4]=31;r[5]=15<<10;r[9]=15<<8;r[10]=64;
 port_aica_key_execute(&m,r,0);port_aica_render(&m,r,ram,out,2);
 assert(fabsf(out[0]-238/32768.f)<.00001);assert(fabsf(out[2]+332/32768.f)<.00001);
 // Master mute is obeyed, and independent voices are latched by one KYONEX.
 port_aica_init(&m);memset(r,0,sizeof r);r[0]=0xc000;r[32]=0x4000;r[3]=r[35]=4;r[4]=r[36]=31;
 port_aica_key_execute(&m,r,0);assert(m.voices[0].active&&m.voices[1].active);
 port_aica_render(&m,r,ram,out,2);assert(out[0]==0&&out[1]==0);
 return 0;
}'''
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'test.c').write_text(source)
            subprocess.run(['clang','-std=c11','-O2','-fsanitize=address,undefined','-I',str(ROOT/'runtime'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True)
