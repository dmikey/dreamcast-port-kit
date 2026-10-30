/* Stable back-to-front triangle ordering; exact per-pixel sorting is pending. */
#include <stdlib.h>
#include <string.h>
static PVR2RenderVertex *port_sort_buffer;
static int port_sort_capacity;
static float port_triangle_depth(const PVR2RenderVertex *v){return v[0].z+v[1].z+v[2].z;}
static void port_sort_transparent(const PVR2TriList *list) {
    int count=list->count/3;if(count<2)return;
    if(port_sort_capacity<list->count){
        void *next=realloc(port_sort_buffer,list->count*sizeof *port_sort_buffer);
        if(!next)abort();port_sort_buffer=next;port_sort_capacity=list->count;
    }
    PVR2RenderVertex *source=list->vertices,*dest=port_sort_buffer;
    for(int span=1;span<count;span*=2){
        for(int start=0;start<count;start+=2*span){
            int a=start,mid=start+span<count?start+span:count,b=mid,end=start+2*span<count?start+2*span:count;
            for(int out=start;out<end;out++){
                int take_a=a<mid&&(b>=end||!(port_triangle_depth(source+a*3)>port_triangle_depth(source+b*3)));
                int index=take_a?a++:b++;memcpy(dest+out*3,source+index*3,3*sizeof *source);
            }
        }
        PVR2RenderVertex *swap=source;source=dest;dest=swap;
    }
    if(source!=list->vertices)memcpy(list->vertices,source,list->count*sizeof *source);
}
