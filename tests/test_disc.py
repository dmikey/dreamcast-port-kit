import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
import port


def directory_record(name, lba, size, directory=False):
    raw = name if isinstance(name, bytes) else name.encode()
    result = bytearray(33 + len(raw) + (0 if len(raw) % 2 else 1))
    result[0] = len(result)
    struct.pack_into('<I', result, 2, lba)
    struct.pack_into('>I', result, 6, lba)
    struct.pack_into('<I', result, 10, size)
    struct.pack_into('>I', result, 14, size)
    result[25], result[28], result[31], result[32] = 2 if directory else 0, 1, 1, len(raw)
    result[33:33 + len(raw)] = raw
    return result


def fixture(path, raw=False, offset=0, title='ANOTHER DREAMCAST TITLE', boot='MAIN.BIN'):
    base = 45000
    sectors = [bytearray(2048) for _ in range(32)]
    sectors[0][:16] = b'SEGA SEGAKATANA '
    def field(start, end, text):
        sectors[0][start:end] = text.encode().ljust(end - start, b' ')
    field(48, 56, 'JUE'); field(64, 74, 'T-TEST001'); field(74, 80, 'V1.000')
    field(80, 88, '20000101'); field(96, 112, boot); field(128, 256, title)
    pvd = sectors[16]
    pvd[:7] = b'\x01CD001\x01'
    pvd[156:190] = directory_record(b'\0', base + 20, 2048, True)
    records = (directory_record(b'\0', base + 20, 2048, True)
               + directory_record(b'\1', base + 20, 2048, True)
               + directory_record(boot + ';1', base + 21, 8))
    sectors[20][:len(records)] = records
    sectors[21][:8] = b'FIXTURE!'
    track = path / 'Different title track.bin'
    if raw:
        chunks = []
        for n, sector in enumerate(sectors):
            frame = n + base + 150
            m, rest = divmod(frame, 60 * 75); s, f = divmod(rest, 75)
            bcd = lambda x: ((x // 10) << 4) | x % 10
            chunks.append(b'\0' + b'\xff' * 10 + b'\0' + bytes([bcd(m), bcd(s), bcd(f), 1])
                          + sector + b'\0' * 288)
        track.write_bytes(b'\0' * offset + b''.join(chunks))
        descriptor = path / 'anything.cue'
        descriptor.write_text('FILE "Different title track.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n')
    else:
        track.write_bytes(b'\0' * offset + b''.join(sectors))
        descriptor = path / 'anything.gdi'
        descriptor.write_text(f'1\n1 45000 4 2048 "Different title track.bin" {offset}\n')
    return descriptor


class DiscTests(unittest.TestCase):
    def test_different_title_and_boot_filename_are_discovered(self):
        with tempfile.TemporaryDirectory() as temp:
            disc = port.Disc(fixture(Path(temp)))
            self.assertEqual(disc.metadata()['title'], 'ANOTHER DREAMCAST TITLE')
            self.assertEqual(disc.metadata()['bootFile'], 'MAIN.BIN')
            self.assertEqual(disc.read(disc.files()[0]['lba'], 8), b'FIXTURE!')

    def test_gdi_track_byte_offsets_are_honored(self):
        with tempfile.TemporaryDirectory() as temp:
            disc = port.Disc(fixture(Path(temp), offset=123))
            self.assertEqual(disc.metadata()['bootFile'], 'MAIN.BIN')

    def test_cue_uses_sector_address_not_track_number(self):
        with tempfile.TemporaryDirectory() as temp:
            disc = port.Disc(fixture(Path(temp), raw=True))
            self.assertEqual(disc.tracks[0].lba, 45000)
            self.assertEqual(disc.metadata()['title'], 'ANOTHER DREAMCAST TITLE')

    def test_unknown_title_stays_unverified_and_import_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = fixture(base)
            project = base / 'port'
            args = argparse.Namespace(input=str(source), project=str(project), descriptor=None, all_files=False)
            original = port.digest(base / 'Different title track.bin')
            with contextlib.redirect_stdout(io.StringIO()):
                port.prepare(args)
                before = (project / 'port.json').read_bytes()
                port.prepare(args)
            self.assertEqual(before, (project / 'port.json').read_bytes())
            manifest = json.loads(before)
            self.assertEqual(manifest['state'], 'needs-title-profile')
            self.assertIsNone(manifest['profileId'])
            self.assertFalse(manifest['evidence']['playable'])
            self.assertEqual(original, port.digest(base / 'Different title track.bin'))
            self.assertEqual((project / '.gitignore').read_text().strip(), '.local/')

    def test_modified_executable_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = fixture(base); project = base / 'port'
            args = argparse.Namespace(input=str(source), project=str(project), descriptor=None, all_files=False)
            with contextlib.redirect_stdout(io.StringIO()): port.prepare(args)
            (project / '.local/extracted/MAIN.BIN').write_bytes(b'tampered')
            with self.assertRaises(port.PortError): port.verify_project(project)

    def test_path_escape_and_links_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for name in ('../escape', '/absolute', 'C:\\escape', '..\\escape'):
                with self.assertRaises(port.PortError): port.contained(base, name)
            (base / 'link').symlink_to('/private/tmp')
            with self.assertRaises(port.PortError): port.contained(base, 'link/outside')

    def test_truncated_disc_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = fixture(base)
            (base / 'Different title track.bin').write_bytes(b'broken')
            with self.assertRaises(port.PortError): port.Disc(source)

    def test_high_density_volume_is_preferred_over_low_density(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=fixture(base)
            low=bytearray(32*2048);low[16*2048:16*2048+7]=b'\x01CD001\x01'
            (base/'low.bin').write_bytes(low)
            source.write_text('2\n1 0 4 2048 "low.bin" 0\n3 45000 4 2048 "Different title track.bin" 0\n')
            self.assertEqual(port.Disc(source).metadata()['volumeLBA'],45000)

    def test_changed_assets_retire_old_evidence_even_if_executable_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=fixture(base);project=base/'port'
            args=argparse.Namespace(input=str(source),project=str(project),descriptor=None,all_files=False)
            with contextlib.redirect_stdout(io.StringIO()):port.prepare(args)
            manifest=json.loads((project/'port.json').read_text())
            manifest['evidence']['compiled']=True;manifest['state']='compiled-unverified'
            port.write_json(project/'port.json',manifest)
            track=base/'Different title track.bin';data=bytearray(track.read_bytes());data[-1]=1;track.write_bytes(data)
            with contextlib.redirect_stdout(io.StringIO()):port.prepare(args)
            changed=json.loads((project/'port.json').read_text())
            self.assertFalse(changed['evidence']['compiled'])
            self.assertNotEqual(manifest['sourceSetSHA256'],changed['sourceSetSHA256'])


if __name__ == '__main__': unittest.main()
