---
name: dreamcast-port
description: Inspect user-supplied Dreamcast discs, generate local C translations, and bring up native or browser ports using a pinned reusable pipeline with exact executable title profiles. Use for Dreamcast reverse engineering and ports.
---

# Dreamcast Port

Use the shared CLI at `../../port.py` relative to this skill folder. Read the
kit's `../../README.md` for commands, supported inputs and current target limits.
Preserve the requested game's mechanics and platform. A newly written driving
game or a character viewer does not establish a port of an original engine.

## Runtime architecture

The accepted route recompiles SH-4 game code, emulates Dreamcast hardware, and
interprets the ARM7 sound CPU. Describe it accurately as recompilation with an
emulation layer. An all-new engine is an optional future replacement, not a
prerequisite. Keep reusable platform code separate from exact-title profiles;
prove each new title rather than claiming universal ROM compatibility.

## Import and identify

Run `prepare` on the supplied archive or descriptor into a named project. It
reads IP.BIN and ISO9660, hashes the executable and all data tracks, and chooses
a known profile only by exact executable hash. Input images stay unchanged;
generated data and source stay under the project's ignored `.local/`.

For an unknown title, complete its generated `title-profile.json` from evidence
in that executable. Never copy Crazy Taxi's entry, interrupt vector, bootstrap
relocation, model offsets or texture tables into another title. The importer
supports GDI and supported raw CUE layouts, including 7z/zip packaging. Unsupported
CDI, CHD, scrambled images, or WinCE startup require explicit format/runtime
adapters; surface that need and keep the inspected input intact.

## Translate, build, debug

Run `bootstrap` once for a pinned shared toolchain; it applies the checked-in
patches without overwriting unrelated changes. Run `translate`, `build --abi`,
then bounded `run` tests. Use `port.json`, source/build provenance and
`.local/native/run-result.json` as the handoff state.

Translation emits heuristic C, including code/data false positives. Unknown
instructions, missing callbacks, incomplete hardware, and title-specific
calling conventions need analysis. Do not make unresolved code silently succeed.
The checked-in patches fix lost calls at shared delay-slot entries and preserve
the dispatch PC across interrupts; keep new general fixes here and test them
with small independently executable instruction cases.

Native ABI warnings are diagnostic: compiler helpers can intentionally pop
caller-owned words. Read the original call/return convention before "fixing"
register saves or forcing stack balance. Confirm library initialization and
disc commands before bypassing a wait or patching a game's error branch.

## Assets and browser validation

Asset adapters belong to title profiles. Validate pointer tables, skeletons,
texture formats and regions against the input before exporting. Use reversible
replacement packs bound to material/texture slots, preserving the original
data. Test the selected character in actual driving before expanding the roster.

Use `build-browser --emsdk PATH` and `serve_browser.py` for the product target.
The native build is a diagnostic. WebAssembly/WebGL2, chunked disc loading and
initial texture adapters exist; a finished game still needs their behavior
and audio/input verified in a browser; compiler installation or
a WASM file alone is not that evidence.

Record separately: extracted, translated, compiled, original geometry packets,
title screen, controllable gameplay, audio, browser behavior, deterministic
replay. Only mark each demonstrated stage true.
Publication and deployment remain separate from local port work.
