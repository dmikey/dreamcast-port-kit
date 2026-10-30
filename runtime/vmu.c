/* Independently implemented from Maple protocol behavior documented by
 * Flycast and KallistiOS. See docs/vmu.md for references and limitations. */
#include "vmu.h"
#include <stdio.h>
#include <string.h>
#include <time.h>
static uint8_t flash[131072],lcd[192];
static int connected,last_error;
static time_t clock_offset;
#define STORAGE 0x02000000u
#define LCD 0x04000000u
#define CLOCK 0x08000000u
#ifdef __EMSCRIPTEN__
#include <emscripten.h>
EM_ASYNC_JS(int,load_image,(uint8_t *destination),{
 try{const bytes=await portVmu.load();HEAPU8.set(bytes,destination);return 1;}catch(error){postMessage({kind:'vmu-status',error:error.message});return 0;}
});
EM_ASYNC_JS(int,save_phase,(unsigned block,unsigned phase,const uint8_t *data),{
 try{await portVmu.write(block,phase,HEAPU8.slice(data,data+128));return 1;}catch(error){postMessage({kind:'vmu-status',error:error.message});return 0;}
});
EM_JS(void,show_lcd,(const uint8_t *data),{postMessage({kind:'vmu-lcd',bytes:HEAPU8.slice(data,data+192)});});
#else
#include "project.h"
#include <sys/file.h>
#include <unistd.h>
static int load_image(uint8_t *destination){
 FILE *lock=fopen(PORT_VMU_PATH ".lock","ab"),*f=NULL;int ok=0;
 if(!lock)return 0;flock(fileno(lock),LOCK_EX);f=fopen(PORT_VMU_PATH,"rb");
 if(f){ok=fread(destination,1,sizeof flash,f)==sizeof flash&&fgetc(f)==EOF;fclose(f);}
 flock(fileno(lock),LOCK_UN);fclose(lock);return ok;
}
static int save_phase(unsigned block,unsigned phase,const uint8_t *data){
 FILE *lock=fopen(PORT_VMU_PATH ".lock","ab"),*f=NULL;int ok=0;
 if(!lock)return 0;flock(fileno(lock),LOCK_EX);f=fopen(PORT_VMU_PATH,"rb+");
 if(f){ok=fseek(f,(long)(block*512+phase*128),SEEK_SET)==0&&fwrite(data,1,128,f)==128&&fflush(f)==0&&fsync(fileno(f))==0;if(fclose(f))ok=0;}
 flock(fileno(lock),LOCK_UN);fclose(lock);return ok;
}
static void show_lcd(const uint8_t *data){(void)data;}
#endif
int port_vmu_init(void){connected=load_image(flash);printf("[VMU] A1 %s\n",connected?"connected, 128 KiB persistent storage":"unavailable; existing image preserved");return connected;}
int port_vmu_connected(void){return connected;}
static void reply(uint32_t frame,uint32_t *out,unsigned code,unsigned words){out[0]=code|((frame>>16)&255)<<8|((frame>>8)&255)<<16|words<<24;}
static void error(uint32_t frame,uint32_t *out,unsigned bits){last_error=(int)bits;out[1]=bits;reply(frame,out,0xfb,1);}
static unsigned swap32(unsigned x){return (x>>24)|((x>>8)&0xff00)|((x<<8)&0xff0000)|(x<<24);}
void port_vmu_dma(uint32_t frame,const uint32_t *in,unsigned words,uint32_t *out){
 unsigned cmd=frame&255,func=words?in[0]:0;
 static unsigned requests;if(requests++<64)printf("[VMU] cmd=%02X function=%08X words=%u\n",cmd,func,words);
 if(!connected){out[0]=~0u;return;}
 if(cmd==1||cmd==2){
  memset(out+1,0,112);out[1]=STORAGE|LCD|CLOCK;out[2]=0x403f7e7e;out[3]=0x00100500;out[4]=0x00410f00;
  uint8_t *p=(uint8_t*)(out+1);p[16]=255;memset(p+18,' ',90);memcpy(p+18,"Visual Memory",13);memcpy(p+48,"Dreamcast Port Lab virtual memory unit",37);p[108]=0x7c;p[110]=0x82;
  if(cmd==2){memset(out+29,' ',80);memcpy(out+29,"Port Lab VMU storage/LCD/clock",29);reply(frame,out,6,48);}else reply(frame,out,5,28);
  return;
 }
 if(cmd==3||cmd==4){last_error=0;reply(frame,out,7,0);return;}
 if(!words){reply(frame,out,0xfc,0);return;}
 if(cmd==9){if(func!=CLOCK){reply(frame,out,0xfe,0);return;}out[1]=CLOCK;out[2]=~0u;reply(frame,out,8,2);return;}
 if(cmd==10){
  out[1]=func;
  if(func==STORAGE){const uint16_t media[12]={255,0,255,254,1,253,13,0,200,31,0,0};memcpy(out+2,flash[255*512+64]==255?flash+255*512+64:(const uint8_t*)media,24);reply(frame,out,8,7);return;}
  if(func==LCD&&words>=2&&in[1]==0){out[2]=0x02101f2f;reply(frame,out,8,2);return;}
  reply(frame,out,0xfe,0);return;
 }
 if(cmd==13){if(last_error)error(frame,out,(unsigned)last_error);else reply(frame,out,7,0);return;}
 if(cmd==14){/* Buzzer is not synthesized; reject rather than acknowledge sound. */reply(frame,out,0xfe,0);return;}
 if(cmd!=11&&cmd!=12){reply(frame,out,0xfd,0);return;}
 if(words<2){reply(frame,out,0xfc,0);return;}
 unsigned address=swap32(in[1]),block=address&65535,phase=(address>>16)&255,partition=address>>24;
 if(func==STORAGE){
  if(partition||block>=256||phase>=4){error(frame,out,0x10);return;}
  if(cmd==11){if(phase){error(frame,out,0x10);return;}out[1]=STORAGE;out[2]=in[1];memcpy(out+3,flash+block*512,512);reply(frame,out,8,130);return;}
  if(words!=34){error(frame,out,0x10);return;}
  if(!save_phase(block,phase,(const uint8_t*)(in+2))){error(frame,out,8);return;}
  memcpy(flash+block*512+phase*128,in+2,128);last_error=0;reply(frame,out,7,0);return;
 }
 if(func==LCD){
  if(in[1]){reply(frame,out,0xfc,0);return;}
  if(cmd==11){out[1]=LCD;out[2]=0;memcpy(out+3,lcd,192);reply(frame,out,8,50);return;}
  if(words!=50){reply(frame,out,0xfc,0);return;}
  memcpy(lcd,in+2,192);show_lcd(lcd);reply(frame,out,7,0);return;
 }
 if(func==CLOCK){
  if(in[1]){reply(frame,out,0xfc,0);return;}
  if(cmd==11){time_t now=time(NULL)+clock_offset;struct tm t=*localtime(&now);out[1]=CLOCK;uint8_t *p=(uint8_t*)(out+2);unsigned year=(unsigned)t.tm_year+1900;p[0]=year&255;p[1]=year>>8;p[2]=t.tm_mon+1;p[3]=t.tm_mday;p[4]=t.tm_hour;p[5]=t.tm_min;p[6]=t.tm_sec;p[7]=0;reply(frame,out,8,3);return;}
  if(words!=4){reply(frame,out,0xfc,0);return;}
  const uint8_t *p=(const uint8_t*)(in+2);struct tm t={0};unsigned year=p[0]+((unsigned)p[1]<<8);
  if(year<1900||year>9999||p[2]<1||p[2]>12||p[3]<1||p[3]>31||p[4]>23||p[5]>59||p[6]>59){reply(frame,out,0xfc,0);return;}
  t.tm_year=(int)year-1900;t.tm_mon=p[2]-1;t.tm_mday=p[3];t.tm_hour=p[4];t.tm_min=p[5];t.tm_sec=p[6];t.tm_isdst=-1;clock_offset=mktime(&t)-time(NULL);reply(frame,out,7,0);return;
 }
 reply(frame,out,0xfe,0);
}
