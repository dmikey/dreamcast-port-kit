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
code runs as WebAssembly, with WebGL2 graphics, SDL keyboard input and same-origin
bounded disc chunks. Only the executable is embedded; the full disc is not a
startup download. The server binds to loopback. Keep disc-derived browser
artifacts private. This is local browser bring-up, not a published game.

`control_flow.py` lowers terminal cross-function jumps to a bounded-stack
trampoline. Normal calls retain their continuations. Its hash and the generated
source hashes are recorded at translation. The synthetic regression executes
100,000 cross-function iterations with nested calls.

`graphics.py` and `runtime/texture_gl.h` preserve material state and decode
16-bit direct-color, VQ and palette textures from live VRAM. Cached textures
are reused only while their exact source bytes and palette remain unchanged. Unsupported texture
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

This repository is distributed under GPL-2.0; see `LICENSE` and `NOTICE.md`.
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
and texture fidelity. Exploratory local frame-rate measurements are not a compatibility or
performance guarantee. Controllable driving, audible audio, and deterministic
replay remain unverified.

## Browser validation

Verify the original renderer, asset loading, input and audio in the browser.
Keep tests and build tool versions pinned. The current CLI does not claim that
unfinished validation stages are automatic.

The reusable agent workflow is in `skills/dreamcast-port/SKILL.md`.

Renderer packet layouts and shading behavior are cross-checked against the [Flycast hardware structures](https://github.com/flyinghead/flycast/blob/master/core/hw/pvr/ta_structs.h) and [GL renderer](https://github.com/flyinghead/flycast/blob/master/core/rend/gles/gles.cpp).
