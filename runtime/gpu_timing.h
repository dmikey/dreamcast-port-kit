/* Sparse asynchronous GPU timing. Availability is polled; no GPU wait/readback.
 * At most four outstanding queries, sampling one out of thirty game frames. */
EM_JS(void,port_gpu_begin,(),{
    let s=Module.portGpuTrace;
    if(!s){
        const ext=GLctx.getExtension('EXT_disjoint_timer_query_webgl2');
        s=Module.portGpuTrace={ext,frame:0,pending:[],active:null,total:0,max:0,count:0,reported:performance.now(),discarded:0};
        Module.print('[GPU] asynchronous_timer_queries='+(ext?'enabled':'unavailable'));
    }
    if(!s.ext || (++s.frame%30)!==0 || GLctx.isContextLost())return;
    const disjoint=s.pending.length && GLctx.getParameter(s.ext.GPU_DISJOINT_EXT);
    for(let i=0;i<s.pending.length;){
        const q=s.pending[i];
        if(!disjoint && !GLctx.getQueryParameter(q,GLctx.QUERY_RESULT_AVAILABLE)){i++;continue;}
        if(disjoint)s.discarded++;
        else{const ms=GLctx.getQueryParameter(q,GLctx.QUERY_RESULT)/1000000;s.total+=ms;s.max=Math.max(s.max,ms);s.count++;}
        GLctx.deleteQuery(q);s.pending.splice(i,1);
    }
    const now=performance.now();
    if(now-s.reported>=5000){
        Module.print('[GPU] samples='+s.count+' avg_ms='+(s.count?s.total/s.count:0).toFixed(3)+' max_ms='+s.max.toFixed(3)+' disjoint_discarded='+s.discarded);
        s.total=s.max=s.count=s.discarded=0;s.reported=now;
    }
    if(s.pending.length<4){const q=GLctx.createQuery();if(q){s.active=q;GLctx.beginQuery(s.ext.TIME_ELAPSED_EXT,q);}}
});
EM_JS(void,port_gpu_end,(),{
    const s=Module.portGpuTrace;
    if(s?.active){GLctx.endQuery(s.ext.TIME_ELAPSED_EXT);s.pending.push(s.active);s.active=null;}
});
