# Browser frame pacing

Target: a steady 60 submissions per second with correct game/audio timing.
VBlank remains at 60 Hz. No frame generation or duplicate-frame FPS counting.

## Changes

- Transparency sorting moves compact depth/index keys through merge passes,
  then copies each complete triangle once. Stable ties and vertex payloads are
  preserved; sanitized tests cover scratch-buffer growth and reuse.
- Adjacent triangles with equivalent effective WebGL state share a draw call.
  Texture addressing/wrapping, alpha, shading, blend, depth and culling changes
  still split batches. Triangle order is unchanged.
- The workbench reports a recent five-second submission cadence, p95/p99/max
  frame intervals and intervals over 20 ms. Loading/pause gaps over a second
  restart sampling. These are CPU submission times, not GPU/display timings.
- Renderer logs include draw-call totals alongside texture uploads and CPU
  submission costs. Storage is bounded; no synchronous GPU queries are added.

## Evidence and limits

A native synthetic benchmark of 8,000 triangles over 500 sorts measured
0.983 ms before and 0.577 ms after, including identical setup and validation
(~41% less time). This is not a browser or whole-game speedup claim.

The pre-change browser's observed 3D windows submitted about 54–55 fps, with
average renderer CPU costs of 0.4–1.1 ms. Those scenes are diagnostic samples,
not a matched before/after benchmark. The renderer measurement excludes GPU
completion and much of game/hardware execution.

A lower-end device and Safari need independent gameplay measurements. Neither
synthetic tests nor a fast desktop establish a universal 60 fps guarantee.

## RAM and audio clock

The browser translator has a direct-RAM fast path guarded by the address
segment, configured RAM size and MMU enable bit. P0/P3 translations with the MMU
enabled, P4 and device accesses retain the original implementation. An
ASAN/UBSAN harness compares it with the pinned translator across 800,000 random
addresses, RAM boundaries, aliases and enabled-MMU mappings. Memory access and
interrupt polling remain in place.

A separate regression reproduces the pinned AICA clock emitting 45,454 samples
in one second of frequent polling. The browser adapter retains fractional
sample units in the numerator and emits exactly 44,100. Tests cover regular and
irregular polling and clock resets. This corrects source-clock drift without
changing playback pitch to follow the game frame rate.

A 30-second release-build sample before the RAM/audio-clock changes measured
58.14 submissions/s. Its audio report recorded 1,987 cumulative buffer overflows
and a near-capacity queue. These are observations from that session; its
uncontrolled attract scenes and timing do not establish an end-to-end speedup.

## Combined browser validation

Artifact `20261030-232240-5ccc7645`, WASM SHA-256
`4066477f9aa54c86c6e5cc14d3a548aeb7e6ef8b6e60bcea92d4ba43614724bb`.
The 30.016-second attract-sequence sample submitted 1,771 frames (59.00 fps).
Recent windows ranged from 57.79 to 59.60 fps, with remaining 33 ms spikes.
This is progress toward 60 fps, not a locked-60 result or lower-end device proof.

After approximately 155 seconds of received audio, the live browser reported
zero underruns and zero overflows, with 3,432 source frames (~78 ms) queued.
This validates buffer stability in that run, not an exhaustive listening test.
The previous session had a nearly full ~362 ms queue and repeated overflows.
Scenes and run durations were not controlled for an overall speedup comparison.

Validation: 59 Python tests and nine JavaScript suites passed. The Python suite
includes parser/compiler checks against the pinned local toolchain, sanitized
memory/clock/sort harnesses and the loopback HTTP test. Commercial save/load
and PSO gameplay remain independent bring-up work.

## Follow-up: CPU read path and bounded idle cooperation

The browser now separates normal direct-RAM reads into a small wrapper. Reads
that reach the existing 256-access polling boundary still use the complete
original function, as do MMU, device, P4 and foreign-CPU cases. The original
heartbeat path and poll-side memory changes are preserved. A sanitized harness
compares 400,000 reads plus control-register cases and counter wraparound.
A native 10-million-read experiment measured about 49 ms before and 23 ms after;
this is not a browser frame-rate comparison.

