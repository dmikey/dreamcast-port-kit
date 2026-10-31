/* Same-origin raw sectors. Keep a bounded working set so alternating game
 * streams do not suspend WASM for the same chunk on every read. */
#include <emscripten.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define PORT_DISC_CACHE_SLOTS 16
#define PORT_DISC_CHUNK (2352L*128)
static struct {
    unsigned char *data;int track,size;long offset;uint64_t used;
} port_disc_cache[PORT_DISC_CACHE_SLOTS];
static uint64_t port_disc_serial,port_disc_hits,port_disc_misses;
static double port_disc_wait_ms;
static void port_disc_read(int track,long offset,void *destination) {
    long start=offset/PORT_DISC_CHUNK*PORT_DISC_CHUNK;int slot=-1;
    for(int i=0;i<PORT_DISC_CACHE_SLOTS;i++)if(port_disc_cache[i].data &&
        port_disc_cache[i].track==track && port_disc_cache[i].offset==start){slot=i;break;}
    if(slot<0){
        slot=0;
        for(int i=0;i<PORT_DISC_CACHE_SLOTS;i++){
            if(!port_disc_cache[i].data){slot=i;break;}
            if(port_disc_cache[i].used<port_disc_cache[slot].used)slot=i;
        }
        free(port_disc_cache[slot].data);port_disc_cache[slot].data=NULL;
        char url[128];snprintf(url,sizeof url,"/disc/%d?offset=%ld&length=%ld",track,start,PORT_DISC_CHUNK);
        int error=0;double before=emscripten_get_now();
        emscripten_wget_data(url,(void**)&port_disc_cache[slot].data,&port_disc_cache[slot].size,&error);
        port_disc_wait_ms+=emscripten_get_now()-before;port_disc_misses++;
        if(error || !port_disc_cache[slot].data){fprintf(stderr,"[DISC] read failed: %s\n",url);abort();}
        port_disc_cache[slot].offset=start;port_disc_cache[slot].track=track;
    }else port_disc_hits++;
    long relative=offset-start;
    if(relative<0 || relative+2352>port_disc_cache[slot].size){fprintf(stderr,"[DISC] truncated sector\n");abort();}
    memcpy(destination,port_disc_cache[slot].data+relative,2352);
    port_disc_cache[slot].used=++port_disc_serial;
    static double reported;double now=emscripten_get_now();
    if(now-reported>=5000){
        printf("[DISC] cache_hits=%llu misses=%llu wait_ms=%.2f slots=%d\n",(unsigned long long)port_disc_hits,(unsigned long long)port_disc_misses,port_disc_wait_ms,PORT_DISC_CACHE_SLOTS);
        reported=now;
    }
}
