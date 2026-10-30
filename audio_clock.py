"""Preserve fractional AICA samples instead of rounding on every device poll."""
def adapt(hardware):
    begin=hardware.index('    static uint64_t last_us;',hardware.index('static void aica_advance_timer_a('))
    end=hardware.index('    uint32_t *ta = aica_reg(AICA_TIMER_A);',begin)
    old=hardware[begin:end]
    if 'frac_us' not in old or 'elapsed * 441 / 10000' not in old:
        raise ValueError('Unexpected AICA timer implementation')
    # Browser adapter already supplies one monotonic timestamp to this poll.
    return hardware[:begin]+'''    static PortAudioClock clock;
    uint32_t samples=port_audio_clock_step(&clock,now_us);
    if(!samples)return;

'''+hardware[end:]
