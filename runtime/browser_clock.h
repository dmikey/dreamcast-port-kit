/* Wall-clock VBlank pacing: keep fractional frame time, drop stale debt. */
static double port_vblank_due;
static int port_vblank_ready(double now) {
    const double period=1000.0/60.0;
    if(port_vblank_due==0)port_vblank_due=now+period;
    if(now+0.000001<port_vblank_due)return 0;
    port_vblank_due+=period;
    if(now-port_vblank_due>period)port_vblank_due=now+period;
    return 1;
}
