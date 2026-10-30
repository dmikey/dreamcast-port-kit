#!/usr/bin/env python3
"""Repeatable, title-profiled Dreamcast disc inspection and C translation.

Only the Python standard library and system bsdtar/git are required. The input
disc is never modified. Generated game data stays in each project's .local/.
"""
import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parent
SCHEMA = 1
CORE_COMMIT = '3c60e6f03cbbaaabeaa1f3165247ed3120f23c3e'


class PortError(Exception):
    pass


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def contained(base, name):
    relative = PurePosixPath(name.replace('\\', '/'))
    if relative.is_absolute() or '..' in relative.parts or re.match(r'^[A-Za-z]:', name):
        raise PortError(f'Path escapes its disc/archive: {name}')
    result = (base / str(relative)).resolve()
    if not result.is_relative_to(base.resolve()):
        raise PortError(f'Path escapes its disc/archive: {name}')
    return result


@dataclass
class Track:
    lba: int
    sector_bytes: int
    path: Path
    offset: int = 0

    @property
    def sectors(self):
        return (self.path.stat().st_size - self.offset) // self.sector_bytes


def raw_lba(path, offset=0):
    with path.open('rb') as f:
        f.seek(offset)
        head = f.read(16)
    if len(head) != 16 or head[:12] != b'\0' + b'\xff' * 10 + b'\0' or head[15] != 1:
        raise PortError(f'{path.name}: expected a raw MODE1 sector header')
    bcd = lambda v: (v >> 4) * 10 + (v & 15)
    return (bcd(head[12]) * 60 + bcd(head[13])) * 75 + bcd(head[14]) - 150


def read_tracks(descriptor):
    base = descriptor.parent
    tracks = []
    if descriptor.suffix.lower() == '.gdi':
        lines = descriptor.read_text().splitlines()
        expected = int(lines[0].strip())
        records = [shlex.split(line) for line in lines[1:] if line.strip()]
        if len(records) != expected:
            raise PortError('GDI track count does not match its records')
        for record in records:
            if len(record) != 6:
                raise PortError('Malformed GDI track record')
            number, lba, kind, sector, filename, offset = record
            if int(kind) == 4:
                tracks.append(Track(int(lba), int(sector), contained(base, filename), int(offset)))
    elif descriptor.suffix.lower() == '.cue':
        current, mode, index = None, None, None
        def finish():
            if current and mode and mode.startswith('MODE1/'):
                width = int(mode.split('/')[1])
                if width != 2352:
                    raise PortError('CUE with cooked sectors needs an explicit-LBA GDI descriptor')
                offset = (index or 0) * width
                tracks.append(Track(raw_lba(current, offset), width, current, offset))
            elif mode and mode != 'AUDIO':
                raise PortError(f'CUE mode {mode} requires a disc-format adapter')
        for line in descriptor.read_text().splitlines():
            tokens = shlex.split(line)
            if not tokens:
                continue
            if tokens[0].upper() == 'FILE':
                finish()
                if len(tokens) < 3 or tokens[-1].upper() != 'BINARY':
                    raise PortError('Only binary CUE tracks are supported')
                current, mode, index = contained(base, tokens[1]), None, None
            elif tokens[0].upper() == 'TRACK':
                if mode:
                    raise PortError('Multi-track-per-file CUE needs a format adapter; no LBA will be guessed')
                mode = tokens[2].upper()
            elif tokens[:2] == ['INDEX', '01']:
                m, s, f = map(int, tokens[2].split(':'))
                index = (m * 60 + s) * 75 + f
        finish()
    else:
        raise PortError('Use a GDI or CUE descriptor, or a 7z/zip archive containing one')
    for track in tracks:
        if track.sector_bytes not in (2048, 2352) or track.offset < 0 or track.sectors <= 0:
            raise PortError(f'Invalid track: {track.path}')
    if not tracks:
        raise PortError('No supported data tracks found')
    return sorted(tracks, key=lambda t: t.lba)


