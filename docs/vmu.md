# VMU cards

Browser builds connect one A1 VMU with 128 KiB of storage, a 48×32 LCD and a
clock. The VMU CPU and buzzer are not implemented.

Cards live in **IndexedDB in the current browser**, separately for each project.
The workbench and player share a project's card on the same origin. On first
use, an existing native project card is imported when available; otherwise a
formatted 200-block card is created. Subsequent browser writes stay in the
browser. Export a card before moving to another browser, computer or server
origin. Clearing site data removes browser cards.

## Manage saves

Open the VMU inspector. Stop the game to edit its card. The manager can:

- Inspect saved-file descriptions, application IDs, allocation and bytes.
- Copy, rename or delete a save; export a file as VMS.
- Rename, import, export or clear the whole card.
- Restore any of the last ten management edits.

Each management edit preserves the previous card as a recoverable version.
Game writes are acknowledged after the IndexedDB transaction commits. Every
writer must hold the current revision; stale writes fail rather than overwrite
another session. Restart the game after editing a card.

Malformed chains, overlapping files and unsupported geometry are rejected for
edits. Import accepts a valid full 128 KiB card. The manager does not alter
game-specific checksums or arbitrary game data.

The native diagnostic runtime uses `.local/vmu/a1.bin`. Its loopback HTTP API
remains available for migration and native tools; it is not the browser's live
save store.

## Debugger

`get_vmu_status(session_id)` returns the browser card's storage identity,
revision, capacity and file directory. `manage_vmu_file` exposes named copy,
rename and delete operations on a stopped workbench, with automatic recovery.
Neither tool accepts JavaScript or arbitrary memory writes.

## References and evidence

The implementation uses independently written protocol and filesystem code,
referencing [Flycast's Maple devices](https://github.com/flyinghead/flycast/blob/master/core/hw/maple/maple_devs.cpp)
and KallistiOS's [VMU filesystem](https://github.com/KallistiOS/KallistiOS/blob/master/kernel/arch/dreamcast/include/dc/vmufs.h)
and [save headers](https://github.com/KallistiOS/KallistiOS/blob/master/kernel/arch/dreamcast/include/dc/vmu_pkg.h).
No VMU BIOS or default firmware image is included.

Native tests cover discovery, phased write/readback, LCD, clock and storage
failures. Browser manager validation uses synthetic saves. These checks do not
establish a commercial title's save/load round trip.
