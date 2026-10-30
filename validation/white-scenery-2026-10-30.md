# White city scenery correction, 2026-10-30

The kit previously returned zero for the read-only Holly system-bus revision
register `SB_SBREV` (`0x005F689C`). The Dreamcast value is `0x0B`, also used in
[Flycast's system-bus reset](https://github.com/flyinghead/flycast/blob/master/core/hw/holly/sb.cpp).
The register value was verified against the game's driver initialization logic
and a local Flycast RAM capture. The port selected capability flags zero while
the reference selected `0x8F`. The reduced set prevented normal texture allocation
across both memory banks. City material records consequently selected the
game's white dummy texture.

`patches/holly-revision.patch` corrects the shared register read path. The
regression checks physical, cached and uncached address mirrors, read-only
behavior, and an adjacent unmapped register. The pinned hardware source hash
and translation provenance were regenerated. No title-specific addresses or
texture substitutions are in the runtime fix.

| Local captured state | Before | After |
| --- | ---: | ---: |
| Graphics driver capability flags | `0x00` | `0x8F` |
| Texture surface allocation failures, code 3 | 320 | 0 |
| Referenced white dummy surfaces | 85 | 0 |

The compared states are different frames of Arcade / Work for 10 Minutes with
Axel. They establish the allocation/material change, not deterministic replay.
The corrected browser build displayed textured road, pavement, walls, trees
and buildings at spawn and after a bounded acceleration input moved the taxi
to another location. Frame and RAM/VRAM/geometry captures remain private.

Corrected browser WASM SHA256:
`4fa717cdc664464c7101c24603cfd86d542d2a06d81e803b812d59f1921bb413`.
Validation: all 37 Python checks and five browser contract suites passed;
optimized browser and native diagnostic builds linked successfully.

This corrects the white city texture failure. Background-plane color,
modifier-volume shadows and other hardware effects remain separate limitations.
The earlier stationary-scene performance comparison used the defective build;
it has not been rerun with the restored scenery and does not establish an
accuracy-equivalent win over Flycast.
