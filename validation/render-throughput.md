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