class Disc:
    def __init__(self, descriptor):
        self.descriptor = Path(descriptor).resolve()
        self.tracks = read_tracks(self.descriptor)
        candidates = sorted(self.tracks, key=lambda t: (t.lba == 45000, t.lba), reverse=True)
        self.volume_lba = next((t.lba for t in candidates if t.sectors > 16
                                and self.sector(t.lba + 16)[1:6] == b'CD001'), None)
        if self.volume_lba is None:
            raise PortError('No ISO9660 volume found; image may need decompression or a format adapter')

    def sector(self, lba):
        for track in self.tracks:
            if track.lba <= lba < track.lba + track.sectors:
                with track.path.open('rb') as f:
                    f.seek(track.offset + (lba - track.lba) * track.sector_bytes + (16 if track.sector_bytes == 2352 else 0))
                    data = f.read(2048)
                if len(data) != 2048:
                    raise PortError('Truncated disc sector')
                return data
        raise PortError(f'LBA {lba} is not in any supplied data track')

    def read(self, lba, size):
        if size < 0 or size > 2 * 1024 ** 3:
            raise PortError('Invalid file extent length')
        # Keep file handles open only for this read, with contiguous runs batched.
        out = bytearray()
        for start in range(0, size, 2048 * 1024):
            count = min(1024, (size - start + 2047) // 2048)
            at = lba + start // 2048
            track = next((t for t in self.tracks if t.lba <= at and at + count <= t.lba + t.sectors), None)
            if track:
                with track.path.open('rb') as f:
                    f.seek(track.offset + (at - track.lba) * track.sector_bytes)
                    raw = f.read(count * track.sector_bytes)
                if len(raw) != count * track.sector_bytes:
                    raise PortError('Truncated file extent')
                if track.sector_bytes == 2048:
                    out.extend(raw)
                else:
                    for i in range(count):
                        out.extend(raw[i * 2352 + 16:i * 2352 + 2064])
            else:
                for i in range(count):
                    out.extend(self.sector(at + i))
        return bytes(out[:size])

    def files(self):
        pvd = self.sector(self.volume_lba + 16)
        root = pvd[156:190]
        found, visited = [], set()
        def walk(lba, size, prefix, depth=0):
            if (lba, size) in visited or depth > 32:
                raise PortError('Cyclic or excessively deep ISO directory')
            visited.add((lba, size))
            data, at = self.read(lba, size), 0
            while at < len(data):
                length = data[at]
                if not length:
                    at = (at // 2048 + 1) * 2048
                    continue
                record = data[at:at + length]
                if length < 34 or len(record) != length or 33 + record[32] > length:
                    raise PortError('Malformed ISO directory record')
                name = record[33:33 + record[32]]
                if name not in (b'\0', b'\1'):
                    name = name.decode('ascii').split(';')[0]
                    contained(Path('/disc'), name)
                    path = prefix + name
                    elba, esize = struct.unpack_from('<I', record, 2)[0], struct.unpack_from('<I', record, 10)[0]
                    if record[25] & 2:
                        walk(elba, esize, path + '/', depth + 1)
                    else:
                        found.append({'path':path, 'lba':elba, 'bytes':esize})
                at += length
        walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')
        return sorted(found, key=lambda f: f['path'])

    def metadata(self):
        ip = self.read(self.volume_lba, 32768)
        if ip[:16] != b'SEGA SEGAKATANA ':
            raise PortError('Dreamcast IP.BIN signature missing; no bootstrap assumptions will be made')
        text = lambda a, b: ip[a:b].decode('ascii', 'replace').strip()
        return {'title':text(128, 256), 'product':text(64, 74), 'version':text(74, 80),
                'releaseDate':text(80, 88), 'region':text(48, 56), 'bootFile':text(96, 112),
                'volumeLBA':self.volume_lba}


def unpack_archive(source, destination):
    listing = subprocess.run(['bsdtar', '-tf', str(source)], check=True, capture_output=True, text=True).stdout
    for name in listing.splitlines():
        contained(destination, name)
    types = subprocess.run(['bsdtar', '-tvf', str(source)], check=True, capture_output=True, text=True).stdout
    if any(line and line[0] not in '-d' for line in types.splitlines()):
        raise PortError('Archive links and special entries are unsupported')
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(['bsdtar', '-xf', str(source), '-C', str(destination), '--no-same-owner'], check=True)
    for path in destination.rglob('*'):
        if path.is_symlink():
            raise PortError('Archive contains a symlink')


def choose_disc(source, project, descriptor=None):
    if source.suffix.lower() in ('.7z', '.zip'):
        dest = project / '.local/disc'
        lock = project / '.local/archive-lock.json'
        source_hash = digest(source)
        if dest.exists():
            if not lock.exists() or json.loads(lock.read_text()).get('sha256') != source_hash:
                raise PortError('Project already contains a different archive; choose a new project folder')
        else:
            with tempfile.TemporaryDirectory(prefix='dc-import-', dir=str(project / '.local')) as tmp:
                staging = Path(tmp) / 'disc'
                unpack_archive(source, staging)
                staging.rename(dest)
            write_json(lock, {'sha256':source_hash, 'name':source.name})
        choices = sorted(p for p in dest.rglob('*') if p.suffix.lower() in ('.gdi', '.cue'))
        if descriptor:
            chosen = contained(dest, descriptor)
            if chosen not in choices:
                raise PortError('Selected descriptor was not found in the archive')
            return chosen
        if len(choices) != 1:
            raise PortError('Archive needs exactly one descriptor, or use --descriptor with its relative path')
        return choices[0]
    if source.suffix.lower() in ('.gdi', '.cue'):
        return source
    raise PortError('Unsupported input. Supply GDI/CUE or a 7z/zip containing one. CHD/CDI need a format adapter.')


def prepare(args):
    source, project = Path(args.input).resolve(), Path(args.project).resolve()
    if not source.is_file():
        raise PortError('Input file does not exist')
    (project / '.local').mkdir(parents=True, exist_ok=True)
    ignore = project / '.gitignore'
    current = ignore.read_text() if ignore.exists() else ''
    if '.local/' not in current.splitlines():
        ignore.write_text(current + ('\n' if current and not current.endswith('\n') else '') + '.local/\n')
    disc_path = choose_disc(source, project, args.descriptor)
    disc = Disc(disc_path)
    metadata, inventory = disc.metadata(), disc.files()
    boot = next((f for f in inventory if f['path'].upper() == metadata['bootFile'].upper()), None)
    if not boot:
        raise PortError(f"Boot executable {metadata['bootFile']} was not found")
    executable = disc.read(boot['lba'], boot['bytes'])
    sha1, sha256 = hashlib.sha1(executable).hexdigest(), hashlib.sha256(executable).hexdigest()
    profiles = [json.loads(p.read_text()) for p in (KIT / 'profiles').glob('*.json')]
    profile = next((p for p in profiles if p.get('executableSHA1') == sha1), None)
    previous_file = project / 'port.json'
    if previous_file.exists():
        previous = json.loads(previous_file.read_text())
        if previous.get('executable', {}).get('sha256') != sha256:
            raise PortError('Different executable already occupies this project; choose a new project folder')
    asset_dir = project / '.local/extracted'
    asset_dir.mkdir(exist_ok=True)
    boot_output = contained(asset_dir, metadata['bootFile'])
    boot_output.parent.mkdir(parents=True, exist_ok=True)
    boot_output.write_bytes(executable)
    (asset_dir / 'IP.BIN').write_bytes(disc.read(disc.volume_lba, 32768))
    if args.all_files:
        for f in inventory:
            path = contained(asset_dir, f['path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(disc.read(f['lba'], f['bytes']))
    tracks = [{'lba':t.lba, 'sectorBytes':t.sector_bytes, 'path':str(t.path), 'offset':t.offset,
               'bytes':t.path.stat().st_size, 'sha256':digest(t.path)} for t in disc.tracks]
    identity = [{k:v for k,v in t.items() if k!='path'} for t in tracks]
    source_set_sha = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    manifest = {'schemaVersion':SCHEMA, 'disc':metadata,
                'executable':{'path':'.local/extracted/' + metadata['bootFile'], 'bytes':len(executable), 'sha1':sha1, 'sha256':sha256},
                'profileId':profile['id'] if profile else None,
                'sourceSetSHA256':source_set_sha,
                'state':'inspected' if profile else 'needs-title-profile',
                'evidence':{'discRead':True, 'translated':False, 'compiled':False, 'bootedToMenu':False,
                            'playable':False, 'browserPlayable':False, 'deterministicReplay':False}}
    # Preserve completed-stage evidence on an idempotent import of the same disc.
    if previous_file.exists() and previous.get('sourceSetSHA256') == source_set_sha:
        manifest['evidence'] = previous['evidence']
        manifest['state'] = previous['state']
    write_json(project / 'port.json', manifest)
    write_json(project / '.local/disc-inventory.json', inventory)
    write_json(project / '.local/source-lock.json', {'descriptor':str(disc_path), 'sha256':digest(disc_path), 'tracks':tracks})
    if not profile and not (project / 'title-profile.json').exists():
        write_json(project / 'title-profile.json', {'schemaVersion':SCHEMA, 'id':None, 'title':metadata['title'],
                    'executableSHA1':sha1, 'loadAddress':None, 'runtimeEntry':None, 'irqEntry':None,
                    'notes':'Determine from this executable; do not copy addresses from another title.'})
    print(json.dumps(manifest, indent=2))


def verify_project(project):
    manifest = json.loads((project / 'port.json').read_text())
    executable = contained(project, manifest['executable']['path'])
    if digest(executable) != manifest['executable']['sha256']:
        raise PortError('Extracted executable changed; re-import and investigate before translating')
    return manifest, executable


def translate(args):
    project, toolchain = Path(args.project).resolve(), Path(args.toolchain).resolve()
    manifest, executable = verify_project(project)
    profile = None
    profile_directory = KIT / 'profiles'
    if manifest['profileId']:
        profile = next((json.loads(p.read_text()) for p in (KIT / 'profiles').glob('*.json')
                        if json.loads(p.read_text())['id'] == manifest['profileId']), None)
    elif (project / 'title-profile.json').exists():
        profile = json.loads((project / 'title-profile.json').read_text())
        profile_directory = project
    base = args.base or (profile or {}).get('loadAddress')
    if not base:
        raise PortError('Translation needs a verified loadAddress in the title profile or explicit --base')
    if profile and profile['executableSHA1'] != manifest['executable']['sha1']:
        raise PortError('Profile executable hash mismatch')
    revision = subprocess.run(['git', '-C', str(toolchain), 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
    if revision != CORE_COMMIT:
        raise PortError(f'Toolchain revision differs from the tested pin {CORE_COMMIT}')
    generated = project / '.local/generated'
    generated.mkdir(exist_ok=True)
    argv = [sys.executable, str(toolchain / 'tools/static_recompile.py'), str(executable),
            str(generated / 'src'), str(generated / 'include/game'), '--base', base]
    if (profile or {}).get('entriesFile'):
        entries = contained(profile_directory, profile['entriesFile'])
        argv += ['--entries', str(entries)]
    aliases = generated / 'code-aliases.json'
    write_json(aliases, (profile or {}).get('codeAliases', []))
    argv += ['--aliases', str(aliases)]
    with (generated / 'translation.log').open('w') as log:
        subprocess.run(argv, check=True, stdout=log, stderr=subprocess.STDOUT)
    import control_flow
    control_flow.lower(generated,(profile or {}).get('codeAliases',[]))
    patches = subprocess.run(['git', '-C', str(toolchain), 'diff', '--binary'], check=True, capture_output=True).stdout
    sources = sorted((generated / 'src').glob('*.c'))
    write_json(generated / 'provenance.json', {'schemaVersion':SCHEMA, 'toolchainCommit':revision,
                'localPatchSHA256':hashlib.sha256(patches).hexdigest(), 'executableSHA256':digest(executable),
                'base':base, 'profileId':manifest['profileId'], 'sourceSetSHA256':manifest['sourceSetSHA256'],
                'sourceHashes':{p.name:digest(p) for p in sources},
                'controlFlowLoweringSHA256':digest(KIT/'control_flow.py'), 'behaviorVerified':False})
    manifest['evidence']['translated'] = True
    manifest['state'] = 'translated-unverified'
    write_json(project / 'port.json', manifest)
    print(f'Translated {len(sources)} C files. Runtime behavior remains unverified.')


def bootstrap(args):
    destination = Path(args.toolchain).resolve()
    pins = json.loads((KIT / 'toolchain-lock.json').read_text())
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git','clone','--no-checkout',pins['repository'],str(destination)],check=True)
        subprocess.run(['git','-C',str(destination),'checkout','--detach',pins['commit']],check=True)
    revision = subprocess.run(['git','-C',str(destination),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    if revision != pins['commit']:
        raise PortError('Existing toolchain has a different revision; use a new destination')
    for patch in pins['patches']:
        path=KIT/'patches'/patch
        check=subprocess.run(['git','-C',str(destination),'apply','--check',str(path)],capture_output=True)
        if check.returncode == 0:
            subprocess.run(['git','-C',str(destination),'apply',str(path)],check=True)
        else:
            reverse=subprocess.run(['git','-C',str(destination),'apply','--reverse','--check',str(path)],capture_output=True)
            if reverse.returncode:
                raise PortError(f'Cannot apply {patch} to this working tree; existing changes were preserved')
    for name, expected in pins['patchedSourceSHA256'].items():
        if digest(destination/name)!=expected:
            raise PortError('Toolchain source differs from the tested pin: '+name)
    print('Pinned toolchain and shared fixes are ready:',destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare', help='Inspect, hash and extract a user-supplied disc')
    p.add_argument('input'); p.add_argument('--project', required=True)
    p.add_argument('--descriptor'); p.add_argument('--all-files', action='store_true')
    p = commands.add_parser('translate', help='Translate the exact executable with a pinned toolchain')
    p.add_argument('--project', required=True); p.add_argument('--toolchain', required=True); p.add_argument('--base')
    p = commands.add_parser('status', help='Validate the executable and show honest stage evidence')
    p.add_argument('--project', required=True)
    p = commands.add_parser('bootstrap', help='Fetch the pinned public translator and apply reviewed shared patches')
    p.add_argument('--toolchain',required=True)
    p = commands.add_parser('build',help='Build a diagnostic native runtime from an exact title profile')
    p.add_argument('--project',required=True);p.add_argument('--toolchain',required=True);p.add_argument('--abi',action='store_true')
    p.add_argument('--graphics',action='store_true',help='Enable native SDL2/OpenGL diagnostic rendering')
    p = commands.add_parser('build-browser',help='Build the exact game for WebAssembly and WebGL2')
    p.add_argument('--project',required=True);p.add_argument('--toolchain',required=True);p.add_argument('--emsdk',required=True);p.add_argument('--abi',action='store_true')
    p = commands.add_parser('run',help='Run a bounded native bring-up test and write structured evidence')
    p.add_argument('--project',required=True);p.add_argument('--seconds',type=float,default=10)
    p.add_argument('--capture-frame',type=int,help='Capture this submitted graphics frame to .local/native/frame.ppm')
    args = parser.parse_args()
    try:
        if args.command == 'prepare': prepare(args)
        elif args.command == 'translate': translate(args)
        elif args.command == 'bootstrap': bootstrap(args)
        elif args.command == 'build':
            import native
            native.build(args,KIT,PortError,verify_project,write_json)
        elif args.command == 'build-browser':
            import browser
            browser.build(args,KIT,PortError,verify_project,write_json)
        elif args.command == 'run':
            import native
            return native.run(args,PortError,verify_project,write_json)
        else: print(json.dumps(verify_project(Path(args.project).resolve())[0], indent=2))
    except (PortError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'PORT ERROR: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
