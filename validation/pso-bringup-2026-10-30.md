# PSO startup investigation

Target: Phantasy Star Online (USA), Rev B, V2.011; executable SHA-256
`11dc59ee0278675decf5e0bf1fa30646f889a0e5a7f10251f3c3a697e42a28e5`.

The original browser build entered title code but drew no frames. Native traces
showed graphics waiting after initialization had failed and shut down interrupts.

Verified shared defects and corrections:

- GETTOC2 ignored the density area and supplied the low-density track. The
  high-density response now supplies track 3 at FAD 45150, first/last track
  metadata and lead-out. This clears the observed initialization error `-51`.
- Completed sector reads reported zero transferred bytes. Reporting the actual
  count clears the next `-19` read failure and allows root-directory reads.
- Interrupt routing treated encoded IRL line numbers as CPU priorities and
  synthesized an interrupt when VBlank was unrouted. Holly IML6/4/2 now map to
  priorities 6/4/2, with external-only sources also considered.

Routing was cross-checked with Flycast's
[Holly interrupt wiring](https://github.com/flyinghead/flycast/blob/master/core/hw/holly/holly_intc.cpp)
and [SH-4 priority table](https://github.com/flyinghead/flycast/blob/master/core/hw/sh4/sh4_interrupts.cpp).
Read completion counts were checked against its
[GD-ROM HLE implementation](https://github.com/flyinghead/flycast/blob/master/core/reios/gdrom_hle.cpp).

The TOC regression fails against the previous response and passes after adaptation.
The compiler integration test executes BIOS reads and checks busy/completed byte
counts and clearing them for a subsequent command. Interrupt tests execute the
actual adapted routing function. All 69 Python tests and 11 JavaScript suites pass.

Native artifact `20261031-040507-ebe8901b` gets past disc initialization and delivers
interrupts. It stops during context restoration at `0x8C113C4C`: the restored guest
stack and return address change, but execution resumes in the previous translated
C caller, then dispatches into stack data at `0x8C00F2F8`. Supporting that nonlocal
return remains outstanding. No title screen, gameplay or PSO audio is verified.

Crazy Taxi's previously validated WASM remains unchanged while PSO is rebuilt.
