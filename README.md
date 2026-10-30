# Dreamcast port kit

A repeatable pipeline for user-supplied Dreamcast discs. Shared tools inspect,
extract, translate, compile and diagnose. Exact executable profiles hold each
title's addresses, interrupt setup and bootstrap aliases.

The accepted architecture recompiles the main SH-4 game code to C, retains
Dreamcast hardware emulation, and interprets the ARM7 sound CPU. It is a
recompilation with an emulation layer, not an all-new engine implementation.
New platform adapters and reusable fixes can replace components incrementally;
a clean rewrite is not required for this workflow.

**This does not automatically turn every Dreamcast game into a playable browser
game.** Runtime/hardware adaptation, graphics, audio, asset formats and gameplay
verification can require title-specific work. The same process and shared fixes
apply to new titles; compatibility must be demonstrated for each one.

## Start a port

Python 3.9+ (3.10+ for Emscripten), `git`, `bsdtar`, and a C11 compiler are required. Native diagnostics
were tested on Apple Silicon macOS. They are not a Windows runtime package.
Run from this folder (paths are examples and may contain spaces):

```sh
python3 port.py bootstrap --toolchain .local/dcrecomp
python3 port.py prepare "/path/to/My Game.7z" --project ports/my-game
python3 port.py translate --project ports/my-game --toolchain .local/dcrecomp
python3 port.py build --project ports/my-game --toolchain .local/dcrecomp --abi
python3 port.py run --project ports/my-game --seconds 10
python3 port.py status --project ports/my-game
```

For an unknown executable, `prepare` creates `title-profile.json` and sets
`needs-title-profile`. Fill in its load address and runtime/IRQ configuration
from that executable. Translation accepts an explicit `--base` for analysis;
the native build requires a complete profile. Extra discovered entry points go
in a profile-relative `entriesFile`; bootstrap code aliases are explicit
`codeAliases`, absent by default. No Crazy Taxi relocation is injected into
other titles.

Re-running a stage uses the same project. Archive import is idempotent; a
different archive/executable cannot silently replace an existing project.
Changed track contents retire prior stage evidence. Compile objects are cached
against source, headers and compiler options. Bounded execution returns a
nonzero status when unresolved execution is reached.

## Browser build

Install and activate the official Emscripten SDK (tested: 6.0.13). Use Python
3.10 or newer for this stage:

```sh
python3 port.py build-browser --project ports/my-game --toolchain .local/dcrecomp --emsdk /path/to/emsdk
python3 serve_browser.py --project ports/my-game --port 4390
```

Open `http://127.0.0.1:4390/` and choose Start game. The same translated title
code runs as WebAssembly in a dedicated Web Worker. That worker owns the SH-4
execution, ARM7 interpreter, hardware, texture decoding and WebGL2 rendering on a
transferred OffscreenCanvas. The page owns keyboard, Gamepad and touch input, DOM
controls, and forwarding audio blocks to the AudioWorklet. The browser target
does not use SDL or proxy graphics calls through the page. Disc chunks stay
bounded and same-origin. Only the executable is embedded; the full disc is not a
startup download. The server binds to loopback. Keep disc-derived browser
artifacts private. This is local browser bring-up, not a published game.

The worker build requires Web Workers, WebAssembly and WebGL2 on OffscreenCanvas
(Safari 17 or newer, with actual browser verification still required). It does
not require SharedArrayBuffer or cross-origin isolation. Input changes are
batched and deduplicated; stereo audio buffers transfer ownership to the page.
CPU execution yields to worker messages roughly every 8 ms. Moving this work
off the page keeps browser controls responsive; it does not guarantee a higher
guest frame rate or correct remaining texture defects.

Browser builds default to `-O2`. Add `--optimize` to test `-O3` with cached
ThinLTO across files; the flag is experimental until matched gameplay shows an
advantage. It can increase final WASM size and browser compilation time. `--abi`
keeps the `-O2` diagnostic build with runtime assertions. Render timing reports CPU-side
submission time every five seconds, including texture work and transparent
sorting. It is not a GPU completion measurement. Compare identical game scenes
on the same browser/device with sound and resolution held constant before
claiming an advantage over another runtime. The historical `[FRAME]` fps value
is cumulative from boot and should not be used as a steady gameplay benchmark.
Export diagnostics and run `python3 benchmark.py before.json after.json` for
windowed submission timings, frame event intervals and audio health. Compare
matching gameplay scenes; static menus can legitimately submit fewer frames.