Hardware-clock diagnostics separately report VBlank frequency, lateness and
stale-debt resets. The measured pre-follow-up clock held 60 Hz with sub-ms
lateness in steady windows even when frame submissions fell behind.

Idle cooperation compares complete CPU snapshots and physical RAM addresses at
existing polling boundaries. It only yields for repeated foreground states
without foreground writes, outside interrupt handlers and more than two ms
before the next VBlank deadline. It neither skips memory reads nor advances
guest time. The host wait is bounded to one requested millisecond and resumes
through a message task to avoid chained timer clamping. All three write widths
invalidate foreground history; interrupt work remains serviced normally.

Tests cover changing integer/FPU state, writes, seven-phase polling cycles,
device addresses, duplicate polls, interrupt-handler exclusion and the deadline
guard. Browser scheduler tests check timer-to-message continuation. Browser
performance validation of this follow-up is recorded separately below.

## Disc working set and native stack switching

The raw-sector cache now retains 16 chunks (at most 4,816,896 bytes), keyed by
track and offset with LRU eviction. A sanitized harness alternates across all
16 chunks and verifies hits, eviction, track separation and truncated sectors.
This avoids repeatedly suspending the entire executable to fetch the same
working set. Cache misses still suspend execution; this is not asynchronous
GD-ROM emulation.

`build-browser --optimize --jspi` builds both compatibility Asyncify and native
WebAssembly Promise Integration (JSPI) bundles from the same objects. A worker
selects JSPI only when both `WebAssembly.Suspending` and `WebAssembly.promising`
exist and that build includes the companion. Otherwise it selects Asyncify.
Artifact receipts verify and retain both bundles; the runtime reports the
selected suspension mode and WASM identity. Capability tests cover absent and
partial APIs and missing companion builds. Actual Safari execution of this
follow-up has not been verified.

The approach follows [Emscripten's asynchronous-code documentation](https://emscripten.org/docs/porting/asyncify.html): native stack switching avoids
Asyncify's transformation throughout the translated call graph. No indirect
calls or potentially asynchronous functions are excluded from Asyncify analysis.

An initial 30-second driving run with the RAM/idle/cache changes measured
58.53 presentations/s. A subsequent JSPI experiment measured 59.31/s, including
several clean 60.00 windows and one 56.33 window. These runs do not establish a
matched end-to-end speedup or a locked 60. Audio recorded zero underruns and
overflows in the latter session. Timing counters now distinguish gaps between
CPU polls from normal task and idle wake-up delays. Measurements below use the
published dual-bundle artifact, with compilation stopped before driving.

The published dual-bundle artifact is `20261031-020345-207c11b3`: Asyncify
`2eb711c2f8c88abcbb13e03b6a8c1e2241957cb74527b7a5abc6ea25c0370e48`,
JSPI `2b196da441564d1211ef43bd2b3dd6f0d048d63eccc1d4aa1c03bb4aff2fe661`.
The browser confirmed native selection and reported that exact JSPI identity.
A subsequent title-screen test received Start at the Maple controller layer but
did not reliably advance into the menus. JSPI therefore remains an explicit
experimental build option, not the default. A repeat compatibility run is not
a matched driving comparison. One trace recorded a 73.2 ms gap between CPU
polls and a 44 ms idle wake-up, while normal message-task waits stayed below
1 ms in that window. These counters include host scheduling delays and do not
identify all gaps as CPU execution cost. No locked-60 claim is supported.

Validation: 64 Python tests and ten JavaScript suites passed, including real
loopback routing for older projects, companion artifact integrity, accurate
runtime build identity and capability-based fallback. Browser testing was on
an Apple M1 with 16 GiB RAM; low-end hardware remains unverified.

The live preview was restored to the previously verified playable artifact
`20261031-000454-199f5523` (WASM `097b4f916c011875`) after the experiments.
The experimental dual-bundle artifact remains available locally for reproduction.
Restoration is a compatibility precaution, not evidence of a locked 60.
