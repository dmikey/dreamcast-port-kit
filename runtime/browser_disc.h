/* Same-origin, bounded raw-sector reads. No full-disc download is needed. */
#include <emscripten.h>
#include <stdlib.h>
static unsigned char *port_disc_cache;
static int port_disc_track=-1,port_disc_size;
static long port_disc_offset=-1;
static void port_disc_read(int track,long offset,void *destination) {
    const long chunk=2352*128;
    long start=offset/chunk*chunk;
    if(track!=port_disc_track || start!=port_disc_offset) {
        free(port_disc_cache);port_disc_cache=NULL;
        char url[128];snprintf(url,sizeof url,"/disc/%d?offset=%ld&length=%ld",track,start,chunk);
        int error=0;emscripten_wget_data(url,(void**)&port_disc_cache,&port_disc_size,&error);
        if(error || !port_disc_cache) {fprintf(stderr,"[DISC] read failed: %s\n",url);abort();}
        port_disc_offset=start;port_disc_track=track;
    }
    long relative=offset-start;
    if(relative+2352>port_disc_size) {fprintf(stderr,"[DISC] truncated sector\n");abort();}
    memcpy(destination,port_disc_cache+relative,2352);
}