`control_flow.py` lowers terminal cross-function jumps to a bounded-stack
trampoline. Normal calls retain their continuations. Its hash and the generated
source hashes are recorded at translation. The synthetic regression executes
100,000 cross-function iterations with nested calls.

`graphics.py` and `runtime/texture_gl.h` preserve material state and decode
16-bit direct-color, VQ and palette textures from live VRAM. Cached textures
are reused only while their exact source bytes and palette remain unchanged.
The cache holds up to 512 entries with true least-recently-used eviction, a
64 MiB GPU image budget and a 16 MiB source-byte budget. Blend and color flags
do not duplicate identical texture images. Unsupported texture
formats show a diagnostic magenta texture; modifier volumes and full hardware
render fidelity remain unfinished. Native `build --graphics` is an optional
SDL2/OpenGL diagnostic; the product target is the browser.

## Supported disc inputs

| Input | Current support |
|---|---|
| GDI + data tracks | Inspection/extraction for 2048/2352-byte sectors, including byte offsets and extents crossing tracks |
| CUE + BIN | Separate-file raw MODE1/2352 data tracks; LBA read from actual sector headers |
| 7z / zip | Archives containing a descriptor and its tracks; select ambiguous descriptors with `--descriptor` |
| Cooked CUE, shared-file multi-track CUE, CDI, CHD | Explicit conversion/reader adapter required; no layout guesses |
| Scrambled self-boot / WinCE | Startup/unscrambling/runtime adapter required; not claimed supported |

The current native BIOS adapter requires 2352-byte raw tracks with zero byte
offset. Inspection supports more layouts than native execution. Audio tracks
are not rendered by the headless runtime.

## Project artifacts

- `port.json`: title, exact executable/source-set hashes, selected profile, stage
  evidence. A translation or successful link never marks gameplay true.
- `title-profile.json`: the editable bootstrap configuration for a new title.
- `.local/source-lock.json`: track paths/hashes and descriptor provenance.
- `.local/extracted/`: the executable, IP.BIN, and optional `--all-files` assets.
- `.local/generated/`: local translated game C and its source/toolchain hashes.
- `.local/native/`: the diagnostic executable, compile logs, unresolved targets,
  `run.log`, and `run-result.json`.

The project `.gitignore` excludes `.local/`. The supplied disc is unchanged.
Generated game C/assets are local outputs, separate from reusable tooling.

## Tested shared fixes

The upstream revision and patched file hashes are pinned in
`toolchain-lock.json`. `bootstrap` verifies them and preserves unexpected local
changes. Checked-in patches:

- Calls with separately addressable delay slots execute the real call and
  execute the slot once; independent entry at that slot still works.
- Branching into an internal delay-slot label does not repeat the preceding branch.
- Delayed branches and calls execute slots across generated function boundaries
  and continue after the slot exactly once.
- Bounded inline BRAF branch tables expose all computed entries.
- Conditional branches at fragment ends preserve their untaken continuation.
- The interrupt bridge restores the pending dispatch PC.
- GD-ROM BIOS reads convert FAD addresses to disc LBA addresses correctly.
- Bootstrap remaps come from title profiles, not a Crazy Taxi constant.
- Unresolved dynamic calls trap visibly rather than return as successful no-ops.

`LICENSE.dcrecomp` and `NOTICE.dcrecomp` retain the upstream GPL-2.0 notices.
The runtime harness links that core. These tooling licenses do not relicense
commercial game code or assets produced from a disc.

## Verification

```sh
python3 -m unittest discover -s tests -v
DC_PORT_TEST_TOOLCHAIN="$PWD/.local/dcrecomp" python3 -m unittest discover -s tests -v
```

The integration test creates an original eight-byte synthetic SH-4 program in
a differently named fixture disc. It runs prepare → translate → native build →
execution and verifies that no Crazy Taxi remap or gameplay claim leaks in.
Disc tests cover high-density selection, raw CUE addresses, track byte offsets,
idempotence, modified executable rejection, changed asset evidence, traversal
and truncation. Compiler execution tests are in `tests/test_recompiler.py`.

