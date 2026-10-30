/* Explicit local diagnostic capture; no snapshots or allocations in normal frames. */
static int port_snapshot_requested;
EMSCRIPTEN_KEEPALIVE void port_render_snapshot(void){port_snapshot_requested=1;}
EM_JS(void,port_save_snapshot,(const void *ram,unsigned ram_bytes,const void *vram,const void *opaque,unsigned opaque_count,const void *punch,unsigned punch_count,const void *trans,unsigned trans_count,unsigned stride),{
 const parts=[HEAPU8.slice(ram,ram+ram_bytes),HEAPU8.slice(vram,vram+0x800000),HEAPU8.slice(opaque,opaque+opaque_count*stride),HEAPU8.slice(punch,punch+punch_count*stride),HEAPU8.slice(trans,trans+trans_count*stride)];
 const header=new TextEncoder().encode(JSON.stringify({version:1,ramBytes:ram_bytes,vramBytes:0x800000,stride,counts:[opaque_count,punch_count,trans_count],fields:['x','y','z','u','v','r','g','b','a','pcw','tsp','tcw','isp']}));
 const bytes=new Uint8Array(4+header.length+parts.reduce((n,p)=>n+p.length,0));new DataView(bytes.buffer).setUint32(0,header.length,true);bytes.set(header,4);let at=4+header.length;for(const p of parts){bytes.set(p,at);at+=p.length;}
 postMessage({kind:'snapshot',bytes:bytes.buffer},[bytes.buffer]);
});
static void port_capture_snapshot(void){
 if(!port_snapshot_requested)return;port_snapshot_requested=0;
 const PVR2TriList *a=pvr2_ta_get_list(PVR2_LIST_OPAQUE),*b=pvr2_ta_get_list(PVR2_LIST_PUNCHTHRU),*c=pvr2_ta_get_list(PVR2_LIST_TRANS);
 port_save_snapshot(sh4_get_ram_ptr(),sh4_get_ram_mask()+1,sh4_get_vram_ptr(),a->vertices,a->count,b->vertices,b->count,c->vertices,c->count,sizeof(PVR2RenderVertex));
}
