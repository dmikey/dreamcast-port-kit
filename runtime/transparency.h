/* Stable back-to-front triangle ordering; exact per-pixel sorting is pending. */
#include <stdlib.h>
#include <string.h>
static PVR2RenderVertex *port_sort_buffer;
typedef struct {float depth;int triangle;} PortSortKey;
static PortSortKey *port_sort_keys,*port_sort_scratch;
static int port_sort_capacity;
static float port_triangle_depth(const PVR2RenderVertex *v){return v[0].z+v[1].z+v[2].z;}
static void port_sort_transparent(const PVR2TriList *list) {
    int count=list->count/3;if(count<2)return;
    if(port_sort_capacity<list->count){
        void *next=realloc(port_sort_buffer,list->count*sizeof *port_sort_buffer);
        if(!next)abort();port_sort_buffer=next;port_sort_capacity=list->count;
        void *keys=realloc(port_sort_keys,(size_t)count*sizeof *port_sort_keys);
        void *scratch=realloc(port_sort_scratch,(size_t)count*sizeof *port_sort_scratch);
        if(!keys || !scratch)abort();port_sort_keys=keys;port_sort_scratch=scratch;
    }
    /* Sort compact keys, then move each triangle once. Full vertex records
     * contain UVs, colors and materials and need not traverse every merge. */
    PortSortKey *source=port_sort_keys,*dest=port_sort_scratch;
    for(int i=0;i<count;i++){source[i].depth=port_triangle_depth(list->vertices+i*3);source[i].triangle=i;}
    for(int span=1;span<count;span*=2){
        for(int start=0;start<count;start+=2*span){
            int a=start,mid=start+span<count?start+span:count,b=mid,end=start+2*span<count?start+2*span:count;
            for(int out=start;out<end;out++){
                int take_a=a<mid&&(b>=end||!(source[a].depth>source[b].depth));
                dest[out]=source[take_a?a++:b++];
            }
        }
        PortSortKey *swap=source;source=dest;dest=swap;
    }
    for(int i=0;i<count;i++)memcpy(port_sort_buffer+i*3,list->vertices+source[i].triangle*3,3*sizeof *port_sort_buffer);
    memcpy(list->vertices,port_sort_buffer,(size_t)count*3*sizeof *port_sort_buffer);
}