Synthetic fixtures verify pipeline behavior. Real Crazy Taxi has reached its
startup logos, memory-card notice, title screen and Mode Selection in the
browser. The current bring-up work addresses additional computed branch targets
and texture fidelity. Local timing improved to a user-reported 54.3 fps after
browser scheduling and texture-cache fixes. The city and Axel taxi have loaded. Acceleration and steering through the browser overlay and a passenger pickup were observed. Texture/color fidelity remains incomplete. Direct AICA audio mixing and browser playback are implemented. Local browser diagnostics confirmed nonzero source samples reaching a running 48 kHz AudioWorklet; an eight-second 44.1 kHz stereo mixer capture was non-silent with no clipped samples. This confirms the signal path, not hardware-perfect sound. Deterministic replay remains unverified.

## Browser validation

Verify the original renderer, asset loading, input and audio in the browser.
Keep tests and build tool versions pinned. The current CLI does not claim that
unfinished validation stages are automatic.

The reusable agent workflow is in `skills/dreamcast-port/SKILL.md`.

Renderer packet layouts and shading behavior are cross-checked against the [Flycast hardware structures](https://github.com/flyinghead/flycast/blob/master/core/hw/pvr/ta_structs.h) and [GL renderer](https://github.com/flyinghead/flycast/blob/master/core/rend/gles/gles.cpp).


Browser input uses the standard HTML Gamepad API (first connected standard-mapped
controller), keyboard, and a toggleable Dreamcast touch overlay. Left stick and
D-pad steer, RT accelerates, LT brakes, and face buttons retain Dreamcast mappings.
Triggers preserve analog values; the stick uses a 15 percent dead zone. Input is
released on blur, tab hiding, pointer cancellation, and controller disconnect.
Rapid pointer presses track individual pointer IDs; pointer clicks do not create a second timed press. Acknowledged worker messages cap pending input at 16 states, merge redundant analog changes, and preserve the final release even under overload. Diagnostics include queue depth and dropped/coalesced states. Physical Safari button-mashing still requires target-device confirmation.
Controller discovery now returns the standard capability definition immediately
after its function code, including the four analog axes. Verify physical
controllers on the target browser; isolated mapping tests do not prove a device.

Run `node dreamcast-port-kit/tests/browser_input_test.cjs` from the kit parent directory (or use the
bundled Emscripten Node runtime). The test resolves the browser source relative to its own location.
Maple DMA packet tests are included in the Python test suite.

Recent shared fixes cover comment-only fragment endings (preserving fall-through
and stack cleanup), complete 64-byte modifier-volume packets (stencil shadows
remain pending), first-volume polygon layouts, per-material depth/blend settings,
mipmap offsets, and matching the viewport to the browser canvas drawing buffer.

Browser VBlank pacing now uses fractional 60 Hz deadlines and drops stale frame
debt after stalls. It does not inject virtual disc-time credits into browser
VBlanks. `test_browser_clock.py` verifies 60 ticks per second and no repeated
same-time catch-up bursts. Actual game countdown timing still needs a measured
browser check. Runtime output includes a targeted material capture control for
investigating the remaining color corruption.

Color type 3 polygon headers reuse the prior intensity face color. They must not
read new colors from their unused header words. A captured scene showed the
old behavior taking UV-like values as alpha/red and zeroing blue; a packet
regression test now checks reused RGB/alpha with deliberately invalid header
padding. This is a shared TA fix, not a Crazy Taxi asset replacement.

## Flycast WASM reference adaptation

Upstream reviewed on 2026-10-30 at [`16e9c7b`](https://github.com/nasomers/flycast-wasm/tree/16e9c7b4b7065a4bd42e7490e8aab3e9283d5415).
The repository identifies its license as GPLv2. Keep attribution and license
notices with any source adapted from it.

The [nasomers/flycast-wasm technical write-up](https://github.com/nasomers/flycast-wasm/blob/16e9c7b4b7065a4bd42e7490e8aab3e9283d5415/TECHNICAL_WRITEUP.md), [validator backend](https://github.com/nasomers/flycast-wasm/blob/16e9c7b4b7065a4bd42e7490e8aab3e9283d5415/patches/rec_wasm.cpp), [instrumentation](https://github.com/nasomers/flycast-wasm/blob/16e9c7b4b7065a4bd42e7490e8aab3e9283d5415/patches/fly_instrument.h), and [emitter](https://github.com/nasomers/flycast-wasm/blob/16e9c7b4b7065a4bd42e7490e8aab3e9283d5415/patches/wasm_emit.h) inform this work. These are design references; its Flycast/SHIL JIT backend is not a drop-in replacement for the kit's ahead-of-time C translator. Performance figures in that project are not measurements of this kit.

| Area | Current implementation | Remaining work |
| --- | --- | --- |
| Differential validation | Independent integer/control-flow subset oracle compares actual translated O2 C against synthetic RAM-only programs, including ordered writes. Initial run: 4,096 comparisons, zero differences. A corrupted candidate test confirms mismatch detection. | Full interpreter-backed title snapshots, FPU, PC/dispatch, interrupts, and hardware-aware isolation. The current oracle is not Flycast. |
| Scheduling | Fractional 60 Hz wall-clock VBlank deadlines, no virtual-disc-time burst; bounded cooperative browser yields. | Guest-cycle accounting and a cycle-denominated debt budget. Current pacing is not cycle-accurate. |
| Diagnostics | Fixed-capacity browser history, event categories, batched DOM updates, no normal console flood, progress watchdog, downloadable JSON, and targeted render samples. Overflow is explicit. | Structured core IRQ/cycle/DMA events; audio queue/underrun counters are already exported. |
| Audio | ARM7 driver plus 64-channel PCM16/PCM8/Yamaha ADPCM direct stereo mixer, pitch/loop/key control, amplitude envelopes, pan/master attenuation, and a bounded AudioWorklet queue with device-rate resampling. | DSP effects, filter/LFO modulation, CDDA, and hardware-accurate sample/CPU scheduling. Browser listening and underrun behavior must be verified per title. |
| Optimization | Dedicated worker/OffscreenCanvas, cached ThinLTO, material-state caching, bounded LRU texture cache, and windowed render/texture telemetry. | Validate guarded RAM access, register caching and block merging before enabling them. Include the real production memory path in comparisons. |

The next execution work references the emitter's register cache (flush dirty
registers at calls/exits), guarded RAM loads with the original address preserved
for slow paths, and the validator's production-write-path comparisons. These
are not enabled merely because the upstream tests passed: our C translator has
different CPU structures, address translation and interrupt polling. Our helpers
share one WASM module, so upstream JIT import-crossing counts do not predict our
costs. Measure helper density and validate the actual optimized path here.

The production build script is another reference for separating diagnostic and
release behavior. Guest-cycle debt and idle-loop handling still need their own
implementation and validation; the current wall-clock pacing is not that code.

Run the reproducible subset validation from the kit's parent directory:

```sh
python3 dreamcast-port-kit/validation/sh4_subset.py \
  --toolchain crazy-taxi-port/research/dcrecomp \
  --seed 1 --programs 32 --cases 128 \
  --report crazy-taxi-port/portable-project/.local/translation-differential.json
```

The JSON report enumerates coverage and excluded state. Unsupported oracle
instructions fail rather than silently passing. Hardware reads/writes are
excluded by construction; they are not replayed into live devices. A future
full-state validator must snapshot or journal side effects and report excluded
blocks by reason. CPU time in competitive rules must stay deterministic;
audio-buffer rate control must not silently change ranked simulation speed.

The browser adapter uses Emscripten's monotonic clock directly for microsecond
timestamps, avoiding overflow in SDL performance-counter multiplication during
long browser sessions. Audio work is bounded after stalls; discarded time is
reported in diagnostics rather than mixed in an unbounded burst.

## Browser sound

Start game creates/resumes Web Audio in the click gesture. Enable sound retries
if the browser suspended it; Mute controls listening gain. The runtime synthesizes
44.1 kHz stereo from the game's own sound RAM and AICA channel registers. The
AudioWorklet maintains a bounded queue, primes 4,096 source frames, linearly
resamples to the device rate, and reports underruns/overruns without changing
game speed. Source blocks are transferred through MessagePort; no shared-memory
or cross-origin-isolation requirement is added.

Runtime output offers an eight-second WAV capture of actual mixer output and
JSON diagnostics with nonzero mixer/output frame counts. This is not microphone
recording. Captures and source game audio must stay private. `NOTICE.audio`
credits the sound-hardware reference and derived timing tables.

Run `node tests/audio_worklet_test.cjs` inside the kit. Python `test_audio.py`
checks synthetic PCM16/PCM8, ADPCM vectors, pitch, loops, global key execution,
stereo routing and master mute under address/undefined-behavior sanitizers.
A fixture passing does not establish a particular game's music or speech.

The browser shell is named **Dreamcast Port Lab**. Its 4:3 game canvas is
centered, with page settings below the game and no duplicate page heading or
startup status paragraph. Fatal diagnostics remain available in Runtime output.

## Safari startup diagnostics

A local Mac Safari user confirmed graphics and audio output. Menu speed remains under investigation. Startup checks report missing
WebAssembly/WebGL 2, script-load errors, WASM aborts and shader failures in a
visible error banner. Ordinary startup text stays hidden. The loopback dev
server accepts a bounded same-origin diagnostic POST and stores one local
report per browser family under the project `.local/` folder. These reports
include the user-agent, failure and last 40 log entries; they are not uploaded
externally or served as page assets. Restart an older dev server to enable the
endpoint. SDL audio initialization is disabled in browser builds because the
separate Web Audio path owns sound; an audio initialization failure does not
prevent loading the game.

`node tests/browser_startup_test.cjs` checks the startup/error contract.

## Active-tab scheduling and performance builds

Browser CPU execution yields after roughly eight milliseconds of work through
MessageChannel tasks. This avoids chained zero-delay timers consuming a large
part of active Safari execution time. Hidden tabs and browsers without
MessageChannel retain timer yielding. The task grants an event-loop opportunity;
it does not advance guest time. VBlank deadlines and the audio source clock stay
independent. `node tests/browser_scheduler_test.cjs` checks asynchronous FIFO
completion, channel reuse and fallbacks.

Use a normal `build-browser` for playback. Add `--abi` only while investigating
register/stack corruption. The build receipt and diagnostic export now identify
the ABI mode and scheduler so performance reports can be tied to a specific
build. A user-supplied Mac Safari report confirmed working audio/graphics but
about 19 FPS and approximately 2.1 seconds of timer wait per 5-second window.
The user subsequently confirmed the updated build works. A local Chromium
check measured about 50–70 ms of yield waiting per five-second window; that
number is not a new Safari FPS measurement.

## Rendering diagnostics and local reference measurement

The worker can run a bounded input timeline, capture the current frame or VRAM,
isolate rendering passes, pause execution, and measure 30 seconds of platform
presentations. These controls live under Runtime output. Replay is a debugging
input script, not an authoritative or deterministic game replay. Manual input
and pause cancel a pending script. Diagnostic render modes must be restored to
Normal before recording performance. GPU completion is not measured.

Texture reads now mirror at the 8 MiB VRAM boundary, including cache comparisons
that cross it. Vertex interpolation recovers clip W from PVR reciprocal W.
Material state honors signed-area culling and TSP blending in opaque lists as
well as translucent lists. Flycast's opaque-list blending behavior is documented
in its [OpenGL renderer](https://github.com/flyinghead/flycast/blob/master/core/rend/gles/gldraw.cpp).
These changes do not establish complete rendering fidelity.

Browser rebuilds publish a content-addressed WASM file before atomically replacing
the loader. Existing loaders retain their prior complete binary while a rebuild
is in progress. Older content-addressed files remain for active pages.

See [the local comparison record](validation/browser-comparison-2026-10-30.md)
for the measured gameplay scene and limitations.

## White scenery correction

The Dreamcast system-bus revision register, `SB_SBREV` at `0x005F689C`, now
returns the read-only value `0x0B`. Returning zero made the game graphics driver
select a reduced hardware capability set and exhaust one texture-memory bank.
The game then substituted its white dummy texture for city materials. This is
a shared hardware-register fix, with no title-address patch or replacement art.

The road, pavement, walls, trees and buildings were verified in browser Arcade
driving after the correction. Captured allocation failures fell from 320 to zero
in the compared local states. See [the validation record](validation/white-scenery-2026-10-30.md).
Other rendering effects remain incomplete; this does not establish full hardware
accuracy or change the earlier benchmark into an equivalent-performance claim.

Runtime output also offers an explicit one-frame render snapshot: a binary file
with a length-prefixed JSON layout followed by main RAM, VRAM and geometry lists.
It captures diagnostic state only on request and is not a restorable save state.
Keep captures local because they contain disc-derived game data.
