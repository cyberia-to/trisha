"""Bounded original ZIP/tar replay. Extract only data, never execute it."""
import hashlib
import gzip
import struct
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile

from common import identity, require, unique
from contracts import MIB

MAX_MEMBERS = 10000
MAX_EXPANSION = 128 * MIB
MAX_MEMBER = 32 * MIB
MAX_TAR_STREAM = 144 * MIB


class LimitedDecoded:
    def __init__(self, source):
        self.source = source
        self.count = 0

    def read(self, size=-1):
        require(0 <= size <= MAX_TAR_STREAM, "bounded decoded tar request")
        value = self.source.read(min(size, MAX_TAR_STREAM - self.count + 1))
        self.count += len(value)
        require(self.count <= MAX_TAR_STREAM, "decoded tar stream cap including hidden headers")
        return value


def zip_preflight(path):
    size = path.stat().st_size
    with path.open("rb") as source:
        source.seek(max(0, size - 65557)); tail = source.read(65557)
    at = tail.rfind(b"PK\x05\x06")
    require(at >= 0 and len(tail) - at >= 22, "ZIP end record")
    sig, disk, start, disk_count, count, directory_size, offset, comment = struct.unpack("<4s4H2LH", tail[at:at+22])
    require(at + 22 + comment == len(tail) and disk == start == 0 and disk_count == count and count <= MAX_MEMBERS, "bounded single-disk ZIP count")
    require(directory_size <= 8 * MIB and offset + directory_size <= size - len(tail) + at, "bounded ZIP central directory before parsing")
    require(tail[max(0, at-20):at-16] != b"PK\x06\x07", "no ZIP64 metadata expansion")


def safe(name):
    p = PurePosixPath(name)
    require(name and name != '.' and str(p) == name and not p.is_absolute() and '..' not in p.parts and
            '\\' not in name and ':' not in name and not any(ord(c) < 32 for c in name), 'safe canonical archive path')
    return p


def extract_zip(path, destination, budget):
    require(not destination.exists(), 'new archive destination')
    zip_preflight(path)
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist(); names = set(); total = 0
        require(len(members) <= MAX_MEMBERS, 'ZIP member count')
        for m in members:
            safe(m.filename)
            mode = m.external_attr >> 16
            require(not m.is_dir() and (stat.S_IFMT(mode) in (0, stat.S_IFREG)) and not m.flag_bits & 1, 'regular unencrypted ZIP member')
            require(m.filename not in names and 0 <= m.file_size <= MAX_MEMBER, 'unique bounded ZIP member')
            names.add(m.filename); total += m.file_size
        require(total <= MAX_EXPANSION, 'ZIP expansion cap'); budget(total)
        destination.mkdir()
        for m in members:
            target = destination / m.filename; target.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            with archive.open(m) as src, target.open('xb') as out:
                while chunk := src.read(min(MIB, m.file_size - count + 1)):
                    count += len(chunk); require(count <= m.file_size, 'ZIP actual expansion'); out.write(chunk)
            require(count == m.file_size, 'ZIP exact member size')
    return {name: identity(destination / name) for name in sorted(names)}


def replay_tar(path, evidence, expected_snapshot, budget):
    """Check metadata bytes against original Actions members without retaining expansion."""
    members = {}; total = 0; manifest = None
    with gzip.open(path, 'rb') as decoded, tarfile.open(fileobj=LimitedDecoded(decoded), mode='r|') as archive:
        for member in archive:
            safe(member.name)
            require(member.isfile() and member.name.startswith('evidence/') and member.name not in members,
                    'unique regular metadata member')
            require(0 <= member.size <= MAX_MEMBER and len(members) < MAX_MEMBERS, 'metadata member bounds')
            total += member.size; require(total <= MAX_EXPANSION, 'metadata expansion cap')
            name = member.name.removeprefix('evidence/'); safe(name)
            digest = hashlib.sha256(); raw = bytearray() if name.endswith('.json') else None; size = 0
            with archive.extractfile(member) as source:
                while chunk := source.read(MIB):
                    size += len(chunk); require(size <= member.size, 'metadata actual expansion'); digest.update(chunk)
                    if raw is not None:
                        raw.extend(chunk)
            require(size == member.size, 'metadata exact member size')
            row = dict(bytes=size, sha256=digest.hexdigest()); members[member.name] = row
            if name == 'files.json':
                require(size <= 4 * MIB, 'bounded metadata manifest')
                manifest = json.loads(raw, object_pairs_hook=unique)
            elif name == 'receipt.json':
                require(row == identity(evidence / expected_snapshot), 'metadata pre-retention receipt original bytes')
            elif name.startswith('transport-') and name.endswith('.json') and row != identity(evidence / name):
                snapshot = json.loads(raw, object_pairs_hook=unique)
                final = json.loads((evidence / name).read_text(), object_pairs_hook=unique)
                require(snapshot['status'] == 'running', 'metadata transport snapshot')
                for k, value in snapshot.items():
                    if k not in ('status', 'commands'):
                        require(final[k] == value, 'unchanged metadata transport snapshot')
                require(final['commands'][:len(snapshot['commands'])] == snapshot['commands'], 'original completed transport command prefix')
            else:
                require(row == identity(evidence / name), 'metadata member equals authenticated Actions ZIP')
    require(isinstance(manifest, dict) and len(manifest) < MAX_MEMBERS, 'metadata inventory')
    require(set(members) == {'evidence/' + name for name in manifest} | {'evidence/files.json'}, 'exact metadata inventory membership')
    require(all(members['evidence/' + n] == v for n, v in manifest.items()), 'metadata inventory byte identities')
    budget(0)
    return dict(members=len(members), expanded_bytes=total, archive=identity(path))
