# Projects and artifacts

A project owns one exact source-disc set, its title profile, translated code,
builds and diagnostic evidence. The workspace registry holds links to project
folders; it does not move or duplicate the input archive.

## Import and register

```sh
python3 port.py prepare "/path/to/game.7z" --project /path/to/project
python3 workspace.py add --project /path/to/project --id my-game
python3 serve_browser.py --project /path/to/project --port 4390
```

The workbench's **Project** selector opens `/projects/my-game/`. Each project
has its own `/player.html` and debug sessions. The server routes streamed disc
reads to that project's tracks, including when multiple sessions are open.
Switching projects starts a fresh session; game state is not transferred.

The local registry defaults to the kit's `.local/workspace.json`. Use
`workspace.py --workspace /path/to/workspace.json ...` and the server's matching
`--workspace` option for a different workspace. Registry paths stay local.
Only registered project ids can be opened through the server.

## Inspect artifacts

Open **Inspector → Artifacts** to see stage outcomes, timestamps, source/build
identity, recorded evidence, output logs and downloadable files. **Refresh**
reads new receipts after a CLI operation finishes. An unbuilt project shows its
bring-up requirements instead of offering a broken Play button.

Each CLI `prepare`, `translate`, `build`, `build-browser` and `run` attempt saves
an immutable receipt under `<project>/.local/artifacts/<id>/`. Failed stages are
included, with their error and output; they never become runnable builds.
Build success and playable behavior are separate evidence fields.

A successful browser build snapshots its loader, content-addressed WASM, build
metadata and frontend. **Open build** opens that exact snapshot in a workbench;
its player is a fresh session of the same build. Later builds and UI edits do
not replace those saved bytes. Source-disc reads still use the owning project's
local tracks, so keep those files in place. Native builds retain their binary
and metadata for download; the browser does not launch native executables.

For an existing build created before artifact recording was introduced:

```sh
python3 workspace.py snapshot --project /path/to/project --stage build-browser
```

This records existing output and verifies its WASM/source identity. It does not
rerun the build or add gameplay verification. Other supported snapshot stages
are `prepare`, `translate`, `build` and `run`.

## Keep local data private

The registry, extracted disc files, translated game code, build binaries, logs
and captures live under ignored `.local/` folders. Artifact downloads can contain
game data and local paths. They are local development outputs, not public game
releases. The repository contains the reusable tooling and synthetic tests.

An unknown title needs addresses and startup/interrupt behavior verified against
its own executable. Importing or translating it does not imply it can boot. The
workbench preserves that distinction in project status and recorded evidence.
