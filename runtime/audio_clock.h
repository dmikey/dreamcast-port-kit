/* Exact 44.1 kHz clock from monotonic microseconds. Fractional units are
 * retained in the numerator; converting them back to whole us causes drift. */
#include <stdint.h>
typedef struct {uint64_t last;uint32_t remainder;int initialized;} PortAudioClock;
static uint32_t port_audio_clock_step(PortAudioClock *s,uint64_t now){
    if(!s->initialized || now<s->last){s->last=now;s->remainder=0;s->initialized=1;return 0;}
    uint64_t units=(now-s->last)*441+s->remainder;s->last=now;
    s->remainder=(uint32_t)(units%10000);
    return (uint32_t)(units/10000);
}
