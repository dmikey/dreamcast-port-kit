/* Submission cadence, not display refresh or GPU completion. Fixed storage;
 * pauses/loading gaps restart the window instead of inflating gameplay FPS. */
#include <stdlib.h>
typedef struct {
    double last,elapsed,intervals[512];unsigned count;
    double fps,p95,p99,maximum;unsigned slow;
} PortFrameTiming;
static int port_interval_compare(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
static int port_frame_timing(PortFrameTiming *s,double now){
    double delta=now-s->last;s->last=now;
    if(delta<=0 || delta>1000){s->count=0;s->elapsed=0;return 0;}
    s->intervals[s->count++]=delta;s->elapsed+=delta;
    if(s->elapsed<5000 && s->count<512)return 0;
    s->fps=s->count*1000.0/s->elapsed;s->slow=0;
    for(unsigned i=0;i<s->count;i++)if(s->intervals[i]>20.0)s->slow++;
    qsort(s->intervals,s->count,sizeof(double),port_interval_compare);
    s->p95=s->intervals[(s->count*95+99)/100-1];
    s->p99=s->intervals[(s->count*99+99)/100-1];s->maximum=s->intervals[s->count-1];
    s->count=0;s->elapsed=0;return 1;
}
