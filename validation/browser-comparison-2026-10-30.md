# Local browser comparison, 2026-10-30

This is a single local measurement, not a cross-browser benchmark or a claim
that the port has matched Flycast's emulation accuracy.

| Runtime | Count | Duration | Rate |
| --- | ---: | ---: | ---: |
| Port kit, O3 ThinLTO, dedicated worker | 1754 platform presentations | 30.0157 s | 58.44/s |
| nasomers/flycast-wasm v1.0 | 1119 reported emulated frames | 30.0115 s | 37.29/s |

Both used the same local Crazy Taxi USA disc, Arcade / Work for 10 Minutes,
Axel at the initial stationary spawn, a 640 x 480 physical canvas, audio enabled,
and the same Chromium browser on the same Mac. The other runtime was paused
during each interval. There were no builds or test runs during either interval.
This is a scene workload test; sustained driving across the map is unmeasured.
The port's game was in Drive, the reference in Reverse, both stationary. The
port displayed a larger CSS canvas; compositor workloads were not identical.
The two counters have different definitions and do not measure GPU completion.

The port still draws white city scenery. Material diagnostics include many
8 x 8 white-texture materials; capturing nonwhite texture data elsewhere in VRAM
does not prove that each city surface has its correct material. The blending
change alone did not resolve this. The reference correctly textures the scene.
This fidelity difference prevents a like-for-like speed or accuracy claim.
Background plane/color, modifier-volume shadows and full hardware effects also
remain incomplete in the port. The 58.44/s figure must not be described as an
accuracy-equivalent win over full emulation.

The official reference release WASM was unchanged (SHA256
`db2b87d8d2742087a56c4eeed317da14e3549ee037e36de3d77c1e6e5291bead`).
Its private frontend needed missing resource-ZIP imports, EmulatorJS DOM target
mapping, and a WebGL extension-query compatibility repair before it could run
standalone. It used the user-supplied US BIOS v1.01d and flash, with HLE BIOS
disabled. Native resolution, no frame skipping, strip alpha sorting, no texture
upscaling, and mipmapping disabled were requested. The upscaling option was
rejected by the core; its default applied. The port uses its existing HLE boot.
No reference core, BIOS, ROM, generated commercial code, screenshot or audio is
distributed with this record.

Port WASM SHA256: `a8d5f71f8d0c70264876e0e4cb6fd67169dd1b24a5b52bd498de1d0c88fe14b5`.
The scene's five-second port telemetry reported roughly 0.775 ms average CPU
render submission, 2.0 ms maximum and zero texture uploads in that window.
This excludes GPU completion and does not imply that guest execution is free.

For repeat measurements: warm the same scene, pause competing runtimes, restore
Normal rendering, run the 30-second counter, export diagnostics and retain the
build hash, browser/host, scene, audio mode and reference repairs. Repeat runs
and moving-camera scenarios are needed before making performance claims.
